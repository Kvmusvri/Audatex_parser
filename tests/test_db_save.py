import asyncio
import json
import logging
import os
from core.database.models import start_db, get_moscow_time, engine, async_session
from core.database.requests import save_parser_data_to_db
from sqlalchemy import text, select
from core.database.models import ParserCarDetail, ParserCarDetailGroupZone, ParserCarRequestStatus, ParserCarOptions

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def drop_existing_tables():
    """Удаляет существующие таблицы для пересоздания"""
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS parser_car_options CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS parser_car_detail CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS parser_car_detail_group_zone CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS parser_car_request_status CASCADE"))
        logger.info("✅ Старые таблицы удалены")

def find_latest_json_file():
    """Находит самый новый JSON файл в static/data"""
    data_dir = "static/data"
    if not os.path.exists(data_dir):
        logger.error(f"Директория {data_dir} не существует")
        return None
    
    latest_file = None
    latest_time = 0
    
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.json'):
                file_path = os.path.join(root, file)
                file_time = os.path.getctime(file_path)
                if file_time > latest_time:
                    latest_time = file_time
                    latest_file = file_path
    
    return latest_file

def extract_claim_number_from_path(file_path):
    """Извлекает claim_number из пути к файлу"""
    # Путь вида: static/data/3109624_LB37852D6RS125970/data_20250725_224349.json
    parts = file_path.split(os.sep)
    if len(parts) >= 3:
        folder_name = parts[2]  # 3109624_LB37852D6RS125970
        claim_number = folder_name.split('_')[0]  # 3109624
        return claim_number
    return None

async def check_saved_data(claim_number: str, vin: str):
    """Проверяет сохраненные данные"""
    async with async_session() as session:
        # Проверяем статус
        status_result = await session.execute(
            select(ParserCarRequestStatus)
            .where(ParserCarRequestStatus.request_id == claim_number)
            .where(ParserCarRequestStatus.vin == vin)
        )
        status = status_result.scalar_one_or_none()
        if status:
            logger.info(f"✅ Статус: {status.vin_status}, комментарий: {status.comment}")
        
        # Проверяем зоны
        zones_result = await session.execute(
            select(ParserCarDetailGroupZone)
            .where(ParserCarDetailGroupZone.request_id == claim_number)
            .where(ParserCarDetailGroupZone.vin == vin)
        )
        zones = zones_result.scalars().all()
        logger.info(f"✅ Зон создано: {len(zones)}")
        for zone in zones[:3]:  # Показываем первые 3 зоны
            logger.info(f"   - ID: {zone.id}, Тип: {zone.type}, Название: {zone.title}")
        
        # Проверяем детали
        details_result = await session.execute(
            select(ParserCarDetail)
            .where(ParserCarDetail.request_id == claim_number)
            .where(ParserCarDetail.vin == vin)
        )
        details = details_result.scalars().all()
        logger.info(f"✅ Деталей создано: {len(details)}")
        
        # Проверяем, что group_zone содержит ID, а не название
        sample_details = details[:5]
        for detail in sample_details:
            logger.info(f"   - Код: {detail.code}, Название: {detail.title[:50]}..., Group_zone: {detail.group_zone}")
        
        # Проверяем опции
        options_result = await session.execute(
            select(ParserCarOptions)
            .where(ParserCarOptions.request_id == claim_number)
            .where(ParserCarOptions.vin == vin)
        )
        options = options_result.scalars().all()
        logger.info(f"✅ Опций создано: {len(options)}")
        
        # Проверяем AZT опции
        azt_options = [opt for opt in options if "AZT" in opt.option_code]
        if azt_options:
            logger.info(f"✅ AZT опций найдено: {len(azt_options)}")
            for opt in azt_options[:2]:
                logger.info(f"   - Код: {opt.option_code}, Название: {opt.option_title[:50]}...")
        
        # Проверяем партиции
        await check_partitions(session)

async def check_partitions(session):
    """Проверяет созданные партиции"""
    try:
        # Проверяем партиции для всех таблиц
        tables = [
            'parser_car_detail',
            'parser_car_detail_group_zone', 
            'parser_car_request_status',
            'parser_car_options'
        ]
        
        for table in tables:
            result = await session.execute(text(f"""
                SELECT schemaname, tablename 
                FROM pg_tables 
                WHERE tablename LIKE '{table}_%' 
                AND schemaname = 'public'
                ORDER BY tablename
            """))
            partitions = result.fetchall()
            logger.info(f"📊 Партиции для {table}: {len(partitions)}")
            for partition in partitions[:3]:  # Показываем первые 3
                logger.info(f"   - {partition[1]}")
                
    except Exception as e:
        logger.warning(f"⚠️ Ошибка проверки партиций: {e}")

async def test_database_optimizations():
    """Тестирует все оптимизации базы данных с реальными данными"""
    
    # Удаляем старые таблицы
    await drop_existing_tables()
    
    # Создаем таблицы
    await start_db()
    logger.info("✅ Таблицы созданы")
    
    # Находим реальный JSON файл
    json_file = find_latest_json_file()
    if not json_file:
        logger.error("❌ Не найден JSON файл для тестирования")
        return
    
    logger.info(f"📁 Используем файл: {json_file}")
    
    # Читаем реальные данные
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            real_data = json.load(f)
        
        # Извлекаем claim_number из пути
        claim_number = extract_claim_number_from_path(json_file)
        if not claim_number:
            claim_number = "3109624"  # Fallback
        
        vin_value = real_data.get("vin_value", "LB37852D6RS125970")
        
        logger.info(f"🔍 Тестируем с данными: claim_number={claim_number}, vin={vin_value}")
        
        # Тестируем сохранение реальных данных
        logger.info("🔄 Тестируем сохранение реальных данных...")
        success = await save_parser_data_to_db(
            real_data, 
            claim_number, 
            vin_value, 
            is_success=True
        )
        
        if success:
            logger.info("✅ Тест сохранения реальных данных прошел успешно")
            
            # Проверяем сохраненные данные
            logger.info("🔍 Проверяем сохраненные данные...")
            await check_saved_data(claim_number, vin_value)
            
            # Проверяем временные метки
            moscow_time = get_moscow_time()
            logger.info(f"🕐 Московское время: {moscow_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            
            # Тестируем повторное сохранение (UPSERT)
            logger.info("🔄 Тестируем повторное сохранение (UPSERT)...")
            success2 = await save_parser_data_to_db(
                real_data, 
                claim_number, 
                vin_value, 
                is_success=True
            )
            
            if success2:
                logger.info("✅ UPSERT работает корректно с реальными данными")
                
                # Выводим статистику
                zone_count = len(real_data.get("zone_data", []))
                total_details = sum(len(zone.get("details", [])) for zone in real_data.get("zone_data", []))
                options_data = real_data.get("options_data", {})
                total_options = sum(len(zone.get("options", [])) for zone in options_data.get("zones", []))
                
                logger.info(f"📊 Статистика данных:")
                logger.info(f"   - Зон: {zone_count}")
                logger.info(f"   - Деталей: {total_details}")
                logger.info(f"   - Опций: {total_options}")
                logger.info(f"   - VIN статус: {real_data.get('vin_status', 'Неизвестно')}")
                
            else:
                logger.error("❌ Ошибка UPSERT с реальными данными")
        else:
            logger.error("❌ Ошибка сохранения реальных данных")
            
    except Exception as e:
        logger.error(f"❌ Ошибка чтения JSON файла: {e}")

if __name__ == "__main__":
    asyncio.run(test_database_optimizations()) 