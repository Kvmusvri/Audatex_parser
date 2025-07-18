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
from core.database.models import start_db, ParserCarDetail, ParserCarDetailGroupZone, ParserCarRequestStatus, async_session
from pydantic import BaseModel
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.sql import text
import re
from core.database.requests import (
    create_request_status,
    create_equipment_zone,
    create_group_zone,
    create_car_detail,
)
from core.database.engine import engine
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


def normalize_paths(record: dict, folder_name: str) -> dict:
    """Нормализует пути к файлам, добавляя claim_number и vin исправляя слеши"""

    def fix_path(path: str, folder: str) -> str:
        if not path:
            return path
        # Убираем двойные слеши и добавляем claim_number
        parts = path.split('/')
        if len(parts) >= 4 and parts[3] == '':
            parts[3] = folder_name
        return '/'.join(parts)

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
                    async with AsyncSession(engine) as session:
                        await create_request_status(session, claim_number, vin_number, "nsvg")
                    results.append({
                        "requestId": item.requestId,
                        "vin": vin_number,
                        "status": "error",
                        "error": f"Ошибка парсинга: {parser_result['error']}"
                    })
                    continue

                # Проверяем, создался ли JSON-файл
                folder_path = os.path.join("static", "data", claim_number)
                if not os.path.isdir(folder_path):
                    logger.error(f"Папка {folder_path} не существует после парсинга")
                    async with AsyncSession(engine) as session:
                        await create_request_status(session, claim_number, vin_number, "nsvg")
                    results.append({
                        "requestId": item.requestId,
                        "vin": vin_number,
                        "status": "error",
                        "error": "Папка не найдена после парсинга"
                    })
                    continue

                json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
                if not json_files:
                    logger.error(f"JSON-файлы не найдены в {folder_path}")
                    async with AsyncSession(engine) as session:
                        await create_request_status(session, claim_number, vin_number, "nsvg")
                    results.append({
                        "requestId": item.requestId,
                        "vin": vin_number,
                        "status": "error",
                        "error": "Данные не найдены после парсинга"
                    })
                    continue

                # Записываем статус ysvg, так как JSON-файл найден
                async with AsyncSession(engine) as session:
                    await create_request_status(session, claim_number, vin_number, "ysvg")

                    # Создаём зону комплектации
                    equipment_zone_id = await create_equipment_zone(session, claim_number, vin_number)

                    # Читаем последний JSON-файл
                    latest_json = max(json_files, key=lambda f: os.path.getctime(os.path.join(folder_path, f)))
                    file_path = os.path.join(folder_path, latest_json)

                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)

                        vin_value = data.get("vin_value", vin_number)
                        zone_data = data.get("zone_data", [])

                        if not zone_data:
                            logger.warning(f"Зоны не найдены в JSON для requestId {claim_number}")
                            results.append({
                                "requestId": item.requestId,
                                "vin": vin_number,
                                "status": "error",
                                "error": "Зоны не найдены"
                            })
                            continue

                        logger.info(f"Найдено зон для requestId {claim_number}: {len(zone_data)}")
                        for zone in zone_data:
                            zone_title = zone.get("title", "").strip()
                            has_pictograms = zone.get("has_pictograms", False)
                            logger.debug(f"Обработка зоны: {zone_title}, has_pictograms: {has_pictograms}")

                            group_zone_id = await create_group_zone(
                                session, claim_number, vin_value, has_pictograms, zone_title
                            )

                            items = zone.get("pictograms", []) if has_pictograms else zone.get("details", [])
                            logger.debug(f"Количество элементов в зоне {zone_title}: {len(items)}")

                            if has_pictograms:
                                for pictogram in items:
                                    works = pictogram.get("works", [])
                                    logger.debug(f"Количество работ в пиктограмме: {len(works)}")
                                    for work in works:
                                        title = work.get("work_name1", "")
                                        titles = title.split(",")
                                        for t in titles:
                                            t = t.strip()
                                            if not t:
                                                logger.debug(f"Пропущен пустой элемент: {t}")
                                                continue
                                            code_match = re.match(r'^[A-Za-z0-9]+', t)
                                            if not code_match:
                                                logger.debug(f"Пропущен элемент без кода: {t}")
                                                continue
                                            code = code_match.group(0)
                                            clean_title = t[len(code):].strip().strip("- ")
                                            is_letter_code = bool(re.match(r'^[A-Za-z]', code))
                                            if clean_title:
                                                await create_car_detail(
                                                    session,
                                                    claim_number,
                                                    equipment_zone_id if is_letter_code else group_zone_id,
                                                    vin_value,
                                                    code,
                                                    clean_title
                                                )
                                                logger.debug(f"Записана деталь: code={code}, title={clean_title}, group_zone={equipment_zone_id if is_letter_code else group_zone_id}")
                                            else:
                                                logger.debug(f"Пропущена деталь с пустым clean_title: {t}")
                            else:
                                for detail in items:
                                    titles = detail.get("title", "").split(",")
                                    logger.debug(f"Количество заголовков в детали: {len(titles)}")
                                    for title in titles:
                                        title = title.strip()
                                        if not title:
                                            logger.debug(f"Пропущен пустой элемент: {title}")
                                            continue
                                        code_match = re.match(r'^[A-Za-z0-9]+', title)
                                        if not code_match:
                                            logger.debug(f"Пропущен элемент без кода: {title}")
                                            continue
                                        code = code_match.group(0)
                                        clean_title = title[len(code):].strip().strip("- ")
                                        is_letter_code = bool(re.match(r'^[A-Za-z]', code))
                                        if clean_title:
                                            await create_car_detail(
                                                session,
                                                claim_number,
                                                equipment_zone_id if is_letter_code else group_zone_id,
                                                vin_value,
                                                code,
                                                clean_title
                                            )
                                            logger.debug(f"Записана деталь: code={code}, title={clean_title}, group_zone={equipment_zone_id if is_letter_code else group_zone_id}")
                                        else:
                                            logger.debug(f"Пропущена деталь с пустым clean_title: {title}")

                        results.append({
                            "requestId": item.requestId,
                            "vin": vin_number,
                            "status": "success",
                            "message": "Данные импортированы"
                        })

                    except Exception as e:
                        logger.error(f"Ошибка обработки JSON для requestId {claim_number}: {str(e)}")
                        results.append({
                            "requestId": item.requestId,
                            "vin": vin_number,
                            "status": "error",
                            "error": f"Ошибка обработки JSON: {str(e)}"
                        })

    finally:
        await engine.dispose()

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
        "zone_data": parser_result.get("zone_data", []),
        "main_screenshot_path": parser_result.get("main_screenshot_path", ""),
        "main_svg_path": parser_result.get("main_svg_path", ""),
        "all_svgs_zip": parser_result.get("all_svgs_zip", ""),
        "options_data": parser_result.get("options_data", {"success": False, "zones": []}),
        "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Нормализуем пути
    record = normalize_paths(record, folder_name)

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
    asyncio.run(start_db())
    uvicorn.run(app, host="0.0.0.0", port=8000)