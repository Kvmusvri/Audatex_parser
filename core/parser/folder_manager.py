"""
Управление файлами и папками для сохранения данных

Основные функции:
    * safe_remove_directory: Безопасно удаляет директорию и все её содержимое
    * create_folders: Создаёт папки для сохранения данных с перезаписью существующих
"""
# Модуль для управления папками
import logging
import os
import shutil
import re
from .constants import SCREENSHOT_DIR, SVG_DIR, DATA_DIR

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
    # Очищаем строки от лишних пробелов и символов табуляции
    clean_claim_number = claim_number.strip() if claim_number else ""
    clean_vin = vin.strip() if vin else ""
    
    # Безопасная обработка номера дела - заменяем все проблемные символы
    # Заменяем все символы, которые могут вызвать проблемы в именах файлов/папок
    safe_claim_number = re.sub(r'[<>:"/\\|?*]', '_', clean_claim_number)
    # Дополнительно заменяем дефисы и точки на подчеркивания для безопасности
    safe_claim_number = safe_claim_number.replace('-', '_').replace('.', '_')
    # Убираем множественные подчеркивания
    safe_claim_number = re.sub(r'_+', '_', safe_claim_number)
    # Убираем подчеркивания в начале и конце
    safe_claim_number = safe_claim_number.strip('_')
    
    # Проверяем, что данные не пустые
    if not safe_claim_number and not clean_vin:
        logger.error("❌ Невозможно создать папку: claim_number и vin пустые")
        raise ValueError("claim_number и vin не могут быть пустыми одновременно")
    
    folder_name = f"{safe_claim_number}_{clean_vin}"
    logger.info(f"📁 Создаем папку с именем: '{folder_name}'")
    
    screenshot_dir = os.path.join(SCREENSHOT_DIR, folder_name)
    svg_dir = os.path.join(SVG_DIR, folder_name)
    data_dir = os.path.join(DATA_DIR, folder_name)
    
    # Удаляем существующие папки если они есть
    safe_remove_directory(screenshot_dir)
    safe_remove_directory(svg_dir)
    safe_remove_directory(data_dir)
    
    # Создаем новые папки
    logger.info(f"📁 Создаем папки для: {folder_name}")
    logger.info(f"🔍 Исходные данные: claim_number='{claim_number}', vin='{vin}'")
    logger.info(f"🔍 Очищенные данные: clean_claim_number='{clean_claim_number}', clean_vin='{clean_vin}'")
    logger.info(f"🔍 Безопасное имя папки: safe_claim_number='{safe_claim_number}'")
    
    try:
        os.makedirs(screenshot_dir, exist_ok=True)
        os.makedirs(svg_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)
        
        logger.info(f"✅ Папки успешно созданы: screenshots={screenshot_dir}, svg={svg_dir}, data={data_dir}")
        return screenshot_dir, svg_dir, data_dir
    except Exception as e:
        logger.error(f"❌ Ошибка создания папок: {e}")
        logger.error(f"❌ Пути: screenshot_dir={screenshot_dir}, svg_dir={svg_dir}, data_dir={data_dir}")
        raise 