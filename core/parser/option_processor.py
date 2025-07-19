"""
Модуль для сбора опций автомобиля из системы Audatex.
Универсальный обобщенный алгоритм без жесткой типизации.
"""

import logging
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

logger = logging.getLogger(__name__)

# Константы для таймаутов
OPTION_TIMEOUT = 15
FAST_POLL_INTERVAL = 0.1
SECTION_TIMEOUT = 10
OPTION_POLL_INTERVAL = 0.2


def wait_for_element_stable(driver, selector, timeout=OPTION_TIMEOUT):
    """Ждет стабилизации элемента с оптимизированным polling"""
    wait = WebDriverWait(driver, timeout, poll_frequency=FAST_POLL_INTERVAL,
                        ignored_exceptions=[NoSuchElementException, TimeoutException])
    return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))


def wait_for_element_clickable(driver, selector, timeout=OPTION_TIMEOUT):
    """Ждет готовности элемента к клику"""
    wait = WebDriverWait(driver, timeout, poll_frequency=FAST_POLL_INTERVAL)
    return wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))


def wait_for_content_loaded(driver, timeout=SECTION_TIMEOUT):
    """Ждет загрузки контента опций"""
    wait = WebDriverWait(driver, timeout, poll_frequency=OPTION_POLL_INTERVAL,
                        ignored_exceptions=[NoSuchElementException])
    return wait.until(
        lambda d: d.find_element(By.CSS_SELECTOR, "#model-options-section-content")
    )


def navigate_to_options(driver):
    """Переходит к разделу опций через селектор #navigation-adjustment"""
    logger.info("🎯 Начинаем переход к разделу опций")
    
    try:
        current_url = driver.current_url
        logger.info(f"🔍 Текущий URL: {current_url}")
        
        ready_state = driver.execute_script("return document.readyState")
        logger.info(f"🔍 Состояние документа: {ready_state}")
        
        iframe_selector = "#iframe_root\\.task\\.damageCapture\\.inlineWebPad"
        logger.info(f"🔍 Ищем iframe: {iframe_selector}")
        
        iframe = wait_for_element_stable(driver, iframe_selector)
        logger.info("✅ Iframe найден, переключаемся в него")
        
        driver.switch_to.frame(iframe)
        logger.info("✅ Переключились в iframe")
        
        logger.info("🔍 Ищем span элемент navigation-adjustment внутри iframe...")
        adjustment_span = wait_for_element_clickable(driver, "#navigation-adjustment")
        adjustment_span.click()
        logger.info("✅ Клик по span#navigation-adjustment выполнен")
        
        options_container = wait_for_element_stable(driver, "#model-options-sections")
        logger.info("✅ Контейнер опций #model-options-sections загружен")
        
        return True
        
    except (TimeoutException, WebDriverException) as e:
        logger.error(f"❌ Ошибка навигации к опциям: {e}")
        return False


def ensure_in_iframe(driver):
    """Проверяет, находимся ли мы в нужном iframe, и переключается если нужно"""
    try:
        driver.find_element(By.CSS_SELECTOR, "#model-options-sections")
        return True
    except:
        try:
            driver.switch_to.default_content()
            iframe_selector = "#iframe_root\\.task\\.damageCapture\\.inlineWebPad"
            iframe = wait_for_element_stable(driver, iframe_selector)
            driver.switch_to.frame(iframe)
            logger.debug("🔄 Переключились в iframe для работы с опциями")
            return True
        except Exception as e:
            logger.error(f"❌ Не удалось переключиться в iframe: {e}")
            return False


def extract_option_zones(driver):
    """Извлекает ВСЕ зоны опций из div#model-options-sections включая специальные"""
    logger.info("🔍 Извлекаем ВСЕ зоны опций из model-options-sections (включая специальные)")
    zones = []
    
    try:
        if not ensure_in_iframe(driver):
            logger.error("❌ Не удалось переключиться в iframe для извлечения зон")
            return zones
        
        zones_container = wait_for_element_stable(driver, "#model-options-sections")
        zone_sections = zones_container.find_elements(By.CSS_SELECTOR, "div.model-options-section")
        logger.info(f"🔍 Найдено {len(zone_sections)} секций зон в контейнере")
        
        for section in zone_sections:
            section_id = section.get_attribute("id")
            data_value = section.get_attribute("data-value")
            
            # УБИРАЕМ ФИЛЬТРАЦИЮ - теперь собираем все зоны включая специальные
            # if section_id in ["model-options-section-all-selected", "model-options-section-zone-relevant"]:
            #     logger.debug(f"⏩ Пропускаем специальную секцию: {section_id}")
            #     continue
                
            if section_id and (section_id.startswith("model-options-section-") or section_id == "predefined-model-options-section"):
                try:
                    description_span = section.find_element(By.CSS_SELECTOR, "span.model-options-section-description")
                    zone_title = description_span.text.strip()
                    
                    if zone_title:
                        zones.append({
                            "id": section_id,
                            "data_value": data_value,
                            "title": zone_title,
                            "element": section
                        })
                        # Помечаем специальные зоны для логирования
                        zone_type = "специальная" if section_id in ["model-options-section-all-selected", "model-options-section-zone-relevant"] else "обычная"
                        logger.info(f"📝 Зона опций ({zone_type}): '{zone_title}' (ID: {section_id}, data-value: {data_value})")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки зоны {section_id}: {e}")
                    continue
        
        

        logger.info(f"✅ Извлечено {len(zones)} зон опций (включая специальные)")
        return zones
        
    except (TimeoutException, WebDriverException) as e:
        logger.error(f"❌ Ошибка извлечения зон опций: {e}")
        return []


