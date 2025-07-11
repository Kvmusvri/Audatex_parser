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



# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Константы
urllib3.util.connection.CONNECTION_POOL_MAXSIZE = 20
BASE_URL = "https://www.audatex.ru/breclient/ui?process=NO_PROCESS&step=WorkListGrid#"
COOKIES_FILE = "cookies.pkl"
MODAL_BUTTON_SELECTOR = "#btn-confirm"
SCREENSHOT_DIR = "static/screenshots"
SVG_DIR = "static/svgs"
DATA_DIR = "static/data"
TIMEOUT = 60
MORE_ICON_SELECTOR = "#BREForm > div > div > div.gdc-contentBlock-body > div > div.list-grid-container.worklistgrid_custom_sent > div.worklist-grid-component > div.react-datagrid.z-cell-ellipsis.z-style-alternate.z-with-column-menu > div.z-inner > div.z-scroller > div.z-content-wrapper > div.z-content-wrapper-fix > div > div:nth-child(1) > div.z-last.z-cell > div"
VIN_SELECTOR = "#root\\.task\\.basicClaimData\\.vehicle\\.vehicleIdentification\\.VINQuery-VIN"
CLAIM_NUMBER_SELECTOR = "#root\.task\.claimNumber"
OUTGOING_TABLE_SELECTOR = "#BREForm > div > div > div.gdc-contentBlock-body > div > div.list-grid-container.worklistgrid_custom_sent > div.worklist-grid-component > div.react-datagrid.z-cell-ellipsis.z-style-alternate.z-with-column-menu > div.z-inner > div.z-scroller > div.z-content-wrapper > div.z-content-wrapper-fix > div"
OPEN_TABLE_SELECTOR = "#BREForm > div > div > div.gdc-contentBlock-body > div > div.list-grid-container.worklistgrid_custom_open > div.worklist-grid-component > div.react-datagrid.z-cell-ellipsis.z-style-alternate.z-with-column-menu > div.z-inner > div.z-scroller > div.z-content-wrapper > div.z-content-wrapper-fix > div"
ROW_SELECTOR = "#BREForm .react-datagrid .z-row"
IFRAME_ID = "iframe_root.task.damageCapture.inlineWebPad"
EMPTY_TABLE_TEXT_SELECTOR = (
    "#BREForm > div > div > div.gdc-contentBlock-body > div > "
    "div.list-grid-container div.noHeaderDataGrid > div > "
    "div.z-inner > div.z-scroller > div.z-content-wrapper > "
    "div.z-empty-text > div > div.no-items-title"
)
EMPTY_TABLE_TEXT = "Похоже у вас нет ни одного дела"



def kill_chrome_processes():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] in ['chrome.exe', 'chromedriver.exe']:
            try:
                proc.kill()
                logger.info(f"Завершен процесс: {proc.info['name']}")
            except Exception as e:
                logger.error(f"Ошибка при завершении процесса {proc.info['name']}: {e}")

def get_chromedriver_version():
    try:
        # Получаем путь к ChromeDriver
        chromedriver_path = ChromeDriverManager().install()
        # Выполняем команду chromedriver --version
        result = subprocess.check_output([chromedriver_path, "--version"], stderr=subprocess.STDOUT).decode()
        # Извлекаем версию из вывода (например, "ChromeDriver 137.0.7151.68")
        version = re.search(r"ChromeDriver\s+(\S+)", result)
        return version.group(1) if version else "неизвестно"
    except Exception as e:
        logger.warning(f"Не удалось получить версию ChromeDriver: {str(e)}")
        return "неизвестно"


def init_browser():
    try:
        system = platform.system()
        print(f"ПЛАТФОРМА - {system}")

        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-images")
        options.add_argument(
            f"user-agent=Mozilla/5.0 ({'Windows NT 10.0; Win64; x64' if system == 'Windows' else 'X11; Linux x86_64'}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.7151.122 Safari/537.36"
        )
        # options.add_argument('--headless=new')  # Включаем headless-режим
        options.add_argument('--no-sandbox')    # Для стабильной работы на Ubuntu
        options.add_argument('--disable-dev-shm-usage')  # Для избежания проблем с памятью

        # Определяем пути для ChromeDriver в зависимости от платформы
        base_tmp_dir = "tmp" if system == "Windows" else "/tmp"
        if system == "Windows":
            driver_url = "https://storage.googleapis.com/chrome-for-testing-public/137.0.7151.122/win64/chromedriver-win64.zip"
            driver_zip_path = os.path.join(base_tmp_dir, "chromedriver-win64.zip")
            driver_dir = os.path.join(base_tmp_dir, "chromedriver-win64")
            driver_path = os.path.join(driver_dir, "chromedriver-win64", "chromedriver.exe")
        else:
            driver_url = "https://storage.googleapis.com/chrome-for-testing-public/137.0.7151.122/linux64/chromedriver-linux64.zip"
            driver_zip_path = os.path.join(base_tmp_dir, "chromedriver-linux64.zip")
            driver_dir = os.path.join(base_tmp_dir, "chromedriver-linux64")
            driver_path = os.path.join(driver_dir, "chromedriver-linux64", "chromedriver")

        # Создаём директорию для распаковки
        os.makedirs(driver_dir, exist_ok=True)

        # Загружаем ChromeDriver, если он ещё не существует
        if not os.path.exists(driver_path):
            response = requests.get(driver_url)
            with open(driver_zip_path, "wb") as f:
                f.write(response.content)
            with zipfile.ZipFile(driver_zip_path, "r") as zip_ref:
                zip_ref.extractall(driver_dir)
            if system != "Windows":
                os.chmod(driver_path, 0o755)
            logger.info(f"Скачан и разархивирован ChromeDriver: {driver_path}")
        else:
            logger.info(f"Используется существующий ChromeDriver: {driver_path}")

        driver = uc.Chrome(driver_executable_path=driver_path, options=options, use_subprocess=True)
        logger.info(f"Используется ChromeDriver: {driver_path}")
        return driver
    except Exception as e:
        logger.error(f"Ошибка при инициализации браузера: {str(e)}")
        raise

