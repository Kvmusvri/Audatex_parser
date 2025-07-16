# Функции для работы с браузером
import psutil
import logging
import subprocess
import re
import platform
import os
import requests
import zipfile
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


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