def parse_option_code_title(option_text):
    """Парсит текст опции для извлечения кода и названия с улучшенной логикой"""
    if not option_text or not option_text.strip():
        return "", ""
    
    original_text = option_text.strip()
    
    # Если в тексте есть разделитель " - ", используем его
    separator_index = original_text.find(" - ")
    
    if separator_index != -1:
        code = original_text[:separator_index].strip()
        title = original_text[separator_index + 3:].strip()
        
        # Проверяем что код не слишком длинный (обычно коды короткие)
        if len(code) <= 10 and code and title:
            return code, title
        else:
            # Если "код" слишком длинный, вероятно это не настоящий разделитель
            return "", original_text
    
    # Пытаемся найти код в начале строки (буквы и цифры)
    code_match = re.match(r'^([A-Za-z0-9]{1,10})\s+(.+)', original_text)
    if code_match:
        code = code_match.group(1)
        title = code_match.group(2).strip()
        
        # Проверяем что title не является просто продолжением кода
        if title and len(title) > 3:  # Минимальная длина для осмысленного названия
            return code, title
    
    # Если не смогли разделить на код и название, возвращаем весь текст как название
    # Но проверяем, что это не слишком короткий фрагмент
    if len(original_text) >= 3:  # Минимальная длина для осмысленной опции
        return "", original_text
    else:
        # Слишком короткий текст, вероятно артефакт
        logger.debug(f"⚠️ Пропущен слишком короткий фрагмент: '{original_text}'")
        return "", ""


def extract_sections_from_container(content_container):
    """Универсально извлекает секции из контейнера если они есть"""
    sections = []
    errors = []
    
    try:
        section_selectors = [
            "div.model-options-sub-page-title",
            "div[class*='sub-page-title']",
            "div[id*='sub-page-title']"
        ]
        
        section_elements = []
        for selector in section_selectors:
            try:
                found_sections = content_container.find_elements(By.CSS_SELECTOR, selector)
                if found_sections:
                    section_elements.extend(found_sections)
                    logger.debug(f"🔍 Найдено {len(found_sections)} секций через селектор: {selector}")
            except Exception as e:
                logger.debug(f"⚠️ Ошибка поиска секций через {selector}: {e}")
                continue
        
        unique_sections = []
        seen_texts = set()
        
        for section_el in section_elements:
            try:
                section_text = section_el.text.strip()
                if section_text and section_text not in seen_texts:
                    unique_sections.append({
                        "element": section_el,
                        "text": section_text
                    })
                    seen_texts.add(section_text)
                    logger.debug(f"📋 Найдена секция: '{section_text}'")
            except Exception as e:
                errors.append(f"Ошибка обработки секции: {e}")
                continue
        
        sections = unique_sections
        
    except Exception as e:
        error_msg = f"Ошибка извлечения секций: {e}"
        logger.warning(f"⚠️ {error_msg}")
        errors.append(error_msg)
    
    logger.info(f"📋 Извлечено {len(sections)} секций, ошибок: {len(errors)}")
    return sections, errors


def extract_azt_options_from_container(content_container):
    """Извлекает опции AZT зоны с универсальными селекторами"""
    options = []
    errors = []
    
    try:
        logger.info("🔧 Проверяем наличие AZT зоны...")
        
        # Сначала ищем основной контейнер AZT
        azt_containers = []
        azt_selectors = [
            "#paint-system-options",
            "#azt-paint-system-options", 
            "div[id*='paint-system']",
            "div[id*='azt']"
        ]
        
        for container_selector in azt_selectors:
            try:
                containers = content_container.find_elements(By.CSS_SELECTOR, container_selector)
                if containers:
                    azt_containers.extend(containers)
                    logger.info(f"🎯 Найден AZT контейнер через: {container_selector}")
                    break
            except:
                continue
        
        if not azt_containers:
            logger.debug("ℹ️ AZT контейнер не найден")
            return options, errors
        
        # Ищем список AZT опций
        li_elements = []
        for container in azt_containers:
            try:
                # Основной селектор из HTML пользователя
                ul_elements = container.find_elements(By.CSS_SELECTOR, "ul.ps-azt-list")
                for ul in ul_elements:
                    li_elements.extend(ul.find_elements(By.TAG_NAME, "li"))
                    
                if li_elements:
                    logger.info(f"🎯 Найдено {len(li_elements)} AZT опций в ul.ps-azt-list")
                    break
                else:
                    # Fallback селекторы
                    fallback_selectors = [
                        "ul[class*='azt-list'] li",
                        "ul[class*='azt'] li", 
                        "li[class*='azt']"
                    ]
                    for fallback in fallback_selectors:
                        try:
                            li_elements = container.find_elements(By.CSS_SELECTOR, fallback)
                            if li_elements:
                                logger.info(f"🎯 Найдено {len(li_elements)} AZT опций через fallback: {fallback}")
                                break
                        except:
                            continue
                    if li_elements:
                        break
            except Exception as e:
                logger.debug(f"⚠️ Ошибка поиска в AZT контейнере: {e}")
                continue
        
        if not li_elements:
            logger.info("ℹ️ AZT опции не найдены")
            return options, errors
        
        logger.info(f"🔧 Обрабатываем {len(li_elements)} AZT элементов")
        
        for i, li in enumerate(li_elements):
            try:
                # Ищем описание опции
                description_text = ""
                description_selectors = [
                    "div.ps-azt-description-text",
                    "div[class*='description-text']",
                    "div[class*='azt-description']"
                ]
                
                for desc_selector in description_selectors:
                    try:
                        desc_element = li.find_element(By.CSS_SELECTOR, desc_selector)
                        description_text = desc_element.text.strip()
                        if description_text:
                            break
                    except:
                        continue
                
                if not description_text:
                    error_msg = f"AZT элемент {i+1}: не найдено описание"
                    logger.debug(f"⚠️ {error_msg}")
                    errors.append(error_msg)
                    continue
                
                # Ищем статус чекбокса
                is_selected = False
                checkbox_selectors = [
                    "input[type='checkbox']",
                    "input[type='checkbox'].toggle-input", 
                    "span.ps-azt-checkbox-container input[type='checkbox']",
                    "label.toggle input[type='checkbox']"
                ]
                
                for cb_selector in checkbox_selectors:
                    try:
                        checkbox = li.find_element(By.CSS_SELECTOR, cb_selector)
                        # Проверяем и атрибут checked и свойство checked
                        checked_attr = checkbox.get_attribute("checked")
                        checked_prop = checkbox.get_property("checked")
                        is_selected = checked_attr is not None or checked_prop
                        logger.debug(f"AZT опция {i+1}: checked_attr={checked_attr}, checked_prop={checked_prop}, selected={is_selected}")
                        break
                    except Exception as cb_error:
                        logger.debug(f"⚠️ AZT элемент {i+1}, селектор {cb_selector}: {cb_error}")
                        continue
                
                # Добавляем опцию с префиксом AZT
                options.append({
                    "code": "",
                    "title": f"AZT - {description_text}",
                    "selected": is_selected,
                    "source": "azt_zone"
                })
                
                status_mark = "✅" if is_selected else "❌"
                logger.debug(f"{status_mark} AZT опция {i+1}: AZT - {description_text}")
                
            except Exception as e:
                error_msg = f"AZT элемент {i+1}: {e}"
                logger.warning(f"⚠️ {error_msg}")
                errors.append(error_msg)
                continue
        
        logger.info(f"✅ Извлечено {len(options)} AZT опций, ошибок: {len(errors)}")
        
    except Exception as e:
        error_msg = f"Критическая ошибка извлечения AZT: {e}"
        logger.error(f"❌ {error_msg}")
        errors.append(error_msg)
    
    return options, errors