def load_cookies(driver, url, cookies_file):
    cookies_valid = False
    driver.get(url)
    try:
        with open(cookies_file, "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                driver.add_cookie(cookie)
        logger.info("Cookies загружены")
        driver.refresh()
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            logger.info("Cookies недействительны, требуется авторизация")
        except TimeoutException:
            logger.info("Cookies действительны, авторизация не требуется")
            cookies_valid = True
    except FileNotFoundError:
        logger.info("Файл cookies не найден, продолжаем без cookies")
    except Exception as e:
        logger.error(f"Ошибка при загрузке cookies: {e}")
    return cookies_valid

def perform_login(driver, username, password, cookies_file):
    try:
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        logger.info("Поле username найдено")
    except TimeoutException:
        logger.error(f"Страница логина не загрузилась. URL: {driver.current_url}")
        logger.error(f"Код страницы: {driver.page_source[:500]}")
        return False

    captcha = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='captcha']")
    if captcha:
        logger.error("Обнаружена CAPTCHA")
        return False

    username_input = driver.find_element(By.NAME, "username")
    password_input = driver.find_element(By.NAME, "password")
    driver.execute_script("arguments[0].scrollIntoView(true);", username_input)
    username_input.clear()
    username_input.send_keys(username)
    logger.info("Введен логин")
    driver.execute_script("arguments[0].scrollIntoView(true);", password_input)
    password_input.clear()
    password_input.send_keys(password)
    logger.info("Введен пароль")
    submit_button = WebDriverWait(driver, TIMEOUT).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit']"))
    )
    submit_button.click()
    logger.info("Кнопка submit нажата")
    time.sleep(5)

    try:
        WebDriverWait(driver, TIMEOUT).until(
            EC.url_contains("breclient/ui")
        )
        logger.info("Авторизация успешна")
        cookies = driver.get_cookies()
        with open(cookies_file, "wb") as f:
            pickle.dump(cookies, f)
        logger.info("Новые cookies сохранены")
        return True
    except TimeoutException:
        logger.error("Авторизация не удалась, возможно неверные учетные данные")
        logger.error(f"Код страницы: {driver.page_source[:500]}")
        return False

# Создаёт папки для сохранения данных
def create_folders(claim_number, vin):
    # Формируем имя папки на основе VIN, номера дела или текущей даты
    folder_name = f"{claim_number}_{vin}"

    # Создаём пути для папок
    screenshot_dir = os.path.join(SCREENSHOT_DIR, folder_name)
    svg_dir = os.path.join(SVG_DIR, folder_name)
    data_dir = os.path.join(DATA_DIR, folder_name)

    # Создаём папки, если они не существуют
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(svg_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)

    return screenshot_dir, svg_dir, data_dir

# Проверяет, загрузилась ли таблица
def wait_for_table(driver, selector=None):
    selectors_to_check = [selector] if selector else [OPEN_TABLE_SELECTOR, OUTGOING_TABLE_SELECTOR]

    for sel in selectors_to_check:
        try:
            WebDriverWait(driver, TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
            logger.info(f"Таблица с селектором '{sel}' загрузилась")
            return True
        except TimeoutException:
            logger.warning(f"Таблица с селектором '{sel}' не загрузилась")

    logger.error("Ни одна из таблиц не загрузилась")
    return False


# Нажимает на кнопку закрыть при входа в раздел дела, если она есть
def click_cansel_button(driver):
    try:
        confirm_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#confirm > div > div > div.modal-footer > button"))
        )
        confirm_button.click()
        logger.info("Кнопка подтверждения нажата")
    except TimeoutException:
        logger.info("Кнопка подтверждения не найдена")



# сначала переходим в раздел с открытыми заявками, потом переходим в исходящие, если не нашли в открытых
def click_request_type_button(driver, req_type: str):
    """
    Совершает клик по выбранной кнопке типа заявок

    params: req_type - принимает значения "outgoing" или "open"
    """
    try:
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )

        if req_type == "open":
            more_views_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#view-link-worklistgrid_custom_open"))
            )
        elif req_type == "outgoing":
            more_views_link = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#view-link-worklistgrid_custom_sent"))
            )
        more_views_link.click()
        logger.info("Клик по кнопке исходящие")
        return True
    except (TimeoutException, StaleElementReferenceException) as e:
        logger.error(f"Ошибка при клике по кнопке исходящие: {str(e)}")
        return False

# Выполняет поиск в таблице по значению
def search_in_table(driver, search_value, log_msg):
    try:
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        search_input = WebDriverWait(driver, TIMEOUT).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#root\\.quickfilter\\.searchbox"))
        )
        search_input.clear()
        search_input.send_keys(search_value)
        logger.info(f"Введён {log_msg}: {search_value}")
        time.sleep(1)
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ROW_SELECTOR))
        )
        logger.info(f"Найдены строки по {log_msg}")
        return True
    except (TimeoutException, StaleElementReferenceException):
        logger.info(f"Таблица пустая после поиска по {log_msg}")
        return False

# Нажимает на иконку "ещё"
def click_more_icon(driver):
    try:
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        more_icon = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, MORE_ICON_SELECTOR))
        )
        more_icon.click()
        logger.info("Клик по иконке 'ещё'")
        return True
    except (TimeoutException, StaleElementReferenceException) as e:
        logger.error(f"Ошибка при клике по иконке 'ещё': {str(e)}")
        return False

# Открывает задачу
def open_task(driver):
    try:
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        open_task = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#openTask"))
        )
        open_task.click()
        logger.info("Кнопка 'openTask' нажата")
        return True
    except (TimeoutException, StaleElementReferenceException) as e:
        logger.error(f"Ошибка при клике по openTask: {str(e)}")
        return False

# Извлекает VIN и claim_number со страницы
def extract_vin_and_claim_number(driver, current_url):
    base_url = current_url.split('step')[0][:-1]
    configs = [
        {
            'url': current_url,
            'selector': CLAIM_NUMBER_SELECTOR,
            'log_name': 'CLAIM NUMBER',
            'key': 'claim_number'
        },
        {
            'url': base_url + '&step=Osago+Vehicle+Identification',
            'selector': VIN_SELECTOR,
            'log_name': 'VIN',
            'key': 'vin'
        }
    ]

    result = {}
    for config in configs:
        time.sleep(5)
        logger.info(f"Переход на URL для {config['log_name']}: {config['url']}")
        driver.get(config['url'])
        try:
            WebDriverWait(driver, TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            input_element = WebDriverWait(driver, TIMEOUT).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, config['selector']))
            )
            result[config['key']] = input_element.get_attribute("value") or ""
            logger.info(f"Извлечён {config['log_name']}: {result[config['key']]}")

            time.sleep(5)
        except (TimeoutException, StaleElementReferenceException):
            logger.warning(f"Не удалось извлечь {config['log_name']}")
            result[config['key']] = ""

    return result['claim_number'], result['vin']

# Переключается на фрейм и нажимает кнопку подтверждения
def switch_to_frame_and_confirm(driver):
    try:
        WebDriverWait(driver, TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
        )
        WebDriverWait(driver, TIMEOUT).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, IFRAME_ID))
        )
        logger.info(f"Переключено на фрейм: {IFRAME_ID}")
        try:
            modal_div = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.modal"))
            )
            confirm_button = modal_div.find_element(By.CSS_SELECTOR, ".btn.btn-confirm")
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn.btn-confirm"))
            )
            confirm_button.click()
            logger.info("Кнопка подтверждения в фрейме нажата")
            time.sleep(0.5)
        except TimeoutException:
            logger.info("Кнопка подтверждения в фрейме не найдена")
        return True
    except TimeoutException as e:
        logger.error(f"Ошибка при переключении на фрейм {IFRAME_ID}: {str(e)}")
        return False

