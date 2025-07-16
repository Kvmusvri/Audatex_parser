# Функции для работы с авторизацией
import asyncio
import logging
import pickle
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .constants import TIMEOUT, COOKIES_FILE
from .browser import kill_chrome_processes, init_browser

logger = logging.getLogger(__name__)


def check_if_authorized(driver):
    """
    Проверяет, авторизован ли пользователь на текущей странице.
    
    Returns:
        True если авторизован, False если нужна авторизация
    """
    try:
        # Проверяем, есть ли поле для логина (если есть - не авторизованы)
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        logger.info("Найдено поле логина - требуется авторизация")
        return False
    except TimeoutException:
        # Поля логина нет - проверяем, что мы в системе
        try:
            # Ищем характерные элементы авторизованной зоны
            WebDriverWait(driver, 3).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#BREForm")),
                    EC.url_contains("breclient/ui"),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".gdc-contentBlock-body"))
                )
            )
            logger.info("Пользователь уже авторизован")
            return True
        except TimeoutException:
            logger.warning("Не удалось определить статус авторизации")
            return False


def load_cookies(driver, url, cookies_file):
    """
    Загружает cookies и проверяет валидность авторизации.
    
    Returns:
        True если авторизация валидна, False если нужно логиниться
    """
    if not os.path.exists(cookies_file):
        logger.info("Файл cookies не найден, требуется авторизация")
        driver.get(url)
        return False
    
    try:
        driver.get(url)
        with open(cookies_file, "rb") as f:
            cookies = pickle.load(f)
            for cookie in cookies:
                try:
                    driver.add_cookie(cookie)
                except Exception as e:
                    logger.warning(f"Не удалось добавить cookie: {e}")
        
        logger.info("Cookies загружены, проверяем авторизацию...")
        driver.refresh()
        time.sleep(2)  # Даем время для загрузки страницы
        
        # Проверяем статус авторизации
        if check_if_authorized(driver):
            logger.info("Cookies действительны - авторизация не требуется")
            return True
        else:
            logger.info("Cookies недействительны или истекли - требуется авторизация")
            return False
            
    except FileNotFoundError:
        logger.info("Файл cookies не найден, требуется авторизация")
        driver.get(url)
        return False
    except Exception as e:
        logger.error(f"Ошибка при загрузке cookies: {e}")
        driver.get(url)
        return False


def perform_login(driver, username, password, cookies_file):
    """
    Выполняет авторизацию с сохранением cookies.
    """
    try:
        # Убеждаемся что мы на странице логина
        if not check_if_authorized(driver):
            logger.info("Начинаем процедуру авторизации")
        else:
            logger.info("Пользователь уже авторизован, пропускаем логин")
            return True

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        logger.info("Поле username найдено")
    except TimeoutException:
        logger.error(f"Страница логина не загрузилась. URL: {driver.current_url}")
        logger.error(f"Код страницы: {driver.page_source[:500]}")
        return False

    # Проверяем наличие CAPTCHA
    captcha = driver.find_elements(By.CSS_SELECTOR, "iframe[src*='captcha']")
    if captcha:
        logger.error("Обнаружена CAPTCHA - требуется ручное вмешательство")
        return False

    # Вводим данные для авторизации
    try:
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
        
        submit_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit']"))
        )
        submit_button.click()
        logger.info("Кнопка submit нажата")
        
        # Ждем результата авторизации
        time.sleep(3)
        
        # Проверяем успешность авторизации
        try:
            WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.url_contains("breclient/ui"),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#BREForm")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".gdc-contentBlock-body"))
                )
            )
            logger.info("Авторизация успешна")
            
            # Сохраняем cookies после успешной авторизации
            cookies = driver.get_cookies()
            with open(cookies_file, "wb") as f:
                pickle.dump(cookies, f)
            logger.info("Новые cookies сохранены")
            return True
            
        except TimeoutException:
            logger.error("Авторизация не удалась - возможно неверные учетные данные")
            logger.error(f"Текущий URL: {driver.current_url}")
            logger.error(f"Код страницы: {driver.page_source[:500]}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка во время авторизации: {e}")
        return False

 