def extract_predefined_options_from_container(content_container):
    """Извлекает предустановленные опции из контейнера predefined-model-options"""
    options = []
    errors = []
    
    try:
        logger.info("🔧 Проверяем наличие предустановленных опций...")
        
        # Ищем контейнер предустановленных опций
        predefined_containers = []
        predefined_selectors = [
            "#predefined-model-options",
            "div[id*='predefined-model-options']",
            "div[class*='predefined-model-options']"
        ]
        
        for container_selector in predefined_selectors:
            try:
                containers = content_container.find_elements(By.CSS_SELECTOR, container_selector)
                if containers:
                    predefined_containers.extend(containers)
                    logger.info(f"🎯 Найден контейнер предустановленных опций через: {container_selector}")
                    break
            except:
                continue
        
        if not predefined_containers:
            logger.debug("ℹ️ Контейнер предустановленных опций не найден")
            return options, errors
        
        # Ищем опции в контейнере
        option_elements = []
        for container in predefined_containers:
            try:
                # Ищем стандартные элементы опций
                option_selectors = [
                    "div.model-option",
                    "div[class*='model-option']", 
                    "div[class*='option']",
                    "li.model-option",
                    "li[class*='option']"
                ]
                
                for selector in option_selectors:
                    try:
                        found_options = container.find_elements(By.CSS_SELECTOR, selector)
                        if found_options:
                            option_elements.extend(found_options)
                            logger.info(f"🎯 Найдено {len(found_options)} предустановленных опций через: {selector}")
                    except:
                        continue
                        
                if option_elements:
                    break
                    
            except Exception as e:
                logger.debug(f"⚠️ Ошибка поиска в контейнере предустановленных опций: {e}")
                continue
        
        if not option_elements:
            logger.info("ℹ️ Предустановленные опции не найдены в контейнере")
            return options, errors
        
        logger.info(f"🔧 Обрабатываем {len(option_elements)} элементов предустановленных опций")
        
        # Обрабатываем каждый элемент
        for i, element in enumerate(option_elements):
            try:
                option_data, element_errors = extract_option_from_element(element, "predefined")
                errors.extend(element_errors)
                
                if option_data:
                    options.append(option_data)
                    logger.debug(f"✅ Предустановленная опция {i+1}: {option_data.get('title', 'БЕЗ НАЗВАНИЯ')}")
                
            except Exception as e:
                error_msg = f"Предустановленная опция {i+1}: {e}"
                logger.warning(f"⚠️ {error_msg}")
                errors.append(error_msg)
                continue
        
        logger.info(f"✅ Извлечено {len(options)} предустановленных опций, ошибок: {len(errors)}")
        
    except Exception as e:
        error_msg = f"Критическая ошибка извлечения предустановленных опций: {e}"
        logger.error(f"❌ {error_msg}")
        errors.append(error_msg)
    
    return options, errors


def extract_regular_options_from_container(content_container):
    """Специальная функция для извлечения опций из regular-options секции"""
    options = []
    errors = []
    
    try:
        logger.info("🔧 Проверяем наличие regular-options секции...")
        
        # Ищем контейнер regular-options
        regular_options_container = None
        regular_selectors = [
            "#regular-options",
            "div#regular-options",
            "div[class*='regular-options']"
        ]
        
        for container_selector in regular_selectors:
            try:
                containers = content_container.find_elements(By.CSS_SELECTOR, container_selector)
                if containers:
                    regular_options_container = containers[0]
                    logger.info(f"🎯 Найден контейнер regular-options через: {container_selector}")
                    break
            except:
                continue
        
        if not regular_options_container:
            logger.debug("ℹ️ Контейнер regular-options не найден")
            return options, errors
        
        # Ищем все элементы с классом isolated-model-option-in-group
        isolated_elements = regular_options_container.find_elements(By.CSS_SELECTOR, "div.isolated-model-option-in-group")
        logger.info(f"🔍 Найдено {len(isolated_elements)} элементов isolated-model-option-in-group")
        
        # Если не найдено, ищем по другим селекторам
        if not isolated_elements:
            isolated_elements = regular_options_container.find_elements(By.XPATH, ".//*[contains(@class, 'isolated-model-option-in-group')]")
            logger.info(f"🔍 Найдено {len(isolated_elements)} элементов через XPath")
        
        # Если все еще не найдено, ищем по id начинающимся с 's-'
        if not isolated_elements:
            isolated_elements = regular_options_container.find_elements(By.XPATH, ".//*[starts-with(@id, 's-')]")
            logger.info(f"🔍 Найдено {len(isolated_elements)} элементов с id начинающимся с 's-'")
        
        if not isolated_elements:
            logger.warning("⚠️ Не найдено элементов опций в regular-options")
            return options, errors
        
        logger.info(f"🔧 Обрабатываем {len(isolated_elements)} элементов regular-options")
        
        # Логируем первые несколько элементов для диагностики
        logger.info(f"📊 Первые элементы regular-options:")
        for i, elem in enumerate(isolated_elements[:3]):
            elem_class = elem.get_attribute("class") or ""
            elem_id = elem.get_attribute("id") or ""
            elem_text = elem.text.strip()[:50] if elem.text else ""
            logger.info(f"    {i+1}. class='{elem_class}' id='{elem_id}' text='{elem_text}'")
        
        # Обрабатываем каждый элемент
        for i, element in enumerate(isolated_elements):
            # Человеческая пауза при обработке regular опций
            batch_processing_pause(i, len(isolated_elements), "regular опций")
            
            try:
                option_data, element_errors = extract_option_from_element(element, "regular")
                errors.extend(element_errors)
                
                if option_data:
                    options.append(option_data)
                    logger.debug(f"✅ Regular опция {i+1}: {option_data.get('title', 'БЕЗ НАЗВАНИЯ')}")
                
            except Exception as e:
                error_msg = f"Regular опция {i+1}: {e}"
                logger.warning(f"⚠️ {error_msg}")
                errors.append(error_msg)
                continue
        
        logger.info(f"✅ Извлечено {len(options)} regular опций, ошибок: {len(errors)}")
        
    except Exception as e:
        error_msg = f"Критическая ошибка извлечения regular опций: {e}"
        logger.error(f"❌ {error_msg}")
        errors.append(error_msg)
    
    return options, errors


