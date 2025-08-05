import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from core.parser.parser import login_audatex, terminate_all_processes_and_restart
import json
import os
from datetime import datetime
import logging
from core.database.models import ParserCarDetail, ParserCarDetailGroupZone, ParserCarRequestStatus, get_moscow_time, async_session
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.sql import text
import re
from core.database.requests import (
    save_parser_data_to_db,
    update_json_with_claim_number,
    save_updated_json_to_file,
)
from core.database.requests import (
    get_schedule_settings,
    save_schedule_settings,
    is_time_in_working_hours,
    get_time_to_start,
    get_time_to_end,
)
from core.parser.output_manager import restore_started_at_from_db, restore_last_updated_from_db, restore_completed_at_from_db
from core.queue.api_endpoints import router as queue_router
from core.queue.redis_manager import redis_manager
from core.queue.queue_processor import queue_processor
from core.auth.db_routes import router as auth_router
from core.auth.db_decorators import require_auth, get_current_user
from core.security.rate_limiter import rate_limit_middleware
from core.security.ddos_protection import ddos_protection_middleware
from core.security.security_monitor import security_monitoring_middleware
from core.security.auth_middleware import security_api_auth_middleware
from core.security.api_endpoints import router as security_router
from core.security.session_middleware import session_middleware

import time
import concurrent.futures
import threading
import psutil

# Отключаем retry логику urllib3 для предотвращения WARNING сообщений
import urllib3
urllib3.disable_warnings()
logging.getLogger("urllib3").setLevel(logging.ERROR)

# Глобальные переменные для отслеживания состояния парсера
parser_running = False
parser_task = None
parser_start_time = None

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    # Startup
    try:
        # Создаем таблицы базы данных
        from core.database.models import start_db
        await start_db()
        logger.info("✅ Таблицы базы данных созданы")
        
        # Создаем пользователей по умолчанию
        from core.auth.db_auth import create_default_users
        create_default_users()
        logger.info("✅ Аутентификация через базу данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации: {e}")
    
    # Проверяем подключение к Redis
    try:
        if redis_manager.test_connection():
            logger.info("✅ Redis подключен")
        else:
            logger.warning("⚠️ Redis недоступен, очередь будет работать в памяти")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Redis: {e}")
    
    yield
    
    # Shutdown
    try:
        redis_manager.close()
        logger.info("✅ Соединение с Redis закрыто")
    except Exception as e:
        logger.error(f"❌ Ошибка закрытия Redis: {e}")
    
    try:
        from core.database.models import close_db
        await close_db()
        logger.info("✅ Соединение с базой данных закрыто")
    except Exception as e:
        logger.error(f"❌ Ошибка закрытия базы данных: {e}")

# Инициализация FastAPI приложения
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Подключаем роутеры
app.include_router(auth_router)
app.include_router(queue_router)
app.include_router(security_router)

# Добавляем middleware для безопасности (в правильном порядке)
app.middleware("http")(session_middleware)
app.middleware("http")(security_monitoring_middleware)
app.middleware("http")(ddos_protection_middleware)
app.middleware("http")(rate_limit_middleware)

# Модели для валидации входного JSON
class SearchItem(BaseModel):
    requestId: int
    vin: str

class AppCredentials(BaseModel):
    username: str
    password: str

class ParserCredentials(BaseModel):
    login: str
    password: str

class SearchRequest(BaseModel):
    # Авторизация в нашем приложении
    app_credentials: AppCredentials
    # Учетные данные парсера
    parser_credentials: ParserCredentials
    # Заявки для обработки
    searchList: List[SearchItem]
    svg_collection: bool = True

class ScheduleSettingsRequest(BaseModel):
    start_time: str
    end_time: str
    svg_collection: bool = True

def normalize_paths(record: dict, folder_name: str) -> dict:
    """Нормализует пути к файлам, добавляя claim_number и vin, исправляя слеши"""
    if record.get("main_screenshot_path"):
        record["main_screenshot_path"] = fix_path(record["main_screenshot_path"], folder_name)
    if record.get("main_svg_path"):
        record["main_svg_path"] = fix_path(record["main_svg_path"], folder_name)
    if record.get("all_svgs_zip"):
        record["all_svgs_zip"] = fix_path(record["all_svgs_zip"], folder_name)

    for zone in record.get("zone_data", []):
        if zone.get("screenshot_path"):
            zone["screenshot_path"] = fix_path(zone["screenshot_path"], folder_name)
        if zone.get("svg_path"):
            zone["svg_path"] = fix_path(zone["svg_path"], folder_name)

        for detail in zone.get("details", []):
            if detail.get("svg_path"):
                detail["svg_path"] = fix_path(detail["svg_path"], folder_name)

        for pictogram in zone.get("pictograms", []):
            for work in pictogram.get("works", []):
                if work.get("svg_path"):
                    work["svg_path"] = fix_path(work["svg_path"], folder_name)

    return record