# Нажимает на breadcrumb
def click_breadcrumb(driver):
    try:
        breadcrumb = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "breadcrumb-navigation-title"))
        )
        breadcrumb.click()
        logger.info("Клик по breadcrumb")
        time.sleep(0.5)
        return True
    except TimeoutException as e:
        logger.error(f"Ошибка при клике по breadcrumb: {str(e)}")
        return False

# Извлекает зоны
def extract_zones(driver):
    zones = []
    try:
        zones_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "tree-navigation-zones-container"))
        )
        zone_containers = zones_container.find_elements(By.CSS_SELECTOR, "div.navigation-tree-zone-container")
        for container in zone_containers:
            zone_id = container.get_attribute("data-value")
            try:
                description_span = container.find_element(By.ID, f"tree-navigation-zone-description-{zone_id}")
                title = description_span.text.strip()
                zones.append({
                    "title": title,
                    "element": description_span,
                    "link": zone_id
                })
            except Exception as e:
                logger.warning(f"Не удалось найти описание для зоны с id {zone_id}: {str(e)}")
        logger.info(f"Извлечено {len(zones)} зон: {[z['title'] for z in zones]}")
    except Exception as e:
        logger.error(f"Ошибка при извлечении зон: {str(e)}")
    return zones

# Функция для проверки имени файла по шаблону zone_YYYYMMDD_HHMMSS_NNNNNN.svg
def is_zone_file(filename: str) -> bool:
    return 'zone' in filename.split('_')

