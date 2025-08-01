# Модуль для stealth-методов обхода детекции бота
# Основан на техниках SeleniumBase UC Mode и современных методах обхода бот-детекта

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


def apply_advanced_stealth_masking(driver: WebDriver):
    """
    Применяет расширенные настройки для маскировки headless режима
    Основано на современных методах обхода бот-детекта
    """
    try:
        driver.execute_script("""
            // Безопасная функция для определения свойств
            function safeDefineProperty(obj, prop, descriptor) {
                try {
                    const existingDescriptor = Object.getOwnPropertyDescriptor(obj, prop);
                    if (existingDescriptor && !existingDescriptor.configurable) {
                        return false; // Свойство неконфигурируемое
                    }
                    Object.defineProperty(obj, prop, descriptor);
                    return true;
                } catch (e) {
                    return false;
                }
            }
            
            // Расширенная маскировка webdriver
            try {
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            } catch (e) {
                // Игнорируем ошибки
            }
            
            // Маскируем webdriver
            safeDefineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Маскируем chrome runtime
            if (window.chrome) {
                try {
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                } catch (e) {
                    // Игнорируем ошибки
                }
            }
            
            // Маскируем permissions
            try {
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
            } catch (e) {
                // Игнорируем ошибки
            }
            
            // Маскируем plugins
            safeDefineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
                configurable: true
            });
            
            // Маскируем languages
            safeDefineProperty(navigator, 'languages', {
                get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                configurable: true
            });
            
            // Маскируем connection
            safeDefineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false,
                }),
                configurable: true
            });
            
            // Маскируем hardwareConcurrency
            safeDefineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
                configurable: true
            });
            
            // Маскируем deviceMemory
            safeDefineProperty(navigator, 'deviceMemory', {
                get: () => 8,
                configurable: true
            });
            
            // Маскируем userAgent
            try {
                const originalUserAgent = navigator.userAgent;
                
                // Добавляем дополнительные методы обхода детекции
                safeDefineProperty(navigator, 'maxTouchPoints', {
                    get: () => 0,
                    configurable: true
                });
                
                safeDefineProperty(navigator, 'vendor', {
                    get: () => 'Google Inc.',
                    configurable: true
                });
                
                safeDefineProperty(navigator, 'platform', {
                    get: () => 'Win32',
                    configurable: true
                });
                
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
                Object.defineProperty(navigator, 'userAgent', {
                    get: () => originalUserAgent.replace('HeadlessChrome', 'Chrome'),
                });
            } catch (e) {
                // Свойство уже определено, пропускаем
            }
            
            // Удаляем признаки автоматизации
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Маскируем screen свойства безопасно
            safeDefineProperty(screen, 'width', { get: () => 1920 });
            safeDefineProperty(screen, 'height', { get: () => 1080 });
            safeDefineProperty(screen, 'availWidth', { get: () => 1920 });
            safeDefineProperty(screen, 'availHeight', { get: () => 1040 });
            safeDefineProperty(screen, 'colorDepth', { get: () => 24 });
            safeDefineProperty(screen, 'pixelDepth', { get: () => 24 });
            
            // Маскируем window свойства безопасно
            safeDefineProperty(window, 'outerWidth', { get: () => 1920 });
            safeDefineProperty(window, 'outerHeight', { get: () => 1080 });
            safeDefineProperty(window, 'innerWidth', { get: () => 1920 });
            safeDefineProperty(window, 'innerHeight', { get: () => 937 });
            
            // Маскируем devicePixelRatio безопасно
            safeDefineProperty(window, 'devicePixelRatio', { get: () => 1 });
        """)
        
        logger.debug("✅ Расширенная маскировка headless режима применена")
        
    except Exception as e:
        logger.debug(f"⚠️ Ошибка при применении расширенной маскировки: {e}")