def find_all_option_elements_in_container(content_container):
    """Универсально находит все возможные элементы опций в контейнере"""
    option_elements = []
    errors = []
    
    try:
        logger.debug("🔍 Начинаем поиск элементов опций в контейнере...")
        
        option_selectors = [
            "div.model-option",
            "div[class*='model-option']",
            "div[class*='option']",
            "*[class*='model-option']",
            # Добавляем селекторы для isolated-model-option-in-group
            "div.isolated-model-option-in-group",
            "div[class*='isolated-model-option-in-group']",
            "*[class*='isolated-model-option-in-group']",
            # Добавляем селекторы для всех возможных типов опций
            "div[id^='s-']",
            "div[data-value]",
            "div[data-parent]",
            # Добавляем селекторы для элементов с model-option-description
            "div:has(span.model-option-description)",
            "div:has(span[class*='option-description'])",
            # Добавляем селекторы для элементов в model-option-group
            "div.model-option-group div[class*='model-option']",
            "div.model-option-group div[class*='option']",
            # Добавляем селекторы для элементов в model-option-sub-group-content
            "div.model-option-sub-group-content div[class*='model-option']",
            "div.model-option-sub-group-content div[class*='option']"
        ]
        
        for selector in option_selectors:
            try:
                logger.debug(f"🔍 Ищем элементы через селектор: {selector}")
                found_elements = content_container.find_elements(By.CSS_SELECTOR, selector)
                
                new_elements = 0
                for element in found_elements:
                    if element not in option_elements:
                        option_elements.append(element)
                        new_elements += 1
                
                logger.debug(f"🔍 Селектор '{selector}': найдено {len(found_elements)} элементов, новых: {new_elements}")
                    
            except Exception as e:
                error_msg = f"Ошибка поиска через {selector}: {e}"
                logger.debug(f"⚠️ {error_msg}")
                errors.append(error_msg)
                continue
        
        logger.info(f"🔍 Всего найдено {len(option_elements)} уникальных элементов опций")
        
        if len(option_elements) == 0:
            # Дополнительная диагностика если ничего не найдено
            logger.warning("⚠️ Не найдено элементов опций, выполняем дополнительную диагностику...")
            
            try:
                # Ищем все div элементы
                all_divs = content_container.find_elements(By.TAG_NAME, "div")
                logger.warning(f"    📊 Всего div элементов в контейнере: {len(all_divs)}")
                
                # Ищем элементы с class содержащим 'option'
                option_like = content_container.find_elements(By.XPATH, ".//*[contains(@class, 'option')]")
                logger.warning(f"    📊 Элементов с 'option' в классе: {len(option_like)}")
                
                # Ищем элементы с class содержащим 'model'
                model_like = content_container.find_elements(By.XPATH, ".//*[contains(@class, 'model')]")
                logger.warning(f"    📊 Элементов с 'model' в классе: {len(model_like)}")
                
                # Ищем элементы с class содержащим 'isolated'
                isolated_like = content_container.find_elements(By.XPATH, ".//*[contains(@class, 'isolated')]")
                logger.warning(f"    📊 Элементов с 'isolated' в классе: {len(isolated_like)}")
                
                # Ищем элементы с id начинающимся с 's-'
                s_id_elements = content_container.find_elements(By.XPATH, ".//*[starts-with(@id, 's-')]")
                logger.warning(f"    📊 Элементов с id начинающимся с 's-': {len(s_id_elements)}")
                
                # Ищем элементы с data-value
                data_value_elements = content_container.find_elements(By.XPATH, ".//*[@data-value]")
                logger.warning(f"    📊 Элементов с data-value: {len(data_value_elements)}")
                
                # Показываем первые несколько div элементов
                logger.warning("    📊 Первые 5 div элементов:")
                for i, div in enumerate(all_divs[:5]):
                    div_class = div.get_attribute("class") or ""
                    div_id = div.get_attribute("id") or ""
                    div_text = div.text.strip()[:50] if div.text else ""
                    logger.warning(f"        {i+1}. class='{div_class}' id='{div_id}' text='{div_text}'")
                    
                # Показываем элементы с isolated в классе
                if isolated_like:
                    logger.warning("    📊 Элементы с 'isolated' в классе:")
                    for i, elem in enumerate(isolated_like[:3]):
                        elem_class = elem.get_attribute("class") or ""
                        elem_id = elem.get_attribute("id") or ""
                        elem_text = elem.text.strip()[:50] if elem.text else ""
                        logger.warning(f"        {i+1}. class='{elem_class}' id='{elem_id}' text='{elem_text}'")
                        
            except Exception as diag_error:
                logger.warning(f"⚠️ Ошибка диагностики: {diag_error}")
        
    except Exception as e:
        error_msg = f"Критическая ошибка поиска элементов опций: {e}"
        logger.error(f"❌ {error_msg}")
        errors.append(error_msg)
    
    return option_elements, errors


