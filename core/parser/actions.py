# Улучшенные функции для действий и взаимодействий с элементами интерфейса
# Оптимизированы для скорости с сохранением надежности

import logging
import time
import functools
import random
from typing import Optional, Callable, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.action_chains import ActionChains
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


def human_like_delay(min_seconds: float = 0.5, max_seconds: float = 2.0):
    """Человеческая задержка с рандомизацией"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def human_like_click(driver: WebDriver, element, use_actions: bool = False):
    """Человеческий клик с рандомизацией"""
    try:
        if use_actions:
            # Используем ActionChains для более человечного поведения
            actions = ActionChains(driver)
            actions.move_to_element(element)
            human_like_delay(0.1, 0.3)
            actions.click()
            actions.perform()
        else:
            # Обычный клик с небольшой задержкой
            human_like_delay(0.1, 0.2)
            element.click()
        return True
    except ElementClickInterceptedException:
        # Fallback на JavaScript клик
        driver.execute_script("arguments[0].click();", element)
        return True
    except Exception as e:
        logger.error(f"Ошибка при клике: {e}")
        return False


def add_human_behavior(driver: WebDriver):
    """Добавляет человеческое поведение для обхода детекции"""
    try:
        # Случайные движения мыши в пределах окна
        try:
            window_size = driver.get_window_size()
            max_x = window_size['width'] - 100
            max_y = window_size['height'] - 100
            
            actions = ActionChains(driver)
            for _ in range(random.randint(2, 5)):
                x = random.randint(50, max(100, max_x))
                y = random.randint(50, max(100, max_y))
                actions.move_by_offset(x, y)
                human_like_delay(0.1, 0.3)
        except Exception as e:
            logger.debug(f"Ошибка движения мыши: {e}")
        
        # Случайный скролл
        scroll_amount = random.randint(-300, 300)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        human_like_delay(0.2, 0.5)
        
        logger.debug("Добавлено человеческое поведение")
    except Exception as e:
        logger.debug(f"Ошибка при добавлении человеческого поведения: {e}")


def add_extended_human_behavior(driver: WebDriver, total_delay: float = 60.0):
    """
    Расширенное человеческое поведение с контролируемой общей задержкой.
    Распределяет задержку на различные человеческие действия.
    
    Args:
        driver: WebDriver instance
        total_delay: Общая задержка в секундах (по умолчанию 1 минута)
    """
    try:
        logger.info(f"🤖 Добавляем расширенное человеческое поведение (общая задержка: {total_delay:.1f}с)")
        
        # Распределяем задержку на различные действия
        actions_count = random.randint(8, 15)
        delay_per_action = total_delay / actions_count
        
        for i in range(actions_count):
            action_type = random.choice([
                'mouse_movement',
                'scroll',
                'pause',
                'window_focus',
                'element_hover'
            ])
            
            if action_type == 'mouse_movement':
                # Случайные движения мыши в пределах окна
                try:
                    # Получаем размеры окна
                    window_size = driver.get_window_size()
                    max_x = window_size['width'] - 100  # Оставляем отступ от краев
                    max_y = window_size['height'] - 100
                    
                    # Генерируем координаты в пределах окна
                    x = random.randint(50, max(100, max_x))
                    y = random.randint(50, max(100, max_y))
                    
                    actions = ActionChains(driver)
                    actions.move_by_offset(x, y)
                    actions.perform()
                    time.sleep(delay_per_action * 0.3)
                except Exception as e:
                    logger.debug(f"Ошибка движения мыши: {e}")
                    time.sleep(delay_per_action * 0.5)
                
            elif action_type == 'scroll':
                # Случайный скролл
                scroll_amount = random.randint(-500, 500)
                driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
                time.sleep(delay_per_action * 0.4)
                
            elif action_type == 'pause':
                # Простая пауза
                time.sleep(delay_per_action * 0.8)
                
            elif action_type == 'window_focus':
                # Фокус на окно
                driver.execute_script("window.focus();")
                time.sleep(delay_per_action * 0.2)
                
            elif action_type == 'element_hover':
                # Наведение на случайный элемент
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, "div, span, a, button")
                    if elements:
                        random_element = random.choice(elements)
                        actions = ActionChains(driver)
                        actions.move_to_element(random_element)
                        actions.perform()
                        time.sleep(delay_per_action * 0.3)
                except:
                    time.sleep(delay_per_action * 0.5)
            
            # Небольшая пауза между действиями
            time.sleep(random.uniform(0.1, 0.3))
            
            if i % 5 == 0:
                logger.debug(f"🤖 Выполнено {i+1}/{actions_count} человеческих действий")
        
        logger.info("✅ Расширенное человеческое поведение завершено")
        
    except Exception as e:
        logger.debug(f"Ошибка при добавлении расширенного человеческого поведения: {e}")


def check_for_bot_detection(driver: WebDriver) -> bool:
    """Проверяет признаки детекции бота"""
    try:
        page_source = driver.page_source.lower()
        bot_indicators = [
            "gethandleverifier",
            "white screen",
            "bot detected",
            "automation detected",
            "captcha",
            "cloudflare"
        ]
        
        for indicator in bot_indicators:
            if indicator in page_source:
                logger.warning(f"🚨 Обнаружен индикатор детекции бота: {indicator}")
                return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при проверке детекции бота: {e}")
        return False


def handle_bot_detection(driver: WebDriver):
    """Обрабатывает детекцию бота с расширенным человеческим поведением"""
    logger.warning("🚨 Обрабатываем детекцию бота...")
    
    # Длительная пауза
    human_like_delay(5.0, 10.0)
    
    # Добавляем расширенное человеческое поведение
    add_extended_human_behavior(driver, total_delay=60.0)
    
    # Пробуем обновить страницу
    try:
        driver.refresh()
        human_like_delay(3.0, 5.0)
        add_human_behavior(driver)
    except Exception as e:
        logger.error(f"Ошибка при обновлении страницы: {e}")


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
                    # Проверяем детекцию бота перед выполнением
                    if len(args) > 0 and hasattr(args[0], 'page_source'):
                        driver = args[0]
                        if check_for_bot_detection(driver):
                            handle_bot_detection(driver)
                    
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
    Ожидание загрузки таблицы с явным ожиданием элементов.
    """
    # Добавляем человеческое поведение перед ожиданием таблицы
    add_human_behavior(driver)
    
    selectors_to_check = [selector] if selector else [OPEN_TABLE_SELECTOR, OUTGOING_TABLE_SELECTOR]
    
    # Увеличиваем таймаут для медленного сайта
    timeout = 60  # 60 секунд для полной загрузки
    
    for sel in selectors_to_check:
        try:
            logger.info(f"Ожидание таблицы с селектором: {sel}")
            
            # Ждем появления элемента
            table_element = WebDriverWait(driver, timeout, poll_frequency=0.5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, sel))
            )
            
            # Дополнительно ждем, что элемент стал видимым и интерактивным
            WebDriverWait(driver, 10, poll_frequency=0.5).until(
                EC.visibility_of(table_element)
            )
            
            # Проверяем, что таблица не пустая (есть строки или сообщение о пустоте)
            try:
                # Ждем либо строки таблицы, либо сообщения о пустоте
                WebDriverWait(driver, 10, poll_frequency=0.5).until(
                    lambda d: (
                        len(d.find_elements(By.CSS_SELECTOR, ROW_SELECTOR)) > 0 or
                        len(d.find_elements(By.CSS_SELECTOR, EMPTY_TABLE_TEXT_SELECTOR)) > 0
                    )
                )
                logger.info(f"✅ Таблица '{sel}' полностью загружена и готова")
                return True
            except TimeoutException:
                logger.warning(f"⚠️ Таблица '{sel}' найдена, но содержимое не загрузилось")
                # Возвращаем True, так как таблица есть, просто может быть пустая
                return True
                
        except TimeoutException:
            logger.warning(f"⚠️ Таблица с селектором '{sel}' не найдена за {timeout} секунд")
            continue

    logger.error("❌ Ни одна из таблиц не загрузилась")
    return False


