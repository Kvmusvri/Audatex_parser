# Модуль для управления папками и извлечения данных со страниц
import logging
import os
import time
import shutil
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from .constants import SCREENSHOT_DIR, SVG_DIR, DATA_DIR, TIMEOUT, CLAIM_NUMBER_SELECTOR, VIN_SELECTOR
from .actions import get_vin_status

logger = logging.getLogger(__name__)


def safe_remove_directory(path):
    """
    Безопасно удаляет директорию и все её содержимое кроссплатформенно
    """
    try:
        if os.path.exists(path):
            logger.info(f"🗑️ Удаляем существующую папку: {path}")
            shutil.rmtree(path)
            logger.info(f"✅ Папка успешно удалена: {path}")
        return True
    except PermissionError as e:
        logger.error(f"❌ Ошибка прав доступа при удалении {path}: {e}")
        return False
    except OSError as e:
        logger.error(f"❌ Ошибка ОС при удалении {path}: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Неожиданная ошибка при удалении {path}: {e}")
        return False


# Создаёт папки для сохранения данных с перезаписью существующих
def create_folders(claim_number, vin):
    # Заменяем / на _ чтобы избежать создания подпапок
    safe_claim_number = claim_number.replace("/", "_")
    folder_name = f"{safe_claim_number}_{vin}"
    
    screenshot_dir = os.path.join(SCREENSHOT_DIR, folder_name)
    svg_dir = os.path.join(SVG_DIR, folder_name)
    data_dir = os.path.join(DATA_DIR, folder_name)
    
    # Удаляем существующие папки если они есть
    safe_remove_directory(screenshot_dir)
    safe_remove_directory(svg_dir)
    safe_remove_directory(data_dir)
    
    # Создаем новые папки
    logger.info(f"📁 Создаем папки для: {folder_name}")
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(svg_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    
    logger.info(f"✅ Папки успешно созданы: screenshots={screenshot_dir}, svg={svg_dir}, data={data_dir}")
    return screenshot_dir, svg_dir, data_dir


# Извлекает VIN и claim_number со страницы с логикой обновления при проблемах с прогрузкой
def extract_vin_and_claim_number(driver, current_url):
    base_url = current_url.split('step')[0][:-1]
    configs = [
        {'url': base_url + '&step=General+Data+Ingos', 'selector': CLAIM_NUMBER_SELECTOR, 'log_name': 'CLAIM NUMBER', 'key': 'claim_number'},
        {'url': base_url + '&step=Osago+Vehicle+Identification', 'selector': VIN_SELECTOR, 'log_name': 'VIN', 'key': 'vin'}
    ]
    result = {}
    
    for config in configs:
        max_page_refresh_attempts = 10
        success = False
        
        logger.info(f"🔍 Начинаем извлечение {config['log_name']} с URL: {config['url']}")
        
        for attempt in range(1, max_page_refresh_attempts + 1):
            try:
                logger.info(f"📄 Попытка {attempt}/{max_page_refresh_attempts}: Переход на URL для {config['log_name']}")
                driver.get(config['url'])
                time.sleep(3)  # Базовая задержка после перехода
                
                # Проверяем готовность страницы
                WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
                time.sleep(2)  # Дополнительная задержка для прогрузки элементов
                
                # Пытаемся найти целевой элемент
                logger.info(f"🔎 Ищем элемент по селектору: {config['selector']}")
                input_element = WebDriverWait(driver, TIMEOUT).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, config['selector']))
                )
                
                # Проверяем, что элемент действительно загружен и доступен
                if input_element and input_element.is_displayed():
                    value = input_element.get_attribute("value") or ""
                    result[config['key']] = value
                    logger.info(f"✅ Успешно извлечён {config['log_name']}: '{value}' (попытка {attempt})")
                    success = True
                    time.sleep(2)  # Стабилизация перед следующим полем
                    break
                else:
                    raise Exception("Элемент найден, но не отображается")
                    
            except (TimeoutException, StaleElementReferenceException, Exception) as e:
                logger.warning(f"⚠️ Попытка {attempt}: Ошибка при извлечении {config['log_name']}: {str(e)}")
                
                if attempt < max_page_refresh_attempts:
                    logger.info(f"🔄 Обновляем страницу и повторяем попытку...")
                    try:
                        driver.refresh()
                        time.sleep(3)  # Ждем после обновления
                    except Exception as refresh_error:
                        logger.error(f"❌ Ошибка при обновлении страницы: {refresh_error}")
                else:
                    logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось извлечь {config['log_name']} после {max_page_refresh_attempts} попыток!")
                    logger.error(f"❌ Это указывает на серьезные проблемы с сайтом. Требуется полный перезапуск парсера.")
        
        # Если не удалось извлечь поле после всех попыток - возвращаем ошибку
        if not success:
            error_msg = f"Не удалось извлечь {config['log_name']} после {max_page_refresh_attempts} обновлений страницы"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
    
    logger.info(f"✅ Все поля успешно извлечены: claim_number='{result.get('claim_number', '')}', vin='{result.get('vin', '')}'")
    
    # Получаем статус VIN кнопок сразу после извлечения VIN
    vin_status = get_vin_status(driver)
    logger.info(f"📊 VIN статус определен: {vin_status}")
    
    return result['claim_number'], result['vin'], vin_status 