def extract_option_from_element(option_element, section_suffix=""):
    """Универсально извлекает данные опции из элемента с улучшенной фильтрацией"""
    option_data = None
    errors = []
    
    try:
        class_attr = option_element.get_attribute("class") or ""
        is_selected = "selected" in class_attr
        
        option_text = ""
        text_selectors = [
            "span.model-option-description",
            "span[class*='option-description']", 
            "span[class*='description']",
            "*[class*='description']",
            # Добавляем селекторы для isolated-model-option-in-group
            "span.mo-white-space",
            "span[class*='white-space']",
            # Добавляем селекторы для всех возможных текстовых элементов
            "span",
            "div",
            "label"
        ]
        
        for text_selector in text_selectors:
            try:
                text_elements = option_element.find_elements(By.CSS_SELECTOR, text_selector)
                for text_element in text_elements:
                    candidate_text = text_element.text.strip()
                    if candidate_text and len(candidate_text) > 2:
                        option_text = candidate_text
                        break
                if option_text:
                    break
            except:
                continue
        
        if not option_text:
            try:
                option_text = option_element.text.strip()
                lines = option_text.split('\n')
                if lines:
                    option_text = lines[0].strip()
            except:
                pass
        
        if option_text:
            code, title = parse_option_code_title(option_text)
            
            # Логируем результат парсинга для диагностики
            logger.debug(f"🔍 Парсинг: '{option_text}' -> код='{code}', название='{title}'")
            
            # Проверяем что у нас есть либо код либо осмысленное название
            if not code and not title:
                errors.append(f"Отфильтрован пустой результат парсинга: '{option_text}'")
                return None, errors
            
            # Проверяем на подозрительные короткие названия без кода
            if not code and title and len(title) < 5:
                suspicious_words = ["кпп", "лкп", "бензин", "дизель", "газ", "акп", "мкп"]
                if title.lower() in suspicious_words:
                    errors.append(f"Отфильтровано подозрительное короткое название: '{title}'")
                    return None, errors
            
            final_title = f"{title}_{section_suffix}" if section_suffix and title else title
            
            # Проверяем финальное название на осмысленность
            if final_title and len(final_title.replace("_", " ").strip()) >= 3:
                option_data = {
                    "code": code,
                    "title": final_title,
                    "selected": is_selected,
                    "source": "regular_option"
                }
                
                status_mark = "✅" if is_selected else "❌"
                logger.debug(f"{status_mark} Опция: {code} - {final_title}")
            else:
                errors.append(f"Отфильтровано слишком короткое финальное название: '{final_title}'")
        else:
            errors.append("Не найден текст опции")
            
    except Exception as e:
        error_msg = f"Ошибка извлечения опции: {e}"
        logger.debug(f"⚠️ {error_msg}")
        errors.append(error_msg)
    
    return option_data, errors


def extract_options_with_sections(content_container, sections):
    """Извлекает опции сгруппированные по секциям"""
    options = []
    errors = []
    
    try:
        logger.info(f"🔧 Извлекаем опции по секциям (найдено {len(sections)} секций)")
        
        for section in sections:
            section_name = section["text"]
            section_element = section["element"]
            
            try:
                next_elements = []
                current = section_element
                
                while True:
                    try:
                        current = current.find_element(By.XPATH, "following-sibling::*[1]")
                        
                        current_class = current.get_attribute("class") or ""
                        if any(sec_class in current_class for sec_class in ["sub-page-title", "section-title"]):
                            break
                        
                        next_elements.append(current)
                        
                        if len(next_elements) > 20:
                            break
                            
                    except:
                        break
                
                section_option_count = 0
                for element in next_elements:
                    try:
                        inner_option_elements, inner_errors = find_all_option_elements_in_container(element)
                        errors.extend(inner_errors)
                        
                        for option_element in inner_option_elements:
                            option_data, option_errors = extract_option_from_element(option_element, section_name)
                            errors.extend(option_errors)
                            
                            if option_data is not None:  # Проверяем на None
                                options.append(option_data)
                                section_option_count += 1
                            else:
                                logger.debug(f"⚠️ Опция отфильтрована в секции '{section_name}'")
                                
                    except Exception as e:
                        error_msg = f"Ошибка обработки элемента в секции '{section_name}': {e}"
                        logger.debug(f"⚠️ {error_msg}")
                        errors.append(error_msg)
                        continue
                
                logger.info(f"📋 Секция '{section_name}': найдено {section_option_count} валидных опций")
                
            except Exception as e:
                error_msg = f"Ошибка обработки секции '{section_name}': {e}"
                logger.warning(f"⚠️ {error_msg}")
                errors.append(error_msg)
                continue
        
    except Exception as e:
        error_msg = f"Критическая ошибка извлечения опций по секциям: {e}"
        logger.error(f"❌ {error_msg}")
        errors.append(error_msg)
    
    return options, errors


def extract_options_without_sections(content_container):
    """Извлекает опции без группировки по секциям"""
    options = []
    errors = []
    
    try:
        logger.info("🔧 Извлекаем опции без секций")
        
        option_elements, search_errors = find_all_option_elements_in_container(content_container)
        errors.extend(search_errors)
        
        valid_count = 0
        for i, option_element in enumerate(option_elements):
            # Человеческая пауза при массовой обработке опций
            batch_processing_pause(i, len(option_elements), "опций")
            
            option_data, option_errors = extract_option_from_element(option_element)
            errors.extend(option_errors)
            
            if option_data is not None:  # Проверяем на None
                options.append(option_data)
                valid_count += 1
            else:
                logger.debug(f"⚠️ Элемент опции {i+1}: отфильтрован")
        
        logger.info(f"✅ Извлечено {valid_count} валидных опций без секций (из {len(option_elements)} элементов)")
        
    except Exception as e:
        error_msg = f"Критическая ошибка извлечения опций без секций: {e}"
        logger.error(f"❌ {error_msg}")
        errors.append(error_msg)
    
    return options, errors


