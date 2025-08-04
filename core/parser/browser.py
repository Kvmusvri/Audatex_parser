"""
Управление браузером Chrome и WebDriver

Основные функции:
    * kill_chrome_processes: Завершает все процессы Chrome и ChromeDriver
    * get_chromedriver_version: Получает версию установленного ChromeDriver
    * init_browser: Инициализирует браузер Chrome с настройками для обхода бот-детекта
"""
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
    """
    Завершает все процессы Chrome и ChromeDriver.
    
    Returns:
        None
    """
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] in ['chrome.exe', 'chromedriver.exe']:
            try:
                proc.kill()
                logger.info(f"Завершен процесс: {proc.info['name']}")
            except Exception as e:
                logger.error(f"Ошибка при завершении процесса {proc.info['name']}: {e}")

def get_chromedriver_version():
    """
    Получает версию установленного ChromeDriver.
    
    Returns:
        str - версия ChromeDriver или "неизвестно"
    """
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
    """
    Инициализирует браузер Chrome с настройками для обхода бот-детекта.
    
    Returns:
        uc.Chrome - экземпляр браузера
    """
    try:
        system = platform.system()
        print(f"ПЛАТФОРМА - {system}")

        options = uc.ChromeOptions()
        
        # Современные настройки для обхода бот-детекта
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-images")
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # Расширенные настройки для маскировки headless режима
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-field-trial-config')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--disable-hang-monitor')
        options.add_argument('--disable-prompt-on-repost')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-component-extensions-with-background-pages')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--hide-scrollbars')
        options.add_argument('--mute-audio')
        options.add_argument('--no-first-run')
        options.add_argument('--safebrowsing-disable-auto-update')
        options.add_argument('--disable-background-networking')
        options.add_argument('--metrics-recording-only')
        options.add_argument('--no-default-browser-check')
        options.add_argument('--no-pings')
        options.add_argument('--password-store=basic')
        options.add_argument('--use-mock-keychain')
        
        # Дополнительные настройки для обхода детекции
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-automation')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-setuid-sandbox')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-browser-side-navigation')
        options.add_argument('--disable-site-isolation-trials')
        options.add_argument('--disable-features=TranslateUI')
        options.add_argument('--disable-ipc-flooding-protection')
        options.add_argument('--disable-background-timer-throttling')
        options.add_argument('--disable-backgrounding-occluded-windows')
        options.add_argument('--disable-renderer-backgrounding')
        options.add_argument('--disable-field-trial-config')
        options.add_argument('--disable-hang-monitor')
        options.add_argument('--disable-prompt-on-repost')
        options.add_argument('--disable-client-side-phishing-detection')
        options.add_argument('--disable-component-extensions-with-background-pages')
        options.add_argument('--disable-default-apps')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-sync')
        options.add_argument('--disable-translate')
        options.add_argument('--hide-scrollbars')
        options.add_argument('--mute-audio')
        options.add_argument('--no-first-run')
        options.add_argument('--safebrowsing-disable-auto-update')
        options.add_argument('--disable-background-networking')
        options.add_argument('--metrics-recording-only')
        options.add_argument('--no-default-browser-check')
        options.add_argument('--no-pings')
        options.add_argument('--password-store=basic')
        options.add_argument('--use-mock-keychain')
        
        # Настройки окна для headless режима
        options.add_argument('--window-size=1920,1080')
        
        # Современный User-Agent для разных платформ
        if system == 'Windows':
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.169 Safari/537.36"
        else:
            user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.7204.169 Safari/537.36"
        
        options.add_argument(f'--user-agent={user_agent}')
        
        # Дополнительные настройки для обхода детекции
        options.add_argument('--disable-blink-features=AutomationControlled')

        # Определяем пути для ChromeDriver в зависимости от платформы
        base_tmp_dir = "tmp" if system == "Windows" else "/tmp"
        if system == "Windows":
            driver_url = "https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.169/win64/chromedriver-win64.zip"
            driver_zip_path = os.path.join(base_tmp_dir, "chromedriver-win64.zip")
            driver_dir = os.path.join(base_tmp_dir, "chromedriver-win64")
            driver_path = os.path.join(driver_dir, "chromedriver-win64", "chromedriver.exe")
        else:
            driver_url = "https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.169/linux64/chromedriver-linux64.zip"
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

        driver = uc.Chrome(driver_executable_path=driver_path, options=options, use_subprocess=True, headless=True)
        
        # Дополнительные настройки для маскировки headless режима
        try:
            # Применяем расширенную маскировку из stealth модуля
            from .stealth import apply_advanced_stealth_masking
            apply_advanced_stealth_masking(driver)
            
            logger.info("✅ Расширенные настройки маскировки headless режима применены")
            
        except Exception as e:
            logger.debug(f"⚠️ Ошибка при применении расширенных настроек маскировки: {e}")
        
        logger.info(f"Используется ChromeDriver: {driver_path}")
        return driver
    except Exception as e:
        logger.error(f"Ошибка при инициализации браузера: {str(e)}")
        raise 