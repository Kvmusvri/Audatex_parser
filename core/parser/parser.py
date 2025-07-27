import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from selectolax.lexbor import LexborHTMLParser
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, WebDriverException
import logging
import time
import pickle
import psutil
import os
import json
import datetime
from lxml import etree
import urllib3
import copy
import re
import xml.etree.ElementTree as ET
from collections import Counter
from transliterate import translit
from PIL import Image
from io import BytesIO
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import subprocess
from webdriver_manager.core.os_manager import ChromeType
import shutil
import requests
import zipfile
import platform
import sys
import signal

# Импорт констант и функций
from .constants import *
from .browser import kill_chrome_processes, get_chromedriver_version, init_browser
from .auth import load_cookies, perform_login, check_if_authorized
from .folder_manager import create_folders, extract_vin_and_claim_number
from .output_manager import create_zones_table, save_data_to_json
from .visual_processor import (
    is_zone_file, split_svg_by_details, save_svg_sync, 
    save_main_screenshot_and_svg, extract_zones, 
    process_zone, process_pictograms, ensure_zone_details_extracted
)
from .option_processor import process_vehicle_options
from .actions import (
    wait_for_table, click_cansel_button, click_request_type_button,
    search_in_table, click_more_icon, open_task, 
    switch_to_frame_and_confirm, click_breadcrumb, is_table_empty,
    find_claim_data
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Основная функция
def search_and_extract(driver, claim_number, vin_number, svg_collection=True, started_at=None):
    logger.info(f"🎛️ Флаг сбора SVG: {'ВКЛЮЧЕН' if svg_collection else 'ОТКЛЮЧЕН'}")
    zone_data = []
    if not wait_for_table(driver):
        return {"error": "Таблица не загрузилась"}
    click_cansel_button(driver)
    result = find_claim_data(driver, claim_number=claim_number, vin_number=vin_number)
    if "error" in result:
        return result
    if not click_more_icon(driver):
        return {"error": "Не удалось открыть меню действий"}
    if not open_task(driver):
        return {"error": "Не удалось открыть задачу"}
    WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
    time.sleep(0.5)
    current_url = driver.current_url
    logger.info(f"Текущий URL: {current_url}")
    claim_number, vin_number, vin_status = extract_vin_and_claim_number(driver, current_url)
    screenshot_dir, svg_dir, data_dir = create_folders(claim_number, vin_number)
    
    # Формируем URL страницы повреждений для повторного использования
    base_url = current_url.split('step')[0][:-1] + '&step=Damage+capturing'
    logger.info(f"Сформирован URL повреждений: {base_url}")
    
    # Переходим на страницу повреждений для main screenshot
    logger.info(f"Переход на URL повреждений для main screenshot: {base_url}")
    driver.get(base_url)
    WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
    time.sleep(0.5)
    if not switch_to_frame_and_confirm(driver):
        driver.switch_to.default_content()
        return {"error": f"Не удалось переключиться на фрейм {IFRAME_ID}"}
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    main_screenshot_relative, main_svg_relative = save_main_screenshot_and_svg(driver, screenshot_dir, svg_dir, timestamp, claim_number, vin_number, svg_collection)
    
    # Исправляем проблему с None при ошибке скриншота
    if main_screenshot_relative is None:
        main_screenshot_relative = ""
        logger.warning("⚠️ Основной скриншот не был сохранен, устанавливаем пустой путь")
    if main_svg_relative is None:
        main_svg_relative = ""
        logger.warning("⚠️ Основной SVG не был сохранен, устанавливаем пустой путь")
    
    # Выходим из фрейма для сбора опций
    driver.switch_to.default_content()
    
    # СНАЧАЛА СОБИРАЕМ ОПЦИИ АВТОМОБИЛЯ (до обработки зон)
    logger.info("🚗 ЭТАП 1: Сбор опций автомобиля")
    options_result = process_vehicle_options(driver, claim_number, vin_number)
    
    # ВОЗВРАЩАЕМСЯ К СТРАНИЦЕ ПОВРЕЖДЕНИЙ ДЛЯ СБОРА SVG
    logger.info("🔄 Возвращаемся к странице повреждений для сбора SVG")
    logger.info(f"Переход на URL повреждений для SVG: {base_url}")
    driver.get(base_url)
    WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
    time.sleep(0.5)
    if not switch_to_frame_and_confirm(driver):
        driver.switch_to.default_content()
        return {"error": f"Не удалось переключиться на фрейм {IFRAME_ID} для SVG"}
    
    if not click_breadcrumb(driver):
        driver.switch_to.default_content()
        return {"error": "Не удалось кликнуть по breadcrumb"}
    zones = extract_zones(driver)
    if not zones:
        driver.switch_to.default_content()
        return {"error": "Зоны не найдены"}
    
    # ЗАТЕМ ОБРАБАТЫВАЕМ ЗОНЫ И SVG
    logger.info("🎨 ЭТАП 2: Обработка зон и SVG")
    for zone in zones:
        # Проверяем, не была ли задача отменена
        try:
            if asyncio.current_task().cancelled():
                logger.info("🛑 Задача парсера была отменена во время обработки зон")
                return {"error": "Парсер был остановлен пользователем"}
        except RuntimeError:
            # Если мы не в async контексте, пропускаем проверку
            pass
        zone_data.extend(process_zone(driver, zone, screenshot_dir, svg_dir, claim_number=claim_number, vin=vin_number, svg_collection=svg_collection))
    driver.switch_to.default_content()
    
    # ГАРАНТИРУЕМ извлечение деталей из всех зон
    logger.info(f"🔧 Запускаем финальную проверку извлечения деталей для {len(zone_data)} зон")
    zone_data = ensure_zone_details_extracted(zone_data, svg_dir, claim_number=claim_number, vin=vin_number, svg_collection=svg_collection)
    
    zones_table = create_zones_table(zone_data)
    
    # Получаем время завершения
    completed_at = datetime.datetime.now()
    logger.info(f"🕐 Парсер завершен в: {completed_at.strftime('%H:%M:%S')}")
    
    json_path = save_data_to_json(
        vin_number, zone_data, main_screenshot_relative, main_svg_relative, 
        zones_table, "", data_dir, claim_number, options_result, vin_status,
        started_at=started_at, completed_at=completed_at
    )
    
    return {
        "success": "Задача открыта", 
        "main_screenshot_path": main_screenshot_relative, 
        "main_svg_path": main_svg_relative, 
        "zones_table": zones_table, 
        "zone_data": zone_data, 
        "options_data": options_result, 
        "vin_value": vin_number, 
        "claim_number": claim_number,
        "started_at": started_at,
        "completed_at": completed_at
    }

# Точка входа в парсер 
async def login_audatex(username: str, password: str, claim_number: str, vin_number: str, svg_collection: bool = True, started_at=None):
    """
    Асинхронная функция для входа в Audatex и выполнения парсинга
    """
    driver = None
    try:
        logger.info("🚀 Начинаем процесс входа в Audatex")
        
        # Инициализируем браузер
        driver = init_browser()
        if not driver:
            return {"error": "Не удалось инициализировать браузер"}
        
        # Загружаем cookies
        if not load_cookies(driver, BASE_URL, COOKIES_FILE):
            logger.warning("⚠️ Cookies не загружены, выполняем вход заново")
            if not perform_login(driver, username, password, COOKIES_FILE):
                return {"error": "Не удалось выполнить вход в систему"}
        else:
            logger.info("✅ Cookies загружены успешно")
            if not check_if_authorized(driver):
                logger.warning("⚠️ Cookies устарели, выполняем вход заново")
                if not perform_login(driver, username, password, COOKIES_FILE):
                    return {"error": "Не удалось выполнить вход в систему"}
        
        logger.info("✅ Вход в систему выполнен успешно")
        
        # Выполняем поиск и извлечение данных в отдельном потоке
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: search_and_extract(driver, claim_number, vin_number, svg_collection, started_at))
        
        # Сохраняем cookies после успешного выполнения
        if "success" in result:
            try:
                cookies = driver.get_cookies()
                with open(COOKIES_FILE, "wb") as f:
                    pickle.dump(cookies, f)
                logger.info("✅ Cookies обновлены после успешного выполнения")
            except Exception as e:
                logger.warning(f"⚠️ Не удалось сохранить cookies: {e}")
        
        return result
        
    except asyncio.CancelledError:
        logger.info("🛑 Задача парсера была отменена")
        return {"error": "Парсер был остановлен пользователем"}
    except Exception as e:
        logger.error(f"❌ Ошибка в login_audatex: {e}")
        return {"error": f"Ошибка парсинга: {str(e)}"}
    finally:
        if driver:
            try:
                driver.quit()
                logger.info("Попытка 1: Браузер закрыт в finally")
            except Exception as e:
                logger.error(f"Ошибка при закрытии браузера: {e}")

# Функция для завершения всех процессов браузера
def terminate_all_processes_and_restart(current_url=None):
    logger.critical("🛑 Завершение всех процессов браузера инициировано!")
    try:
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] in ['chrome.exe', 'chromedriver.exe', 'chrome', 'chromedriver']:
                try:
                    proc.kill()
                    logger.critical(f"✅ Завершён процесс браузера: {proc.info['name']} (pid={proc.info['pid']})")
                except Exception as e:
                    logger.error(f"❌ Ошибка при завершении процесса {proc.info['name']}: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка при завершении процессов Chrome/Chromedriver: {e}")
    
    logger.critical("✅ Все процессы браузера завершены")
    return "Все процессы браузера успешно завершены"