async def process_parser_result_data(claim_number: str, vin_value: str, parser_result: dict, started_at=None, completed_at=None) -> bool:
    """
    Обрабатывает данные результата парсера: ищет JSON файл и сохраняет в БД
    
    Args:
        claim_number: Номер заявки из формы
        vin_value: VIN номер из формы
        parser_result: Результат парсера
        started_at: Время начала парсинга
        completed_at: Время завершения парсинга
    
    Returns:
        bool: True если обработка прошла успешно
    """
    try:
        # Проверяем, есть ли ошибка в результате
        if "error" in parser_result:
            logger.error(f"❌ Парсер вернул ошибку: {parser_result['error']}")
            return False
        
        # Используем данные из формы
        clean_claim_number = claim_number.strip() if claim_number else ""
        clean_vin_value = vin_value.strip() if vin_value else ""
        
        logger.info(f"🔍 Используем данные из формы: claim_number='{clean_claim_number}', vin='{clean_vin_value}'")
        
        # Формируем имя папки с безопасной обработкой символов
        import re
        safe_claim_number = re.sub(r'[<>:"/\\|?*]', '_', clean_claim_number)
        safe_claim_number = safe_claim_number.replace('-', '_').replace('.', '_')
        safe_claim_number = re.sub(r'_+', '_', safe_claim_number)
        safe_claim_number = safe_claim_number.strip('_')
        
        folder_name = f"{safe_claim_number}_{clean_vin_value}"
        folder_path = os.path.join("static", "data", folder_name)
        
        # Проверяем существование папки
        if not os.path.isdir(folder_path):
            logger.error(f"Папка {folder_path} не существует после парсинга")
            return False
        
        # Ищем JSON файлы в папке
        json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
        if not json_files:
            logger.error(f"JSON-файлы не найдены в {folder_path}")
            return False
        
        # Берем самый новый JSON файл
        latest_json = max(json_files, key=lambda f: os.path.getctime(os.path.join(folder_path, f)))
        file_path = os.path.join(folder_path, latest_json)
        
        logger.info(f"✅ Найден JSON файл: {file_path}")
        
        logger.info(f"📁 Обрабатываем JSON файл: {file_path}")
        
        # Читаем JSON файл
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Обновляем JSON с данными из формы
        updated_json = update_json_with_claim_number(json_data, clean_claim_number)
        
        # Сохраняем обновленный JSON обратно в файл
        save_success = await save_updated_json_to_file(updated_json, file_path)
        if not save_success:
            logger.error(f"Не удалось сохранить обновленный JSON: {file_path}")
            return False
        
        # Сохраняем данные в БД с временными метками и путем к файлу
        db_success = await save_parser_data_to_db(updated_json, clean_claim_number, clean_vin_value, is_success=True, started_at=started_at, completed_at=completed_at, file_path=file_path)
        if not db_success:
            logger.error(f"Не удалось сохранить данные в БД: {clean_claim_number}_{clean_vin_value}")
            return False
        
        logger.info(f"✅ Обработка завершена успешно: {clean_claim_number}_{clean_vin_value}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки данных: {e}")
        return False


def fix_path(path: str, folder_name: str) -> str:
    """Исправляет пути к файлам, добавляя folder_name"""
    if not path:
        return ""
    
    # Убираем лишние слеши в начале
    path = path.lstrip("/")
    
    # Если путь уже содержит folder_name, возвращаем как есть
    if folder_name in path:
        return "/" + path
    
    # Проверяем, начинается ли путь с static/
    if path.startswith("static/"):
        # Убираем "static/" из начала
        path_without_static = path[7:]  # len("static/") = 7
        
        # Если путь уже содержит screenshots/ или svgs/, добавляем folder_name после них
        if path_without_static.startswith("screenshots/"):
            return f"/static/screenshots/{folder_name}/{path_without_static[12:]}"  # len("screenshots/") = 12
        elif path_without_static.startswith("svgs/"):
            return f"/static/svgs/{folder_name}/{path_without_static[5:]}"  # len("svgs/") = 5
        else:
            # Если нет специальных папок, добавляем folder_name после static/
            return f"/static/{folder_name}/{path_without_static}"
    
    # Если путь не начинается с static/, добавляем static/ и folder_name
    return f"/static/{folder_name}/{path}"


def clean_json_data(data):
    """Очищает JSON данные от Undefined полей"""
    if isinstance(data, dict):
        cleaned = {}
        for key, value in data.items():
            if value is not None and str(value) != "Undefined":
                cleaned[key] = clean_json_data(value)
        return cleaned
    elif isinstance(data, list):
        return [clean_json_data(item) for item in data if item is not None and str(item) != "Undefined"]
    else:
        return data if data is not None and str(data) != "Undefined" else ""


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...),
                claim_number: str = Form(default=""), vin_number: str = Form(default=""),
                svg_collection: str = Form(default=""), start_time: str = Form(...), 
                end_time: str = Form(...)):
    """Обработка входа и добавление заявки в очередь"""
    try:
        # Проверяем, что оба поля заполнены
        if not claim_number.strip() or not vin_number.strip():
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Необходимо указать номер дела И VIN номер. Оба поля обязательны."
                }
            )
        
        # Проверяем настройки времени работы парсера
        async with async_session() as session:
            # Сохраняем настройки времени из формы
            await save_schedule_settings(session, start_time, end_time)
            
            # Определяем статус работы парсера
            is_working_hours = is_time_in_working_hours(start_time, end_time)
            time_to_start = 0
            
            if not is_working_hours:
                time_to_start = get_time_to_start(start_time)
        
        # Проверяем подключение к Redis
        if not redis_manager.test_connection():
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Redis недоступен. Очередь не может быть обработана."
                }
            )
        
        # Добавляем заявку в очередь
        request_data = {
            "claim_number": claim_number.strip(),
            "vin_number": vin_number.strip(),
            "svg_collection": svg_collection == "on",
            "username": username,
            "password": password
        }
        
        logger.info(f"📝 Добавление заявки в очередь: Номер дела: {claim_number}, VIN: {vin_number}")
        
        success = redis_manager.add_request_to_queue(request_data)
        if not success:
            logger.error(f"❌ Ошибка добавления заявки в очередь: {claim_number}, {vin_number}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Ошибка добавления заявки в очередь."
                }
            )
        
        # Запускаем обработку очереди если она еще не запущена
        if not queue_processor.is_running:
            asyncio.create_task(queue_processor.start_processing())
        
        queue_length = redis_manager.get_queue_length()
        
        logger.info(f"✅ Заявка успешно добавлена в очередь. Позиция: {queue_length}")
        
        # Формируем сообщение в зависимости от статуса работы парсера
        if is_working_hours:
            message = f"Заявка добавлена в очередь. Номер дела: {claim_number}, VIN: {vin_number}"
            queue_info = f"Позиция в очереди: {queue_length}. Обработка запущена автоматически."
        else:
            hours = time_to_start // 60
            minutes = time_to_start % 60
            message = f"Заявка добавлена в очередь. Номер дела: {claim_number}, VIN: {vin_number}"
            queue_info = f"Позиция в очереди: {queue_length}. Обработка начнется в {start_time} (через {hours}ч {minutes}м)."
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": message,
                "queue_length": queue_length,
                "queue_info": queue_info,
                "is_working_hours": is_working_hours,
                "start_time": start_time,
                "time_to_start_minutes": time_to_start
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки входа: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Произошла ошибка: {str(e)}"
            }
        )


