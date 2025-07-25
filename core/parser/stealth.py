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


def stealth_open_url(driver: WebDriver, url: str, reconnect_time: Optional[float] = None) -> bool:
    """
    Скрытное открытие URL с методами обхода детекции
    """
    try:
        logger.info(f"🔒 Скрытное открытие URL: {url}")
        
        # Добавляем случайные заголовки
        driver.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)
        
        # Устанавливаем случайный user-agent
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
        
        driver.execute_script(f"""
            Object.defineProperty(navigator, 'userAgent', {{
                get: () => '{random.choice(user_agents)}',
            }});
        """)
        
        # Открываем URL
        driver.get(url)
        
        # Человеческая задержка
        if reconnect_time:
            time.sleep(reconnect_time)
        else:
            time.sleep(random.uniform(3.0, 6.0))
        
        # Проверяем на детекцию
        if check_stealth_detection(driver):
            logger.warning("🚨 Обнаружена детекция при открытии URL")
            return handle_stealth_detection(driver, url)
        
        logger.info("✅ URL успешно открыт скрытно")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном открытии URL: {e}")
        return False


def stealth_click(driver: WebDriver, selector: str, use_actions: bool = True) -> bool:
    """
    Скрытный клик с обходом детекции
    """
    try:
        logger.info(f"🔒 Скрытный клик по селектору: {selector}")
        
        # Ждем элемент
        element = WebDriverWait(driver, 10).until(
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
        
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном клике: {e}")
        return False


def add_stealth_behavior(driver: WebDriver):
    """
    Добавляет stealth-поведение для обхода детекции
    """
    try:
        # Случайные движения мыши
        for _ in range(random.randint(2, 4)):
            x = random.randint(50, 700)
            y = random.randint(50, 500)
            driver.execute_script(f"window.scrollTo({x}, {y});")
            time.sleep(random.uniform(0.1, 0.3))
        
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
    Обрабатывает детекцию stealth-методов
    """
    logger.warning("🚨 Обрабатываем stealth-детекцию...")
    
    try:
        # Длительная пауза
        time.sleep(random.uniform(8.0, 15.0))
        
        # Добавляем stealth-поведение
        add_stealth_behavior(driver)
        
        # Пробуем обновить страницу
        if url:
            driver.get(url)
        else:
            driver.refresh()
        
        time.sleep(random.uniform(4.0, 7.0))
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
        
        # Ждем элемент
        element = WebDriverWait(driver, 10).until(
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
        
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном вводе: {e}")
        return False


def stealth_wait_for_element(driver: WebDriver, selector: str, timeout: int = 15) -> bool:
    """
    Скрытное ожидание элемента с проверкой детекции
    """
    try:
        logger.info(f"🔒 Скрытное ожидание элемента: {selector}")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Проверяем на детекцию
                if check_stealth_detection(driver):
                    logger.warning("🚨 Обнаружена детекция при ожидании элемента")
                    if not handle_stealth_detection(driver):
                        return False
                
                # Проверяем элемент
                element = driver.find_element(By.CSS_SELECTOR, selector)
                if element.is_displayed():
                    logger.info("✅ Элемент найден скрытно")
                    return True
                    
            except Exception:
                pass
            
            time.sleep(random.uniform(0.5, 1.0))
        
        logger.error(f"❌ Элемент не найден за {timeout} секунд")
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном ожидании элемента: {e}")
        return False 