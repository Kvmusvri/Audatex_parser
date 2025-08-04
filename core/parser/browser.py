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
        
        # Дополнительные настройки для обхода детекции
        options.add_argument('--disable-blink-features=AutomationControlled')
        
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

        driver = uc.Chrome(driver_executable_path=driver_path, options=options, use_subprocess=True)
        
        # Дополнительные настройки для маскировки headless режима
        try:
            # Применяем расширенную маскировку из stealth модуля
            from .stealth import apply_advanced_stealth_masking
            apply_advanced_stealth_masking(driver)
            
            # Применяем дополнительную маскировку после инициализации
            apply_enhanced_stealth_masking(driver)
            
            logger.info("✅ Расширенные настройки маскировки headless режима применены")
            
        except Exception as e:
            logger.debug(f"⚠️ Ошибка при применении расширенных настроек маскировки: {e}")
        
        logger.info(f"Используется ChromeDriver: {driver_path}")
        return driver
    except Exception as e:
        logger.error(f"Ошибка при инициализации браузера: {str(e)}")
        raise


def apply_enhanced_stealth_masking(driver):
    """
    Применяет дополнительную маскировку для обхода детекта
    """
    try:
        driver.execute_script("""
            // Дополнительная маскировка для обхода детекта
            (function() {
                // Маскируем webdriver
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                    configurable: true
                });
                
                // Маскируем chrome runtime
                if (window.chrome) {
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                }
                
                // Маскируем permissions
                const originalPermissions = navigator.permissions;
                navigator.permissions = {
                    ...originalPermissions,
                    query: (parameters) => {
                        if (parameters.name === 'notifications') {
                            return Promise.resolve({ state: 'granted' });
                        }
                        return originalPermissions.query(parameters);
                    }
                };
                
                // Маскируем plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                    configurable: true
                });
                
                // Маскируем languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                    configurable: true
                });
                
                // Маскируем connection
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10,
                        saveData: false,
                    }),
                    configurable: true
                });
                
                // Маскируем hardwareConcurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8,
                    configurable: true
                });
                
                // Маскируем deviceMemory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,
                    configurable: true
                });
                
                // Маскируем maxTouchPoints
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 0,
                    configurable: true
                });
                
                // Маскируем vendor
                Object.defineProperty(navigator, 'vendor', {
                    get: () => 'Google Inc.',
                    configurable: true
                });
                
                // Маскируем platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32',
                    configurable: true
                });
                
                // Удаляем признаки автоматизации
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                
                // Маскируем screen свойства
                Object.defineProperty(screen, 'width', { get: () => 1920 });
                Object.defineProperty(screen, 'height', { get: () => 1080 });
                Object.defineProperty(screen, 'availWidth', { get: () => 1920 });
                Object.defineProperty(screen, 'availHeight', { get: () => 1040 });
                Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
                Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
                
                // Маскируем window свойства
                Object.defineProperty(window, 'outerWidth', { get: () => 1920 });
                Object.defineProperty(window, 'outerHeight', { get: () => 1080 });
                Object.defineProperty(window, 'innerWidth', { get: () => 1920 });
                Object.defineProperty(window, 'innerHeight', { get: () => 937 });
                
                // Маскируем devicePixelRatio
                Object.defineProperty(window, 'devicePixelRatio', { get: () => 1 });
                
                // Маскируем WebGL
                try {
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        if (parameter === 37445) {
                            return 'Intel Inc.';
                        }
                        if (parameter === 37446) {
                            return 'Intel(R) Iris(TM) Graphics 6100';
                        }
                        return getParameter.call(this, parameter);
                    };
                } catch (e) {
                    // Игнорируем ошибки WebGL
                }
                
                // Маскируем Canvas fingerprinting
                try {
                    const originalGetContext = HTMLCanvasElement.prototype.getContext;
                    HTMLCanvasElement.prototype.getContext = function(type, ...args) {
                        const context = originalGetContext.call(this, type, ...args);
                        if (type === '2d') {
                            const originalFillText = context.fillText;
                            context.fillText = function(...args) {
                                return originalFillText.apply(this, args);
                            };
                        }
                        return context;
                    };
                } catch (e) {
                    // Игнорируем ошибки Canvas
                }
                
                // Маскируем Audio fingerprinting
                try {
                    const originalGetChannelData = AudioBuffer.prototype.getChannelData;
                    AudioBuffer.prototype.getChannelData = function(channel) {
                        const data = originalGetChannelData.call(this, channel);
                        // Добавляем небольшие изменения для уникальности
                        for (let i = 0; i < data.length; i += 100) {
                            data[i] += Math.random() * 0.0001;
                        }
                        return data;
                    };
                } catch (e) {
                    // Игнорируем ошибки Audio
                }
                
                // Маскируем userAgent
                try {
                    const originalUserAgent = navigator.userAgent;
                    Object.defineProperty(navigator, 'userAgent', {
                        get: () => originalUserAgent.replace('HeadlessChrome', 'Chrome'),
                    });
                } catch (e) {
                    // Свойство уже определено, пропускаем
                }
                
                // Добавляем случайные задержки для имитации человеческого поведения
                const originalSetTimeout = window.setTimeout;
                window.setTimeout = function(fn, delay, ...args) {
                    if (delay < 100) {
                        delay += Math.random() * 50;
                    }
                    return originalSetTimeout.call(this, fn, delay, ...args);
                };
                
                // Маскируем performance API
                try {
                    const originalGetEntries = Performance.prototype.getEntries;
                    Performance.prototype.getEntries = function() {
                        const entries = originalGetEntries.call(this);
                        // Добавляем случайные вариации
                        return entries.map(entry => {
                            if (entry.duration) {
                                entry.duration += Math.random() * 0.1;
                            }
                            return entry;
                        });
                    };
                } catch (e) {
                    // Игнорируем ошибки Performance
                }
                
            })();
        """)
        
        logger.debug("✅ Дополнительная маскировка применена")
        
    except Exception as e:
        logger.debug(f"⚠️ Ошибка при применении дополнительной маскировки: {e}") 