@app.get("/", response_class=HTMLResponse)
@require_auth()
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/queue", response_class=HTMLResponse)
@require_auth()
async def queue_monitor(request: Request):
    """Страница мониторинга очереди"""
    return templates.TemplateResponse("queue_monitor.html", {"request": request})


@app.get("/security", response_class=HTMLResponse)
@require_auth()
async def security_monitor_page(request: Request):
    """Страница мониторинга безопасности"""
    return templates.TemplateResponse("security_monitor.html", {"request": request})


@app.get("/success", response_class=HTMLResponse)
@require_auth()
async def success(request: Request):
    """Страница успешного добавления заявок"""
    return templates.TemplateResponse("success.html", {"request": request})

@app.get("/history", response_class=HTMLResponse)
@require_auth()
async def history(request: Request):
    try:
        # Читаем данные из JSON файлов в папке static/data
        data_dir = "static/data"
        if not os.path.exists(data_dir):
            return templates.TemplateResponse("history.html", {
                "request": request, 
                "records": []
            })
        
        formatted_records = []
        
        # Проходим по всем папкам в static/data
        for folder_name in os.listdir(data_dir):
            folder_path = os.path.join(data_dir, folder_name)
            
            # Проверяем, что это папка и содержит JSON файлы
            if not os.path.isdir(folder_path):
                continue
                
            json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
            if not json_files:
                continue
            
            # Берем самый новый JSON файл
            latest_json = max(json_files, key=lambda f: os.path.getctime(os.path.join(folder_path, f)))
            json_path = os.path.join(folder_path, latest_json)
            
            try:
                # Читаем JSON файл
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                # Очищаем JSON от Undefined полей
                json_data = clean_json_data(json_data)
                
                # Извлекаем данные из JSON
                claim_number = json_data.get("claim_number", "")
                vin = json_data.get("vin_value", "")  # Используем vin_value вместо vin
                
                # Если нет claim_number в JSON, пробуем извлечь из имени папки
                if not claim_number and "_" in folder_name:
                    claim_number = folder_name.split("_")[0]
                
                # Если нет vin в JSON, пробуем извлечь из имени папки
                if not vin and "_" in folder_name:
                    vin = folder_name.split("_")[1] if len(folder_name.split("_")) > 1 else ""
                
                # Получаем метаданные
                metadata = json_data.get("metadata", {})
                started_at = metadata.get("started_at", "") if metadata else ""
                completed_at = metadata.get("completed_at", "") if metadata else ""
                last_updated = metadata.get("last_updated", "") if metadata else ""
                json_completed = metadata.get("json_completed", False) if metadata else False
                db_saved = metadata.get("db_saved", False) if metadata else False
                options_success = metadata.get("options_success", False) if metadata else False
                total_zones = len(json_data.get("zone_data", [])) if json_data else 0
                
                # Восстанавливаем started_at из БД если он null или неправильный
                should_restore_started = (started_at is None or started_at == "null" or started_at == "None" or started_at == "")
                
                # Также проверяем, если время есть, но оно на 3 часа меньше (признак неправильного времени)
                if not should_restore_started and started_at:
                    try:
                        # Парсим время из JSON
                        json_time = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                        # Проверяем, что время не слишком старое (признак неправильного времени)
                        current_time = datetime.now()
                        time_diff = (current_time - json_time).total_seconds()
                        if time_diff > 86400:  # Если разница больше 24 часов
                            should_restore_started = True
                            logger.info(f"🔍 Время в JSON слишком старое для {claim_number}_{vin}: {started_at}")
                    except:
                        should_restore_started = True
                
                # Восстанавливаем completed_at из БД если он null
                should_restore_completed = (completed_at is None or completed_at == "null" or completed_at == "None" or completed_at == "")
                
                # Восстанавливаем last_updated из БД если он null
                should_restore_last_updated = (last_updated is None or last_updated == "null" or last_updated == "None" or last_updated == "")
                
                if (should_restore_started or should_restore_completed or should_restore_last_updated) and claim_number and vin:
                    try:
                        if should_restore_started:
                            logger.info(f"🔍 Восстанавливаем started_at из БД для {claim_number}_{vin}")
                            await restore_started_at_from_db(json_path, claim_number, vin)
                        
                        if should_restore_completed:
                            logger.info(f"🔍 Восстанавливаем completed_at из БД для {claim_number}_{vin}")
                            await restore_completed_at_from_db(json_path, claim_number, vin)
                        
                        if should_restore_last_updated:
                            logger.info(f"🔍 Восстанавливаем last_updated из БД для {claim_number}_{vin}")
                            await restore_last_updated_from_db(json_path, claim_number, vin)
                        
                        # Перечитываем JSON после восстановления
                        with open(json_path, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)
                        metadata = json_data.get("metadata", {})
                        started_at = metadata.get("started_at", "") if metadata else ""
                        completed_at = metadata.get("completed_at", "") if metadata else ""
                        last_updated = metadata.get("last_updated", "") if metadata else ""
                        logger.info(f"✅ Восстановлено started_at: {started_at}")
                        logger.info(f"✅ Восстановлено completed_at: {completed_at}")
                        logger.info(f"✅ Восстановлено last_updated: {last_updated}")
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось восстановить время для {claim_number}_{vin}: {e}")
                
                # Определяем статус по флагам из метаданных
                
                # Добавляем отладочную информацию
                logger.info(f"🔍 Статус для {claim_number}_{vin}: json_completed={json_completed}, db_saved={db_saved}, options_success={options_success}, total_zones={total_zones}")
                logger.info(f"🔍 Детали для {claim_number}_{vin}: started_at='{started_at}', completed_at='{completed_at}', last_updated='{last_updated}'")
                
                # Основная логика определения статуса
                if json_completed and db_saved and total_zones > 0:
                    # Если есть зоны и JSON завершен, считаем успешным даже без options_success
                    status = "Завершена"
                elif not json_completed:
                    status = "В процессе"
                elif json_completed and total_zones == 0:
                    # Если JSON завершен, но зон нет - это ошибка
                    status = "Ошибка"
                elif json_completed and not db_saved:
                    # Если JSON завершен, но БД не сохранена - это ошибка
                    status = "Ошибка"
                else:
                    # Для всех остальных случаев считаем успешным
                    status = "Завершена"
                
                # Форматируем время
                started_time = "—"
                completed_time = "—"
                duration = ""
                
                if started_at and started_at != "null" and started_at != "None":
                    try:
                        # Парсим время из строки "2025-07-27 17:30:00"
                        start_dt = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                        started_time = start_dt.strftime("%H:%M:%S")
                        
                        # Используем completed_at если есть и не null, иначе last_updated
                        end_time_str = completed_at if completed_at and completed_at != "null" and completed_at != "None" else last_updated
                        if end_time_str and end_time_str != "null" and end_time_str != "None":
                            end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                            
                            # Проверяем, что конечное время больше начального
                            if end_dt <= start_dt:
                                logger.warning(f"⚠️ Конечное время меньше или равно начальному для {claim_number}_{vin}: {end_dt} <= {start_dt}")
                                # Пытаемся восстановить правильное время из БД
                                try:
                                    await restore_completed_at_from_db(json_path, claim_number, vin, force_restore=True)
                                    # Перечитываем JSON после восстановления
                                    with open(json_path, 'r', encoding='utf-8') as f:
                                        json_data = json.load(f)
                                    metadata = json_data.get("metadata", {})
                                    completed_at = metadata.get("completed_at", "") if metadata else ""
                                    last_updated = metadata.get("last_updated", "") if metadata else ""
                                    
                                    # Пробуем снова с восстановленным временем
                                    end_time_str = completed_at if completed_at and completed_at != "null" and completed_at != "None" else last_updated
                                    if end_time_str and end_time_str != "null" and end_time_str != "None":
                                        end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                                        logger.info(f"✅ Время восстановлено из БД: {end_dt}")
                                    else:
                                        logger.error(f"❌ Не удалось восстановить время из БД для {claim_number}_{vin}")
                                except Exception as e:
                                    logger.error(f"❌ Ошибка восстановления времени из БД для {claim_number}_{vin}: {e}")
                            
                            completed_time = end_dt.strftime("%H:%M:%S")
                            
                            # Вычисляем длительность
                            duration_seconds = (end_dt - start_dt).total_seconds()
                            duration = f"{int(duration_seconds // 60)}м {int(duration_seconds % 60)}с"
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка парсинга времени для {claim_number}_{vin}: {e}")
                        pass
                
                # Получаем дату создания из времени файла
                created_date = datetime.fromtimestamp(os.path.getctime(json_path)).strftime("%d.%m.%Y")
                
                # Получаем vin_status из JSON
                vin_status = json_data.get("vin_status", "Неизвестно")
                
                formatted_records.append({
                    "request_id": claim_number,  # Используем claim_number как request_id для URL
                    "claim_number": claim_number,  # Добавляем отдельно для шаблона
                    "vin": vin,
                    "vin_status": vin_status,
                    "status": status,
                    "started_time": started_time,
                    "completed_time": completed_time,
                    "duration": duration,
                    "created_date": created_date,
                    "folder_name": folder_name,
                    "json_completed": json_completed,
                    "db_saved": db_saved,
                    "options_success": options_success,
                    "total_zones": total_zones
                })
                
            except Exception as e:
                logger.error(f"Ошибка чтения JSON файла {json_path}: {e}")
                continue
        
        # Сортируем записи по дате создания (новые сверху)
        formatted_records.sort(key=lambda x: x["created_date"], reverse=True)
        
        return templates.TemplateResponse("history.html", {
            "request": request, 
            "records": formatted_records
        })
        
    except Exception as e:
        logger.error(f"Ошибка при получении истории: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "error": f"Ошибка при получении истории: {e}"
        })

