# Улучшенные функции для действий и взаимодействий с элементами интерфейса
# Оптимизированы для скорости с сохранением надежности

import logging
import time
import functools
from typing import Optional, Callable, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import (
    TimeoutException, 
    StaleElementReferenceException, 
    ElementNotInteractableException,
    NoSuchElementException,
    ElementClickInterceptedException
)
from .constants import (
    TIMEOUT, OPEN_TABLE_SELECTOR, OUTGOING_TABLE_SELECTOR, ROW_SELECTOR, 
    MORE_ICON_SELECTOR, IFRAME_ID, EMPTY_TABLE_TEXT_SELECTOR, EMPTY_TABLE_TEXT
)

logger = logging.getLogger(__name__)


# Декоратор для повторных попыток - оптимизированный
def retry_on_failure(max_attempts: int = 2, delay: float = 0.5):
    """
    Быстрый декоратор для повторных попыток.
    
    Args:
        max_attempts: Максимальное количество попыток (по умолчанию 2)
        delay: Задержка между попытками (по умолчанию 0.5 сек)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(f"Функция {func.__name__} успешна с попытки {attempt}")
                    return result
                except (StaleElementReferenceException, ElementNotInteractableException, 
                        ElementClickInterceptedException, NoSuchElementException, TimeoutException) as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(f"Попытка {attempt} неудачна, повторяем через {delay}с: {str(e)}")
                        time.sleep(delay)
                    else:
                        logger.error(f"Все {max_attempts} попыток функции {func.__name__} исчерпаны")
                        
            raise last_exception
        return wrapper
    return decorator


@retry_on_failure(max_attempts=2, delay=0.5)
def wait_for_table(driver: WebDriver, selector: Optional[str] = None) -> bool:
    """
    Быстрое ожидание загрузки таблицы.
    """
    selectors_to_check = [selector] if selector else [OPEN_TABLE_SELECTOR, OUTGOING_TABLE_SELECTOR]
    timeout = 8  # Уменьшен с TIMEOUT

    for sel in selectors_to_check:
        try:
            WebDriverWait(driver, timeout, poll_frequency=0.3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
            logger.info(f"Таблица '{sel}' загружена")
            return True
        except TimeoutException:
            continue

    logger.error("Таблицы не загрузились")
    return False


@retry_on_failure(max_attempts=2, delay=0.5)
def click_cansel_button(driver: WebDriver) -> bool:
    """
    Быстрое нажатие кнопки отмены.
    """
    selector = "#confirm > div > div > div.modal-footer > button"
    
    try:
        button = WebDriverWait(driver, 5, poll_frequency=0.3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        
        try:
            button.click()
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", button)
        
        logger.info("Кнопка подтверждения нажата")
        return True
        
    except TimeoutException:
        logger.info("Кнопка подтверждения не найдена")
        return True  # Это нормально
    except Exception as e:
        logger.error(f"Ошибка клика кнопки подтверждения: {e}")
        return False


@retry_on_failure(max_attempts=2, delay=0.5)
def click_request_type_button(driver: WebDriver, req_type: str) -> bool:
    """
    Быстрое переключение между типами заявок.
    """
    try:
        if req_type == "open":
            more_views_link = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#view-link-worklistgrid_custom_open"))
            )
        elif req_type == "outgoing":
            more_views_link = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#view-link-worklistgrid_custom_sent"))
            )
        else:
            logger.error(f"Неизвестный тип заявки: {req_type}")
            return False
            
        more_views_link.click()
        logger.info(f"Клик по кнопке {req_type}")
        return True
        
    except TimeoutException as e:
        logger.error(f"Ошибка клика по кнопке {req_type}: {str(e)}")
        return False


@retry_on_failure(max_attempts=2, delay=0.5)
def search_in_table(driver: WebDriver, search_value: str, search_type: str) -> bool:
    """
    Быстрый поиск в таблице.
    """
    try:
        search_input = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#root\\.quickfilter\\.searchbox"))
        )
        search_input.clear()
        search_input.send_keys(search_value)
        logger.info(f"Введён {search_type}: {search_value}")
        time.sleep(0.8)  # Уменьшено с 1 сек
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ROW_SELECTOR))
        )
        logger.info(f"Найдены строки по {search_type}")
        return True
        
    except TimeoutException:
        logger.info(f"Таблица пустая после поиска по {search_type}")
        return False


@retry_on_failure(max_attempts=2, delay=0.5)
def click_more_icon(driver: WebDriver) -> bool:
    """
    Быстрое нажатие иконки "Еще". Пробует селекторы для исходящих и открытых дел.
    """
    # Селекторы для разных типов таблиц
    selectors = [
        MORE_ICON_SELECTOR,  # Исходящие дела
        MORE_ICON_SELECTOR.replace("worklistgrid_custom_sent", "worklistgrid_custom_open")  # Открытые дела
    ]
    
    for i, selector in enumerate(selectors):
        try:
            more_icon = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            more_icon.click()
            table_type = "исходящих" if i == 0 else "открытых"
            logger.info(f"Клик по иконке 'ещё' в таблице {table_type} дел")
            return True
        except TimeoutException:
            continue
    
    logger.error("Ошибка клика по иконке 'ещё': не найдена ни в одной таблице")
    return False


@retry_on_failure(max_attempts=2, delay=0.5)
def open_task(driver: WebDriver) -> bool:
    """
    Быстрое открытие задачи.
    """
    try:
        open_task = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#openTask"))
        )
        open_task.click()
        logger.info("Кнопка 'openTask' нажата")
        return True
    except TimeoutException as e:
        logger.error(f"Ошибка клика по openTask: {str(e)}")
        return False


@retry_on_failure(max_attempts=3, delay=1.0)
def switch_to_frame_and_confirm(driver: WebDriver) -> bool:
    """
    Надёжное переключение в iframe с дополнительными проверками.
    """
    try:
        # Ждём полной загрузки страницы
        WebDriverWait(driver, 15).until(
            lambda d: d.execute_script("return document.readyState === 'complete'")
        )
        logger.info("Страница полностью загружена")
        
        # Дополнительная пауза для загрузки динамического контента
        time.sleep(2)
        
        # Проверяем наличие iframe в DOM
        iframe_exists = driver.execute_script(f"""
            return document.getElementById('{IFRAME_ID}') !== null;
        """)
        
        if not iframe_exists:
            logger.error(f"Iframe {IFRAME_ID} не найден в DOM")
            # Выводим список всех iframe на странице для диагностики
            iframes = driver.execute_script("""
                var iframes = document.getElementsByTagName('iframe');
                var result = [];
                for (var i = 0; i < iframes.length; i++) {
                    result.push({
                        id: iframes[i].id || 'no-id',
                        src: iframes[i].src || 'no-src',
                        name: iframes[i].name || 'no-name'
                    });
                }
                return result;
            """)
            logger.info(f"Найдены iframe на странице: {iframes}")
            return False
        
        logger.info(f"Iframe {IFRAME_ID} найден в DOM, переключаемся...")
        
        # Переключаемся на iframe с увеличенным таймаутом
        WebDriverWait(driver, 15).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, IFRAME_ID))
        )
        logger.info(f"✅ Успешно переключились на фрейм: {IFRAME_ID}")
        
        # Ждём загрузки содержимого iframe
        time.sleep(1)
        
        try:
            confirm_button = WebDriverWait(driver, 8).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn.btn-confirm"))
            )
            confirm_button.click()
            logger.info("Кнопка подтверждения в фрейме нажата")
            time.sleep(0.5)
        except TimeoutException:
            logger.info("Кнопка подтверждения в фрейме не найдена (это нормально)")
        
        return True
        
    except TimeoutException as e:
        logger.error(f"❌ Ошибка переключения на фрейм {IFRAME_ID}: Таймаут ожидания")
        # Дополнительная диагностика
        try:
            current_url = driver.current_url
            page_title = driver.title
            logger.error(f"Текущий URL: {current_url}")
            logger.error(f"Заголовок страницы: {page_title}")
        except Exception:
            pass
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при переключении на фрейм {IFRAME_ID}: {str(e)}")
        return False


@retry_on_failure(max_attempts=2, delay=0.5)
def click_breadcrumb(driver: WebDriver) -> bool:
    """
    Быстрое нажатие breadcrumb.
    """
    try:
        breadcrumb = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "breadcrumb-navigation-title"))
        )
        breadcrumb.click()
        logger.info("Клик по breadcrumb")
        time.sleep(0.3)  # Уменьшено с 0.5
        return True
    except TimeoutException as e:
        logger.error(f"Ошибка клика по breadcrumb: {str(e)}")
        return False


def is_table_empty(driver: WebDriver, selector: str = EMPTY_TABLE_TEXT_SELECTOR) -> bool:
    """
    Быстрая проверка пустоты таблицы.
    """
    try:
        element = driver.find_element(By.CSS_SELECTOR, selector)
        if EMPTY_TABLE_TEXT in element.text:
            logger.info("Таблица пуста")
            return True
    except Exception:
        pass
    return False


@retry_on_failure(max_attempts=2, delay=0.5)
def find_claim_data(driver: WebDriver, claim_number: Optional[str] = None, 
                    vin_number: Optional[str] = None) -> dict:
    """
    Быстрый поиск данных заявки.
    """
    section_selector_map = {"open": OPEN_TABLE_SELECTOR, "outgoing": OUTGOING_TABLE_SELECTOR}
    
    for section in ["open", "outgoing"]:
        if not click_request_type_button(driver, section):
            logger.error(f"Не удалось перейти в раздел {section}")
            return {"error": f"Не удалось перейти в раздел {section}"}
        if not wait_for_table(driver, section_selector_map.get(section)):
            return {"error": f"Таблица не загрузилась в разделе {section}"}
        if is_table_empty(driver):
            logger.info(f"Раздел {section} пуст")
            continue
        if claim_number and search_in_table(driver, claim_number, "номеру дела"):
            return {"success": True}
        elif vin_number and search_in_table(driver, vin_number, "VIN"):
            return {"success": True}
        logger.info(f"Данные не найдены в разделе {section}")
    return {"error": "Данные не найдены ни в одном разделе"} 


@retry_on_failure(max_attempts=3, delay=1.0)
def get_vin_status(driver: WebDriver) -> str:
    """
    Определяет активный статус VIN кнопок.
    
    Returns:
        str: "VIN", "VIN лайт" или "Нет"
    """
    logger.info("🔍 Определяем статус VIN кнопок...")
    
    try:
        vin_query_id = "root.task.basicClaimData.vehicle.vehicleIdentification.VINQuery-VINQueryButton"
        vin_lite_id = "root.task.basicClaimData.vehicle.vehicleIdentification.VINQuery-vinDecoderButton"
        
        # Ищем кнопки с небольшим ожиданием
        wait = WebDriverWait(driver, 5)
        
        vin_query_enabled = False
        vin_lite_enabled = False
        
        try:
            vin_query_button = wait.until(EC.presence_of_element_located((By.ID, vin_query_id)))
            vin_query_enabled = vin_query_button.is_enabled()
            logger.info(f"📋 VIN Запрос: {'активна' if vin_query_enabled else 'неактивна'}")
        except TimeoutException:
            logger.warning("❌ Кнопка VIN Запрос не найдена")
        
        try:
            vin_lite_button = driver.find_element(By.ID, vin_lite_id)
            vin_lite_enabled = vin_lite_button.is_enabled()
            logger.info(f"📋 VIN Лайт: {'активна' if vin_lite_enabled else 'неактивна'}")
        except NoSuchElementException:
            logger.warning("❌ Кнопка VIN Лайт не найдена")
        
        # Определяем статус
        if vin_query_enabled and not vin_lite_enabled:
            result = "VIN"
            logger.info("✅ Статус: VIN Запрос активен")
        elif vin_lite_enabled and not vin_query_enabled:
            result = "VIN лайт"
            logger.info("✅ Статус: VIN Лайт активен")
        elif vin_query_enabled and vin_lite_enabled:
            # Если обе активны, проверяем визуально какая выбрана (оранжевая)
            result = "VIN"  # По умолчанию VIN Запрос
            logger.info("✅ Статус: Обе активны, выбран VIN Запрос")
        else:
            result = "Нет"
            logger.info("❌ Статус: Ни одна кнопка не активна")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка при определении VIN статуса: {e}")
        return "Нет" 