def apply_headless_masking(driver: WebDriver):
    """
    Применяет дополнительные настройки для маскировки headless режима
    """
    try:
        driver.execute_script("""
            // Маскируем headless режим
            try {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            } catch (e) {
                // Свойство уже определено, пропускаем
            }
            
            // Маскируем chrome
            try {
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['ru-RU', 'ru', 'en-US', 'en'],
                });
            } catch (e) {
                // Свойство уже определено, пропускаем
            }
            
            // Маскируем permissions
            try {
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: () => Promise.resolve({ state: 'granted' }),
                    }),
                });
            } catch (e) {
                // Свойство уже определено, пропускаем
            }
            
            // Маскируем plugins
            try {
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
            } catch (e) {
                // Свойство уже определено, пропускаем
            }
            
            // Маскируем connection
            try {
                Object.defineProperty(navigator, 'connection', {
                    get: () => ({
                        effectiveType: '4g',
                        rtt: 50,
                        downlink: 10,
                    }),
                });
            } catch (e) {
                // Свойство уже определено, пропускаем
            }
            
            // Маскируем hardwareConcurrency
            try {
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8,
                });
            } catch (e) {
                // Свойство уже определено, пропускаем
            }
            
            // Маскируем deviceMemory
            try {
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,
                });
            } catch (e) {
                // Свойство уже определено, пропускаем
            }
            
            // Удаляем признаки автоматизации
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Маскируем screen свойства безопасно (используем уже определенную safeDefineProperty)
            if (typeof safeDefineProperty === 'function') {
                safeDefineProperty(screen, 'width', { get: () => 1920 });
                safeDefineProperty(screen, 'height', { get: () => 1080 });
                safeDefineProperty(screen, 'availWidth', { get: () => 1920 });
                safeDefineProperty(screen, 'availHeight', { get: () => 1040 });
                
                // Маскируем window свойства безопасно
                safeDefineProperty(window, 'outerWidth', { get: () => 1920 });
                safeDefineProperty(window, 'outerHeight', { get: () => 1080 });
                safeDefineProperty(window, 'innerWidth', { get: () => 1920 });
                safeDefineProperty(window, 'innerHeight', { get: () => 937 });
            }
        """)
        
        logger.debug("✅ Дополнительная маскировка headless режима применена")
        
    except Exception as e:
        logger.debug(f"⚠️ Ошибка при применении маскировки headless: {e}")


def stealth_open_url(driver: WebDriver, url: str, reconnect_time: Optional[float] = None) -> bool:
    """
    Скрытное открытие URL с методами обхода детекции
    """
    try:
        logger.info(f"🔒 Скрытное открытие URL: {url}")
        
        # Применяем расширенную маскировку для headless режима с дополнительной защитой
        try:
            apply_advanced_stealth_masking(driver)
        except Exception as stealth_error:
            logger.debug(f"⚠️ Ошибка при применении stealth маскировки: {stealth_error}")
            # Продолжаем выполнение даже если маскировка не удалась
        
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
    def _perform_click():
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
        
        return True
    
    try:
        logger.info(f"🔒 Скрытный клик по селектору: {selector}")
        
        # Используем безопасное выполнение с повторными попытками
        result = safe_stealth_execution(driver, f"клик по {selector}", _perform_click)
        
        logger.info("✅ Скрытный клик выполнен")
        return result
        
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
        logger.debug(f"Ошибка при добавлении stealth-поведения: {e}")


def check_stealth_detection(driver: WebDriver) -> bool:
    """
    Проверяет признаки детекции stealth-методов
    """
    try:
        # Проверяем содержимое страницы
        page_source = driver.page_source.lower()
        detection_indicators = [
            "gethandleverifier",
            "white screen",
            "bot detected",
            "automation detected",
            "captcha",
            "cloudflare",
            "access denied",
            "blocked",
            "security check",
            "verify you are human",
            "please wait"
        ]
        
        for indicator in detection_indicators:
            if indicator in page_source:
                logger.warning(f"🚨 Обнаружен индикатор детекции: {indicator}")
                return True
        
        # Проверяем JavaScript признаки детекции
        js_detection_checks = [
            "return navigator.webdriver",
            "return window.chrome && window.chrome.runtime",
            "return navigator.plugins.length === 0",
            "return navigator.languages.length === 0",
            "return !navigator.connection",
            "return !navigator.hardwareConcurrency",
            "return !navigator.deviceMemory",
            "return !navigator.maxTouchPoints",
            "return !navigator.vendor",
            "return !navigator.platform"
        ]
        
        detection_count = 0
        for check in js_detection_checks:
            try:
                result = driver.execute_script(check)
                if result:
                    detection_count += 1
                    logger.warning(f"🚨 Обнаружена JavaScript детекция: {check}")
            except Exception:
                continue
        
        if detection_count > 3:
            logger.error(f"🚨 Обнаружено {detection_count} признаков JavaScript детекции")
            return True
        
        logger.info("✅ Детекция не обнаружена")
        return False
        
    except Exception as e:
        logger.error(f"Ошибка при проверке stealth-детекции: {e}")
        return False