# Функция для разбиения SVG на детали
def split_svg_by_details(svg_file, output_dir, subfolder=None, claim_number="", vin=""):
    """
    Разбивает SVG-файл на отдельные SVG для каждой детали, где каждая деталь соответствует уникальному data-title.
    """
    try:
        tree = ET.parse(svg_file)
        root = tree.getroot()
        # Собираем уникальные data-title без разбиения по запятым
        all_titles = set(elem.attrib['data-title'] for elem in root.iter() if 'data-title' in elem.attrib)

        logger.info("\n\nНайдены следующие уникальные data-title:\n")
        detail_paths = []
        for title in sorted(all_titles):
            logger.info(f"  {title}")

        def has_detail(elem, detail):
            return elem.attrib.get('data-title', '') == detail

        def prune_for_detail(root_element, detail):
            for elem in list(root_element):
                tag = elem.tag.split('}')[-1]
                if tag == 'g' and not has_detail(elem, detail):
                    root_element.remove(elem)
                else:
                    prune_for_detail(elem, detail)

        for detail in all_titles:
            tree = ET.parse(svg_file)
            root = tree.getroot()
            prune_for_detail(root, detail)

            # Очищаем и нормализуем имя файла на основе полного data-title
            safe_detail = re.sub(r'[^\w\s-]', '', detail).strip()  # Удаляем недопустимые символы
            if not safe_detail:
                logger.warning(f"Пропущено пустое или некорректное data-title: {detail!r}")
                continue
            safe_name = translit(safe_detail, 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
            safe_name = re.sub(r'\.+', '', safe_name)  # Удаляем точки

            # Формируем путь с учетом поддиректории
            output_path = os.path.normpath(os.path.join(output_dir, f"{safe_name}.svg"))
            relative_base = f"/static/svgs/{claim_number}_{vin}"
            output_path_relative = f"{relative_base}/{safe_name}.svg".replace("\\", "/")

            # Создаем директорию
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            logger.debug(f"Сохранение SVG: {output_path}")
            tree.write(output_path, encoding="utf-8", xml_declaration=True)
            logger.info(f"✅ Сохранено: {output_path}")
            detail_paths.append({
                "title": detail,
                "svg_path": output_path_relative.replace("\\", "/")  # Нормализуем для JSON
            })

        return detail_paths
    except Exception as e:
        logger.error(f"Ошибка в split_svg_by_details: {str(e)}")
        return []

# Сохраняет SVG с сохранением цветов
def save_svg_sync(driver, element, path, claim_number='', vin=''):
    try:
        if element.tag_name not in ['svg', 'g']:
            logger.warning(f"Элемент {element.tag_name} не является SVG или группой")
            return False, None, []

        has_children = driver.execute_script("""
            return arguments[0].children.length > 0;
        """, element)
        if not has_children and element.tag_name == 'g':
            logger.warning(
                f"Группа {element.get_attribute('data-title') or 'без названия'} не содержит дочерних элементов")
            return False, None, []

        # Извлекаем и применяем стили для сохранения цветов
        driver.execute_script("""
            let element = arguments[0];
            function setInlineStyles(el) {
                let computed = window.getComputedStyle(el);
                if (computed.fill && computed.fill !== 'none') {
                    el.setAttribute('fill', computed.fill);
                }
                if (computed.stroke && computed.stroke !== 'none') {
                    el.setAttribute('stroke', computed.stroke);
                }
                if (computed.strokeWidth && computed.strokeWidth !== '0px') {
                    el.setAttribute('stroke-width', computed.strokeWidth);
                }
                for (let child of el.children) {
                    setInlineStyles(child);
                }
            }
            setInlineStyles(element);
        """, element)

        svg_content = element.get_attribute('outerHTML')

        if element.tag_name == 'g':
            parent_svg = driver.execute_script("""
                let el = arguments[0];
                while (el && el.tagName.toLowerCase() !== 'svg') {
                    el = el.parentElement;
                }
                return el;
            """, element)

            if not parent_svg:
                logger.warning("Не удалось найти родительский SVG для группы")
                return False, None, []

            bounds = driver.execute_script("""
                let element = arguments[0];
                let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                function computeBounds(el) {
                    if (el.tagName === 'path' || el.tagName === 'rect' || el.tagName === 'circle') {
                        let bbox = el.getBBox();
                        if (bbox.width > 0 && bbox.height > 0) {
                            minX = Math.min(minX, bbox.x);
                            minY = Math.min(minY, bbox.y);
                            maxX = Math.max(maxX, bbox.x + bbox.width);
                            maxY = Math.max(maxY, bbox.y + bbox.height);
                        }
                    }
                    for (let child of el.children) {
                        computeBounds(child);
                    }
                }
                computeBounds(element);
                return [minX, minY, maxX - minX, maxY - minY];
            """, element)

            if bounds[2] <= 0 or bounds[3] <= 0 or not all(isinstance(x, (int, float)) for x in bounds):
                logger.warning("Невалидные границы для viewBox, используется запасное значение")
                view_box = '0 0 1000 1000'
            else:
                padding = 10
                view_box = f"{bounds[0] - padding} {bounds[1] - padding} {bounds[2] + 2 * padding} {bounds[3] + 2 * padding}"

            width = '100%'
            height = '100%'
        else:
            view_box = element.get_attribute('viewBox') or '0 0 1000 1000'
            width = element.get_attribute('width') or '100%'
            height = element.get_attribute('height') or '100%'

        # Извлекаем все стили, чтобы сохранить цвета как на сайте
        style_content = driver.execute_script("""
            let styles = '';
            const styleSheets = document.styleSheets;
            for (let sheet of styleSheets) {
                try {
                    for (let rule of sheet.cssRules) {
                        if (rule.selectorText && (
                            rule.selectorText.includes('svg') || 
                            rule.selectorText.includes('path') || 
                            rule.selectorText.includes('rect') || 
                            rule.selectorText.includes('circle') || 
                            rule.selectorText.includes('g') ||
                            rule.selectorText.includes('[fill]') ||
                            rule.selectorText.includes('[stroke]')
                        )) {
                            styles += rule.cssText + '\\n';
                        }
                    }
                } catch (e) {
                    console.warn('Не удалось получить доступ к стилям:', e);
                }
            }
            return styles;
        """)

        svg_full_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="{view_box}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<style>
{style_content}
svg * {{
    fill: inherit;
    stroke: inherit;
    stroke-width: inherit;
}}
</style>
{svg_content}
</svg>"""

        os.makedirs(os.path.dirname(path), exist_ok=True)
        svg_bytes = svg_full_content.encode('utf-8')
        parser = etree.XMLParser(encoding='utf-8')
        try:
            etree.fromstring(svg_bytes, parser)
            with open(path, 'wb') as f:
                f.write(svg_bytes)
        except Exception as e:
            logger.error(f"Ошибка валидации/записи SVG: {e}")
            return False, None, []

        # Проверяем, не находится ли файл в папке pictograms
        if 'pictograms' not in path:
            filename = os.path.basename(path)
            if is_zone_file(filename):
                logger.info(f"Файл {filename} соответствует шаблону, запускаем разбиение")
                detail_paths = split_svg_by_details(path, os.path.dirname(path), claim_number=claim_number, vin=vin)
            else:
                detail_paths = []
        else:
            logger.info(f"SVG сохранён без разбиения для пиктограммы: {path}")
            detail_paths = []

        return True, path, detail_paths
    except Exception as e:
        logger.error(f"Ошибка при сохранении SVG: {e}")
        return False, None, []

# Сохраняет основной скриншот и SVG
def save_main_screenshot_and_svg(driver, screenshot_dir, svg_dir, timestamp, claim_number, vin):
    main_screenshot_path = os.path.join(screenshot_dir, f"main_screenshot.png")
    main_screenshot_relative = f"/static/screenshots/{claim_number}_{vin}/main_screenshot.png"
    main_svg_path = os.path.join(svg_dir, f"main.svg")
    main_svg_relative = f"/static/svgs/{claim_number}_{vin}/main.svg"

    # Проверяем наличие SVG на странице
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.TAG_NAME, "svg"))
        )
        time.sleep(0.5)
        svg = driver.find_element(By.TAG_NAME, "svg")
        os.makedirs(os.path.dirname(main_screenshot_path), exist_ok=True)
        svg.screenshot(main_screenshot_path)
        logger.info(f"Основной скриншот сохранён: {main_screenshot_path}")
        success, _, _ = save_svg_sync(driver, svg, main_svg_path, claim_number=claim_number, vin=vin)
        if not success:
            logger.warning("Не удалось сохранить основной SVG")
        return main_screenshot_relative.replace("\\", "/"), main_svg_relative.replace("\\", "/")
    except Exception as e:
        logger.error(f"Ошибка при сохранении основного скриншота/SVG: {str(e)}")
        return None, None

# Обрабатывает одну зону
def process_zone(driver, zone, screenshot_dir, svg_dir, max_retries=3, claim_number="", vin=""):
    """
    Обрабатывает одну зону, включая сохранение скриншота, SVG и пиктограмм.
    max_retries: максимальное количество повторных попыток при ошибке сессии.
    """
    zone_data = []

    # Проверяем валидность zone
    if not zone.get('title') or not zone.get('link'):
        logger.warning(f"Пропущена некорректная зона: title={zone.get('title')!r}, link={zone.get('link')!r}")
        return zone_data

    logger.debug(f"Обработка зоны: {zone}")

    for attempt in range(max_retries):
        try:
            zone_element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, f"tree-navigation-zone-description-{zone['link']}"))
            )
            zone_element.click()
            logger.info(f"Клик по зоне: {zone['title']}")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            break
        except WebDriverException as e:
            logger.error(f"Ошибка при клике по зоне {zone['title']} (попытка {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"Не удалось кликнуть по зоне {zone['title']} после {max_retries} попыток")
                return zone_data
            time.sleep(1)

    # Формируем безопасное имя для zone['title']
    safe_zone_title = translit(re.sub(r'[^\w\s-]',
                                      '', zone['title']).strip(),
                               'ru', reversed=True).replace(" ", "_").replace("/", "_").lower().replace("'", "")
    safe_zone_title = re.sub(r'\.+', '', safe_zone_title)
    zone_screenshot_path = os.path.join(screenshot_dir, f"zone_{safe_zone_title}.png")
    zone_screenshot_relative = f"/static/screenshots/{claim_number}_{vin}/zone_{safe_zone_title}.png".replace(
        "\\", "/")
    zone_svg_path = os.path.join(svg_dir, f"zone_{safe_zone_title}.svg")
    zone_svg_relative = f"/static/svgs/{claim_number}_{vin}/zone_{safe_zone_title}.svg".replace("\\", "/")

    # Проверяем наличие пиктограмм
    try:
        # Дожидаемся полной загрузки страницы
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState === 'complete'")
        )
        # Находим тег main
        main_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "main"))
        )
        # Дожидаемся div с классом pictograms-grid visible внутри main
        pictograms_grid = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "main div.pictograms-grid.visible"))
        )
        logger.info(f"Зона {zone['title']} содержит пиктограммы")
        # Дожидаемся видимости всех секций пиктограмм
        WebDriverWait(driver, 30).until(
            EC.visibility_of_all_elements_located((
                By.CSS_SELECTOR,
                "main div.pictograms-grid.visible section.pictogram-section"
            ))
        )
        # Дожидаемся, пока все SVG станут видимыми и содержат дочерние элементы
        WebDriverWait(driver, 30).until(
            lambda d: all(
                svg.is_displayed() and
                d.execute_script("return arguments[0].querySelectorAll('path, rect, circle').length", svg) > 0
                for svg in d.find_elements(
                    By.CSS_SELECTOR,
                    "main div.pictograms-grid.visible section.pictogram-section div.navigation-pictogram-svg-container svg"
                )
            )
        )
        # Проверяем стабильность DOM
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("""
                let svgs = document.querySelectorAll('main div.pictograms-grid.visible section.pictogram-section div.navigation-pictogram-svg-container svg');
                if (svgs.length === 0) return false;
                let lastCount = svgs.length;
                setTimeout(() => {
                    lastCount = document.querySelectorAll('main div.pictograms-grid.visible section.pictogram-section div.navigation-pictogram-svg-container svg').length;
                }, 1000);
                return svgs.length === lastCount;
            """)
        )
        time.sleep(2)

        # Кликаем по #breadcrumb-sheet-title, собираем пиктограммы, делаем скриншот, затем второй клик
        try:
            breadcrumb_selector = "#breadcrumb-sheet-title"
            # Первый клик для закрытия меню
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, breadcrumb_selector))
            ).click()
            logger.info(f"Клик по {breadcrumb_selector} для закрытия меню в зоне {zone['title']}")
            time.sleep(1)

            # Делаем скриншот каждой секции и склеиваем в памяти
            os.makedirs(os.path.dirname(zone_screenshot_path), exist_ok=True)
            try:
                # Находим все секции
                sections = WebDriverWait(driver, 10).until(
                    EC.visibility_of_all_elements_located((
                        By.CSS_SELECTOR,
                        "main div.pictograms-grid.visible section.pictogram-section"
                    ))
                )
                logger.debug(f"Найдено {len(sections)} секций для зоны {zone['title']}")

                # Список для хранения изображений в памяти
                images = []

                # Делаем скриншот каждой секции
                for index, section in enumerate(sections):
                    # Прокручиваем к секции
                    driver.execute_script("arguments[0].scrollIntoView(true);", section)
                    time.sleep(0.5)  # Пауза для стабилизации

                    # Получаем размеры секции
                    section_width = driver.execute_script("return arguments[0].scrollWidth", section)
                    section_height = driver.execute_script("return arguments[0].offsetHeight", section)
                    logger.debug(f"Секция {index + 1} для зоны {zone['title']}: {section_width}x{section_height}")

                    # Делаем скриншот в памяти
                    screenshot_png = section.screenshot_as_png
                    img = Image.open(BytesIO(screenshot_png))
                    images.append(img)
                    logger.debug(f"Скриншот секции {index + 1} для зоны {zone['title']} захвачен в памяти")

                # Склеиваем изображения
                max_width = max(img.width for img in images)
                total_height = sum(img.height for img in images)

                # Создаём новое изображение
                final_image = Image.new('RGB', (max_width, total_height))
                y_offset = 0
                for img in images:
                    final_image.paste(img, (0, y_offset))
                    y_offset += img.height

                # Сохраняем итоговый скриншот
                final_image.save(zone_screenshot_path, quality=85, optimize=True)
                logger.info(f"Скриншот всех секций для зоны {zone['title']} сохранён: {zone_screenshot_path}")

                # Закрываем изображения
                for img in images:
                    img.close()

                # Восстанавливаем исходные размеры окна
                try:
                    driver.set_window_size(original_size['width'], original_size['height'])
                except NameError:
                    logger.warning("original_size не определен, пропускаем восстановление размера окна")
                time.sleep(0.5)

            except (TimeoutException, WebDriverException, Exception) as e:
                logger.error(f"Не удалось сделать скриншот секций для зоны {zone['title']}: {str(e)}")
                zone_screenshot_relative = ""  # Устанавливаем пустой путь в случае ошибки
                logger.info(f"Заглушка для зоны {zone['title']}: скриншот не создан")

            # Собираем данные пиктограмм, передаем zone_screenshot_relative
            zone_data = process_pictograms(driver, zone, screenshot_dir, svg_dir, max_retries, zone_screenshot_relative, claim_number=claim_number, vin="")

            # Второй клик для возврата к меню зон
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, breadcrumb_selector))
            ).click()
            logger.info(f"Клик по {breadcrumb_selector} для возврата к меню зон в зоне {zone['title']}")
            # Дожидаемся контейнера зон
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "tree-navigation-zones-container"))
            )
            # Проверяем, что элемент следующей зоны доступен
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, f"tree-navigation-zone-description-{zone['link']}"))
            )
            logger.info(f"Меню зон доступно после обработки {zone['title']}, готов к следующей зоне")
            time.sleep(0.5)

            return zone_data
        except (TimeoutException, WebDriverException) as e:
            logger.error(f"Ошибка при клике по {breadcrumb_selector} или скриншоте для зоны {zone['title']}: {str(e)}")
            # Пытаемся вернуть меню зон
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, breadcrumb_selector))
                ).click()
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "tree-navigation-zones-container"))
                )
                logger.info(f"Восстановлено меню зон для {zone['title']} после ошибки")
            except Exception as ex:
                logger.error(f"Не удалось восстановить меню зон: {str(ex)}")

            return zone_data
    except (TimeoutException, WebDriverException) as e:
        logger.info(f"Зона {zone['title']} не содержит пиктограмм или они не загрузились: {str(e)}")

    # Проверяем наличие SVG
    try:
        sheet_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, f"sheet_{zone['link']}"))
        )
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, f"#sheet_{zone['link']} svg"))
        )
        svg = sheet_div.find_element(By.TAG_NAME, "svg")
        # Проверяем, что SVG содержит дочерние элементы
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return arguments[0].querySelectorAll('path, rect, circle').length", svg) > 0
        )
        time.sleep(2)
        logger.info(f"Найден SVG для зоны {zone['title']}")

        try:
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.TAG_NAME, "svg"))
            )
            logger.debug(f"Сохранение скриншота и SVG для зоны {zone['title']}")
            try:
                # Прокручиваем к SVG
                driver.execute_script("arguments[0].scrollIntoView(true);", svg)
                time.sleep(0.5)  # Пауза для стабилизации
                # Проверяем размеры SVG
                svg_width = driver.execute_script("return arguments[0].scrollWidth", svg)
                svg_height = driver.execute_script("return arguments[0].scrollHeight", svg)
                logger.debug(f"SVG для зоны {zone['title']}: {svg_width}x{svg_height}")
                svg.screenshot(zone_screenshot_path)
                logger.info(f"Скриншот SVG зоны {zone['title']} сохранён: {zone_screenshot_path}")
            except WebDriverException as e:
                logger.warning(f"Не удалось сохранить скриншот SVG для зоны {zone['title']}: {str(e)}")
                os.makedirs(os.path.dirname(zone_screenshot_path), exist_ok=True)
                # Заглушка
                logger.info(f"Заглушка для зоны {zone['title']}: скриншот SVG не создан")
                zone_data.append({
                    "title": zone['title'],
                    "screenshot_path": "",
                    "has_pictograms": False,
                    "graphics_not_available": True,
                    "details": []
                })
                return zone_data

            success, _, detail_paths = save_svg_sync(driver, svg, zone_svg_path, claim_number=claim_number, vin=vin)
            if not success:
                logger.warning(f"Не удалось сохранить SVG для зоны {zone['title']}")
                zone_data.append({
                    "title": zone['title'],
                    "screenshot_path": "",
                    "has_pictograms": False,
                    "graphics_not_available": True,
                    "details": []
                })
                return zone_data

            zone_data.append({
                "title": zone['title'],
                "screenshot_path": zone_screenshot_relative,
                "svg_path": zone_svg_relative,
                "has_pictograms": False,
                "graphics_not_available": False,
                "details": detail_paths
            })
            logger.info(f"Обработано {len(detail_paths)} деталей для зоны {zone['title']}")
        except WebDriverException as e:
            logger.error(f"Ошибка при обработке SVG зоны {zone['title']}: {str(e)}")
            os.makedirs(os.path.dirname(zone_screenshot_path), exist_ok=True)
            # Заглушка
            logger.info(f"Заглушка для зоны {zone['title']}: скриншот не создан")
            zone_data.append({
                "title": zone['title'],
                "screenshot_path": "",
                "has_pictograms": False,
                "graphics_not_available": True,
                "details": []
            })
            return zone_data
    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Ошибка при поиске SVG для зоны {zone['title']}: {str(e)}")
        os.makedirs(os.path.dirname(zone_screenshot_path), exist_ok=True)
        # Заглушка
        logger.info(f"Заглушка для зоны {zone['title']}: скриншот не создан")
        zone_data.append({
            "title": zone['title'],
            "screenshot_path": "",
            "has_pictograms": False,
            "graphics_not_available": True,
            "details": []
        })
        return zone_data

    return zone_data

# Обрабатывает пиктограммы в зоне
def process_pictograms(driver, zone, screenshot_dir, svg_dir, max_retries=2, zone_screenshot_relative="", claim_number="", vin=""):
    """
    Собирает данные о пиктограммах в зоне, сохраняя SVG для каждой работы.
    max_retries: максимальное количество повторных попыток при ошибке сессии.
    zone_screenshot_relative: относительный путь к склеенному скриншоту зоны.
    """
    pictogram_data = []
    try:
        # Дожидаемся полной загрузки страницы
        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState === 'complete'")
        )
        # Находим тег main
        main = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.TAG_NAME, "main"))
        )
        # Находим div с классом pictograms-grid visible
        grid_div = None
        for div in main.find_elements(By.TAG_NAME, "div"):
            if "pictograms-grid" in div.get_attribute("class") and "visible" in div.get_attribute("class"):
                grid_div = div
                break
        if not grid_div:
            logger.error(f"Не найден div с классом pictograms-grid visible в зоне {zone['title']}")
            return pictogram_data
        logger.info(f"Зона {zone['title']} содержит пиктограммы")

        # Собираем секции
        sections = grid_div.find_elements(By.TAG_NAME, "section")
        logger.debug(f"Найдено секций пиктограмм: {len(sections)}")
        for section in sections:
            try:
                # Находим h2 с классом sort-title visible
                h2 = None
                for h in section.find_elements(By.TAG_NAME, "h2"):
                    if "sort-title" in h.get_attribute("class") and "visible" in h.get_attribute("class"):
                        h2 = h
                        break
                if not h2:
                    logger.warning(f"Не найден h2.sort-title.visible в секции зоны {zone['title']}, пропускаем")
                    continue

                # Извлекаем section_name из h2
                section_title_elem = h2
                section_name = section_title_elem.text.strip()
                if not section_name:
                    logger.warning(f"Пустое название секции в зоне {zone['title']}, пропускаем")
                    continue

                # Находим div с id pictograms-grid-holder
                holder = None
                for div in section.find_elements(By.TAG_NAME, "div"):
                    if div.get_attribute("id") == "pictograms-grid-holder":
                        holder = div
                        break
                if not holder:
                    logger.warning(f"Не найден pictograms-grid-holder в секции {section_name}, пропускаем")
                    continue

                # Собираем работы
                works = []
                work_divs = [div for div in holder.find_elements(By.TAG_NAME, "div") if div.get_attribute("data-tooltip")]
                logger.debug(f"Найдено работ в секции '{section_name}': {len(work_divs)}")
                for work_div in work_divs:
                    try:
                        # Собираем work_name1 из data-tooltip
                        work_name1 = work_div.get_attribute("data-tooltip").strip()
                        if not work_name1:
                            logger.warning(f"Пустое data-tooltip в секции {section_name}, пропускаем")
                            continue

                        # Собираем work_name2 из span > span
                        work_name2 = ""
                        try:
                            span = work_div.find_element(By.TAG_NAME, "span")
                            inner_span = span.find_element(By.TAG_NAME, "span")
                            work_name2 = inner_span.text.strip()
                        except Exception:
                            logger.debug(f"Не найден второй span для работы в секции {section_name}")

                        # Находим div с классом navigation-pictogram-svg-container
                        svg_container = None
                        for div in work_div.find_elements(By.TAG_NAME, "div"):
                            if "navigation-pictogram-svg-container" in div.get_attribute("class"):
                                svg_container = div
                                break
                        if not svg_container:
                            logger.warning(f"Не найден navigation-pictogram-svg-container для работы '{work_name1}' в секции {section_name}")
                            continue

                        # Собираем SVG
                        svg = svg_container.find_element(By.TAG_NAME, "svg")
                        WebDriverWait(driver, 5).until(
                            EC.visibility_of(svg)
                        )

                        # Формируем имя файла
                        safe_section_name = translit(re.sub(r'[^\w\s-]', '', section_name).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
                        safe_work_name1 = translit(re.sub(r'[^\w\s-]', '', work_name1).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
                        safe_work_name2 = translit(re.sub(r'[^\w\s-]', '', work_name2).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower() if work_name2 else ""
                        safe_work_name2 = re.sub(r'\.+', '', safe_work_name2)
                        safe_work_name1 = re.sub(r'\.+', '', safe_work_name1)
                        safe_section_name = re.sub(r'\.+', '', safe_section_name)
                        svg_filename = f"{safe_section_name}_{safe_work_name1}" + (f"_{safe_work_name2}" if work_name2 else "") + ".svg"
                        work_svg_path = os.path.join(svg_dir, svg_filename)
                        work_svg_relative = f"/static/svgs/{claim_number}_{vin}/{svg_filename}".replace("\\", "/")

                        # Сохраняем SVG
                        success, saved_path, _ = save_svg_sync(driver, svg, work_svg_path, claim_number=claim_number, vin=vin)
                        if success:
                            logger.info(f"SVG пиктограммы сохранён: {work_svg_path}")
                            works.append({
                                "work_name1": work_name1,
                                "work_name2": work_name2,
                                "svg_path": work_svg_relative
                            })
                        else:
                            logger.warning(f"Не удалось сохранить SVG для работы '{work_name1}' в секции '{section_name}'")
                    except Exception as e:
                        logger.error(f"Ошибка при обработке работы в секции {section_name}: {str(e)}")
                        continue

                if works:
                    pictogram_data.append({
                        "section_name": section_name,
                        "works": works
                    })
            except Exception as e:
                logger.error(f"Ошибка при обработке секции в зоне {zone['title']}: {str(e)}")
                continue

        # Формируем данные зоны
        if pictogram_data:
            zone_entry = {
                "title": zone['title'],
                "screenshot_path": zone_screenshot_relative,  # Устанавливаем путь к склеенному скриншоту
                "svg_path": "",
                "has_pictograms": True,
                "graphics_not_available": False,
                "details": [],
                "pictograms": pictogram_data
            }
            return [zone_entry]
        else:
            logger.info(f"Не найдено пиктограмм для зоны {zone['title']}")

    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Ошибка при обработке пиктограмм для зоны {zone['title']}: {str(e)}")

    return pictogram_data

# Формирует HTML-таблицу зон
def create_zones_table(zone_data):
    table_html = '<div class="zones-table">'
    for zone in zone_data:
        table_html += f'<div class="zone-row"><button class="zone-button" data-zone-title="{zone["title"]}">{zone["title"]}'
        if zone["has_pictograms"]:
            table_html += '<span class="pictogram-icon">🖼️</span>'
        table_html += '</button>'
        if not zone["graphics_not_available"] and zone.get("svg_path"):
            table_html += f'<a href="{zone["svg_path"]}" download class="svg-download" title="Скачать SVG"><span class="download-icon">⬇</span></a>'
        table_html += '</div>'
    if not zone_data:
        table_html += '<p>Зоны не найдены</p>'
    table_html += '</div>'
    logger.info("HTML-таблица зон создана")
    return table_html

# Сохраняет данные в JSON
def save_data_to_json(vin_value, zone_data, main_screenshot_path, main_svg_path, zones_table, all_svgs_zip, data_dir, claim_number):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(data_dir, f"data_{timestamp}.json")

    # Формируем относительные пути с прямыми слэшами
    relative_data_dir = f"/static/data/{claim_number}_{vin_value}"  # Используем прямые слэши
    data = {
        "vin_value": vin_value,
        "zone_data": [
            {
                "title": zone["title"],
                "screenshot_path": zone["screenshot_path"].replace("\\", "/"),  # Заменяем \ на /
                "svg_path": zone["svg_path"].replace("\\", "/") if zone.get("svg_path") else "",
                "has_pictograms": zone["has_pictograms"],
                "graphics_not_available": zone["graphics_not_available"],
                "details": [
                    {
                        "title": detail["title"],
                        "svg_path": detail["svg_path"].replace("\\", "/")  # Заменяем \ на /
                    } for detail in zone["details"]
                ],
                "pictograms": [
                    {
                        "section_name": pictogram["section_name"],
                        "works": [
                            {
                                "work_name1": work["work_name1"],
                                "work_name2": work["work_name2"],
                                "svg_path": work["svg_path"].replace("\\", "/")
                            } for work in pictogram["works"]
                        ]
                    } for pictogram in zone.get("pictograms", [])
                ]
            } for zone in zone_data
        ],
        "main_screenshot_path": main_screenshot_path.replace("\\", "/") if main_screenshot_path else "",
        "main_svg_path": main_svg_path.replace("\\", "/") if main_svg_path else "",
        "zones_table": zones_table,
        "all_svgs_zip": all_svgs_zip.replace("\\", "/") if all_svgs_zip else ""
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Данные сохранены в {json_path}")
    return json_path


def is_table_empty(driver, selector=EMPTY_TABLE_TEXT_SELECTOR):
    try:
        element = driver.find_element(By.CSS_SELECTOR, selector)
        if EMPTY_TABLE_TEXT in element.text:
            logger.info("Таблица пуста: данных нет")
            return True
    except Exception:
        pass  # Элемент не найден — таблица, скорее всего, не пуста
    return False



# проверяем наличие нашей заявки по секциям
def find_claim_data(driver, claim_number=None, vin_number=None):
    section_selector_map = {
        "open": OPEN_TABLE_SELECTOR,
        "outgoing": OUTGOING_TABLE_SELECTOR
    }

    for section in ["open", "outgoing"]:
        if not click_request_type_button(driver, section):
            logger.error(f"Не удалось перейти в раздел {section}")
            return {"error": f"Не удалось перейти в раздел {section}"}

        if not wait_for_table(driver, section_selector_map.get(section)):
            return {"error": f"Таблица не загрузилась в разделе {section}"}

        if is_table_empty(driver):
            logger.info(f"Раздел {section} пуст — переходим дальше")
            continue  # Пробуем следующий раздел

        if claim_number and search_in_table(driver, claim_number, "номеру дела"):
            return {"success": True}
        elif vin_number and search_in_table(driver, vin_number, "VIN"):
            return {"success": True}

        logger.info(f"Данные не найдены в разделе {section}")

    return {"error": "Данные не найдены ни в одном разделе"}





# Основная функция
def search_and_extract(driver, claim_number, vin_number):
    zone_data = []

    # Проверяем загрузку таблицы
    if not wait_for_table(driver):
        return {"error": "Таблица не загрузилась"}

    # Нажимаем кнопку подтверждения
    click_cansel_button(driver)

    # сначала переходим в раздел открытые
    # если заявки нет, то переходим в исходящие
    # Ищем данные по номеру дела или VIN
    result = find_claim_data(driver, claim_number=claim_number, vin_number=vin_number)
    if "error" in result:
        return result

    # Нажимаем на иконку "ещё"
    if not click_more_icon(driver):
        return {"error": "Не удалось открыть меню действий"}

    # Открываем задачу
    if not open_task(driver):
        return {"error": "Не удалось открыть задачу"}

    # Ожидаем загрузку страницы
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
    )
    time.sleep(1)

    # Получаем текущий URL
    current_url = driver.current_url
    logger.info(f"Текущий URL: {current_url}")

    # Извлекаем VIN и claim_number со страницы для надежности
    claim_number, vin_number = extract_vin_and_claim_number(driver, current_url)

    # Создаём папки
    screenshot_dir, svg_dir, data_dir = create_folders(claim_number, vin_number)

    # Переходим на страницу повреждений
    base_url = current_url.split('step')[0][:-1] + '&step=Damage+capturing'
    logger.info(f"Переход на URL повреждений: {base_url}")
    driver.get(base_url)
    WebDriverWait(driver, TIMEOUT).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
    )
    time.sleep(1)

    # Переключаемся на фрейм
    if not switch_to_frame_and_confirm(driver):
        driver.switch_to.default_content()
        return {"error": f"Не удалось переключиться на фрейм {IFRAME_ID}"}

    # Сохраняем основной скриншот и SVG
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    main_screenshot_relative, main_svg_relative = save_main_screenshot_and_svg(driver, screenshot_dir, svg_dir, timestamp, claim_number, vin_number)

    # Нажимаем на breadcrumb
    if not click_breadcrumb(driver):
        driver.switch_to.default_content()
        return {"error": "Не удалось кликнуть по breadcrumb"}

    # Извлекаем зоны
    zones = extract_zones(driver)
    if not zones:
        driver.switch_to.default_content()
        return {"error": "Зоны не найдены"}

    # Обрабатываем каждую зону
    for zone in zones:
        zone_data.extend(process_zone(driver, zone, screenshot_dir, svg_dir, claim_number=claim_number, vin=vin_number))

    # Возвращаемся в основной контент
    driver.switch_to.default_content()

    # Создаём HTML-таблицу
    zones_table = create_zones_table(zone_data)

    # Сохраняем данные в JSON
    json_path = save_data_to_json(vin_number, zone_data, main_screenshot_relative, main_svg_relative, zones_table, "", data_dir, claim_number)

    # Возвращаем результат
    return {
        "success": "Задача открыта",
        "main_screenshot_path": main_screenshot_relative,
        "main_svg_path": main_svg_relative,
        "zones_table": zones_table,
        "zone_data": zone_data,
        "vin_value": vin_number,
        "claim_number": claim_number
    }

async def login_audatex(username: str, password: str, claim_number: str, vin_number: str):
    driver = None
    max_attempts = 10
    error_message = None
    error_count = 0

    for attempt in range(1, max_attempts + 1):
        try:
            if not claim_number and not vin_number:
                logger.error("Ни номер дела, ни VIN не введены")
                return {"error": "Введите хотя бы номер дела или VIN"}

            logger.info(f"Попытка {attempt} из {max_attempts}: Запуск парсинга для claim_number={claim_number}, vin_number={vin_number}")
            kill_chrome_processes()
            driver = init_browser()
            cookies_valid = load_cookies(driver, BASE_URL, COOKIES_FILE)

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.NAME, "username"))
                )
                logger.info("Страница логина найдена")
            except TimeoutException:
                logger.error(f"Попытка {attempt}: Страница логина не найдена. URL: {driver.current_url}")
                if os.path.exists(COOKIES_FILE):
                    try:
                        os.remove(COOKIES_FILE)
                        logger.info("Файл cookies.pkl удалён из-за ошибки страницы")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении cookies.pkl: {e}")
                raise Exception("Не удалось загрузить страницу логина")

            if not cookies_valid:
                if not perform_login(driver, username, password, COOKIES_FILE):
                    raise Exception("Не удалось авторизоваться")

            # Выполняем синхронную функцию search_and_extract в пуле потоков
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: search_and_extract(driver, claim_number, vin_number))

            if "success" in result:
                cookies = driver.get_cookies()
                with open(COOKIES_FILE, "wb") as f:
                    pickle.dump(cookies, f)
                logger.info(f"Попытка {attempt}: Cookies обновлены после успешного выполнения")
                return result

            # Если search_and_extract вернул ошибку, выбрасываем исключение
            raise Exception(result.get("error", "Неизвестная ошибка в search_and_extract"))

        except Exception as e:
            current_error = str(e)
            logger.error(f"Попытка {attempt}: Ошибка: {current_error}")
            logger.error(f"Текущий URL: {driver.current_url if driver else 'Неизвестно'}")
            logger.error(f"Код страницы: {driver.page_source[:500] if driver else 'Неизвестно'}")

            # Закрываем браузер, если он открыт
            if driver:
                try:
                    driver.quit()
                    logger.info(f"Попытка {attempt}: Браузер закрыт")
                except Exception as close_error:
                    logger.error(f"Ошибка при закрытии браузера: {str(close_error)}")
                driver = None

            # Проверяем, совпадает ли ошибка с предыдущей
            if error_message == current_error:
                error_count += 1
            else:
                error_message = current_error
                error_count = 1

            # Если одна и та же ошибка повторилась 10 раз, выбрасываем её
            if error_count >= max_attempts:
                logger.error(f"Ошибка повторилась {max_attempts} раз: {error_message}")
                return {"error": f"Не удалось выполнить парсинг после {max_attempts} попыток: {error_message}"}

            # Если это не последняя попытка, продолжаем
            if attempt < max_attempts:
                logger.info(f"Повторная попытка {attempt + 1} из {max_attempts}")
                time.sleep(1)  # Пауза перед следующей попыткой
                continue

            # Если последняя попытка провалилась, возвращаем текущую ошибку
            logger.error(f"Исчерпаны все {max_attempts} попыток")
            return {"error": f"Не удалось выполнить парсинг: {current_error}"}

        finally:
            # Закрываем браузер в случае любых ошибок, если он ещё открыт
            if driver:
                try:
                    driver.quit()
                    logger.info(f"Попытка {attempt}: Браузер закрыт в finally")
                except Exception as close_error:
                    logger.error(f"Ошибка при закрытии браузера в finally: {str(close_error)}")
                driver = None

    # На случай, если цикл завершится без возврата (хотя это не должно произойти)
    return {"error": f"Не удалось выполнить парсинг после {max_attempts} попыток"}

# Функция для немедленного завершения всех процессов приложения и перезапуска парсера с открытием стартовой страницы
def terminate_all_processes_and_restart(current_url=None):
    """
    Абсолютно приоритетная функция: немедленно завершает все процессы Python, Chrome/Chromedriver,
    а также любые дочерние процессы, после чего запускает новое веб-приложение и открывает главную страницу.
    После завершения текущего процесса, новое приложение будет запущено на порту 8000.
    """

    logger.critical("ПРИНУДИТЕЛЬНОЕ завершение всех процессов приложения и браузера инициировано!")

    # 1. Завершаем все процессы Chrome и Chromedriver
    try:
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] in ['chrome.exe', 'chromedriver.exe', 'chrome', 'chromedriver']:
                try:
                    proc.kill()
                    logger.critical(f"Завершён процесс браузера: {proc.info['name']} (pid={proc.info['pid']})")
                except Exception as e:
                    logger.error(f"Ошибка при завершении процесса {proc.info['name']}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при завершении процессов Chrome/Chromedriver: {e}")

    # 2. Завершаем все дочерние процессы текущего Python-процесса
    try:
        parent = psutil.Process(os.getpid())
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.kill()
                logger.critical(f"Завершён дочерний процесс Python: {child.name()} (pid={child.pid})")
            except Exception as e:
                logger.error(f"Ошибка при завершении дочернего процесса {child.pid}: {e}")
    except Exception as e:
        logger.error(f"Ошибка при завершении дочерних процессов: {e}")

    # 3. Формируем команду для запуска нового веб-приложения на порту 8000
    uvicorn_cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

    # 4. Логируем информацию о перезапуске
    if current_url:
        logger.critical(f"Приложение будет перезапущено. Главная страница будет доступна по адресу: http://localhost:8000{current_url}")
    else:
        logger.critical("Приложение будет перезапущено.")

    # 5. Запускаем новое веб-приложение на порту 8000 уже после завершения текущего процесса
    logger.critical("Текущий процесс Python будет немедленно завершён. Новое приложение будет запущено на порту 8000.")

    try:
        # Используем os.execv для замены текущего процесса на новый uvicorn
        os.execv(sys.executable, uvicorn_cmd)
    except Exception as e:
        logger.error(f"Ошибка при запуске нового веб-приложения через execv: {e}")
        # Если execv не сработал, пробуем через Popen и завершаем процесс
        try:
            subprocess.Popen(uvicorn_cmd)
            logger.critical("Новое веб-приложение запущено на порту 8000 через Popen.")
        except Exception as e2:
            logger.error(f"Ошибка при запуске веб-приложения через Popen: {e2}")
        os._exit(0)
