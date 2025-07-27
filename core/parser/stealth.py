# Модуль для stealth-методов обхода детекции бота
# Основан на техниках SeleniumBase UC Mode

import logging
import time
import random
from typing import Optional
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)


def apply_headless_masking(driver: WebDriver):
    """
    Применяет дополнительные настройки для маскировки headless режима
    """
    try:
        driver.execute_script("""
            // Маскируем headless режим
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Маскируем chrome
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en'],
            });
            
            // Маскируем permissions
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' }),
                }),
            });
            
            // Маскируем plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Маскируем connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                }),
            });
            
            // Маскируем hardwareConcurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
            });
            
            // Маскируем deviceMemory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
            });
            
            // Удаляем признаки автоматизации
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Маскируем screen
            Object.defineProperty(screen, 'width', {
                get: () => 1920,
            });
            Object.defineProperty(screen, 'height', {
                get: () => 1080,
            });
            Object.defineProperty(screen, 'availWidth', {
                get: () => 1920,
            });
            Object.defineProperty(screen, 'availHeight', {
                get: () => 1040,
            });
            
            // Маскируем window
            Object.defineProperty(window, 'outerWidth', {
                get: () => 1920,
            });
            Object.defineProperty(window, 'outerHeight', {
                get: () => 1080,
            });
            Object.defineProperty(window, 'innerWidth', {
                get: () => 1920,
            });
            Object.defineProperty(window, 'innerHeight', {
                get: () => 937,
            });
        """)
        
        logger.debug("✅ Дополнительная маскировка headless режима применена")
        
    except Exception as e:
        logger.warning(f"⚠️ Ошибка при применении маскировки headless: {e}")


def stealth_open_url(driver: WebDriver, url: str, reconnect_time: Optional[float] = None) -> bool:
    """
    Скрытное открытие URL с методами обхода детекции
    """
    try:
        logger.info(f"🔒 Скрытное открытие URL: {url}")
        
        # Применяем расширенную маскировку для headless режима
        apply_headless_masking(driver)
        
        # Открываем URL
        driver.get(url)
        
        # Ждем загрузки DOM модели
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState === 'complete'")
        )
        
        # Человеческая задержка только если указана
        if reconnect_time:
            time.sleep(reconnect_time)
        
        logger.info("✅ URL успешно открыт скрытно")
        return True
        
    except TimeoutException:
        logger.error(f"❌ Страница не загрузилась за 10 секунд: {url}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном открытии URL: {e}")
        return False


def stealth_click(driver: WebDriver, selector: str, use_actions: bool = True) -> bool:
    """
    Скрытный клик с обходом детекции
    """
    try:
        logger.info(f"🔒 Скрытный клик по селектору: {selector}")
        
        # Ждем элемент с WebDriverWait без хардкод таймаута
        element = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        
        # Добавляем человеческое поведение
        add_stealth_behavior(driver)
        
        if use_actions:
            # Используем ActionChains для более человечного клика
            from selenium.webdriver.common.action_chains import ActionChains
            actions = ActionChains(driver)
            actions.move_to_element(element)
            time.sleep(random.uniform(0.1, 0.3))
            actions.click()
            actions.perform()
        else:
            # Обычный клик с задержкой
            time.sleep(random.uniform(0.1, 0.2))
            element.click()
        
        logger.info("✅ Скрытный клик выполнен")
        return True
        
    except TimeoutException:
        logger.error(f"❌ Элемент не найден для клика: {selector}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном клике: {e}")
        return False


def add_stealth_behavior(driver: WebDriver):
    """
    Добавляет stealth-поведение для обхода детекции
    """
    try:
        # Случайные движения мыши в пределах окна
        try:
            window_size = driver.get_window_size()
            max_x = window_size['width'] - 100
            max_y = window_size['height'] - 100
            
            for _ in range(random.randint(2, 4)):
                x = random.randint(50, max(100, max_x))
                y = random.randint(50, max(100, max_y))
                driver.execute_script(f"window.scrollTo({x}, {y});")
                time.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            logger.debug(f"Ошибка движения мыши в stealth: {e}")
        
        # Случайный скролл
        scroll_amount = random.randint(-200, 200)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.2, 0.5))
        
        logger.debug("Добавлено stealth-поведение")
        
    except Exception as e:
        logger.warning(f"Ошибка при добавлении stealth-поведения: {e}")


def check_stealth_detection(driver: WebDriver) -> bool:
    """
    Проверяет признаки детекции stealth-методов
    """
    try:
        page_source = driver.page_source.lower()
        detection_indicators = [
            "gethandleverifier",
            "white screen",
            "bot detected",
            "automation detected",
            "captcha",
            "cloudflare",
            "access denied",
            "blocked"
        ]
        
        for indicator in detection_indicators:
            if indicator in page_source:
                logger.warning(f"🚨 Обнаружен индикатор детекции: {indicator}")
                return True
        return False
        
    except Exception as e:
        logger.error(f"Ошибка при проверке stealth-детекции: {e}")
        return False


def handle_stealth_detection(driver: WebDriver, url: Optional[str] = None) -> bool:
    """
    Обрабатывает детекцию stealth-методов с расширенным человеческим поведением
    """
    logger.warning("🚨 Обрабатываем stealth-детекцию...")
    
    try:
        # Добавляем расширенное человеческое поведение
        from .actions import add_extended_human_behavior
        add_extended_human_behavior(driver, total_delay=60.0)
        
        # Пробуем обновить страницу
        if url:
            driver.get(url)
        else:
            driver.refresh()
        
        # Ждем загрузки DOM модели
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState === 'complete'")
        )
        
        # Применяем маскировку headless режима
        apply_headless_masking(driver)
        add_stealth_behavior(driver)
        
        # Проверяем снова
        if check_stealth_detection(driver):
            logger.error("🚨 Детекция сохраняется после обработки")
            return False
        
        logger.info("✅ Stealth-детекция обработана")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка при обработке stealth-детекции: {e}")
        return False


def stealth_type(driver: WebDriver, selector: str, text: str) -> bool:
    """
    Скрытный ввод текста с человеческими паузами
    """
    try:
        logger.info(f"🔒 Скрытный ввод в селектор: {selector}")
        
        # Ждем элемент с WebDriverWait без хардкод таймаута
        element = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        
        # Очищаем поле
        element.clear()
        time.sleep(random.uniform(0.3, 0.7))
        
        # Вводим текст посимвольно с человеческими паузами
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))
        
        logger.info("✅ Скрытный ввод выполнен")
        return True
        
    except TimeoutException:
        logger.error(f"❌ Элемент не найден для ввода: {selector}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном вводе: {e}")
        return False


def stealth_wait_for_element(driver: WebDriver, selector: str) -> bool:
    """
    Скрытное ожидание элемента с проверкой детекции
    """
    try:
        logger.info(f"🔒 Скрытное ожидание элемента: {selector}")
        
        # Применяем маскировку headless режима
        apply_headless_masking(driver)
        
        # Ждем DOM модель с WebDriverWait без хардкод таймаута
        try:
            # Используем короткий таймаут для быстрой проверки
            element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            
            # Дополнительно проверяем, что элемент видим
            if element.is_displayed():
                logger.info("✅ Элемент найден скрытно")
                return True
            else:
                logger.warning("⚠️ Элемент найден, но не видим")
                return False
                
        except TimeoutException:
            logger.error(f"❌ Элемент не найден: {selector}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном ожидании элемента: {e}")
        return False 