@retry_on_failure(max_attempts=2, delay=0.5)
def click_cansel_button(driver: WebDriver) -> bool:
    """
    Нажатие кнопки отмены с явным ожиданием элемента.
    """
    selector = "#confirm > div > div > div.modal-footer > button"
    
    try:
        # Ждем появления кнопки
        button = WebDriverWait(driver, 10, poll_frequency=0.5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        
        # Добавляем человеческое поведение
        add_human_behavior(driver)
        
        # Используем человеческий клик
        success = human_like_click(driver, button, use_actions=True)
        
        if success:
            logger.info("✅ Кнопка подтверждения нажата")
            return True
        else:
            logger.error("❌ Не удалось нажать кнопку подтверждения")
            return False
        
    except TimeoutException:
        logger.info("ℹ️ Кнопка подтверждения не найдена (это нормально)")
        return True  # Это нормально
    except Exception as e:
        logger.error(f"❌ Ошибка клика кнопки подтверждения: {e}")
        return False


@retry_on_failure(max_attempts=2, delay=0.5)
def click_request_type_button(driver: WebDriver, req_type: str) -> bool:
    """
    Переключение между типами заявок с явным ожиданием элементов.
    """
    try:
        if req_type == "open":
            selector = "#view-link-worklistgrid_custom_open"
        elif req_type == "outgoing":
            selector = "#view-link-worklistgrid_custom_sent"
        else:
            logger.error(f"❌ Неизвестный тип заявки: {req_type}")
            return False
        
        logger.info(f"Ожидание кнопки типа заявки: {req_type}")
        
        # Ждем появления и кликабельности кнопки
        more_views_link = WebDriverWait(driver, 15, poll_frequency=0.5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
        )
        
        # Добавляем человеческое поведение
        add_human_behavior(driver)
        
        # Используем человеческий клик
        success = human_like_click(driver, more_views_link, use_actions=True)
        
        if success:
            logger.info(f"✅ Клик по кнопке {req_type}")
            return True
        else:
            logger.error(f"❌ Не удалось кликнуть по кнопке {req_type}")
            return False
        
    except TimeoutException as e:
        logger.error(f"❌ Ошибка клика по кнопке {req_type}: {str(e)}")
        return False


@retry_on_failure(max_attempts=2, delay=0.5)
def search_in_table(driver: WebDriver, search_value: str, search_type: str) -> bool:
    """
    Поиск в таблице с расширенным человеческим поведением для обхода детекции.
    """
    try:
        logger.info(f"🔍 Начинаем поиск по {search_type}: {search_value}")
        
        # Добавляем расширенное человеческое поведение перед поиском
        add_extended_human_behavior(driver, total_delay=60.0)
        
        search_input = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#root\\.quickfilter\\.searchbox"))
        )
        
        # Добавляем человеческое поведение
        add_human_behavior(driver)
        
        # Очищаем поле с человеческой задержкой
        search_input.clear()
        human_like_delay(0.3, 0.7)
        
        # Вводим текст с человеческими паузами
        for char in search_value:
            search_input.send_keys(char)
            human_like_delay(0.05, 0.15)
        
        logger.info(f"Введён {search_type}: {search_value}")
        human_like_delay(0.8, 1.2)  # Человеческая задержка
        
        logger.info(f"Ожидание результатов поиска по {search_type}")
        WebDriverWait(driver, 15, poll_frequency=0.5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ROW_SELECTOR))
        )
        logger.info(f"✅ Найдены строки по {search_type}")
        return True
        
    except TimeoutException:
        logger.info(f"Таблица пустая после поиска по {search_type}")
        return False