@app.get("/history_detail/{folder_name}", response_class=HTMLResponse)
@require_auth()
async def history_detail(request: Request, folder_name: str):
    try:
        # Используем полное имя папки напрямую
        folder_path = os.path.join("static", "data", folder_name)
        
        if not os.path.exists(folder_path):
            return templates.TemplateResponse("error.html", {
                "request": request, 
                "error": f"Заявка не найдена. Папка: {folder_name}"
            })
        
        # Ищем JSON файлы в папке
        json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
        if not json_files:
            return templates.TemplateResponse("error.html", {
                "request": request, 
                "error": f"JSON файл не найден в папке: {folder_name}"
            })
        
        # Берем самый новый JSON файл
        latest_json = max(json_files, key=lambda f: os.path.getctime(os.path.join(folder_path, f)))
        json_path = os.path.join(folder_path, latest_json)
        
        # Читаем JSON файл
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Очищаем JSON от Undefined полей
        json_data = clean_json_data(json_data)
        
        logger.info(f"JSON загружен успешно. Ключи: {list(json_data.keys())}")
        
        # Извлекаем данные из JSON
        claim_number = json_data.get("claim_number", "")
        vin_value = json_data.get("vin_value", "")
        vin_status = json_data.get("vin_status", "Неизвестно")
        
        # Если нет данных в JSON, извлекаем из имени папки
        if not claim_number and "_" in folder_name:
            claim_number = folder_name.split("_")[0]
        if not vin_value and "_" in folder_name:
            vin_value = folder_name.split("_")[1] if len(folder_name.split("_")) > 1 else ""
        
        # Получаем метаданные (может отсутствовать)
        metadata = json_data.get("metadata", {})
        started_at = metadata.get("started_at", "") if metadata else ""
        completed_at = metadata.get("completed_at", "") if metadata else ""
        last_updated = metadata.get("last_updated", "") if metadata else ""
        json_completed = metadata.get("json_completed", False) if metadata else False
        db_saved = metadata.get("db_saved", False) if metadata else False
        
        # Восстанавливаем started_at из БД если он null или неправильный
        should_restore = (started_at is None or started_at == "null" or started_at == "None" or started_at == "")
        
        # Также проверяем, если время есть, но оно неправильное
        if not should_restore and started_at:
            try:
                # Парсим время из JSON
                json_time = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                # Проверяем, что время не слишком старое (признак неправильного времени)
                current_time = datetime.now()
                time_diff = (current_time - json_time).total_seconds()
                if time_diff > 86400:  # Если разница больше 24 часов
                    should_restore = True
                    logger.info(f"🔍 Время в JSON слишком старое для {folder_name}: {started_at}")
            except:
                should_restore = True
        
        if should_restore and claim_number and vin_value:
            try:
                logger.info(f"🔍 Восстанавливаем started_at из БД для {claim_number}_{vin_value}")
                await restore_started_at_from_db(json_path, claim_number, vin_value)
                
                # Также восстанавливаем completed_at
                logger.info(f"🔍 Восстанавливаем completed_at из БД для {claim_number}_{vin_value}")
                await restore_completed_at_from_db(json_path, claim_number, vin_value)
                
                # Также восстанавливаем last_updated
                logger.info(f"🔍 Восстанавливаем last_updated из БД для {claim_number}_{vin_value}")
                await restore_last_updated_from_db(json_path, claim_number, vin_value)
                
                # Перечитываем JSON после восстановления
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                metadata = json_data.get("metadata", {})
                started_at = metadata.get("started_at", "") if metadata else ""
                completed_at = metadata.get("completed_at", "") if metadata else ""
                last_updated = metadata.get("last_updated", "") if metadata else ""
                logger.info(f"✅ Восстановлено started_at: {started_at}")
                logger.info(f"✅ Восстановлено completed_at: {completed_at}")
                logger.info(f"✅ Восстановлено last_updated: {last_updated}")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось восстановить время для {claim_number}_{vin_value}: {e}")
        
        # Форматируем временные метки
        started_time = "—"
        completed_time = "—"
        duration = ""
        
        if started_at:
            try:
                start_dt = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                started_time = start_dt.strftime("%H:%M:%S")
                
                # Используем completed_at если есть, иначе last_updated
                end_time_str = completed_at if completed_at else last_updated
                if end_time_str:
                    end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                    
                    # Проверяем, что конечное время больше начального
                    if end_dt <= start_dt:
                        logger.warning(f"⚠️ Конечное время меньше или равно начальному для {claim_number}_{vin_value}: {end_dt} <= {start_dt}")
                        # Пытаемся восстановить правильное время из БД
                        try:
                            await restore_completed_at_from_db(json_path, claim_number, vin_value, force_restore=True)
                            # Перечитываем JSON после восстановления
                            with open(json_path, 'r', encoding='utf-8') as f:
                                json_data = json.load(f)
                            metadata = json_data.get("metadata", {})
                            completed_at = metadata.get("completed_at", "") if metadata else ""
                            last_updated = metadata.get("last_updated", "") if metadata else ""
                            
                            # Пробуем снова с восстановленным временем
                            end_time_str = completed_at if completed_at and completed_at != "null" and completed_at != "None" else last_updated
                            if end_time_str and end_time_str != "null" and end_time_str != "None":
                                end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                                logger.info(f"✅ Время восстановлено из БД: {end_dt}")
                            else:
                                logger.error(f"❌ Не удалось восстановить время из БД для {claim_number}_{vin_value}")
                        except Exception as e:
                            logger.error(f"❌ Ошибка восстановления времени из БД для {claim_number}_{vin_value}: {e}")
                    
                    completed_time = end_dt.strftime("%H:%M:%S")
                    
                    duration_seconds = (end_dt - start_dt).total_seconds()
                    duration = f"{int(duration_seconds // 60)}м {int(duration_seconds % 60)}с"
            except Exception as e:
                logger.warning(f"⚠️ Ошибка парсинга времени: {e}")
                pass
        
        # Получаем детали из JSON
        details = []
        zone_data = json_data.get("zone_data", [])
        if isinstance(zone_data, list):
            for zone in zone_data:
                if isinstance(zone, dict):
                    zone_title = zone.get("title", "")
                    zone_details = zone.get("details", [])
                    if isinstance(zone_details, list):
                        for detail in zone_details:
                            if isinstance(detail, dict):
                                detail_title = detail.get("title", "")
                                # Парсим заголовок детали на код и название
                                if " - " in detail_title:
                                    code, title = detail_title.split(" - ", 1)
                                else:
                                    code = ""
                                    title = detail_title
                                
                                details.append({
                                    "group_zone": zone_title,
                                    "code": code,
                                    "title": title
                                })
        
        # Получаем опции из JSON
        options = []
        options_data = json_data.get("options_data", {})
        if isinstance(options_data, dict) and options_data.get("success"):
            zones = options_data.get("zones", [])
            if isinstance(zones, list):
                for zone in zones:
                    if isinstance(zone, dict):
                        zone_title = zone.get("zone_title", "")
                        zone_options = zone.get("options", [])
                        if isinstance(zone_options, list):
                            for option in zone_options:
                                if isinstance(option, dict):
                                    options.append({
                                        "zone_name": zone_title,
                                        "option_code": option.get("code", ""),
                                        "option_title": option.get("title", ""),
                                        "is_selected": option.get("selected", False)
                                    })
        
        # Определяем статус
        if json_completed and db_saved:
            status = "Завершена"
        elif json_completed and not db_saved:
            status = "Ошибка БД"
        elif not json_completed:
            status = "В процессе"
        else:
            status = "Неизвестно"
        
        return templates.TemplateResponse("history_detail.html", {
            "request": request,
            "record": {
                "request_id": claim_number,
                "vin": vin_value,
                "vin_value": vin_value,  # Добавляем для совместимости с шаблоном
                "vin_status": vin_status,
                "status": status,
                "started_time": started_time,
                "completed_time": completed_time,
                "duration": duration,
                "created_date": datetime.fromtimestamp(os.path.getctime(json_path)).strftime("%d.%m.%Y"),
                "created": datetime.fromtimestamp(os.path.getctime(json_path)).strftime("%d.%m.%Y"),  # Для совместимости
                "folder": folder_name,  # Добавляем имя папки
                "folder_name": folder_name,  # Добавляем для совместимости
                "main_screenshot_path": fix_path(json_data.get("main_screenshot_path", ""), folder_name),
                "main_svg_path": fix_path(json_data.get("main_svg_path", ""), folder_name),
                "zone_data": json_data.get("zone_data", []),
                "options_data": {
                    "success": json_data.get("options_data", {}).get("success", False) if isinstance(json_data.get("options_data"), dict) else False,
                    "zones": json_data.get("options_data", {}).get("zones", []) if isinstance(json_data.get("options_data"), dict) else [],
                    "statistics": json_data.get("options_data", {}).get("statistics", {
                        "total_zones": 0,
                        "total_options": 0,
                        "total_selected": 0
                    }) if isinstance(json_data.get("options_data"), dict) else {
                        "total_zones": 0,
                        "total_options": 0,
                        "total_selected": 0
                    },
                    "error": json_data.get("options_data", {}).get("error", "") if isinstance(json_data.get("options_data"), dict) else ""
                },
                "zones_table": json_data.get("zones_table", []),
                "all_svgs_zip": json_data.get("all_svgs_zip", "")
            },
            "details": details,
            "options": options
        })
        

        
    except Exception as e:
        logger.error(f"Ошибка при получении деталей заявки: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request, 
            "error": f"Ошибка при получении деталей: {e}"
        })

