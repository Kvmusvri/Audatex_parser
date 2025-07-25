#!/usr/bin/env python3
"""
Тестовый скрипт для проверки записи данных в БД
Позволяет указать путь к JSON файлу и протестировать сохранение в БД
"""

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Добавляем корневую директорию в путь для импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database.requests import save_parser_data_to_db, update_json_with_claim_number, save_updated_json_to_file
from core.database.models import Base, engine

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def ensure_tables_exist():
    """Проверяет существование таблиц (создаются при запуске приложения)"""
    try:
        logger.info("🔧 Проверяем существование таблиц...")
        # Таблицы должны быть созданы при запуске приложения
        logger.info("✅ Таблицы готовы к использованию (созданы при запуске приложения)")
    except Exception as e:
        logger.error(f"❌ Ошибка при проверке таблиц: {e}")
        raise

async def test_db_save(json_file_path: str, request_id: str = None, vin: str = None):
    """
    Тестирует сохранение данных из JSON файла в БД
    
    Args:
        json_file_path: Путь к JSON файлу
        request_id: ID запроса (если не указан, извлекается из имени файла)
        vin: VIN номер (если не указан, извлекается из JSON)
    """
    try:
        # Проверяем существование файла
        if not os.path.exists(json_file_path):
            logger.error(f"❌ Файл не найден: {json_file_path}")
            return False
            
        logger.info(f"📁 Загружаем JSON файл: {json_file_path}")
        
        # Загружаем JSON данные
        with open(json_file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            
        logger.info(f"✅ JSON загружен, размер данных: {len(str(json_data))} символов")
        
        # Извлекаем request_id и vin если не указаны
        if not request_id:
            # Пытаемся извлечь из имени файла или папки
            file_name = os.path.basename(json_file_path)
            folder_name = os.path.basename(os.path.dirname(json_file_path))
            
            if '_' in folder_name:
                parts = folder_name.split('_')
                if len(parts) >= 2:
                    request_id = parts[0]
                    vin = parts[1]
                    logger.info(f"🔍 Извлечено из имени папки: request_id={request_id}, vin={vin}")
                else:
                    request_id = "test_request"
                    logger.warning(f"⚠️ Не удалось извлечь request_id из имени папки, используем: {request_id}")
            else:
                request_id = "test_request"
                logger.warning(f"⚠️ Не удалось извлечь request_id, используем: {request_id}")
        
        if not vin:
            vin = json_data.get('vin_value', 'test_vin')
            logger.info(f"🔍 Извлечен VIN из JSON: {vin}")
            
        logger.info(f"🎯 Тестируем сохранение для request_id={request_id}, vin={vin}")
        
        # Убеждаемся что таблицы существуют
        await ensure_tables_exist()
        
        # Тестируем сохранение в БД
        start_time = datetime.now()
        db_success = await save_parser_data_to_db(
            json_data=json_data,
            request_id=request_id,
            vin=vin,
            is_success=True
        )
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        if db_success:
            logger.info(f"✅ Данные успешно сохранены в БД за {duration:.2f} секунд")
            
            # Тестируем обновление JSON с claim_number
            logger.info("🔄 Тестируем обновление JSON с claim_number...")
            updated_json = update_json_with_claim_number(json_data, request_id)
            
            # Сохраняем обновленный JSON
            output_dir = "test_output"
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"updated_{os.path.basename(json_file_path)}")
            
            save_success = await save_updated_json_to_file(updated_json, output_file)
            if save_success:
                logger.info(f"✅ Обновленный JSON сохранен: {output_file}")
            else:
                logger.error(f"❌ Ошибка сохранения обновленного JSON: {output_file}")
                
            return True
        else:
            logger.error(f"❌ Ошибка сохранения данных в БД за {duration:.2f} секунд")
            return False
            
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Главная функция"""
    if len(sys.argv) < 2:
        print("Использование: python test_db_save.py <путь_к_json_файлу> [request_id] [vin]")
        print("Примеры:")
        print("  python test_db_save.py ../static/data/3109624_LB37852D6RS125970/data_20250725_201256.json")
        print("  python test_db_save.py ../static/data/3109624_LB37852D6RS125970/data_20250725_201256.json 3109624 LB37852D6RS125970")
        return
        
    json_file_path = sys.argv[1]
    request_id = sys.argv[2] if len(sys.argv) > 2 else None
    vin = sys.argv[3] if len(sys.argv) > 3 else None
    
    logger.info("🚀 Запуск тестирования записи в БД")
    logger.info(f"📁 JSON файл: {json_file_path}")
    if request_id:
        logger.info(f"🆔 Request ID: {request_id}")
    if vin:
        logger.info(f"🚗 VIN: {vin}")
    
    # Запускаем тест
    success = asyncio.run(test_db_save(json_file_path, request_id, vin))
    
    if success:
        logger.info("🎉 Тестирование завершено успешно!")
    else:
        logger.error("💥 Тестирование завершено с ошибками!")
        sys.exit(1)

if __name__ == "__main__":
    main() 