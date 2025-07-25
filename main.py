import asyncio
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from core.parser.parser import login_audatex, terminate_all_processes_and_restart
import json
import os
from datetime import datetime
import logging
from core.database.models import ParserCarDetail, ParserCarDetailGroupZone, ParserCarRequestStatus, async_session
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


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация FastAPI приложения
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Модели для валидации входного JSON
class SearchItem(BaseModel):
    requestId: int
    vin: str

class SearchRequest(BaseModel):
    login: str
    password: str
    searchList: List[SearchItem]
    svg_collection: bool = True  # По умолчанию включен сбор SVG


def fix_path(path: str, folder: str) -> str:
    """Исправляет путь, добавляя имя папки, если нужно, и убирает двойные слеши"""
    if not path:
        return path
    parts = path.split('/')
    if len(parts) >= 4 and parts[3] == '':
        parts[3] = folder
    return '/'.join(parts)

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


async def process_parser_result_data(claim_number: str, vin_value: str, parser_result: dict) -> bool:
    """
    Обрабатывает данные результата парсера: ищет JSON файл и сохраняет в БД
    
    Args:
        claim_number: Номер заявки
        vin_value: VIN номер
        parser_result: Результат парсера
    
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
            logger.error(f"❌ Ошибка сохранения обновленного JSON: {file_path}")
            return False
        
        # Сохраняем данные в БД
        db_success = await save_parser_data_to_db(
            json_data=updated_json,
            request_id=claim_number,
            vin=vin_value,
            is_success=True
        )
        
        if db_success:
            logger.info(f"✅ Данные успешно сохранены в БД для request_id={claim_number}, vin={vin_value}")
            return True
        else:
            logger.error(f"❌ Ошибка сохранения данных в БД для request_id={claim_number}, vin={vin_value}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка обработки данных парсера: {e}")
        return False


@app.post("/process_audatex_requests")
async def import_from_json(request: SearchRequest):
    logger.info(f"🎛️ API запрос с флагом сбора SVG: {'ВКЛЮЧЕН' if request.svg_collection else 'ОТКЛЮЧЕН'}")
    results = []
    try:
        # Разделяем searchList на группы по 10
        batch_size = 10
        search_list = request.searchList
        for i in range(0, len(search_list), batch_size):
            batch = search_list[i:i + batch_size]  # Получаем группу до 10 элементов
            logger.info(f"Обработка группы из {len(batch)} запросов")

            # Обрабатываем каждый запрос в группе последовательно
            for item in batch:
                claim_number = str(item.requestId)
                vin_number = item.vin
                logger.info(f"Запуск парсера для requestId: {claim_number}, VIN: {vin_number}")

                # Вызываем парсер
                parser_result = await login_audatex(request.login, request.password, claim_number, vin_number, request.svg_collection)

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

                # Обрабатываем данные парсера: ищем JSON файл и сохраняем в БД
                try:
                    # Извлекаем данные для БД
                    request_id = str(claim_number)
                    vin = str(parser_result.get('vin_value', vin_number))
                    
                    # Обрабатываем данные через новую функцию
                    db_success = await process_parser_result_data(request_id, vin, parser_result)
                    
                    if db_success:
                        logger.info(f"✅ Данные успешно обработаны и сохранены в БД для requestId {claim_number}")
                        results.append({
                            "requestId": item.requestId,
                            "vin": vin_number,
                            "status": "success",
                            "message": "Данные успешно обработаны и сохранены"
                        })
                    else:
                        logger.error(f"❌ Ошибка обработки данных для requestId {claim_number}")
                        results.append({
                            "requestId": item.requestId,
                            "vin": vin_number,
                            "status": "error",
                            "error": "Ошибка обработки данных"
                        })
                        
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки данных парсера для requestId {claim_number}: {e}")
                    
                    # Сохраняем данные об ошибке в БД
                    error_data = {
                        "folder": f"{claim_number}_{vin_number}",
                        "vin_value": vin_number,
                        "zone_data": [],
                        "error_message": str(e)
                    }
                    await save_parser_data_to_db(error_data, claim_number, vin_number, is_success=False)
                    
                    results.append({
                        "requestId": item.requestId,
                        "vin": vin_number,
                        "status": "error",
                        "error": f"Ошибка обработки данных: {e}"
                    })
                    continue

            logger.info(f"✅ Обработка группы завершена")

    except Exception as e:
        logger.error(f"❌ Общая ошибка обработки: {e}")
        results.append({
            "status": "error",
            "error": f"Общая ошибка: {e}"
        })

    return {"results": results}


# Эндпоинт для главной страницы
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Эндпоинт для авторизации и поиска с запуском парсера в отдельном процессе через пул

# Глобальный пул для парсер-процессов (можно ограничить max_workers)
parser_process_pool = concurrent.futures.ProcessPoolExecutor(max_workers=1)

# Для хранения текущего future парсера и его PID
current_parser_future = None
current_parser_pid = None
parser_lock = threading.Lock()

def run_parser_in_subprocess(username, password, claim_number, vin_number, svg_collection):
    """
    Обёртка для запуска login_audatex в отдельном процессе.
    Важно: login_audatex должен быть синхронной функцией или запускаться через asyncio.run.
    """

    # Ставим низкий приоритет процессу (чтобы его можно было быстро убить через stop_parser)
    try:
        p = psutil.Process(os.getpid())
        p.nice(10)  # 10 — ниже обычного, но не idle
    except Exception as e:
        pass

    # Запускаем парсер
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(login_audatex(username, password, claim_number, vin_number, svg_collection))
    loop.close()
    return result

@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, username: str = Form(...), password: str = Form(...),
                claim_number: str = Form(default=""), vin_number: str = Form(default=""),
                svg_collection: str = Form(default="")):
    global current_parser_future, current_parser_pid

    start_time = time.time()
    
    # Обрабатываем checkbox: если есть значение (любое) - значит включен, если пустое - отключен
    svg_collection_bool = bool(svg_collection and svg_collection.lower() not in ['false', '0', ''])
    logger.info(f"🎛️ Получен флаг сбора SVG с формы: '{svg_collection}' -> {'ВКЛЮЧЕН' if svg_collection_bool else 'ОТКЛЮЧЕН'}")

    # Проверяем, не запущен ли уже парсер
    with parser_lock:
        if current_parser_future and not current_parser_future.done():
            logger.warning("Парсер уже запущен, ожидаем завершения предыдущего процесса")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error": "Парсер уже запущен. Пожалуйста, дождитесь завершения предыдущего запроса или остановите его."
            })

        # Запускаем парсер в отдельном процессе через пул
        future = parser_process_pool.submit(run_parser_in_subprocess, username, password, claim_number, vin_number, svg_collection_bool)
        current_parser_future = future

        # Получаем PID процесса парсера (через _process, это внутреннее API, но работает)
        try:
            current_parser_pid = future._process.pid
            logger.info(f"Парсер запущен в процессе PID={current_parser_pid}")
        except Exception as e:
            current_parser_pid = None
            logger.warning(f"Не удалось получить PID процесса парсера: {e}")

    # Ожидаем завершения парсера (асинхронно, чтобы не блокировать event loop)
    loop = asyncio.get_event_loop()
    parser_result = await loop.run_in_executor(None, current_parser_future.result)

    # После завершения сбрасываем PID
    with parser_lock:
        current_parser_pid = None

    if "error" in parser_result:
        logger.error(f"Ошибка парсинга: {parser_result['error']}")
        return templates.TemplateResponse("error.html", {"request": request, "error": parser_result['error']})

    zone_data = parser_result.get("zone_data", [])
    if not zone_data:
        logger.warning("Зоны не найдены для указанного номера дела или VIN")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Зоны не найдены для указанного номера дела или VIN"
        })

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

    # Обрабатываем данные парсера: ищем JSON файл и сохраняем в БД
    try:
        # Извлекаем данные для БД
        request_id = str(parser_result.get('claim_number', claim_number))
        vin = str(parser_result.get('vin_value', vin_number))
        
        # Обрабатываем данные через новую функцию
        db_success = await process_parser_result_data(request_id, vin, parser_result)
        
        if db_success:
            logger.info(f"✅ Данные успешно обработаны и сохранены в БД для request_id={request_id}, vin={vin}")
        else:
            logger.error(f"❌ Ошибка обработки данных для request_id={request_id}, vin={vin}")
    except Exception as e:
        logger.error(f"❌ Ошибка обработки данных парсера: {e}")

    logger.info("Парсинг успешно завершен, отображаем результаты")

    end_time = time.time()
    duration_sec = end_time - start_time
    duration_min = duration_sec / 60
    logger.info(f"Обработка заняла {duration_sec:.2f} секунд\n({duration_min:.2f} минут)")

    return templates.TemplateResponse("history_detail.html", {
        "request": request,
        "record": record
    })

# Эндпоинт для истории
@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    history_data = []
    data_base_dir = "static/data"

    logger.debug(f"Сканирование директории: {data_base_dir}")
    if not os.path.exists(data_base_dir):
        logger.error(f"Директория {data_base_dir} не существует")
        return templates.TemplateResponse("history.html", {
            "request": request,
            "history": True,
            "history_data": []
        })

    for root, dirs, files in os.walk(data_base_dir):
        json_files = [f for f in files if f.endswith(".json")]
        if not json_files:
            logger.debug(f"JSON-файлы не найдены в {root}")
            continue
        latest_json = max(json_files, key=lambda f: os.path.getctime(os.path.join(root, f)))
        file_path = os.path.join(root, latest_json)
        folder = os.path.relpath(root, data_base_dir).replace(os.sep, "/")
        logger.debug(f"Чтение JSON: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            file_stat = os.stat(file_path)
            history_data.append({
                "folder": folder,
                "vin_value": data.get("vin_value", folder),
                "created": datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
            })
            logger.debug(f"Успешно загружен JSON: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка при чтении {file_path}: {e}")

    logger.info(f"Найдено записей истории: {len(history_data)}")
    return templates.TemplateResponse("history.html", {
        "request": request,
        "history": True,
        "history_data": history_data
    })

# Эндпоинт для данных конкретной папки
@app.get("/history/{folder:path}", response_class=HTMLResponse)
async def history_detail(request: Request, folder: str):
    print(f"folder::{folder}")
    data_base_dir = "static/data"
    folder_path = os.path.join(data_base_dir, folder)
    logger.debug(f"Загрузка данных для папки: {folder_path}")
    print(f"Загрузка данных для папки: {folder_path}")

    if not os.path.isdir(folder_path):
        logger.error(f"Папка {folder_path} не существует")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Папка не найдена"
        })

    json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
    if not json_files:
        logger.error(f"JSON-файлы не найдены в {folder_path}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": "Данные не найдены"
        })

    latest_json = max(json_files, key=lambda f: os.path.getctime(os.path.join(folder_path, f)))
    file_path = os.path.join(folder_path, latest_json)
    logger.debug(f"Чтение JSON: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        file_stat = os.stat(file_path)

        record = {
            "folder": folder,
            "vin_value": data.get("vin_value", folder),
            "zone_data": data.get("zone_data", []),
            "main_screenshot_path": data.get("main_screenshot_path", ""),
            "main_svg_path": data.get("main_svg_path", ""),
            "all_svgs_zip": data.get("all_svgs_zip", ""),
            "options_data": data.get("options_data", {"success": False, "zones": []}),
            "created": datetime.fromtimestamp(file_stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S")
        }

        # Нормализуем пути
        record = normalize_paths(record, folder)

        logger.debug(f"Успешно загружен JSON: {file_path}")
        return templates.TemplateResponse("history_detail.html", {
            "request": request,
            "record": record
        })
    except Exception as e:
        logger.error(f"Ошибка при чтении {file_path}: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": f"Ошибка загрузки данных: {e}"
        })


@app.post("/stop_parser")
async def stop_parser_endpoint():
    global current_parser_future, current_parser_pid
    try:
        logger.warning("Получен запрос на остановку парсера. Запущена процедура завершения всех процессов и перезапуска приложения.")

        # Если есть запущенный процесс парсера — убиваем его

        killed = False
        with parser_lock:
            if current_parser_pid:
                try:
                    proc = psutil.Process(current_parser_pid)
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                        logger.warning(f"Процесс парсера PID={current_parser_pid} успешно завершён.")
                    except psutil.TimeoutExpired:
                        proc.kill()
                        logger.warning(f"Процесс парсера PID={current_parser_pid} был принудительно убит.")
                    killed = True
                except Exception as e:
                    logger.error(f"Не удалось завершить процесс парсера PID={current_parser_pid}: {e}")
                current_parser_pid = None
                current_parser_future = None

        # Возвращаем редирект на главную страницу сразу, чтобы пользователь не видел ошибку соединения
        response = RedirectResponse(url="/")
        # Запускаем завершение процессов и перезапуск приложения в фоне, чтобы не блокировать редирект
        # Передаём current_url как относительный путь, функция сама определит правильный хост
        threading.Thread(target=terminate_all_processes_and_restart, args=("/",), daemon=True).start()
        return response
    except Exception as e:
        logger.error(f"Ошибка при попытке остановки парсера: {e}")
        return JSONResponse(content={"success": False, "message": f"Ошибка при остановке парсера: {e}"})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)