@app.post("/api_parse")
async def api_parse(request: SearchRequest):
    """API эндпоинт для парсинга заявок и добавления их в очередь"""
    try:
        # Аутентифицируем пользователя
        from core.auth.db_auth import authenticate_user
        user = authenticate_user(request.app_credentials.username, request.app_credentials.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль"
            )
        
        if not user['is_active']:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь неактивен"
            )
        
        # Проверяем роль пользователя
        if user['role'] not in ['api', 'admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для выполнения операции"
            )
        
        logger.info(f"API запрос от пользователя: {user['username']} (роль: {user['role']})")
        
        # Проверяем, что есть заявки для обработки
        if not request.searchList:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Необходимо указать хотя бы одну заявку для обработки."
                }
            )
        
        # Проверяем настройки времени работы парсера
        async with async_session() as session:
            settings = await get_schedule_settings(session)
        
        # Определяем статус работы парсера
        is_working_hours = False
        time_to_start = 0
        start_time = "09:00"
        end_time = "18:00"
        
        if settings.get('is_active'):
            start_time = settings['start_time']
            end_time = settings['end_time']
            is_working_hours = is_time_in_working_hours(start_time, end_time)
            
            if not is_working_hours:
                time_to_start = get_time_to_start(start_time)
        
        # Проверяем подключение к Redis
        if not redis_manager.test_connection():
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Redis недоступен. Очередь не может быть обработана."
                }
            )
        
        results = []
        added_to_queue = 0
        
        # Добавляем каждую заявку в очередь
        for item in request.searchList:
            try:
                claim_number = str(item.requestId)
                vin_number = item.vin
                
                # Проверяем, что хотя бы одно поле заполнено
                if not claim_number and not vin_number:
                    results.append({
                        "requestId": item.requestId,
                        "vin": vin_number,
                        "status": "error",
                        "error": "Необходимо указать номер дела или VIN номер."
                    })
                    continue
                
                # Добавляем заявку в очередь
                request_data = {
                    "claim_number": claim_number,
                    "vin_number": vin_number,
                    "svg_collection": getattr(request, 'svg_collection', True),
                    "username": request.parser_credentials.login,
                    "password": request.parser_credentials.password
                }
                
                logger.info(f"📝 Добавление заявки в очередь: Номер дела: {claim_number}, VIN: {vin_number}")
                
                success = redis_manager.add_request_to_queue(request_data)
                if success:
                    added_to_queue += 1
                    results.append({
                        "requestId": item.requestId,
                        "vin": vin_number,
                        "status": "queued",
                        "message": "Заявка добавлена в очередь"
                    })
                else:
                    results.append({
                        "requestId": item.requestId,
                        "vin": vin_number,
                        "status": "error",
                        "error": "Ошибка добавления заявки в очередь"
                    })
                    
            except Exception as e:
                logger.error(f"Ошибка обработки заявки {item.requestId}: {e}")
                results.append({
                    "requestId": item.requestId,
                    "vin": item.vin,
                    "status": "error",
                    "error": f"Внутренняя ошибка: {str(e)}"
                })
        
        # Запускаем обработку очереди если она еще не запущена
        if not queue_processor.is_running:
            asyncio.create_task(queue_processor.start_processing())
        
        queue_length = redis_manager.get_queue_length()
        
        logger.info(f"✅ {added_to_queue} заявок добавлено в очередь. Общая длина очереди: {queue_length}")
        
        # Формируем сообщение в зависимости от статуса работы парсера
        if is_working_hours:
            message = f"{added_to_queue} заявок добавлено в очередь"
            queue_info = f"Позиция в очереди: {queue_length}. Обработка запущена автоматически."
        else:
            hours = time_to_start // 60
            minutes = time_to_start % 60
            message = f"{added_to_queue} заявок добавлено в очередь"
            queue_info = f"Позиция в очереди: {queue_length}. Обработка начнется в {start_time} (через {hours}ч {minutes}м)."
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": message,
                "queue_length": queue_length,
                "queue_info": queue_info,
                "is_working_hours": is_working_hours,
                "start_time": start_time,
                "time_to_start_minutes": time_to_start,
                "results": results
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки API запроса: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Произошла ошибка: {str(e)}"
            }
        )

