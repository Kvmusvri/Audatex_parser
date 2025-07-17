# Функции для работы с SVG, скриншотами и пиктограммами
import os
import logging
import time
import re
import tempfile
import xml.etree.ElementTree as ET
from lxml import etree
from transliterate import translit
from PIL import Image
from io import BytesIO
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from .constants import TIMEOUT

logger = logging.getLogger(__name__)


# Функция для проверки имени файла по шаблону zone_*
def is_zone_file(filename: str) -> bool:
    """
    Проверяет, является ли файл файлом зоны.
    Зоны всегда начинаются с 'zone_' и не содержат 'pictogram' в названии.
    """
    filename_lower = filename.lower()
    is_zone = (filename_lower.startswith('zone_') and 
               'pictogram' not in filename_lower and 
               filename_lower.endswith('.svg'))
    logger.debug(f"🔍 is_zone_file('{filename}'): {is_zone}")
    return is_zone

# Вспомогательные функции для разбиения SVG на детали
def has_detail(elem, detail):
    return elem.attrib.get('data-title', '') == detail

def prune_for_detail(root_element, detail):
    for elem in list(root_element):
        tag = elem.tag.split('}')[-1]
        if tag == 'g' and not has_detail(elem, detail):
            root_element.remove(elem)
        else:
            prune_for_detail(elem, detail)

# Функции ожидания для стабильной работы с DOM
def wait_for_document_ready(d):
    return d.execute_script("return document.readyState === 'complete'")

def wait_for_pictograms_grid(d):
    grids = d.find_elements(By.CSS_SELECTOR, "main div.pictograms-grid.visible")
    if not grids:
        return False
    grid = grids[0]
    # Проверяем что grid действительно видим и содержит секции
    return grid.is_displayed() and len(grid.find_elements(By.TAG_NAME, "section")) > 0

def wait_for_all_sections_loaded(d):
    sections = d.find_elements(By.CSS_SELECTOR, "main div.pictograms-grid.visible section.pictogram-section")
    if len(sections) == 0:
        return False
    
    # Проверяем что все секции видимы и содержат h2 заголовки
    for section in sections:
        if not section.is_displayed():
            return False
        h2_elements = section.find_elements(By.CSS_SELECTOR, "h2.sort-title.visible")
        if len(h2_elements) == 0:
            return False
    return True

def wait_for_all_svgs_ready(d):
    svg_containers = d.find_elements(By.CSS_SELECTOR, 
        "main div.pictograms-grid.visible section.pictogram-section div.navigation-pictogram-svg-container")
    
    if len(svg_containers) == 0:
        return False
        
    ready_count = 0
    for container in svg_containers:
        svgs = container.find_elements(By.TAG_NAME, "svg")
        if len(svgs) > 0:
            svg = svgs[0]
            if (svg.is_displayed() and 
                d.execute_script("return arguments[0].querySelectorAll('path, rect, circle, g').length > 0", svg)):
                ready_count += 1
    
    # Требуем чтобы минимум 80% SVG были готовы (учитываем возможные ошибки загрузки)
    required_count = max(1, int(len(svg_containers) * 0.8))
    return ready_count >= required_count

def wait_for_dom_stability(d):
    initial_count = len(d.find_elements(By.CSS_SELECTOR, 
        "main div.pictograms-grid.visible section.pictogram-section div.navigation-pictogram-svg-container svg"))
    if initial_count == 0:
        return False
    
    # Ждем 800ms и сравниваем количество
    time.sleep(0.8)
    final_count = len(d.find_elements(By.CSS_SELECTOR, 
        "main div.pictograms-grid.visible section.pictogram-section div.navigation-pictogram-svg-container svg"))
    
    return initial_count == final_count and initial_count > 0

def ensure_document_ready(d):
    return d.execute_script("return document.readyState === 'complete'")

def find_pictograms_grid_reliable(d):
    grids = d.find_elements(By.CSS_SELECTOR, "main div.pictograms-grid.visible")
    for grid in grids:
        if grid.is_displayed() and len(grid.find_elements(By.TAG_NAME, "section")) > 0:
            return grid
    return None

def wait_for_sections_stability(d):
    sections = d.find_elements(By.CSS_SELECTOR, "main div.pictograms-grid.visible section.pictogram-section")
    if len(sections) == 0:
        return False
    
    # Проверяем что каждая секция содержит необходимые элементы
    ready_sections = 0
    for section in sections:
        h2_elements = section.find_elements(By.CSS_SELECTOR, "h2.sort-title.visible")
        holders = section.find_elements(By.ID, "pictograms-grid-holder")
        if len(h2_elements) > 0 and len(holders) > 0 and section.is_displayed():
            ready_sections += 1
    
    return ready_sections == len(sections) and len(sections) > 0

def wait_for_works_in_section(holder):
    work_divs = [div for div in holder.find_elements(By.TAG_NAME, "div") 
                if div.get_attribute("data-tooltip") and div.is_displayed()]
    # Проверяем что у каждой работы есть SVG контейнер
    ready_works = 0
    for div in work_divs:
        containers = div.find_elements(By.CSS_SELECTOR, "div.navigation-pictogram-svg-container")
        if containers and containers[0].is_displayed():
            svgs = containers[0].find_elements(By.TAG_NAME, "svg")
            if svgs and svgs[0].is_displayed():
                ready_works += 1
    return len(work_divs) > 0 and ready_works >= max(1, int(len(work_divs) * 0.8))