def extract_zone_options_universal(driver, zone):
    """Универсальная функция извлечения опций из любой зоны с обобщенным алгоритмом"""
    logger.info(f"🔧 Обрабатываем зону: '{zone['title']}'")
    logger.info(f"    📍 ID зоны: {zone.get('id', 'НЕТ')}")
    logger.info(f"    📍 Data-value: {zone.get('data_value', 'НЕТ')}")
    
    options = []
    all_errors = []
    processing_notes = []
    
    try:
        if not ensure_in_iframe(driver):
            error_msg = f"Не удалось переключиться в iframe для зоны '{zone['title']}'"
            logger.error(f"❌ {error_msg}")
            return [], [error_msg], [f"КРИТИЧЕСКАЯ ОШИБКА: {error_msg}"]
        
        logger.info(f"✅ Кликаем по зоне '{zone['title']}'...")
        
        # Человеческий клик с паузами и движением мыши
        human_click(driver, zone['element'], f"зону '{zone['title']}'")
        logger.debug(f"✅ Человеческий клик по зоне '{zone['title']}' выполнен")
        
        logger.info(f"🔄 Ожидаем загрузку контента для зоны '{zone['title']}'...")
        
        # Имитируем человеческое ожидание загрузки
        reading_pause()
        
        content_container = wait_for_content_loaded(driver)
        logger.info(f"✅ Контент загружен для зоны '{zone['title']}'")
        
        # Логируем основную информацию о контейнере
        try:
            container_class = content_container.get_attribute("class") or ""
            container_id = content_container.get_attribute("id") or ""
            logger.info(f"📊 Контейнер контента: ID='{container_id}', CLASS='{container_class}'")
            
            # Логируем количество дочерних элементов
            child_elements = content_container.find_elements(By.XPATH, "./*")
            logger.info(f"📊 Дочерних элементов в контейнере: {len(child_elements)}")
            
            # Логируем первые несколько дочерних элементов для диагностики
            for i, child in enumerate(child_elements[:5]):
                child_tag = child.tag_name
                child_class = child.get_attribute("class") or ""
                child_id = child.get_attribute("id") or ""
                logger.debug(f"    {i+1}. <{child_tag}> id='{child_id}' class='{child_class}'")
                
        except Exception as log_error:
            logger.warning(f"⚠️ Ошибка логирования контейнера: {log_error}")
        
        # Проверяем на пустую зону
        try:
            no_options_msg = content_container.find_element(By.CSS_SELECTOR, "#model-option-group-message")
            if "Нет соответствующих модельных опций для данной зоны" in no_options_msg.text:
                logger.info(f"ℹ️ Зона '{zone['title']}': пустая зона")
                return [{
                    "code": "",
                    "title": "Нет соответствующих модельных опций для данной зоны",
                    "selected": False,
                    "source": "empty_zone"
                }], [], ["Зона пустая - содержит официальное сообщение об отсутствии опций"]
        except NoSuchElementException:
            logger.debug(f"✅ Зона '{zone['title']}': НЕ пустая (сообщение об отсутствии опций не найдено)")
        
        # Проверяем на зону "Все выбранные опции"
        if zone.get('id') == 'model-options-section-all-selected' or 'all-selected' in zone.get('id', ''):
            logger.info(f"🎯 Зона '{zone['title']}': обрабатываем как 'Все выбранные опции'")
            all_selected_options, all_selected_errors = extract_all_selected_options_from_container(content_container)
            all_errors.extend(all_selected_errors)
            
            if all_selected_options:
                logger.info(f"✅ Зона '{zone['title']}': обработана как 'Все выбранные опции'")
                processing_notes.append("Обработано как зона 'Все выбранные опции'")
                return all_selected_options, all_errors, processing_notes
            else:
                logger.warning(f"⚠️ Зона '{zone['title']}': не найдены выбранные опции")
        


        # Проверяем на AZT зону
        logger.info(f"🔍 Проверяем зону '{zone['title']}' на AZT...")
        azt_options, azt_errors = extract_azt_options_from_container(content_container)
        all_errors.extend(azt_errors)
        
        if azt_options:
            logger.info(f"✅ Зона '{zone['title']}': обработана как AZT зона")
            processing_notes.append("Обработано как AZT зона")
            return azt_options, all_errors, processing_notes
        else:
            logger.info(f"ℹ️ Зона '{zone['title']}': НЕ AZT зона")
        
        # Ищем секции
        logger.info(f"🔍 Ищем секции в зоне '{zone['title']}'...")
        sections, section_errors = extract_sections_from_container(content_container)
        all_errors.extend(section_errors)
        logger.info(f"🔍 Найдено секций в зоне '{zone['title']}': {len(sections)}")
        
        if sections:
            for i, section in enumerate(sections):
                logger.info(f"    📋 Секция {i+1}: '{section['text']}'")
        
        # Извлекаем опции
        if sections:
            logger.info(f"🔧 Извлекаем опции по секциям для зоны '{zone['title']}'...")
            section_options, section_option_errors = extract_options_with_sections(content_container, sections)
            all_errors.extend(section_option_errors)
            options.extend(section_options)
            processing_notes.append(f"Обработано {len(sections)} секций с опциями")
            logger.info(f"📋 Извлечено {len(section_options)} опций из секций в зоне '{zone['title']}'")
        else:
            # Ищем опции без секций (только если секции не найдены)
            logger.info(f"🔧 Ищем опции без секций в зоне '{zone['title']}'...")
            regular_options, regular_errors = extract_regular_options_from_container(content_container)
            all_errors.extend(regular_errors)
            options.extend(regular_options)
            processing_notes.append("Обработано как зона без секций")
            logger.info(f"📋 Извлечено {len(regular_options)} опций без секций в зоне '{zone['title']}'")
        
        # Удаляем дубликаты по полному совпадению title и code
        initial_count = len(options)
        unique_options = []
        seen_combinations = set()
        
        for option in options:
            # Создаем уникальный ключ из комбинации code и title
            option_key = (option.get("code", ""), option.get("title", ""))
            
            if option_key not in seen_combinations:
                unique_options.append(option)
                seen_combinations.add(option_key)
            else:
                logger.debug(f"🔄 Удален дубликат: {option.get('code', '')} - {option.get('title', '')}")
        
        # Заменяем options на уникальные
        options = unique_options
        duplicates_removed = initial_count - len(options)
        if duplicates_removed > 0:
            logger.info(f"🔄 Удалено дубликатов в зоне '{zone['title']}': {duplicates_removed}")
        
        # Финальная статистика
        total_found = len(options)
        error_count = len(all_errors)
        
        if total_found > 0:
            logger.info(f"✅ Зона '{zone['title']}': извлечено {total_found} уникальных опций, ошибок: {error_count}")
            processing_notes.append(f"Успешно извлечено {total_found} уникальных опций")
            
            # Логируем первые несколько опций для подтверждения
            logger.info(f"📋 Первые опции в зоне '{zone['title']}':")
            for i, option in enumerate(options[:3]):
                status = "✅" if option.get("selected") else "❌"
                logger.info(f"    {i+1}. {status} {option.get('code', '')} - {option.get('title', '')}")
            if total_found > 3:
                logger.info(f"    ... и еще {total_found - 3} опций")
        else:
            warning_msg = f"Зона '{zone['title']}': опции не найдены"
            logger.warning(f"⚠️ {warning_msg}")
            processing_notes.append("НЕ НАЙДЕНО ОПЦИЙ - возможно новая неизвестная структура")
            
            # Дополнительная диагностика для пустых зон
            try:
                all_divs = content_container.find_elements(By.TAG_NAME, "div")
                all_spans = content_container.find_elements(By.TAG_NAME, "span")
                logger.warning(f"    🔍 Диагностика: найдено {len(all_divs)} div и {len(all_spans)} span элементов")
            except:
                pass
        
        if error_count > 0:
            processing_notes.append(f"Обнаружено {error_count} ошибок при обработке")
            logger.warning(f"⚠️ Зона '{zone['title']}': ошибок при обработке: {error_count}")
        
        return options, all_errors, processing_notes
        
    except (TimeoutException, WebDriverException) as e:
        error_msg = f"Критическая ошибка извлечения опций из зоны '{zone['title']}': {e}"
        logger.error(f"❌ {error_msg}")
        return [], [error_msg], [f"КРИТИЧЕСКАЯ ОШИБКА: {error_msg}"]


