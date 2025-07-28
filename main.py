import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from core.parser.parser import login_audatex, terminate_all_processes_and_restart
import json
import os
from datetime import datetime
import logging
from core.database.models import ParserCarDetail, ParserCarDetailGroupZone, ParserCarRequestStatus, async_session, get_moscow_time
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
        from core.database.models import start_db
        await start_db()
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации БД: {e}")
    
    yield
    
    # Shutdown
    try:
        from core.database.models import close_db
        await close_db()
        logger.info("✅ Соединения с БД закрыты")
    except Exception as e:
        logger.error(f"❌ Ошибка закрытия БД: {e}")

# Инициализация FastAPI приложения
app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Модели для валидации входного JSON
class SearchItem(BaseModel):
    requestId: int
    vin: str

class SearchRequest(BaseModel):
    login: str
    password: str
    items: List[SearchItem]
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
        claim_number: Номер заявки
        vin_value: VIN номер
        parser_result: Результат парсера
        started_at: Время начала парсинга
        completed_at: Время завершения парсинга
    
    Returns:
        bool: True если обработка прошла успешно
    """
    try:
        # Формируем имя папки
        folder_name = f"{claim_number}_{vin_value}"
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
        
        logger.info(f"📁 Обрабатываем JSON файл: {file_path}")
        
        # Читаем JSON файл
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Обновляем JSON с claim_number
        updated_json = update_json_with_claim_number(json_data, claim_number)
        
        # Сохраняем обновленный JSON обратно в файл
        save_success = await save_updated_json_to_file(updated_json, file_path)
        if not save_success:
            logger.error(f"Не удалось сохранить обновленный JSON: {file_path}")
            return False
        
        # Сохраняем данные в БД с временными метками
        db_success = await save_parser_data_to_db(updated_json, claim_number, vin_value, is_success=True, started_at=started_at, completed_at=completed_at)
        if not db_success:
            logger.error(f"Не удалось сохранить данные в БД: {claim_number}_{vin_value}")
            return False
        
        logger.info(f"✅ Обработка завершена успешно: {claim_number}_{vin_value}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка обработки данных: {e}")
        return False


def fix_path(path: str, folder_name: str) -> str:
    """Исправляет пути к файлам, добавляя folder_name"""
    if path and not path.startswith("/"):
        path = "/" + path
    
    if path and path.startswith("/static/"):
        parts = path.split("/")
        if len(parts) >= 3:
            # Вставляем folder_name после /static/
            parts.insert(2, folder_name)
            return "/".join(parts)
    
    return path


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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/history", response_class=HTMLResponse)
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
                
                # Определяем статус по флагам из метаданных
                
                if json_completed and db_saved and options_success:
                    status = "Завершена"
                elif json_completed and not db_saved:
                    status = "Ошибка БД"
                elif not json_completed:
                    status = "В процессе"
                else:
                    status = "Неизвестно"
                
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
                    "folder_name": folder_name
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
                    completed_time = end_dt.strftime("%H:%M:%S")
                    
                    duration_seconds = (end_dt - start_dt).total_seconds()
                    duration = f"{int(duration_seconds // 60)}м {int(duration_seconds % 60)}с"
            except Exception as e:
                logger.warning(f"⚠️ Ошибка парсинга времени: {e}")
                pass
        
        # Получаем детали из JSON
        details = []
        for zone in json_data.get("zone_data", []):
            zone_title = zone.get("title", "")
            for detail in zone.get("details", []):
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
        if options_data and options_data.get("success"):
            for zone in options_data.get("zones", []):
                zone_title = zone.get("zone_title", "")
                for option in zone.get("options", []):
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
                "main_screenshot_path": json_data.get("main_screenshot_path", ""),
                "main_svg_path": json_data.get("main_svg_path", ""),
                "zone_data": json_data.get("zone_data", []),
                "options_data": json_data.get("options_data", {}),
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


@app.post("/process_audatex_requests")
async def import_from_json(request: SearchRequest):
    global parser_start_time
    results = []
    
    for item in request.items:
        try:
            claim_number = str(item.requestId)
            vin_number = item.vin
            logger.info(f"Запуск парсера для requestId: {claim_number}, VIN: {vin_number}")

            # Устанавливаем время начала для каждого запроса
            parser_start_time = get_moscow_time()

            # Вызываем парсер с временными метками
            parser_result = await login_audatex(request.login, request.password, claim_number, vin_number, request.svg_collection, parser_start_time)

            if "error" in parser_result:
                logger.error(f"Ошибка парсинга для requestId {claim_number}: {parser_result['error']}")
                
                # Сохраняем данные об ошибке в БД
                error_data = {
                    "folder": f"{claim_number}_{vin_number}",
                    "vin_value": vin_number,
                    "zone_data": [],
                    "error_message": parser_result['error']
                }
                await save_parser_data_to_db(error_data, claim_number, vin_number, is_success=False)
                
                results.append({
                    "requestId": item.requestId,
                    "vin": vin_number,
                    "status": "error",
                    "error": f"Ошибка парсинга: {parser_result['error']}"
                })
                continue

            # Обрабатываем успешный результат
            success = await process_parser_result_data(claim_number, vin_number, parser_result, parser_result.get('started_at'), parser_result.get('completed_at'))
            
            if success:
                # Логируем время работы для batch запросов
                if parser_start_time and parser_result.get('completed_at'):
                    try:
                        completed_time = parser_result.get('completed_at')
                        if isinstance(completed_time, str):
                            completed_time = datetime.strptime(completed_time, "%Y-%m-%d %H:%M:%S")
                        
                        duration_seconds = (completed_time - parser_start_time).total_seconds()
                        duration_minutes = int(duration_seconds // 60)
                        duration_secs = int(duration_seconds % 60)
                        
                        logger.info(f"⏱️ Парсер {claim_number}_{vin_number} завершен. Время работы: {duration_minutes}м {duration_secs}с")
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка расчета времени работы для {claim_number}_{vin_number}: {e}")

                results.append({
                    "requestId": item.requestId,
                    "vin": vin_number,
                    "status": "success",
                    "message": "Данные успешно обработаны и сохранены"
                })
            else:
                results.append({
                    "requestId": item.requestId,
                    "vin": vin_number,
                    "status": "error",
                    "error": "Ошибка обработки данных"
                })
        except Exception as e:
            logger.error(f"Ошибка обработки заявки {item.requestId}: {e}")
            results.append({
                "requestId": item.requestId,
                "vin": item.vin,
                "status": "error",
                "error": f"Внутренняя ошибка: {str(e)}"
            })

    # Сбрасываем время начала
    parser_start_time = None

    return JSONResponse(content={"results": results})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...),
                claim_number: str = Form(default=""), vin_number: str = Form(default=""),
                svg_collection: str = Form(default="")):
    global parser_running, parser_task, parser_start_time

    if not claim_number and not vin_number:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Необходимо указать номер дела или VIN номер"
        })

    try:
        logger.info(f"Запуск парсера для claim_number: {claim_number}, VIN: {vin_number}")
        # Если checkbox отмечен, приходит "on", если не отмечен - пустая строка
        svg_collection_bool = svg_collection == "on"
        logger.info(f"🎛️ Сбор SVG: {'ВКЛЮЧЕН' if svg_collection_bool else 'ОТКЛЮЧЕН'}")

        # Проверяем, не запущен ли уже парсер
        if parser_running:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Парсер уже запущен. Дождитесь завершения или остановите его."
            })
        
        # Устанавливаем флаг запуска и время начала
        parser_running = True
        parser_start_time = get_moscow_time()
        logger.info(f"🕐 Парсер запущен в: {parser_start_time.strftime('%H:%M:%S')}")

        # Запускаем парсер в отдельной задаче с передачей времени начала
        async def run_parser_with_time():
            return await login_audatex(username, password, claim_number, vin_number, svg_collection_bool, parser_start_time)
        
        parser_task = asyncio.create_task(run_parser_with_time())
        
        try:
            # Ждем завершения парсера
            parser_result = await parser_task
        except asyncio.CancelledError:
            logger.info("Задача парсера была отменена")
            parser_running = False
            parser_task = None
            parser_start_time = None
            # Рендерим страницу логина с пустой формой
            return templates.TemplateResponse("index.html", {"request": request})
        except Exception as e:
            logger.error(f"Ошибка парсинга: {e}")
            parser_running = False
            parser_task = None
            parser_start_time = None
            # Рендерим страницу логина с пустой формой
            return templates.TemplateResponse("index.html", {"request": request})
    finally:
        # Сбрасываем флаг запуска
        parser_running = False
        parser_task = None
        parser_start_time = None

    if "error" in parser_result:
        logger.error(f"Ошибка парсинга: {parser_result['error']}")
        parser_running = False
        parser_task = None
        parser_start_time = None
        # Рендерим страницу логина с пустой формой
        return templates.TemplateResponse("index.html", {"request": request})

    zone_data = parser_result.get("zone_data", [])
    if not zone_data:
        logger.warning("Зоны не найдены для указанного номера дела или VIN")
        parser_running = False
        parser_task = None
        parser_start_time = None
        # Рендерим страницу логина с пустой формой
        return templates.TemplateResponse("index.html", {"request": request})

    # Формируем folder_name
    folder_name = f"{parser_result.get('claim_number')}_{parser_result.get('vin_value')}"

    # Формируем record
    record = {
        "folder": folder_name,
        "vin_value": parser_result.get("vin_value", vin_number or claim_number),
        "vin_status": parser_result.get("vin_status", "Неизвестно"),
        "zone_data": parser_result.get("zone_data", []),
        "main_screenshot_path": parser_result.get("main_screenshot_path", ""),
        "main_svg_path": parser_result.get("main_svg_path", ""),
        "all_svgs_zip": parser_result.get("all_svgs_zip", ""),
        "options_data": parser_result.get("options_data", {"success": False, "zones": []}),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Нормализуем пути
    record = normalize_paths(record, folder_name)

    # Обрабатываем данные с временными метками
    success = await process_parser_result_data(
        parser_result.get('claim_number'), 
        parser_result.get('vin_value'), 
        parser_result,
        parser_start_time,
        parser_result.get('completed_at')
    )

    if not success:
        parser_running = False
        parser_task = None
        # Рендерим страницу логина с пустой формой
        return templates.TemplateResponse("index.html", {"request": request})

    # Сбрасываем флаги
    parser_running = False
    parser_task = None
    
    # Логируем итоговое время работы парсера
    if parser_start_time and parser_result.get('completed_at'):
        try:
            completed_time = parser_result.get('completed_at')
            if isinstance(completed_time, str):
                completed_time = datetime.strptime(completed_time, "%Y-%m-%d %H:%M:%S")
            
            duration_seconds = (completed_time - parser_start_time).total_seconds()
            duration_minutes = int(duration_seconds // 60)
            duration_secs = int(duration_seconds % 60)
            
            logger.info(f"⏱️ Парсер завершен. Время работы: {duration_minutes}м {duration_secs}с")
            logger.info(f"🕐 Начало: {parser_start_time.strftime('%H:%M:%S')}, Завершение: {completed_time.strftime('%H:%M:%S')}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка расчета времени работы: {e}")
    
    parser_start_time = None
    
    # Формируем folder_name для редиректа
    folder_name = f"{parser_result.get('claim_number')}_{parser_result.get('vin_value')}"
    
    # Редиректим на history_detail вместо success.html
    return RedirectResponse(url=f"/history_detail/{folder_name}", status_code=302)


@app.post("/terminate")
async def terminate_parser():
    global parser_running, parser_task, parser_start_time
    try:
        logger.info("🛑 Получен запрос на остановку парсера")
        
        # Сбрасываем флаги сразу
        parser_running = False
        parser_start_time = None
        
        # Отменяем задачу парсера, если она запущена
        if parser_task and not parser_task.done():
            parser_task.cancel()
            try:
                await asyncio.wait_for(parser_task, timeout=2.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("✅ Задача парсера отменена или время ожидания истекло")
        
        # Завершаем процессы браузера
        result = terminate_all_processes_and_restart()
        
        # Очищаем ссылку на задачу
        parser_task = None
        
        logger.info(f"✅ Парсер остановлен: {result}")
        return JSONResponse(content={"status": "success", "message": "Парсер успешно остановлен"})
    except Exception as e:
        logger.error(f"❌ Ошибка при завершении парсера: {e}")
        # Сбрасываем флаги даже при ошибке
        parser_running = False
        parser_task = None
        parser_start_time = None
        return JSONResponse(content={"status": "error", "error": str(e)})

@app.get("/api/processing-stats")
async def get_processing_stats():
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
                
                logger.info(f"📊 Проверяем {folder_name}: json_completed={json_completed}, db_saved={db_saved}, options_success={options_success}")
                
                if json_completed and db_saved and options_success:
                    started_at = metadata.get("started_at", "")
                    completed_at = metadata.get("completed_at", "")
                    last_updated = metadata.get("last_updated", "")
                    
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)