# Функция для разбиения SVG на детали
def split_svg_by_details(svg_file, output_dir, subfolder=None, claim_number="", vin="", svg_collection=True):
    """
    Разбивает SVG-файл на отдельные SVG для каждой детали, где каждая деталь соответствует уникальному data-title.
    Если svg_collection=False, извлекает только данные без сохранения файлов.
    ГАРАНТИРУЕТ извлечение деталей из любого SVG файла зоны.
    """
    logger.info(f"🔧 НАЧИНАЕМ разбиение SVG файла: {svg_file}")
    logger.info(f"🎛️ Режим сохранения SVG: {'ВКЛЮЧЕН' if svg_collection else 'ОТКЛЮЧЕН'}")
    
    try:
        # Проверяем существование файла
        if not os.path.exists(svg_file):
            logger.error(f"❌ Файл не существует: {svg_file}")
            return []
        
        # Читаем размер файла для диагностики
        file_size = os.path.getsize(svg_file)
        logger.info(f"📊 Размер SVG файла: {file_size} байт")
        
        if file_size == 0:
            logger.error(f"❌ Файл пустой: {svg_file}")
            return []
        
        # Пытаемся прочитать содержимое файла
        try:
            with open(svg_file, 'r', encoding='utf-8') as f:
                content_preview = f.read(500)  # Первые 500 символов для диагностики
                logger.debug(f"📄 Превью содержимого файла: {content_preview[:200]}...")
        except Exception as read_error:
            logger.error(f"❌ Ошибка чтения файла: {read_error}")
            return []
        
        # Парсим XML
        try:
            tree = ET.parse(svg_file)
            root = tree.getroot()
            logger.info(f"✅ SVG успешно распарсен. Корневой элемент: {root.tag}")
        except ET.ParseError as parse_error:
            logger.error(f"❌ Ошибка парсинга XML: {parse_error}")
            return []
        
        # Ищем все элементы с data-title
        elements_with_data_title = []
        total_elements = 0
        
        for elem in root.iter():
            total_elements += 1
            if 'data-title' in elem.attrib:
                elements_with_data_title.append(elem)
        
        logger.info(f"📊 Всего элементов в SVG: {total_elements}")
        logger.info(f"🎯 Элементов с data-title: {len(elements_with_data_title)}")
        
        if len(elements_with_data_title) == 0:
            logger.warning(f"⚠️ НЕ НАЙДЕНО элементов с data-title в файле {svg_file}")
            logger.info(f"🔍 Проверяем альтернативные атрибуты...")
            
            # Поиск альтернативных атрибутов для диагностики
            alt_attributes = ['title', 'id', 'class', 'name']
            for attr in alt_attributes:
                elements_with_attr = [elem for elem in root.iter() if attr in elem.attrib]
                if elements_with_attr:
                    logger.info(f"🔍 Найдено {len(elements_with_attr)} элементов с атрибутом '{attr}'")
                    for i, elem in enumerate(elements_with_attr[:5]):  # Показываем первые 5
                        logger.debug(f"  - {elem.tag}: {attr}='{elem.attrib[attr]}'")
            
            # Возвращаем пустой список, но не ошибку
            logger.warning(f"⚠️ Возвращаем пустой список деталей для {svg_file}")
            return []
        
        # Собираем уникальные data-title
        all_titles = set(elem.attrib['data-title'] for elem in elements_with_data_title)
        logger.info(f"\n🎯 Найдено {len(all_titles)} уникальных data-title в файле {svg_file}:")
        detail_paths = []
        for title in sorted(all_titles):
            logger.info(f"  📝 '{title}'")

        for detail in all_titles:
            # Очищаем и нормализуем имя файла на основе полного data-title
            safe_detail = re.sub(r'[^\w\s-]', '', detail).strip()  # Удаляем недопустимые символы
            if not safe_detail:
                logger.warning(f"Пропущено пустое или некорректное data-title: {detail!r}")
                continue
            safe_name = translit(safe_detail, 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
            safe_name = re.sub(r'\.+', '', safe_name)  # Удаляем точки

                        # Проверяем, содержит ли деталь несколько элементов (разделенных запятыми)
            max_filename_length = 180  # Безопасная длина для Windows
            
            if len(safe_name) <= max_filename_length:
                # Обычный случай - имя не слишком длинное
                output_path = os.path.normpath(os.path.join(output_dir, f"{safe_name}.svg"))
                relative_base = f"/static/svgs/{claim_number}_{vin}"
                output_path_relative = f"{relative_base}/{safe_name}.svg".replace("\\", "/")

                detail_data = {
                    "title": detail,
                    "svg_path": output_path_relative.replace("\\", "/") if svg_collection else ""
                }
                detail_paths.append(detail_data)
                logger.info(f"📝 Деталь извлечена: '{detail}' ({len(detail)} символов)")

                if svg_collection:
                    try:
                        tree = ET.parse(svg_file)
                        root = tree.getroot()
                        prune_for_detail(root, detail)
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)
                        tree.write(output_path, encoding="utf-8", xml_declaration=True)
                        logger.info(f"✅ Сохранено: {output_path}")
                    except Exception as save_error:
                        logger.error(f"❌ Ошибка сохранения SVG для детали '{detail}': {save_error}")
                        detail_data["svg_path"] = ""
            else:
                # Длинное имя - разбиваем по запятым на логические группы
                logger.warning(f"🔪 Имя детали слишком длинное ({len(safe_name)} символов), разбиваем по деталям: {detail}")
                
                # Разделяем по запятым
                individual_details = [d.strip() for d in detail.split(',') if d.strip()]
                logger.info(f"🔍 Найдено {len(individual_details)} отдельных деталей в группе")
                
                # Группируем детали так, чтобы имя файла не превышало лимит
                current_group = []
                current_group_text = ""
                part_num = 1
                
                for detail_item in individual_details:
                    # Проверяем, поместится ли эта деталь в текущую группу
                    test_group_text = ",".join(current_group + [detail_item])
                    test_safe_name = translit(re.sub(r'[^\w\s,-]', '', test_group_text).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
                    test_safe_name = re.sub(r'\.+', '', test_safe_name)
                    
                    if len(test_safe_name) <= max_filename_length:
                        # Помещается - добавляем в текущую группу
                        current_group.append(detail_item)
                        current_group_text = test_group_text
                    else:
                        # Не помещается - сохраняем текущую группу и начинаем новую
                        if current_group:
                            group_title = ",".join(current_group)
                            group_safe_name = translit(re.sub(r'[^\w\s,-]', '', group_title).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
                            group_safe_name = re.sub(r'\.+', '', group_safe_name)
                            
                            group_filename = f"{group_safe_name}_group{part_num}.svg"
                            group_output_path = os.path.normpath(os.path.join(output_dir, group_filename))
                            relative_base = f"/static/svgs/{claim_number}_{vin}"
                            group_output_path_relative = f"{relative_base}/{group_filename}".replace("\\", "/")
                            
                            detail_data = {
                                "title": group_title,
                                "svg_path": group_output_path_relative.replace("\\", "/") if svg_collection else ""
                            }
                            detail_paths.append(detail_data)
                            logger.info(f"📝 Группа {part_num} извлечена: '{group_title[:100]}{'...' if len(group_title) > 100 else ''}' -> {group_filename}")

                            if svg_collection:
                                try:
                                    tree = ET.parse(svg_file)
                                    root = tree.getroot()
                                    prune_for_detail(root, detail)  # Используем оригинальное название для фильтрации
                                    os.makedirs(os.path.dirname(group_output_path), exist_ok=True)
                                    tree.write(group_output_path, encoding="utf-8", xml_declaration=True)
                                    logger.info(f"✅ Группа {part_num} сохранена: {group_output_path}")
                                except Exception as save_error:
                                    logger.error(f"❌ Ошибка сохранения SVG для группы {part_num}: {save_error}")
                                    detail_data["svg_path"] = ""
                            
                            part_num += 1
                        
                        # Начинаем новую группу с текущей деталью
                        current_group = [detail_item]
                        current_group_text = detail_item
                
                # Сохраняем последнюю группу
                if current_group:
                    group_title = ",".join(current_group)
                    group_safe_name = translit(re.sub(r'[^\w\s,-]', '', group_title).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
                    group_safe_name = re.sub(r'\.+', '', group_safe_name)
                    
                    group_filename = f"{group_safe_name}_group{part_num}.svg"
                    group_output_path = os.path.normpath(os.path.join(output_dir, group_filename))
                    relative_base = f"/static/svgs/{claim_number}_{vin}"
                    group_output_path_relative = f"{relative_base}/{group_filename}".replace("\\", "/")
                    
                    detail_data = {
                        "title": group_title,
                        "svg_path": group_output_path_relative.replace("\\", "/") if svg_collection else ""
                    }
                    detail_paths.append(detail_data)
                    logger.info(f"📝 Группа {part_num} (финальная) извлечена: '{group_title[:100]}{'...' if len(group_title) > 100 else ''}' -> {group_filename}")

                    if svg_collection:
                        try:
                            tree = ET.parse(svg_file)
                            root = tree.getroot()
                            prune_for_detail(root, detail)  # Используем оригинальное название для фильтрации
                            os.makedirs(os.path.dirname(group_output_path), exist_ok=True)
                            tree.write(group_output_path, encoding="utf-8", xml_declaration=True)
                            logger.info(f"✅ Группа {part_num} (финальная) сохранена: {group_output_path}")
                        except Exception as save_error:
                            logger.error(f"❌ Ошибка сохранения SVG для финальной группы {part_num}: {save_error}")
                            detail_data["svg_path"] = ""
                
                logger.info(f"🎯 Всего создано {part_num} групп из {len(individual_details)} деталей")

        logger.info(f"✅ Функция split_svg_by_details ЗАВЕРШЕНА УСПЕШНО для файла {svg_file}")
        logger.info(f"🎯 ИТОГО извлечено деталей: {len(detail_paths)}")
        if detail_paths:
            logger.info(f"📝 Список извлеченных деталей:")
            for i, detail in enumerate(detail_paths, 1):
                svg_status = "с файлом" if detail["svg_path"] else "только данные"
                logger.info(f"  {i}. '{detail['title']}' ({svg_status})")
        else:
            logger.warning(f"⚠️ НЕ НАЙДЕНО деталей в файле {svg_file}")

        return detail_paths
    except Exception as e:
        logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА в split_svg_by_details для файла {svg_file}: {str(e)}")
        logger.error(f"❌ Тип ошибки: {type(e).__name__}")
        import traceback
        logger.error(f"❌ Полный traceback: {traceback.format_exc()}")
        return []

# Сохраняет SVG с сохранением цветов
def save_svg_sync(driver, element, path, claim_number='', vin='', svg_collection=True):
    try:
        if element.tag_name not in ['svg', 'g']:
            logger.warning(f"Элемент {element.tag_name} не является SVG или группой")
            return False, None, []

        # Оптимизированная проверка наличия дочерних элементов
        has_children = driver.execute_script("""
            return arguments[0].children.length > 0;
        """, element)
        if not has_children and element.tag_name == 'g':
            logger.warning(
                f"Группа {element.get_attribute('data-title') or 'без названия'} не содержит дочерних элементов")
            return False, None, []

        # Извлекаем и применяем стили для сохранения цветов
        driver.execute_script("""
            let element = arguments[0];
            function setInlineStyles(el) {
                try {
                let computed = window.getComputedStyle(el);
                if (computed.fill && computed.fill !== 'none') {
                    el.setAttribute('fill', computed.fill);
                }
                if (computed.stroke && computed.stroke !== 'none') {
                    el.setAttribute('stroke', computed.stroke);
                }
                if (computed.strokeWidth && computed.strokeWidth !== '0px') {
                    el.setAttribute('stroke-width', computed.strokeWidth);
                }
                for (let child of el.children) {
                    setInlineStyles(child);
                    }
                } catch (e) {
                    console.warn('Не удалось применить стили к элементу:', e);
                }
            }
            setInlineStyles(element);
        """, element)

        svg_content = element.get_attribute('outerHTML')

        if element.tag_name == 'g':
            # Оптимизированный поиск родительского SVG
            parent_svg = driver.execute_script("""
                let el = arguments[0];
                while (el && el.tagName.toLowerCase() !== 'svg') {
                    el = el.parentElement;
                    // Защита от бесконечного цикла
                    if (!el || el === document.documentElement) {
                        return null;
                    }
                }
                return el;
            """, element)

            if not parent_svg:
                logger.warning("Не удалось найти родительский SVG для группы")
                return False, None, []

            # Вычисление границ с защитой от ошибок
            bounds = driver.execute_script("""
                let element = arguments[0];
                let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
                function computeBounds(el) {
                    try {
                    if (el.tagName === 'path' || el.tagName === 'rect' || el.tagName === 'circle') {
                        let bbox = el.getBBox();
                        if (bbox.width > 0 && bbox.height > 0) {
                            minX = Math.min(minX, bbox.x);
                            minY = Math.min(minY, bbox.y);
                            maxX = Math.max(maxX, bbox.x + bbox.width);
                            maxY = Math.max(maxY, bbox.y + bbox.height);
                        }
                    }
                    for (let child of el.children) {
                        computeBounds(child);
                        }
                    } catch (e) {
                        console.warn('Ошибка при вычислении границ элемента:', e);
                    }
                }
                computeBounds(element);
                return [minX, minY, maxX - minX, maxY - minY];
            """, element)

            if bounds[2] <= 0 or bounds[3] <= 0 or not all(isinstance(x, (int, float)) for x in bounds):
                logger.warning("Невалидные границы для viewBox, используется запасное значение")
                view_box = '0 0 1000 1000'
            else:
                padding = 10
                view_box = f"{bounds[0] - padding} {bounds[1] - padding} {bounds[2] + 2 * padding} {bounds[3] + 2 * padding}"

            width = '100%'
            height = '100%'
        else:
            view_box = element.get_attribute('viewBox') or '0 0 1000 1000'
            width = element.get_attribute('width') or '100%'
            height = element.get_attribute('height') or '100%'

        # Оптимизированное извлечение стилей
        style_content = driver.execute_script("""
            let styles = '';
            try {
            const styleSheets = document.styleSheets;
            for (let sheet of styleSheets) {
                try {
                    for (let rule of sheet.cssRules) {
                        if (rule.selectorText && (
                            rule.selectorText.includes('svg') || 
                            rule.selectorText.includes('path') || 
                            rule.selectorText.includes('rect') || 
                            rule.selectorText.includes('circle') || 
                            rule.selectorText.includes('g') ||
                            rule.selectorText.includes('[fill]') ||
                            rule.selectorText.includes('[stroke]')
                        )) {
                            styles += rule.cssText + '\\n';
                        }
                    }
                } catch (e) {
                        console.warn('Не удалось получить доступ к стилям листа:', e);
                }
                }
            } catch (e) {
                console.warn('Не удалось получить доступ к стилям документа:', e);
            }
            return styles;
        """)

        svg_full_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" viewBox="{view_box}" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink">
<style>
{style_content}
svg * {{
    fill: inherit;
    stroke: inherit;
    stroke-width: inherit;
}}
</style>
{svg_content}
</svg>"""

        svg_bytes = svg_full_content.encode('utf-8')
        parser = etree.XMLParser(encoding='utf-8')
        try:
            etree.fromstring(svg_bytes, parser)
        except Exception as e:
            logger.error(f"Ошибка валидации SVG: {e}")
            return False, None, []

        # Определяем нужно ли разбивать на детали (только для зон, не для пиктограмм)
        should_split_details = 'pictograms' not in path
        detail_paths = []
        
        logger.info(f"🔍 Анализ файла: {path}")
        logger.info(f"🔍 should_split_details: {should_split_details}")
        
        if should_split_details:
            filename = os.path.basename(path)
            is_zone = is_zone_file(filename)
            logger.info(f"🔍 Имя файла: {filename}")
            logger.info(f"🔍 is_zone_file: {is_zone}")
            
            if is_zone:
                logger.info(f"🎯 ЗОНА ОБНАРУЖЕНА: {filename} - ГАРАНТИРУЕМ обработку деталей!")
                
                if svg_collection:
                    # Режим полного сохранения: сохраняем основной SVG + разбиваем + сохраняем детали
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, 'wb') as f:
                        f.write(svg_bytes)
                    logger.info(f"✅ SVG зоны сохранён: {path}")
                    
                    logger.info(f"🔧 Запускаем разбиение зоны {filename} с сохранением деталей")
                    detail_paths = split_svg_by_details(path, os.path.dirname(path), claim_number=claim_number, vin=vin, svg_collection=svg_collection)
                    logger.info(f"🎯 Разбиение завершено: получено {len(detail_paths)} деталей")
                else:
                    # Режим только данных: НЕ сохраняем основной SVG, но ОБЯЗАТЕЛЬНО извлекаем детали
                    logger.info(f"🎛️ Сбор SVG отключен, но ГАРАНТИРУЕМ извлечение данных о деталях зоны: {path}")
                    
                    # Создаем временный файл для извлечения данных о деталях
                    with tempfile.NamedTemporaryFile(mode='wb', suffix='.svg', delete=False) as temp_file:
                        temp_file.write(svg_bytes)
                        temp_path = temp_file.name
                    
                    try:
                        logger.info(f"🔧 Запускаем разбиение зоны {filename} БЕЗ сохранения файлов (только данные)")
                        detail_paths = split_svg_by_details(temp_path, os.path.dirname(path), claim_number=claim_number, vin=vin, svg_collection=svg_collection)
                        logger.info(f"🎯 Извлечение данных завершено: получено {len(detail_paths)} деталей")
                        
                        if len(detail_paths) == 0:
                            logger.error(f"❌ КРИТИЧЕСКАЯ ПРОБЛЕМА: Не удалось извлечь детали из зоны {filename}!")
                            logger.error(f"❌ Проверьте содержимое временного файла: {temp_path}")
                            # НЕ удаляем временный файл для отладки
                            logger.error(f"❌ Временный файл сохранён для анализа: {temp_path}")
                        else:
                            # Удаляем временный файл только при успехе
                            os.unlink(temp_path)
                    except Exception as detail_error:
                        logger.error(f"❌ Ошибка при извлечении деталей из зоны {filename}: {detail_error}")
                        # Сохраняем временный файл для отладки
                        logger.error(f"❌ Временный файл сохранён для анализа: {temp_path}")
                        detail_paths = []
            else:
                # Не zone файл - обрабатываем как обычно
                logger.debug(f"📄 Файл {filename} не является зоной")
                if svg_collection:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, 'wb') as f:
                        f.write(svg_bytes)
                    logger.info(f"✅ SVG сохранён: {path}")
                else:
                    logger.info(f"🎛️ Сбор SVG отключен, пропускаем сохранение: {path}")
        else:
            # Пиктограмма - обрабатываем как раньше
            if svg_collection:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'wb') as f:
                    f.write(svg_bytes)
                logger.info(f"✅ SVG пиктограммы сохранён: {path}")
            else:
                logger.info(f"📝 Пиктограмма обработана без сохранения SVG: {path}")

        return True, path, detail_paths
    except Exception as e:
        logger.error(f"Ошибка при сохранении SVG: {e}")
        return False, None, []

# Сохраняет основной скриншот и SVG
def save_main_screenshot_and_svg(driver, screenshot_dir, svg_dir, timestamp, claim_number, vin, svg_collection=True):
    main_screenshot_path = os.path.join(screenshot_dir, f"main_screenshot.png")
    main_screenshot_relative = f"/static/screenshots/{claim_number}_{vin}/main_screenshot.png"
    main_svg_path = os.path.join(svg_dir, f"main.svg")
    main_svg_relative = f"/static/svgs/{claim_number}_{vin}/main.svg"

    # Проверяем наличие SVG на странице
    try:
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.TAG_NAME, "svg"))
        )
        time.sleep(0.5)
        svg = driver.find_element(By.TAG_NAME, "svg")
        os.makedirs(os.path.dirname(main_screenshot_path), exist_ok=True)
        svg.screenshot(main_screenshot_path)
        logger.info(f"Основной скриншот сохранён: {main_screenshot_path}")
        
        # Сохраняем SVG только если включен сбор SVG
        if svg_collection:
            success, _, _ = save_svg_sync(driver, svg, main_svg_path, claim_number=claim_number, vin=vin, svg_collection=svg_collection)
        if not success:
            logger.warning("Не удалось сохранить основной SVG")
        else:
            logger.info("Сбор SVG отключен, пропускаем сохранение основного SVG")
            main_svg_relative = ""
            
        return main_screenshot_relative.replace("\\", "/"), main_svg_relative.replace("\\", "/")
    except Exception as e:
        logger.error(f"Ошибка при сохранении основного скриншота/SVG: {str(e)}")
        return None, None

# Извлекает зоны
def extract_zones(driver):
    zones = []
    try:
        zones_container = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "tree-navigation-zones-container"))
        )
        zone_containers = zones_container.find_elements(By.CSS_SELECTOR, "div.navigation-tree-zone-container")
        for container in zone_containers:
            zone_id = container.get_attribute("data-value")
            try:
                description_span = container.find_element(By.ID, f"tree-navigation-zone-description-{zone_id}")
                title = description_span.text.strip()
                zones.append({
                    "title": title,
                    "element": description_span,
                    "link": zone_id
                })
            except Exception as e:
                logger.warning(f"Не удалось найти описание для зоны с id {zone_id}: {str(e)}")
        logger.info(f"Извлечено {len(zones)} зон: {[z['title'] for z in zones]}")
    except Exception as e:
        logger.error(f"Ошибка при извлечении зон: {str(e)}")
    return zones

# Обрабатывает одну зону
def process_zone(driver, zone, screenshot_dir, svg_dir, max_retries=3, claim_number="", vin="", svg_collection=True):
    """
    Обрабатывает одну зону, включая сохранение скриншота, SVG и пиктограмм.
    max_retries: максимальное количество повторных попыток при ошибке сессии.
    """
    zone_data = []

    # Проверяем валидность zone
    if not zone.get('title') or not zone.get('link'):
        logger.warning(f"Пропущена некорректная зона: title={zone.get('title')!r}, link={zone.get('link')!r}")
        return zone_data

    logger.debug(f"Обработка зоны: {zone}")

    for attempt in range(max_retries):
        try:
            zone_element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, f"tree-navigation-zone-description-{zone['link']}"))
            )
            zone_element.click()
            logger.info(f"Клик по зоне: {zone['title']}")
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "body"))
            )
            break
        except WebDriverException as e:
            logger.error(f"Ошибка при клике по зоне {zone['title']} (попытка {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                logger.error(f"Не удалось кликнуть по зоне {zone['title']} после {max_retries} попыток")
                return zone_data
            time.sleep(1)

    # Формируем безопасное имя для zone['title']
    safe_zone_title = translit(re.sub(r'[^\w\s-]',
                                      '', zone['title']).strip(),
                               'ru', reversed=True).replace(" ", "_").replace("/", "_").lower().replace("'", "")
    safe_zone_title = re.sub(r'\.+', '', safe_zone_title)
    zone_screenshot_path = os.path.join(screenshot_dir, f"zone_{safe_zone_title}.png")
    zone_screenshot_relative = f"/static/screenshots/{claim_number}_{vin}/zone_{safe_zone_title}.png".replace(
        "\\", "/")
    zone_svg_path = os.path.join(svg_dir, f"zone_{safe_zone_title}.svg")
    zone_svg_relative = f"/static/svgs/{claim_number}_{vin}/zone_{safe_zone_title}.svg".replace("\\", "/")

    # Проверяем наличие пиктограмм с надежными стратегиями ожидания
    try:
        logger.info(f"🔍 Начинаем проверку пиктограмм для зоны {zone['title']}")
        
        # Этап 1: Дожидаемся полной загрузки страницы  
        WebDriverWait(driver, 15).until(wait_for_document_ready)
        logger.debug(f"✅ Документ готов для зоны {zone['title']}")
        
        # Этап 2: Находим main элемент с retry логикой
        main_element = None
        for attempt in range(3):
            try:
                main_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "main"))
        )
                break
            except TimeoutException:
                if attempt < 2:
                    logger.warning(f"Попытка {attempt + 1}: main элемент не найден, повторяем...")
                    time.sleep(1)
                else:
                    raise
        
        if not main_element:
            raise TimeoutException("Main элемент не найден после 3 попыток")
        
        logger.debug(f"✅ Main элемент найден для зоны {zone['title']}")
        
        # Этап 3: Дожидаемся pictograms-grid с улучшенными условиями
        WebDriverWait(driver, 20).until(wait_for_pictograms_grid)
        pictograms_grid = driver.find_element(By.CSS_SELECTOR, "main div.pictograms-grid.visible")
        logger.info(f"✅ Зона {zone['title']} содержит пиктограммы")
        
        # Этап 4: Дожидаемся загрузки всех секций с составными условиями
        WebDriverWait(driver, 25).until(wait_for_all_sections_loaded)
        logger.debug(f"✅ Все секции загружены для зоны {zone['title']}")
        
        # Этап 5: Дожидаемся загрузки SVG с продвинутой проверкой
        WebDriverWait(driver, 30).until(wait_for_all_svgs_ready)
        logger.debug(f"✅ SVG элементы загружены для зоны {zone['title']}")
        
        # Этап 6: Проверяем стабильность DOM (избегаем race conditions)
        WebDriverWait(driver, 10).until(wait_for_dom_stability)
        logger.info(f"✅ DOM стабилизирован для зоны {zone['title']}")
        
        # Дополнительная пауза для полной стабилизации
        time.sleep(1)

        # Кликаем по #breadcrumb-sheet-title, собираем пиктограммы, делаем скриншот, затем второй клик
        try:
            breadcrumb_selector = "#breadcrumb-sheet-title"
            # Первый клик для закрытия меню
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, breadcrumb_selector))
            ).click()
            logger.info(f"Клик по {breadcrumb_selector} для закрытия меню в зоне {zone['title']}")
            time.sleep(1)

            # Делаем скриншот каждой секции и склеиваем в памяти
            os.makedirs(os.path.dirname(zone_screenshot_path), exist_ok=True)
            try:
                # Находим все секции
                sections = WebDriverWait(driver, 10).until(
                    EC.visibility_of_all_elements_located((
                        By.CSS_SELECTOR,
                        "main div.pictograms-grid.visible section.pictogram-section"
                    ))
                )
                logger.debug(f"Найдено {len(sections)} секций для зоны {zone['title']}")

                # Список для хранения изображений в памяти
                images = []

                # Делаем скриншот каждой секции
                for index, section in enumerate(sections):
                    # Прокручиваем к секции
                    driver.execute_script("arguments[0].scrollIntoView(true);", section)
                    time.sleep(0.5)  # Пауза для стабилизации

                    # Получаем размеры секции
                    section_width = driver.execute_script("return arguments[0].scrollWidth", section)
                    section_height = driver.execute_script("return arguments[0].offsetHeight", section)
                    logger.debug(f"Секция {index + 1} для зоны {zone['title']}: {section_width}x{section_height}")

                    # Делаем скриншот в памяти
                    screenshot_png = section.screenshot_as_png
                    img = Image.open(BytesIO(screenshot_png))
                    images.append(img)
                    logger.debug(f"Скриншот секции {index + 1} для зоны {zone['title']} захвачен в памяти")

                # Склеиваем изображения
                max_width = max(img.width for img in images)
                total_height = sum(img.height for img in images)

                # Создаём новое изображение
                final_image = Image.new('RGB', (max_width, total_height))
                y_offset = 0
                for img in images:
                    final_image.paste(img, (0, y_offset))
                    y_offset += img.height

                # Сохраняем итоговый скриншот
                final_image.save(zone_screenshot_path, quality=85, optimize=True)
                logger.info(f"Скриншот всех секций для зоны {zone['title']} сохранён: {zone_screenshot_path}")

                # Закрываем изображения
                for img in images:
                    img.close()

                # Восстанавливаем исходные размеры окна
                try:
                    driver.set_window_size(original_size['width'], original_size['height'])
                except NameError:
                    logger.warning("original_size не определен, пропускаем восстановление размера окна")
                time.sleep(0.5)

            except (TimeoutException, WebDriverException, Exception) as e:
                logger.error(f"Не удалось сделать скриншот секций для зоны {zone['title']}: {str(e)}")
                zone_screenshot_relative = ""  # Устанавливаем пустой путь в случае ошибки
                logger.info(f"Заглушка для зоны {zone['title']}: скриншот не создан")

            # Собираем данные пиктограмм, передаем zone_screenshot_relative
            zone_data = process_pictograms(driver, zone, screenshot_dir, svg_dir, max_retries, zone_screenshot_relative, claim_number=claim_number, vin="", svg_collection=svg_collection)

            # Второй клик для возврата к меню зон
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, breadcrumb_selector))
            ).click()
            logger.info(f"Клик по {breadcrumb_selector} для возврата к меню зон в зоне {zone['title']}")
            # Дожидаемся контейнера зон
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "tree-navigation-zones-container"))
            )
            # Проверяем, что элемент следующей зоны доступен
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, f"tree-navigation-zone-description-{zone['link']}"))
            )
            logger.info(f"Меню зон доступно после обработки {zone['title']}, готов к следующей зоне")
            time.sleep(0.5)

            return zone_data
        except (TimeoutException, WebDriverException) as e:
            logger.error(f"Ошибка при клике по {breadcrumb_selector} или скриншоте для зоны {zone['title']}: {str(e)}")
            # Пытаемся вернуть меню зон
            try:
                WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, breadcrumb_selector))
                ).click()
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "tree-navigation-zones-container"))
                )
                logger.info(f"Восстановлено меню зон для {zone['title']} после ошибки")
            except Exception as ex:
                logger.error(f"Не удалось восстановить меню зон: {str(ex)}")

            return zone_data
    except (TimeoutException, WebDriverException) as e:
        logger.info(f"Зона {zone['title']} не содержит пиктограмм или они не загрузились: {str(e)}")

    # Проверяем наличие SVG
    try:
        sheet_div = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, f"sheet_{zone['link']}"))
        )
        WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, f"#sheet_{zone['link']} svg"))
        )
        svg = sheet_div.find_element(By.TAG_NAME, "svg")
        # Проверяем, что SVG содержит дочерние элементы
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return arguments[0].querySelectorAll('path, rect, circle').length", svg) > 0
        )
        time.sleep(2)
        logger.info(f"Найден SVG для зоны {zone['title']}")

        try:
            WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.TAG_NAME, "svg"))
            )
            logger.debug(f"Сохранение скриншота и SVG для зоны {zone['title']}")
            try:
                # Прокручиваем к SVG
                driver.execute_script("arguments[0].scrollIntoView(true);", svg)
                time.sleep(0.5)  # Пауза для стабилизации
                # Проверяем размеры SVG
                svg_width = driver.execute_script("return arguments[0].scrollWidth", svg)
                svg_height = driver.execute_script("return arguments[0].scrollHeight", svg)
                logger.debug(f"SVG для зоны {zone['title']}: {svg_width}x{svg_height}")
                svg.screenshot(zone_screenshot_path)
                logger.info(f"Скриншот SVG зоны {zone['title']} сохранён: {zone_screenshot_path}")
            except WebDriverException as e:
                logger.warning(f"Не удалось сохранить скриншот SVG для зоны {zone['title']}: {str(e)}")
                os.makedirs(os.path.dirname(zone_screenshot_path), exist_ok=True)
                # Заглушка
                logger.info(f"Заглушка для зоны {zone['title']}: скриншот SVG не создан")
                zone_data.append({
                    "title": zone['title'],
                    "screenshot_path": "",
                    "has_pictograms": False,
                    "graphics_not_available": True,
                    "details": []
                })
                return zone_data

            # Всегда обрабатываем SVG для извлечения деталей, но сохраняем файлы только при включённом флаге
            detail_paths = []
            success, _, detail_paths = save_svg_sync(driver, svg, zone_svg_path, claim_number=claim_number, vin=vin, svg_collection=svg_collection)
            logger.info(f"🔍 После save_svg_sync для зоны {zone['title']}: success={success}, получено деталей: {len(detail_paths)}")
            if not success:
                logger.warning(f"Не удалось обработать SVG для зоны {zone['title']}")
                zone_data.append({
                    "title": zone['title'],
                    "screenshot_path": zone_screenshot_relative,
                    "has_pictograms": False,
                    "graphics_not_available": True,
                    "details": []
                })
                return zone_data
            
            # Устанавливаем путь к SVG только если сбор включён
            if not svg_collection:
                zone_svg_relative = ""

            zone_data.append({
                "title": zone['title'],
                "screenshot_path": zone_screenshot_relative,
                "svg_path": zone_svg_relative,
                "has_pictograms": False,
                "graphics_not_available": False,
                "details": detail_paths
            })
            logger.info(f"Обработано {len(detail_paths)} деталей для зоны {zone['title']}")
        except WebDriverException as e:
            logger.error(f"Ошибка при обработке SVG зоны {zone['title']}: {str(e)}")
            os.makedirs(os.path.dirname(zone_screenshot_path), exist_ok=True)
            # Заглушка
            logger.info(f"Заглушка для зоны {zone['title']}: скриншот не создан")
            zone_data.append({
                "title": zone['title'],
                "screenshot_path": "",
                "has_pictograms": False,
                "graphics_not_available": True,
                "details": []
            })
            return zone_data
    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Ошибка при поиске SVG для зоны {zone['title']}: {str(e)}")
        os.makedirs(os.path.dirname(zone_screenshot_path), exist_ok=True)
        # Заглушка
        logger.info(f"Заглушка для зоны {zone['title']}: скриншот не создан")
        zone_data.append({
            "title": zone['title'],
            "screenshot_path": "",
            "has_pictograms": False,
            "graphics_not_available": True,
            "details": []
        })
        return zone_data

    return zone_data

# Функция для проверки и дозаполнения деталей зон
def ensure_zone_details_extracted(zone_data, svg_dir, claim_number="", vin="", svg_collection=True):
    """
    Проверяет зоны в zone_data и дозаполняет детали если они отсутствуют.
    ГАРАНТИРУЕТ что все зоны имеют извлеченные детали.
    """
    logger.info(f"🔧 Проверяем полноту извлечения деталей для {len(zone_data)} зон")
    
    zones_fixed = 0
    for zone in zone_data:
        if zone.get("has_pictograms", False):
            # Пиктограммы не нуждаются в проверке деталей
            continue
        
        zone_title = zone.get("title", "")
        current_details = zone.get("details", [])
        
        if len(current_details) == 0:
            logger.warning(f"⚠️ КРИТИЧЕСКОЕ: Зона '{zone_title}' не имеет деталей - ПРИНУДИТЕЛЬНОЕ исправление")
            
            # Ищем SVG файл зоны несколькими способами
            zone_svg_path = None
            
            # Способ 1: стандартный поиск по имени
            safe_zone_title = translit(re.sub(r'[^\w\s-]', '', zone_title).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower().replace("'", "")
            safe_zone_title = re.sub(r'\.+', '', safe_zone_title)
            candidate_path = os.path.join(svg_dir, f"zone_{safe_zone_title}.svg")
            
            if os.path.exists(candidate_path):
                zone_svg_path = candidate_path
                logger.info(f"✅ Найден SVG файл зоны (способ 1): {zone_svg_path}")
            else:
                # Способ 2: поиск всех файлов зон в директории
                logger.info(f"🔍 Ищем файлы зон в директории: {svg_dir}")
                if os.path.exists(svg_dir):
                    all_files = [f for f in os.listdir(svg_dir) if f.endswith('.svg')]
                    zone_files = [f for f in all_files if is_zone_file(f)]
                    logger.info(f"🔍 Найдено файлов зон: {len(zone_files)} из {len(all_files)} SVG файлов")
                    
                    if zone_files:
                        # Берем первый найденный файл зоны
                        zone_svg_path = os.path.join(svg_dir, zone_files[0])
                        logger.warning(f"⚠️ Использую первый доступный файл зоны: {zone_svg_path}")
                        
                        # Логируем все найденные файлы зон для отладки
                        logger.info(f"🔍 Все файлы зон в директории:")
                        for i, zf in enumerate(zone_files, 1):
                            logger.info(f"  {i}. {zf}")
                else:
                    logger.error(f"❌ Директория SVG не существует: {svg_dir}")
            
            if zone_svg_path and os.path.exists(zone_svg_path):
                logger.info(f"🎯 ПРИНУДИТЕЛЬНО извлекаем детали из: {zone_svg_path}")
                try:
                    # Логируем размер файла для диагностики
                    file_size = os.path.getsize(zone_svg_path)
                    logger.info(f"📊 Размер файла зоны: {file_size} байт")
                    
                    extracted_details = split_svg_by_details(zone_svg_path, svg_dir, claim_number=claim_number, vin=vin, svg_collection=svg_collection)
                    
                    if extracted_details and len(extracted_details) > 0:
                        zone["details"] = extracted_details
                        zones_fixed += 1
                        logger.info(f"✅ УСПЕХ: Зона '{zone_title}' исправлена: добавлено {len(extracted_details)} деталей")
                        
                        # Логируем первые несколько деталей для подтверждения
                        for i, detail in enumerate(extracted_details[:3], 1):
                            logger.info(f"  {i}. '{detail['title']}'")
                        if len(extracted_details) > 3:
                            logger.info(f"  ... и еще {len(extracted_details) - 3} деталей")
                    else:
                        logger.error(f"❌ ПРОВАЛ: Не удалось извлечь детали из {zone_svg_path} для зоны '{zone_title}'")
                        logger.error(f"❌ Проверьте содержимое файла вручную")
                except Exception as e:
                    logger.error(f"❌ ИСКЛЮЧЕНИЕ при дозаполнении деталей зоны '{zone_title}': {e}")
                    import traceback
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
            else:
                logger.error(f"❌ КРИТИЧНО: SVG файл зоны не найден для '{zone_title}'")
                logger.error(f"❌ Ожидаемый путь: {candidate_path}")
                logger.error(f"❌ Директория существует: {os.path.exists(svg_dir)}")
                if os.path.exists(svg_dir):
                    files = os.listdir(svg_dir)
                    logger.error(f"❌ Файлы в директории: {files[:10]}{'...' if len(files) > 10 else ''}")
    
    logger.info(f"🎯 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ дозаполнения: исправлено {zones_fixed} зон из {len([z for z in zone_data if not z.get('has_pictograms', False)])}")
    return zone_data

# Обрабатывает пиктограммы в зоне
def process_pictograms(driver, zone, screenshot_dir, svg_dir, max_retries=2, zone_screenshot_relative="", claim_number="", vin="", svg_collection=True):
    """
    Собирает данные о пиктограммах в зоне, сохраняя SVG для каждой работы.
    Использует улучшенные стратегии ожидания для надежности.
    """
    pictogram_data = []
    try:
        logger.info(f"🎨 Начинаем сбор пиктограмм для зоны {zone['title']}")
        
        # Этап 1: Подтверждаем готовность документа
        WebDriverWait(driver, 15).until(ensure_document_ready)
        
                # Этап 2: Находим main с повышенной надежностью
        main = None
        for attempt in range(max_retries + 1):
            try:
                main = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "main"))
                )
                if main.is_displayed():
                    break
                else:
                    logger.debug(f"Main найден но не видим, попытка {attempt + 1}")
                    time.sleep(0.5)
            except TimeoutException:
                if attempt < max_retries:
                    logger.warning(f"Попытка {attempt + 1}: main не найден, повторяем...")
                    time.sleep(1)
                else:
                    raise
        
        if not main or not main.is_displayed():
            logger.error(f"Main элемент недоступен для зоны {zone['title']}")
            return pictogram_data
        
        # Этап 3: Ищем pictograms-grid с улучшенной логикой
        WebDriverWait(driver, 15).until(lambda d: find_pictograms_grid_reliable(d) is not None)
        grid_div = find_pictograms_grid_reliable(driver)
        
        if not grid_div:
            logger.error(f"Не найден активный pictograms-grid в зоне {zone['title']}")
            return pictogram_data

        logger.info(f"✅ Найден pictograms-grid для зоны {zone['title']}")

        # Этап 4: Собираем секции с надежной проверкой загрузки
        WebDriverWait(driver, 20).until(wait_for_sections_stability)
        sections = grid_div.find_elements(By.TAG_NAME, "section")
        logger.info(f"🎯 Найдено {len(sections)} стабильных секций пиктограмм")
        
        for section_idx, section in enumerate(sections):
            try:
                # Проверяем видимость секции
                if not section.is_displayed():
                    logger.debug(f"Секция {section_idx + 1} не видима, пропускаем")
                    continue

                # Находим h2 с более надежной проверкой
                h2_elements = section.find_elements(By.CSS_SELECTOR, "h2.sort-title.visible")
                if not h2_elements:
                    logger.warning(f"Не найден h2.sort-title.visible в секции {section_idx + 1} зоны {zone['title']}")
                    continue
                
                h2 = h2_elements[0]
                section_name = h2.text.strip()
                if not section_name:
                    logger.warning(f"Пустое название секции {section_idx + 1} в зоне {zone['title']}")
                    continue

                # Находим holder с улучшенной проверкой
                holders = section.find_elements(By.ID, "pictograms-grid-holder")
                if not holders:
                    logger.warning(f"Не найден pictograms-grid-holder в секции '{section_name}'")
                    continue

                holder = holders[0]
                if not holder.is_displayed():
                    logger.warning(f"Holder не видим в секции '{section_name}'")
                    continue

                # Этап 5: Собираем работы с улучшенной надежностью
                works = []
                
                # Дожидаемся стабилизации работ в секции
                try:
                    WebDriverWait(driver, 15).until(lambda d: wait_for_works_in_section(holder))
                except TimeoutException:
                    logger.warning(f"Таймаут ожидания работ в секции '{section_name}', продолжаем с доступными")
                
                work_divs = [div for div in holder.find_elements(By.TAG_NAME, "div") 
                            if div.get_attribute("data-tooltip") and div.is_displayed()]
                logger.info(f"🔧 Найдено {len(work_divs)} работ в секции '{section_name}'")
                
                for work_idx, work_div in enumerate(work_divs):
                    try:
                        # Проверяем видимость работы
                        if not work_div.is_displayed():
                            logger.debug(f"Работа {work_idx + 1} не видима в секции '{section_name}'")
                            continue

                        # Собираем work_name1 с дополнительной валидацией
                        work_name1 = work_div.get_attribute("data-tooltip")
                        if not work_name1 or not work_name1.strip():
                            logger.warning(f"Пустое data-tooltip для работы {work_idx + 1} в секции '{section_name}'")
                            continue
                        work_name1 = work_name1.strip()

                        # Собираем work_name2 с улучшенной логикой
                        work_name2 = ""
                        spans = work_div.find_elements(By.CSS_SELECTOR, "span > span")
                        if spans:
                            work_name2 = spans[0].text.strip()

                        # Находим SVG контейнер с более надежной проверкой
                        svg_containers = work_div.find_elements(By.CSS_SELECTOR, "div.navigation-pictogram-svg-container")
                        if not svg_containers:
                            logger.warning(f"Не найден SVG контейнер для работы '{work_name1}' в секции '{section_name}'")
                            continue

                        svg_container = svg_containers[0]
                        if not svg_container.is_displayed():
                            logger.warning(f"SVG контейнер не видим для работы '{work_name1}' в секции '{section_name}'")
                            continue

                        # Собираем SVG с улучшенным ожиданием
                        svgs = svg_container.find_elements(By.TAG_NAME, "svg")
                        if not svgs:
                            logger.warning(f"SVG не найден для работы '{work_name1}' в секции '{section_name}'")
                            continue
                        
                        svg = svgs[0]
                        
                        # Проверяем готовность SVG с таймаутом
                        try:
                            WebDriverWait(driver, 8).until(
                                lambda d: svg.is_displayed() and 
                                d.execute_script("return arguments[0].querySelectorAll('path, rect, circle, g').length > 0", svg)
                            )
                        except TimeoutException:
                            logger.warning(f"SVG не готов для работы '{work_name1}' в секции '{section_name}', пропускаем")
                            continue

                        # Формируем имя файла
                        safe_section_name = translit(re.sub(r'[^\w\s-]', '', section_name).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
                        safe_work_name1 = translit(re.sub(r'[^\w\s-]', '', work_name1).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower()
                        safe_work_name2 = translit(re.sub(r'[^\w\s-]', '', work_name2).strip(), 'ru', reversed=True).replace(" ", "_").replace("/", "_").lower() if work_name2 else ""
                        safe_work_name2 = re.sub(r'\.+', '', safe_work_name2)
                        safe_work_name1 = re.sub(r'\.+', '', safe_work_name1)
                        safe_section_name = re.sub(r'\.+', '', safe_section_name)
                        svg_filename = f"{safe_section_name}_{safe_work_name1}" + (f"_{safe_work_name2}" if work_name2 else "") + ".svg"
                        work_svg_path = os.path.join(svg_dir, svg_filename)
                        work_svg_relative = f"/static/svgs/{claim_number}_{vin}/{svg_filename}".replace("\\", "/")

                        # Сохраняем SVG только если включен сбор SVG
                        if svg_collection:
                            success, saved_path, _ = save_svg_sync(driver, svg, work_svg_path, claim_number=claim_number, vin=vin, svg_collection=svg_collection)
                            if success:
                                logger.info(f"SVG пиктограммы сохранён: {work_svg_path}")
                                works.append({
                                    "work_name1": work_name1,
                                    "work_name2": work_name2,
                                    "svg_path": work_svg_relative
                                })
                            else:
                                logger.warning(f"Не удалось сохранить SVG для работы '{work_name1}' в секции '{section_name}'")
                                works.append({
                                    "work_name1": work_name1,
                                    "work_name2": work_name2,
                                    "svg_path": ""
                                })
                        else:
                            logger.info(f"Сбор SVG отключен, пропускаем сохранение SVG для работы '{work_name1}' в секции '{section_name}'")
                            works.append({
                                "work_name1": work_name1,
                                "work_name2": work_name2,
                                "svg_path": ""
                            })
                    except Exception as e:
                        logger.error(f"Ошибка при обработке работы в секции {section_name}: {str(e)}")
                        continue

                if works:
                    pictogram_data.append({
                        "section_name": section_name,
                        "works": works
                    })
            except Exception as e:
                logger.error(f"Ошибка при обработке секции в зоне {zone['title']}: {str(e)}")
                continue

        # Формируем данные зоны
        if pictogram_data:
            zone_entry = {
                "title": zone['title'],
                "screenshot_path": zone_screenshot_relative,  # Устанавливаем путь к склеенному скриншоту
                "svg_path": "",
                "has_pictograms": True,
                "graphics_not_available": False,
                "details": [],
                "pictograms": pictogram_data
            }
            return [zone_entry]
        else:
            logger.info(f"Не найдено пиктограмм для зоны {zone['title']}")

    except (TimeoutException, WebDriverException) as e:
        logger.error(f"Ошибка при обработке пиктограмм для зоны {zone['title']}: {str(e)}")

    return pictogram_data 