def extract_all_selected_options_from_container(content_container):
    """Специальная функция для извлечения опций из зоны 'Все выбранные опции'"""
    options = []
    errors = []
    
    try:
        logger.info("🔧 Обрабатываем зону 'Все выбранные опции'...")
        
        # Ищем контейнер с выбранными опциями
        all_selected_container = None
        selectors = [
            "#all-selected-options",
            "div.all-selected-options",
            "div[id*='all-selected']"
        ]
        
        for selector in selectors:
            try:
                containers = content_container.find_elements(By.CSS_SELECTOR, selector)
                if containers:
                    all_selected_container = containers[0]
                    logger.info(f"🎯 Найден контейнер выбранных опций через: {selector}")
                    break
            except:
                continue
        
        if not all_selected_container:
            logger.warning("⚠️ Контейнер выбранных опций не найден")
            return options, errors
        
        # Ищем все опции в контейнере
        option_containers = all_selected_container.find_elements(By.CSS_SELECTOR, "div.all-selected-container")
        logger.info(f"🔍 Найдено {len(option_containers)} контейнеров выбранных опций")
        
        # Дополнительная диагностика
        all_divs = all_selected_container.find_elements(By.TAG_NAME, "div")
        logger.info(f"🔍 Всего div элементов в контейнере: {len(all_divs)}")
        
        for i, option_container in enumerate(option_containers):
            try:
                # Логируем ID контейнера для диагностики
                container_id = option_container.get_attribute("id") or f"без-id-{i+1}"
                data_value = option_container.get_attribute("data-value") or "без-data-value"
                logger.debug(f"🔍 Обрабатываем контейнер {i+1}: id='{container_id}', data-value='{data_value}'")
                
                # Извлекаем категорию
                category = ""
                category_selectors = [
                    "span[id*='-category']",
                    "span[class*='category']"
                ]
                
                for cat_selector in category_selectors:
                    try:
                        category_element = option_container.find_element(By.CSS_SELECTOR, cat_selector)
                        category = category_element.text.strip()
                        if category:
                            logger.debug(f"✅ Найдена категория через '{cat_selector}': '{category}'")
                            break
                    except:
                        continue
                
                # Извлекаем описание опции
                description = ""
                description_selectors = [
                    "span[id*='-description']",
                    "span.model-option-description",
                    "span[class*='description']"
                ]
                
                for desc_selector in description_selectors:
                    try:
                        description_element = option_container.find_element(By.CSS_SELECTOR, desc_selector)
                        description = description_element.text.strip()
                        if description:
                            logger.debug(f"✅ Найдено описание через '{desc_selector}': '{description}'")
                            break
                    except:
                        continue
                
                if not description:
                    error_msg = f"Выбранная опция {i+1} (id: {container_id}): не найдено описание"
                    logger.warning(f"⚠️ {error_msg}")
                    
                    # Дополнительная диагностика для пропущенной опции
                    try:
                        all_spans = option_container.find_elements(By.TAG_NAME, "span")
                        logger.warning(f"    🔍 Найдено span элементов: {len(all_spans)}")
                        for j, span in enumerate(all_spans[:3]):
                            span_id = span.get_attribute("id") or ""
                            span_class = span.get_attribute("class") or ""
                            span_text = span.text.strip()[:50]
                            logger.warning(f"        {j+1}. id='{span_id}' class='{span_class}' text='{span_text}'")
                    except:
                        pass
                    
                    errors.append(error_msg)
                    continue
                
                if not category:
                    error_msg = f"Выбранная опция {i+1} (id: {container_id}): не найдена категория"
                    logger.warning(f"⚠️ {error_msg}")
                    errors.append(error_msg)
                    category = "Неизвестная категория"
                
                # Парсим код и название из описания
                code, title = parse_option_code_title(description)
                
                # Все опции в этой зоне выбраны
                option_data = {
                    "code": code,
                    "title": title,  # Только название без категории
                    "category": category,  # Категория отдельно
                    "selected": True,  # Все опции в "Все выбранные" всегда выбраны
                    "source": "all_selected_zone",
                    "original_description": description,
                    "container_id": container_id
                }
                
                options.append(option_data)
                
                logger.debug(f"✅ Выбранная опция {i+1}: {code} - {title} | Категория: {category}")
                
            except Exception as e:
                error_msg = f"Выбранная опция {i+1}: {e}"
                logger.warning(f"⚠️ {error_msg}")
                errors.append(error_msg)
                continue
        
        logger.info(f"✅ Извлечено {len(options)} выбранных опций, ошибок: {len(errors)}")
        
        if len(options) != len(option_containers):
            logger.warning(f"⚠️ ВНИМАНИЕ: Обработано {len(options)} из {len(option_containers)} найденных контейнеров")
            logger.warning(f"    💡 Проверьте логи выше на предмет ошибок обработки отдельных опций")
        
        # Подсчет опций по категориям для диагностики
        category_counts = {}
        for option in options:
            cat = option.get("category", "Без категории")
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        logger.info(f"📊 Распределение по категориям:")
        for cat, count in category_counts.items():
            logger.info(f"    {cat}: {count} опций")
        
    except Exception as e:
        error_msg = f"Критическая ошибка извлечения выбранных опций: {e}"
        logger.error(f"❌ {error_msg}")
        errors.append(error_msg)
    
    return options, errors