@retry_on_failure(max_attempts=2, delay=0.5)
def click_more_icon(driver: WebDriver) -> bool:
    """
    Нажатие иконки "Еще" с явным ожиданием элементов.
    """
    # Селекторы для разных типов таблиц
    selectors = [
        MORE_ICON_SELECTOR,  # Исходящие дела
        MORE_ICON_SELECTOR.replace("worklistgrid_custom_sent", "worklistgrid_custom_open")  # Открытые дела
    ]
    
    for i, selector in enumerate(selectors):
        try:
            logger.info(f"Ожидание иконки 'ещё' с селектором: {selector}")
            
            # Ждем появления и кликабельности иконки
            more_icon = WebDriverWait(driver, 15, poll_frequency=0.5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
            )
            
            # Добавляем человеческое поведение
            add_human_behavior(driver)
            
            # Используем человеческий клик
            success = human_like_click(driver, more_icon, use_actions=True)
            
            if success:
                table_type = "исходящих" if i == 0 else "открытых"
                logger.info(f"✅ Клик по иконке 'ещё' в таблице {table_type} дел")
                return True
        except TimeoutException:
            logger.warning(f"⚠️ Иконка 'ещё' не найдена с селектором: {selector}")
            continue
    
    logger.error("❌ Ошибка клика по иконке 'ещё': не найдена ни в одной таблице")
    return False


@retry_on_failure(max_attempts=2, delay=0.5)
def open_task(driver: WebDriver) -> bool:
    """
    Открытие задачи с явным ожиданием элемента.
    """
    try:
        # Добавляем человеческое поведение перед открытием задачи
        add_human_behavior(driver)
        
        logger.info("Ожидание кнопки 'openTask'")
        
        # Ждем появления и кликабельности кнопки
        open_task = WebDriverWait(driver, 15, poll_frequency=0.5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#openTask"))
        )
        
        # Используем человеческий клик
        success = human_like_click(driver, open_task, use_actions=True)
        
        if success:
            logger.info("✅ Кнопка 'openTask' нажата")
            return True
        else:
            logger.error("❌ Не удалось нажать кнопку 'openTask'")
            return False
            
    except TimeoutException as e:
        logger.error(f"❌ Ошибка клика по openTask: {str(e)}")
        return False