@app.post("/terminate")
@require_auth()
async def terminate_parser():
    global parser_running, parser_task, parser_start_time
    try:
        logger.info("🛑 Получен запрос на остановку парсера")
        
        # Сбрасываем старые флаги (для обратной совместимости)
        parser_running = False
        parser_start_time = None
        
        # Отменяем старую задачу парсера, если она запущена
        if parser_task and not parser_task.done():
            parser_task.cancel()
            try:
                await asyncio.wait_for(parser_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("✅ Старая задача парсера отменена")
        
        # Очищаем ссылку на старую задачу
        parser_task = None
        
        # Останавливаем queue processor
        if queue_processor.is_running:
            logger.info("🛑 Останавливаем queue processor")
            queue_processor.stop_processing()
        
        # Завершаем процессы браузера
        result = terminate_all_processes_and_restart()
        
        logger.info(f"✅ Парсер и очередь остановлены: {result}")
        return JSONResponse(content={"status": "success", "message": "Парсер и очередь успешно остановлены"})
    except Exception as e:
        logger.error(f"❌ Ошибка при завершении парсера: {e}")
        # Сбрасываем флаги даже при ошибке
        parser_running = False
        parser_task = None
        parser_start_time = None
        return JSONResponse(content={"status": "error", "error": str(e)})

@app.get("/api/processing-stats")
async def get_processing_stats(request: Request):
    """Получение статистики обработки"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная сессия"
        )
    
    """Получает статистику времени обработки заявок из истории"""
    try:
        data_dir = "static/data"
        if not os.path.exists(data_dir):
            logger.info("📁 Папка static/data не найдена")
            return JSONResponse(content={
                "average_time": "0м 0с",
                "total_completed": 0,
                "total_time": "0м 0с"
            })
        
        completed_requests = []
        total_duration_seconds = 0
        
        # Проходим по всем папкам в static/data
        for folder_name in os.listdir(data_dir):
            folder_path = os.path.join(data_dir, folder_name)
            
            if not os.path.isdir(folder_path):
                continue
                
            json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
            if not json_files:
                continue
            
            # Берем самый новый JSON файл
            latest_json = max(json_files, key=lambda f: os.path.getctime(os.path.join(folder_path, f)))
            json_path = os.path.join(folder_path, latest_json)
            
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    json_data = json.load(f)
                
                json_data = clean_json_data(json_data)
                metadata = json_data.get("metadata", {})
                
                # Проверяем, что заявка завершена
                json_completed = metadata.get("json_completed", False)
                db_saved = metadata.get("db_saved", False)
                options_success = metadata.get("options_success", False)
                total_zones = len(json_data.get("zone_data", [])) if json_data else 0
                
                logger.info(f"📊 Проверяем {folder_name}: json_completed={json_completed}, db_saved={db_saved}, options_success={options_success}, total_zones={total_zones}")
                
                # Используем ту же логику, что и в эндпоинте /history
                if json_completed and db_saved and total_zones > 0:
                    started_at = metadata.get("started_at", "")
                    completed_at = metadata.get("completed_at", "")
                    last_updated = metadata.get("last_updated", "")
                    
                    # Восстанавливаем started_at из БД если он null или неправильный
                    should_restore = (started_at is None or started_at == "null" or started_at == "None" or started_at == "")
                    
                    # Также проверяем, если время есть, но оно неправильное
                    if not should_restore and started_at:
                        try:
                            # Парсим время из JSON
                            json_time = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                            # Проверяем, что время не слишком старое (признак неправильного времени)
                            current_time = datetime.now()
                            time_diff = (current_time - json_time).total_seconds()
                            if time_diff > 86400:  # Если разница больше 24 часов
                                should_restore = True
                                logger.info(f"🔍 Время в JSON слишком старое для {folder_name}: {started_at}")
                        except:
                            should_restore = True
                    
                    if should_restore:
                        logger.info(f"🔍 Нужно восстановить started_at для {folder_name}: текущее значение='{started_at}'")
                        # Извлекаем claim_number и vin из имени папки
                        if "_" in folder_name:
                            claim_number = folder_name.split("_")[0]
                            vin = folder_name.split("_")[1] if len(folder_name.split("_")) > 1 else ""
                            
                            logger.info(f"🔍 Извлечено из имени папки: claim_number='{claim_number}', vin='{vin}'")
                            
                            if claim_number and vin:
                                try:
                                    logger.info(f"🔍 Вызываем restore_started_at_from_db для {json_path}")
                                    result = await restore_started_at_from_db(json_path, claim_number, vin)
                                    logger.info(f"🔍 Результат восстановления started_at: {result}")
                                    
                                    # Также восстанавливаем completed_at
                                    logger.info(f"🔍 Вызываем restore_completed_at_from_db для {json_path}")
                                    result_completed_at = await restore_completed_at_from_db(json_path, claim_number, vin)
                                    logger.info(f"🔍 Результат восстановления completed_at: {result_completed_at}")
                                    
                                    # Также восстанавливаем last_updated
                                    logger.info(f"🔍 Вызываем restore_last_updated_from_db для {json_path}")
                                    result_last_updated = await restore_last_updated_from_db(json_path, claim_number, vin)
                                    logger.info(f"🔍 Результат восстановления last_updated: {result_last_updated}")
                                    
                                    if result or result_completed_at or result_last_updated:
                                        # Перечитываем JSON после восстановления
                                        with open(json_path, 'r', encoding='utf-8') as f:
                                            json_data = json.load(f)
                                        metadata = json_data.get("metadata", {})
                                        started_at = metadata.get("started_at", "")
                                        completed_at = metadata.get("completed_at", "")
                                        last_updated = metadata.get("last_updated", "")
                                        logger.info(f"🔍 Новое значение started_at: '{started_at}'")
                                        logger.info(f"🔍 Новое значение completed_at: '{completed_at}'")
                                        logger.info(f"🔍 Новое значение last_updated: '{last_updated}'")
                                    else:
                                        logger.warning(f"⚠️ Восстановление не удалось для {folder_name}")
                                except Exception as e:
                                    logger.warning(f"⚠️ Не удалось восстановить время для {folder_name}: {e}")
                            else:
                                logger.warning(f"⚠️ Не удалось извлечь claim_number или vin из {folder_name}")
                        else:
                            logger.warning(f"⚠️ Неправильный формат имени папки: {folder_name}")
                    else:
                        logger.info(f"🔍 started_at уже есть для {folder_name}: '{started_at}'")
                    
                    logger.info(f"⏰ Время для {folder_name}: started_at={started_at}, completed_at={completed_at}")
                    
                    if started_at and started_at != "null" and started_at != "None":
                        try:
                            start_dt = datetime.strptime(started_at, "%Y-%m-%d %H:%M:%S")
                            end_time_str = completed_at if completed_at and completed_at != "null" and completed_at != "None" else last_updated
                            
                            if end_time_str and end_time_str != "null" and end_time_str != "None":
                                end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")
                                duration_seconds = (end_dt - start_dt).total_seconds()
                                
                                if duration_seconds > 0:
                                    completed_requests.append(duration_seconds)
                                    total_duration_seconds += duration_seconds
                                    logger.info(f"✅ Добавлено время для {folder_name}: {duration_seconds}с")
                        except Exception as e:
                            logger.warning(f"⚠️ Ошибка парсинга времени для {folder_name}: {e}")
                            continue
                            
            except Exception as e:
                logger.warning(f"⚠️ Ошибка чтения JSON файла {json_path}: {e}")
                continue
        
        logger.info(f"📈 Найдено завершенных заявок: {len(completed_requests)}")
        
        # Вычисляем статистику
        if completed_requests:
            average_seconds = total_duration_seconds / len(completed_requests)
            average_minutes = int(average_seconds // 60)
            average_secs = int(average_seconds % 60)
            average_time = f"{average_minutes}м {average_secs}с"
            
            total_minutes = int(total_duration_seconds // 60)
            total_secs = int(total_duration_seconds % 60)
            total_time = f"{total_minutes}м {total_secs}с"
            
            logger.info(f"📊 Статистика: среднее время={average_time}, общее время={total_time}")
        else:
            average_time = "0м 0с"
            total_time = "0м 0с"
            logger.info("📊 Нет завершенных заявок для расчета статистики")
        
        return JSONResponse(content={
            "average_time": average_time,
            "total_completed": len(completed_requests),
            "total_time": total_time
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка при получении статистики: {e}")
        return JSONResponse(content={
            "average_time": "0м 0с",
            "total_completed": 0,
            "total_time": "0м 0с"
        })


# API эндпоинты для работы с настройками расписания парсера

@app.get("/api/schedule/settings")
async def get_schedule_settings_api(request: Request):
    """Получение настроек расписания"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная сессия"
        )
    """Получает текущие настройки расписания парсера"""
    try:
        async with async_session() as session:
            settings = await get_schedule_settings(session)
        logger.info(f"📋 Получены настройки расписания: {settings}")
        return JSONResponse(content=settings)
    except Exception as e:
        logger.error(f"❌ Ошибка получения настроек расписания: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Ошибка получения настроек расписания"}
        )