def collect_all_options_extended(driver):
    """Расширенная функция сбора всех опций со всех зон с детальной отчетностью"""
    logger.info("🎯 НАЧИНАЕМ РАСШИРЕННЫЙ СБОР ВСЕХ ОПЦИЙ")
        
    if not navigate_to_options(driver):
        return []
    
    all_zones_data = []
    zones = extract_option_zones(driver)
    
    if not zones:
        logger.error("❌ Не найдены зоны опций")
        return []
    
    for i, zone in enumerate(zones):
        # Пауза между переходами к разным зонам
        if i > 0:  # Не делаем паузу перед первой зоной
            section_transition_pause()
            
        zone_options, zone_errors, processing_notes = extract_zone_options_universal(driver, zone)
        
        zone_data = {
            "zone_title": zone["title"],
            "zone_id": zone["id"],
            "zone_type": "section",
            "data_value": zone.get("data_value", ""),
            "options": zone_options,
            "total_options": len(zone_options),
            "selected_count": sum(1 for opt in zone_options if opt["selected"]),
            "errors": zone_errors,
            "error_count": len(zone_errors),
            "processing_notes": processing_notes,
            "processing_status": "success" if zone_options and not zone_errors else "warning" if zone_options else "error"
        }
        
        all_zones_data.append(zone_data)
        
        status_emoji = "✅" if zone_data["processing_status"] == "success" else "⚠️" if zone_data["processing_status"] == "warning" else "❌"
        logger.info(f"{status_emoji} Зона '{zone['title']}': {zone_data['selected_count']}/{zone_data['total_options']} опций, ошибок: {zone_data['error_count']}")
        
        for note in processing_notes:
            logger.info(f"    📝 {note}")
        
        if zone_errors:
            logger.warning(f"    ⚠️ Ошибки в зоне '{zone['title']}':")
            for error in zone_errors[:3]:
                logger.warning(f"        • {error}")
            if len(zone_errors) > 3:
                logger.warning(f"        • ... и еще {len(zone_errors) - 3} ошибок")
        
        # Быстрая пауза между зонами
        fast_human_pause()
    
    total_zones = len(all_zones_data)
    total_options = sum(zone["total_options"] for zone in all_zones_data)
    total_selected = sum(zone["selected_count"] for zone in all_zones_data)
    total_errors = sum(zone.get("error_count", 0) for zone in all_zones_data)
    
    logger.info(f"🎯 РАСШИРЕННЫЙ СБОР ОПЦИЙ ЗАВЕРШЕН:")
    logger.info(f"    📊 Зон: {total_zones}")
    logger.info(f"    📋 Опций: {total_selected}/{total_options} выбрано")
    logger.info(f"    ⚠️ Ошибок: {total_errors}")
    
    return all_zones_data


def collect_all_options(driver):
    """Собирает все опции со всех зон (оригинальная функция для обратной совместимости)"""
    logger.info("🎯 НАЧИНАЕМ СБОР ВСЕХ ОПЦИЙ")
        
    if not navigate_to_options(driver):
        return []
    
    zones = extract_option_zones(driver)
    if not zones:
        logger.error("❌ Не найдены зоны опций")
        return []
    
    all_zones_data = []
    
    for i, zone in enumerate(zones):
        # Пауза между переходами к разным зонам
        if i > 0:  # Не делаем паузу перед первой зоной
            section_transition_pause()
            
        zone_options, zone_errors, processing_notes = extract_zone_options_universal(driver, zone)
        
        zone_data = {
            "zone_title": zone["title"],
            "zone_id": zone["id"],
            "options": zone_options,
            "total_options": len(zone_options),
            "selected_count": sum(1 for opt in zone_options if opt["selected"])
        }
        
        all_zones_data.append(zone_data)
        logger.info(f"📊 Зона '{zone['title']}': {zone_data['selected_count']}/{zone_data['total_options']} опций выбрано")
        
        # Быстрая пауза между зонами
        fast_human_pause()
    
    logger.info(f"🎯 СБОР ОПЦИЙ ЗАВЕРШЕН: обработано {len(all_zones_data)} зон")
    return all_zones_data


def process_vehicle_options(driver, claim_number="", vin=""):
    """Основная функция обработки опций автомобиля"""
    logger.info(f"🚗 Начинаем обработку опций для дела {claim_number}, VIN {vin}")
    
    try:
        options_data = collect_all_options_extended(driver)
        
        if not options_data:
            return {
                "success": False,
                "error": "Не удалось собрать данные опций",
                "zones": []
            }
        
        total_zones = len(options_data)
        total_options = sum(zone["total_options"] for zone in options_data)
        total_selected = sum(zone["selected_count"] for zone in options_data)
        total_errors = sum(zone.get("error_count", 0) for zone in options_data)
        
        result = {
            "success": True,
            "claim_number": claim_number,
            "vin": vin,
            "zones": options_data,
            "statistics": {
                "total_zones": total_zones,
                "total_options": total_options,
                "total_selected": total_selected,
                "total_errors": total_errors
            }
        }
        
        logger.info(f"✅ ОБРАБОТКА ОПЦИЙ ЗАВЕРШЕНА: {total_selected}/{total_options} опций выбрано в {total_zones} зонах, ошибок: {total_errors}")
        return result
        
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА при обработке опций: {e}")
        return {
            "success": False,
            "error": f"Критическая ошибка: {str(e)}",
            "zones": []
        }
    finally:
        try:
            driver.switch_to.default_content()
            logger.info("🔄 Возвращены к главному контенту после сбора опций")
        except Exception as switch_error:
            logger.warning(f"⚠️ Ошибка при возврате к главному контенту: {switch_error}") 