def restore_stealth_masking(driver: WebDriver) -> bool:
    """
    Восстанавливает stealth маскировку при обнаружении детекции
    """
    try:
        logger.info("🔄 Восстанавливаем stealth маскировку")
        
        # Применяем расширенную маскировку
        apply_advanced_stealth_masking(driver)
        
        # Добавляем человеческое поведение
        add_stealth_behavior(driver)
        
        # Проверяем результат
        if check_stealth_detection(driver):
            logger.error("❌ Не удалось восстановить stealth маскировку")
            return False
        
        logger.info("✅ Stealth маскировка восстановлена")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка при восстановлении stealth маскировки: {e}")
        return False


def safe_stealth_execution(driver: WebDriver, operation_name: str, operation_func, *args, **kwargs):
    """
    Безопасное выполнение stealth операций с восстановлением после ошибок
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.debug(f"🔒 Попытка {attempt + 1}/{max_retries}: {operation_name}")
            result = operation_func(*args, **kwargs)
            logger.debug(f"✅ {operation_name} выполнена успешно")
            return result
        except Exception as e:
            logger.warning(f"⚠️ Ошибка в {operation_name} (попытка {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                # Применяем базовую маскировку перед повторной попыткой
                try:
                    apply_headless_masking(driver)
                    time.sleep(random.uniform(1, 3))
                except Exception as mask_error:
                    logger.debug(f"Ошибка при повторной маскировке: {mask_error}")
            else:
                logger.error(f"❌ {operation_name} не удалась после {max_retries} попыток")
                raise


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
        apply_advanced_stealth_masking(driver)
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
        
        # Применяем расширенную маскировку headless режима
        apply_advanced_stealth_masking(driver)
        
        # Добавляем случайную задержку для имитации человеческого поведения
        time.sleep(random.uniform(0.5, 1.5))
        
        # Ждем DOM модель с WebDriverWait без хардкод таймаута
        try:
            # Используем короткий таймаут для быстрой проверки
            element = WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            
            # Дополнительно проверяем, что элемент видим
            if element.is_displayed():
                logger.info("✅ Элемент найден скрытно")
                return True
            else:
                logger.warning("⚠️ Элемент найден, но не видим")
                # Попробуем прокрутить к элементу
                try:
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                    time.sleep(0.5)
                    if element.is_displayed():
                        logger.info("✅ Элемент стал видим после прокрутки")
                        return True
                except Exception as scroll_error:
                    logger.warning(f"⚠️ Не удалось прокрутить к элементу: {scroll_error}")
                return False
                
        except TimeoutException:
            logger.error(f"❌ Элемент не найден: {selector}")
            
            # Проверяем, не связана ли проблема с детекцией
            if check_stealth_detection(driver):
                logger.warning("🚨 Обнаружена детекция, пытаемся восстановить маскировку")
                if restore_stealth_masking(driver):
                    # Повторяем попытку после восстановления маскировки
                    try:
                        element = WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if element.is_displayed():
                            logger.info("✅ Элемент найден после восстановления маскировки")
                            return True
                    except TimeoutException:
                        pass
            
            # Попробуем альтернативные селекторы
            alternative_selectors = []
            
            # Если селектор содержит точку, пробуем разные варианты
            if '.' in selector:
                # Убираем экранирование и пробуем как есть
                clean_selector = selector.replace('\\.', '.').strip()
                alternative_selectors.append(clean_selector)
                
                # Пробуем с экранированием
                escaped_selector = selector.replace('.', '\\.')
                alternative_selectors.append(escaped_selector)
                
                # Пробуем как атрибут class (убираем экранирование для поиска)
                clean_for_class = selector.replace('\\.', '.').strip()
                class_parts = clean_for_class.split('.')
                if len(class_parts) > 1:
                    class_name = class_parts[-1]  # Берем последнюю часть как имя класса
                    alternative_selectors.append(f'[class*="{class_name}"]')
                    
                # Пробуем найти по частичному совпадению класса
                if 'task' in clean_for_class:
                    alternative_selectors.append('[class*="task"]')
                if 'claimNumber' in clean_for_class:
                    alternative_selectors.append('[class*="claimNumber"]')
                    
                # Пробуем найти по комбинации классов
                if 'task' in clean_for_class and 'claimNumber' in clean_for_class:
                    alternative_selectors.append('[class*="task"][class*="claimNumber"]')
                    alternative_selectors.append('.task.claimNumber')
                    alternative_selectors.append('#root .task .claimNumber')
                    alternative_selectors.append('#root.task.claimNumber')
                    alternative_selectors.append('input[class*="claimNumber"]')
                    alternative_selectors.append('input[name*="claimNumber"]')
                    alternative_selectors.append('input[id*="claimNumber"]')
                    alternative_selectors.append('[data-testid*="claimNumber"]')
            
            # Если селектор содержит #, пробуем как id
            if '#' in selector:
                id_parts = selector.split('#')
                if len(id_parts) > 1:
                    id_name = id_parts[-1]  # Берем последнюю часть как id
                    # Убираем экранирование из id
                    clean_id = id_name.replace('\\.', '.')
                    alternative_selectors.append(f'[id="{clean_id}"]')
                    alternative_selectors.append(f'[id*="{clean_id}"]')
                    
                    # Пробуем найти по частичному совпадению id
                    if 'root' in clean_id:
                        alternative_selectors.append('[id*="root"]')
                    if 'task' in clean_id:
                        alternative_selectors.append('[id*="task"]')
                    if 'claimNumber' in clean_id:
                        alternative_selectors.append('[id*="claimNumber"]')
            
            # Добавляем общие альтернативы
            clean_selector_for_attr = selector.replace('#', '').replace('\\.', '').replace('.', '')
            if clean_selector_for_attr:
                alternative_selectors.extend([
                    f'*[data-testid*="{clean_selector_for_attr}"]',
                    f'*[aria-label*="{clean_selector_for_attr}"]',
                    f'*[name*="{clean_selector_for_attr}"]',
                    f'*[placeholder*="{clean_selector_for_attr}"]'
                ])
            
            # Убираем дублирующиеся селекторы
            alternative_selectors = list(dict.fromkeys(alternative_selectors))
            
            # Логируем сгенерированные альтернативные селекторы для отладки
            logger.debug(f"🔍 Сгенерировано {len(alternative_selectors)} альтернативных селекторов для '{selector}'")
            for i, alt_sel in enumerate(alternative_selectors):
                logger.debug(f"  {i+1}. {alt_sel}")
            
            for alt_selector in alternative_selectors:
                try:
                    # Проверяем валидность селектора
                    if not alt_selector or alt_selector.strip() == '':
                        continue
                        
                    logger.info(f"🔄 Пробуем альтернативный селектор: {alt_selector}")
                    element = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, alt_selector))
                    )
                    if element.is_displayed():
                        logger.info(f"✅ Элемент найден по альтернативному селектору: {alt_selector}")
                        return True
                except TimeoutException:
                    continue
                except Exception as selector_error:
                    logger.debug(f"⚠️ Некорректный селектор '{alt_selector}': {selector_error}")
                    continue
            
            return False
            
    except Exception as e:
        logger.error(f"❌ Ошибка при скрытном ожидании элемента: {e}")
        return False 