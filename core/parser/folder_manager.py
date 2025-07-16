# Модуль для управления папками и извлечения данных со страниц
import logging
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from .constants import SCREENSHOT_DIR, SVG_DIR, DATA_DIR, TIMEOUT, CLAIM_NUMBER_SELECTOR, VIN_SELECTOR

logger = logging.getLogger(__name__)


# Создаёт папки для сохранения данных
def create_folders(claim_number, vin):
    folder_name = f"{claim_number}_{vin}"
    screenshot_dir = os.path.join(SCREENSHOT_DIR, folder_name)
    svg_dir = os.path.join(SVG_DIR, folder_name)
    data_dir = os.path.join(DATA_DIR, folder_name)
    os.makedirs(screenshot_dir, exist_ok=True)
    os.makedirs(svg_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    return screenshot_dir, svg_dir, data_dir


# Извлекает VIN и claim_number со страницы
def extract_vin_and_claim_number(driver, current_url):
    base_url = current_url.split('step')[0][:-1]
    configs = [
        {'url': current_url, 'selector': CLAIM_NUMBER_SELECTOR, 'log_name': 'CLAIM NUMBER', 'key': 'claim_number'},
        {'url': base_url + '&step=Osago+Vehicle+Identification', 'selector': VIN_SELECTOR, 'log_name': 'VIN', 'key': 'vin'}
    ]
    result = {}
    for config in configs:
        time.sleep(5)
        logger.info(f"Переход на URL для {config['log_name']}: {config['url']}")
        driver.get(config['url'])
        try:
            WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.CSS_SELECTOR, "body")))
            input_element = WebDriverWait(driver, TIMEOUT).until(EC.presence_of_element_located((By.CSS_SELECTOR, config['selector'])))
            result[config['key']] = input_element.get_attribute("value") or ""
            logger.info(f"Извлечён {config['log_name']}: {result[config['key']]}")
            time.sleep(5)
        except (TimeoutException, StaleElementReferenceException):
            logger.warning(f"Не удалось извлечь {config['log_name']}")
            result[config['key']] = ""
    return result['claim_number'], result['vin'] 