@retry_on_failure(max_attempts=3, delay=1.0)
def switch_to_frame_and_confirm(driver: WebDriver) -> bool:
    """
    Надёжное переключение в iframe с человеческим поведением и дополнительными проверками.
    """
    try:
        # Добавляем человеческое поведение перед переключением на фрейм
        add_human_behavior(driver)
        
        # Ждём полной загрузки страницы
        logger.info("Ожидание полной загрузки страницы")
        WebDriverWait(driver, 30, poll_frequency=0.5).until(
            lambda d: d.execute_script("return document.readyState === 'complete'")
        )
        logger.info("✅ Страница полностью загружена")
        
        # Дополнительная пауза для загрузки динамического контента
        time.sleep(3)
        
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
        logger.info(f"Ожидание готовности iframe: {IFRAME_ID}")
        WebDriverWait(driver, 30, poll_frequency=0.5).until(
            EC.frame_to_be_available_and_switch_to_it((By.ID, IFRAME_ID))
        )
        logger.info(f"✅ Успешно переключились на фрейм: {IFRAME_ID}")
        
        # Ждём загрузки содержимого iframe
        time.sleep(2)
        
        try:
            logger.info("Ожидание кнопки подтверждения в iframe")
            confirm_button = WebDriverWait(driver, 15, poll_frequency=0.5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".btn.btn-confirm"))
            )
            
            # Используем человеческий клик для кнопки подтверждения
            success = human_like_click(driver, confirm_button, use_actions=True)
            
            if success:
                logger.info("✅ Кнопка подтверждения в фрейме нажата")
                time.sleep(0.5)
            else:
                logger.warning("⚠️ Не удалось нажать кнопку подтверждения в фрейме")
        except TimeoutException:
            logger.info("ℹ️ Кнопка подтверждения в фрейме не найдена (это нормально)")
        
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
    Нажатие breadcrumb с явным ожиданием элемента.
    """
    try:
        logger.info("Ожидание breadcrumb элемента")
        breadcrumb = WebDriverWait(driver, 15, poll_frequency=0.5).until(
            EC.element_to_be_clickable((By.ID, "breadcrumb-navigation-title"))
        )
        
        # Добавляем человеческое поведение
        add_human_behavior(driver)
        
        # Используем человеческий клик
        success = human_like_click(driver, breadcrumb, use_actions=True)
        
        if success:
            logger.info("✅ Клик по breadcrumb выполнен")
            time.sleep(0.3)
            return True
        else:
            logger.error("❌ Не удалось нажать breadcrumb")
            return False
    except TimeoutException as e:
        logger.error(f"❌ Ошибка клика по breadcrumb: {str(e)}")
        return False


def is_table_empty(driver: WebDriver, selector: str = EMPTY_TABLE_TEXT_SELECTOR) -> bool:
    """
    Проверка пустоты таблицы с человеческим поведением.
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
    Поиск данных заявки с расширенным человеческим поведением для обхода детекции.
    """
    logger.info("🤖 Начинаем поиск заявки с расширенным человеческим поведением")
    
    # Добавляем расширенное человеческое поведение перед поиском заявки
    add_extended_human_behavior(driver, total_delay=60.0)
    
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
    Определяет активный статус VIN кнопок с человеческим поведением.
    
    Returns:
        str: "VIN", "VIN лайт" или "Нет"
    """
    logger.info("🔍 Определяем статус VIN кнопок...")
    
    # Добавляем человеческое поведение перед определением статуса
    add_human_behavior(driver)
    
    try:
        vin_query_id = "root.task.basicClaimData.vehicle.vehicleIdentification.VINQuery-VINQueryButton"
        vin_lite_id = "root.task.basicClaimData.vehicle.vehicleIdentification.VINQuery-vinDecoderButton"
        
        # Ищем кнопки с явным ожиданием
        wait = WebDriverWait(driver, 15, poll_frequency=0.5)
        
        vin_query_enabled = False
        vin_lite_enabled = False
        
        try:
            logger.info("Ожидание кнопки VIN Запрос")
            vin_query_button = wait.until(EC.presence_of_element_located((By.ID, vin_query_id)))
            vin_query_enabled = vin_query_button.is_enabled()
            logger.info(f"📋 VIN Запрос: {'активна' if vin_query_enabled else 'неактивна'}")
        except TimeoutException:
            logger.warning("⚠️ Кнопка VIN Запрос не найдена")
        
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