@app.post("/api/schedule/settings")
async def save_schedule_settings_api(request_data: ScheduleSettingsRequest, request: Request):
    """Сохранение настроек расписания"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная сессия"
        )
    """Сохраняет настройки расписания парсера"""
    try:
        # Валидация времени
        if not request_data.start_time or not request_data.end_time:
            return JSONResponse(
                status_code=400,
                content={"error": "Время начала и окончания обязательны"}
            )
        
        # Проверяем формат времени (HH:MM)
        time_pattern = r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$'
        if not re.match(time_pattern, request_data.start_time) or not re.match(time_pattern, request_data.end_time):
            return JSONResponse(
                status_code=400,
                content={"error": "Неверный формат времени. Используйте HH:MM"}
            )
        
        # Проверяем, что время начала меньше времени окончания
        start_minutes = int(request_data.start_time.split(':')[0]) * 60 + int(request_data.start_time.split(':')[1])
        end_minutes = int(request_data.end_time.split(':')[0]) * 60 + int(request_data.end_time.split(':')[1])
        
        if start_minutes >= end_minutes:
            return JSONResponse(
                status_code=400,
                content={"error": "Время начала должно быть раньше времени окончания"}
            )
        
        async with async_session() as session:
            success = await save_schedule_settings(session, request_data.start_time, request_data.end_time)
            
            if success:
                # Получаем обновленные настройки
                settings = await get_schedule_settings(session)
                logger.info(f"✅ Настройки расписания сохранены: {request_data.start_time} - {request_data.end_time}")
                return JSONResponse(content=settings)
            else:
                return JSONResponse(
                    status_code=500,
                    content={"error": "Ошибка сохранения настроек"}
                )
                
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения настроек расписания: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Внутренняя ошибка сервера"}
        )

@app.get("/api/schedule/status")
async def get_schedule_status_api(request: Request):
    """Получение статуса расписания"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная сессия"
        )
    
    """Получает текущий статус расписания парсера"""
    try:
        async with async_session() as session:
            settings = await get_schedule_settings(session)
        
        if not settings.get('is_active'):
            return JSONResponse(content={
                "status": "inactive",
                "message": "Парсер неактивен - настройки не заданы",
                "current_time": get_moscow_time().strftime('%H:%M'),
                "settings": settings
            })
        
        start_time = settings['start_time']
        end_time = settings['end_time']
        
        # Проверяем, находимся ли в рабочем времени
        is_working = is_time_in_working_hours(start_time, end_time)
        
        if is_working:
            time_to_end = get_time_to_end(end_time)
            return JSONResponse(content={
                "status": "active",
                "message": "Парсер активен",
                "current_time": get_moscow_time().strftime('%H:%M'),
                "time_to_end_minutes": time_to_end,
                "settings": settings
            })
        else:
            time_to_start = get_time_to_start(start_time)
            return JSONResponse(content={
                "status": "waiting",
                "message": "Ожидание начала работы",
                "current_time": get_moscow_time().strftime('%H:%M'),
                "time_to_start_minutes": time_to_start,
                "settings": settings
            })
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения статуса расписания: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Ошибка получения статуса расписания"}
        )

@app.get("/api/queue/status")
async def get_queue_status_api(request: Request):
    """Получение статуса очереди"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная сессия"
        )
    """Получает статус очереди заявок"""
    try:
        queue_length = redis_manager.get_queue_length()
        
        return JSONResponse(content={
            "total": queue_length,
            "position": queue_length,  # Позиция последней добавленной заявки
            "is_processing": queue_processor.is_running if 'queue_processor' in globals() else False
        })
                
    except Exception as e:
        logger.error(f"❌ Ошибка получения статуса очереди: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Ошибка получения статуса очереди"}
        )



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
