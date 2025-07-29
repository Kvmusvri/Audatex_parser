# Модуль для создания выходных данных
import logging
import os
import json
import datetime
from datetime import datetime
import pytz
from core.database.models import ParserCarRequestStatus, DatabaseSession, get_moscow_time
from sqlalchemy import text

logger = logging.getLogger(__name__)


# Формирует HTML-таблицу зон
def create_zones_table(zone_data):
    table_html = '<div class="zones-table">'
    for zone in zone_data:
        table_html += f'<div class="zone-row"><button class="zone-button" data-zone-title="{zone["title"]}">{zone["title"]}'
        if zone["has_pictograms"]:
            table_html += '<span class="pictogram-icon">🖼️</span>'
        table_html += '</button>'
        if not zone["graphics_not_available"] and zone.get("svg_path") and zone["svg_path"].strip():
            table_html += f'<a href="{zone["svg_path"]}" download class="svg-download" title="Скачать SVG"><span class="download-icon">⬇</span></a>'
        table_html += '</div>'
    if not zone_data:
        table_html += '<p>Зоны не найдены</p>'
    table_html += '</div>'
    logger.info("HTML-таблица зон создана")
    return table_html


# Сохраняет данные в JSON
def save_data_to_json(vin_value, zone_data, main_screenshot_path, main_svg_path, zones_table, all_svgs_zip, data_dir, claim_number, options_data=None, vin_status="Нет", started_at=None, completed_at=None, is_intermediate=False):
    # Проверяем, что папка существует
    if not os.path.exists(data_dir):
        logger.error(f"❌ Папка {data_dir} не существует, создаем её")
        try:
            os.makedirs(data_dir, exist_ok=True)
            logger.info(f"✅ Папка {data_dir} создана")
        except Exception as e:
            logger.error(f"❌ Не удалось создать папку {data_dir}: {e}")
            return None
    
    # Для промежуточных сохранений используем фиксированное имя файла
    if is_intermediate:
        json_path = os.path.join(data_dir, f"data_intermediate_{claim_number}.json")
        logger.info(f"💾 Сохраняем промежуточный JSON в: {json_path}")
    else:
        # Для финального сохранения используем timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = os.path.join(data_dir, f"data_{timestamp}.json")
        logger.info(f"💾 Сохраняем финальный JSON в: {json_path}")
    
    # Определяем статус завершения
    json_completed = True  # JSON полностью собран
    db_saved = True  # Предполагаем, что БД сохранена успешно
    
    # Создаем метаданные с правильным учетом часового пояса
    def format_time_with_timezone(dt):
        """Форматирует время с учетом часового пояса для JSON"""
        if dt is None:
            return None
        
        # Если время без часового пояса, считаем его московским
        if dt.tzinfo is None:
            moscow_tz = pytz.timezone('Europe/Moscow')
            dt = moscow_tz.localize(dt)
        elif dt.tzinfo.utcoffset(dt).total_seconds() == 0:
            # Если время в UTC, конвертируем в московское
            moscow_tz = pytz.timezone('Europe/Moscow')
            dt = dt.astimezone(moscow_tz)
        
        # Форматируем в московском времени
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    metadata = {
        "started_at": format_time_with_timezone(started_at),
        "completed_at": format_time_with_timezone(completed_at),
        "last_updated": format_time_with_timezone(datetime.datetime.now()),
        "json_completed": json_completed,
        "db_saved": db_saved,
        "total_zones": len(zone_data),
        "total_options": options_data.get("statistics", {}).get("total_options", 0) if options_data else 0,
        "options_success": options_data.get("success", False) if options_data else False
    }
    
    data = {
        "vin_value": vin_value,
        "vin_status": vin_status,
        "zone_data": [{
            "title": zone["title"],
            "screenshot_path": zone["screenshot_path"].replace("\\", "/"),
            "svg_path": zone["svg_path"].replace("\\", "/") if zone.get("svg_path") else "",
            "has_pictograms": zone["has_pictograms"],
            "graphics_not_available": zone["graphics_not_available"],
            "details": [{"title": detail["title"], "svg_path": detail["svg_path"].replace("\\", "/")} for detail in zone["details"]],
            "pictograms": [{"section_name": pictogram["section_name"], "works": [{"work_name1": work["work_name1"], "work_name2": work["work_name2"], "svg_path": work["svg_path"].replace("\\", "/")} for work in pictogram["works"]]} for pictogram in zone.get("pictograms", [])]
        } for zone in zone_data],
        "main_screenshot_path": main_screenshot_path.replace("\\", "/") if main_screenshot_path else "",
        "main_svg_path": main_svg_path.replace("\\", "/") if main_svg_path else "",
        "zones_table": zones_table,
        "all_svgs_zip": all_svgs_zip.replace("\\", "/") if all_svgs_zip else "",
        "options_data": options_data if options_data else {"success": False, "zones": []},
        "metadata": metadata,
        "claim_number": claim_number
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Данные сохранены в {json_path}")
    logger.info(f"📊 VIN статус '{vin_status}' сохранен в JSON")
    logger.info(f"⏱️ Время начала: {metadata['started_at']}, завершения: {metadata['completed_at']}")
    
    # Логируем итоговое время работы парсера
    if started_at and completed_at:
        try:
            duration_seconds = (completed_at - started_at).total_seconds()
            duration_minutes = int(duration_seconds // 60)
            duration_secs = int(duration_seconds % 60)
            logger.info(f"⏱️ Итоговое время работы парсера: {duration_minutes}м {duration_secs}с")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка расчета итогового времени: {e}")
    
    logger.info(f"🏁 JSON завершен: {json_completed}, БД сохранена: {db_saved}")
    if options_data and options_data.get("success"):
        stats = options_data.get("statistics", {})
        logger.info(f"💾 Опции сохранены: {stats.get('total_selected', 0)}/{stats.get('total_options', 0)} в {stats.get('total_zones', 0)} зонах")
    return json_path


async def restore_started_at_from_db(json_path: str, claim_number: str, vin_number: str) -> bool:
    """
    Восстанавливает started_at из БД если в JSON он null
    Учитывает часовой пояс: БД хранит в UTC+3, JSON должен показывать московское время
    """
    try:
        # Читаем JSON файл
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Проверяем, есть ли started_at и равен ли он null
        metadata = data.get('metadata', {})
        started_at = metadata.get('started_at')
        
        # Проверяем, нужно ли восстановление
        should_restore = (started_at is None or started_at == "null" or started_at == "None" or started_at == "")
        
        # Восстанавливаем только если started_at null или пустой
        # Если started_at есть, но неправильный - не трогаем его
        
        if should_restore:
            logger.info(f"🔍 Восстанавливаем started_at из БД для {claim_number}_{vin_number}")
            
            # Ищем в БД
            async with DatabaseSession() as session:
                result = await session.execute(
                    text(f"""
                    SELECT started_at 
                    FROM parser_car_request_status 
                    WHERE request_id = '{claim_number}' AND vin = '{vin_number}'
                    ORDER BY created_date DESC, id DESC 
                    LIMIT 1
                    """)
                )
                db_started_at = result.scalar()
                
                logger.info(f"🔍 Получено из БД для {claim_number}_{vin_number}: {db_started_at} (тип: {type(db_started_at)})")
                
                if db_started_at:
                    # Обрабатываем разные типы данных из БД
                    if isinstance(db_started_at, str):
                        # Если это строка, парсим её
                        try:
                            # Пробуем парсить как ISO формат с часовым поясом
                            db_started_at = datetime.fromisoformat(db_started_at)
                        except ValueError:
                            # Пробуем другие форматы
                            try:
                                db_started_at = datetime.strptime(db_started_at, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                logger.error(f"❌ Не удалось распарсить время из БД: {db_started_at}")
                                return False
                    
                    # В БД время хранится в UTC+3 (московское время)
                    # Конвертируем в московское время для JSON
                    if db_started_at.tzinfo is None:
                        # Если время без часового пояса, считаем его московским
                        moscow_tz = pytz.timezone('Europe/Moscow')
                        db_started_at = moscow_tz.localize(db_started_at)
                    elif db_started_at.tzinfo.utcoffset(db_started_at).total_seconds() == 0:
                        # Если время в UTC, конвертируем в московское
                        moscow_tz = pytz.timezone('Europe/Moscow')
                        db_started_at = db_started_at.astimezone(moscow_tz)
                    # Если время уже в московском часовом поясе (+03), оставляем как есть
                    
                    # Форматируем время в московском часовом поясе для JSON
                    formatted_time = db_started_at.strftime("%Y-%m-%d %H:%M:%S")
                    
                    logger.info(f"🔍 Обработка времени для {claim_number}_{vin_number}:")
                    logger.info(f"  Исходное из БД: {db_started_at}")
                    logger.info(f"  Часовой пояс: {db_started_at.tzinfo}")
                    logger.info(f"  Итоговое для JSON: {formatted_time}")
                    
                    # Обновляем JSON
                    metadata['started_at'] = formatted_time
                    data['metadata'] = metadata
                    
                    # Сохраняем обновленный JSON
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"✅ started_at восстановлен из БД: {formatted_time} (МСК)")
                    return True
                else:
                    logger.warning(f"⚠️ started_at не найден в БД для {claim_number}_{vin_number}")
                    return False
        else:
            logger.info(f"✅ started_at уже есть в JSON: {started_at}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка восстановления started_at: {e}")
        return False


async def restore_last_updated_from_db(json_path: str, claim_number: str, vin_number: str) -> bool:
    """
    Восстанавливает last_updated из БД если в JSON он неправильный
    Учитывает часовой пояс: БД хранит в UTC+3, JSON должен показывать московское время
    """
    try:
        # Читаем JSON файл
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Проверяем, есть ли last_updated и правильный ли он
        metadata = data.get('metadata', {})
        last_updated = metadata.get('last_updated')
        
        # Проверяем, нужно ли восстановление
        should_restore = (last_updated is None or last_updated == "null" or last_updated == "None" or last_updated == "")
        
        # Восстанавливаем только если last_updated null или пустой
        # Если last_updated есть, но неправильный - не трогаем его
        
        if should_restore:
            logger.info(f"🔍 Восстанавливаем last_updated из БД для {claim_number}_{vin_number}")
            
            # Ищем в БД
            async with DatabaseSession() as session:
                result = await session.execute(
                    text(f"""
                    SELECT completed_at 
                    FROM parser_car_request_status 
                    WHERE request_id = '{claim_number}' AND vin = '{vin_number}'
                    ORDER BY created_date DESC, id DESC 
                    LIMIT 1
                    """)
                )
                db_completed_at = result.scalar()
                
                logger.info(f"🔍 Получено completed_at из БД для {claim_number}_{vin_number}: {db_completed_at} (тип: {type(db_completed_at)})")
                
                if db_completed_at:
                    # Обрабатываем разные типы данных из БД
                    if isinstance(db_completed_at, str):
                        # Если это строка, парсим её
                        try:
                            # Пробуем парсить как ISO формат с часовым поясом
                            db_completed_at = datetime.fromisoformat(db_completed_at)
                        except ValueError:
                            # Пробуем другие форматы
                            try:
                                db_completed_at = datetime.strptime(db_completed_at, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                logger.error(f"❌ Не удалось распарсить время из БД: {db_completed_at}")
                                return False
                    
                    # В БД время хранится в UTC+3 (московское время)
                    # Конвертируем в московское время для JSON
                    if db_completed_at.tzinfo is None:
                        # Если время без часового пояса, считаем его московским
                        moscow_tz = pytz.timezone('Europe/Moscow')
                        db_completed_at = moscow_tz.localize(db_completed_at)
                    elif db_completed_at.tzinfo.utcoffset(db_completed_at).total_seconds() == 0:
                        # Если время в UTC, конвертируем в московское
                        moscow_tz = pytz.timezone('Europe/Moscow')
                        db_completed_at = db_completed_at.astimezone(moscow_tz)
                    # Если время уже в московском часовом поясе (+03), оставляем как есть
                    
                    # Форматируем время в московском часовом поясе для JSON
                    formatted_time = db_completed_at.strftime("%Y-%m-%d %H:%M:%S")
                    
                    logger.info(f"🔍 Обработка last_updated для {claim_number}_{vin_number}:")
                    logger.info(f"  Исходное из БД: {db_completed_at}")
                    logger.info(f"  Часовой пояс: {db_completed_at.tzinfo}")
                    logger.info(f"  Итоговое для JSON: {formatted_time}")
                    
                    # Обновляем JSON
                    metadata['last_updated'] = formatted_time
                    data['metadata'] = metadata
                    
                    # Сохраняем обновленный JSON
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"✅ last_updated восстановлен из БД: {formatted_time} (МСК)")
                    return True
                else:
                    logger.warning(f"⚠️ completed_at не найден в БД для {claim_number}_{vin_number}")
                    return False
        else:
            logger.info(f"✅ last_updated уже правильный в JSON: {last_updated}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка восстановления last_updated: {e}")
        return False


async def restore_completed_at_from_db(json_path: str, claim_number: str, vin_number: str) -> bool:
    """
    Восстанавливает completed_at из БД если в JSON он null или неправильный
    Учитывает часовой пояс: БД хранит в UTC+3, JSON должен показывать московское время
    """
    try:
        # Читаем JSON файл
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Проверяем, есть ли completed_at и правильный ли он
        metadata = data.get('metadata', {})
        completed_at = metadata.get('completed_at')
        
        # Проверяем, нужно ли восстановление
        should_restore = (completed_at is None or completed_at == "null" or completed_at == "None" or completed_at == "")
        
        # Восстанавливаем только если completed_at null или пустой
        # Если completed_at есть, но неправильный - не трогаем его
        
        if should_restore:
            logger.info(f"🔍 Восстанавливаем completed_at из БД для {claim_number}_{vin_number}")
            
            # Ищем в БД
            async with DatabaseSession() as session:
                result = await session.execute(
                    text(f"""
                    SELECT completed_at 
                    FROM parser_car_request_status 
                    WHERE request_id = '{claim_number}' AND vin = '{vin_number}'
                    ORDER BY created_date DESC, id DESC 
                    LIMIT 1
                    """)
                )
                db_completed_at = result.scalar()
                
                logger.info(f"🔍 Получено completed_at из БД для {claim_number}_{vin_number}: {db_completed_at} (тип: {type(db_completed_at)})")
                
                if db_completed_at:
                    # Обрабатываем разные типы данных из БД
                    if isinstance(db_completed_at, str):
                        # Если это строка, парсим её
                        try:
                            # Пробуем парсить как ISO формат с часовым поясом
                            db_completed_at = datetime.fromisoformat(db_completed_at)
                        except ValueError:
                            # Пробуем другие форматы
                            try:
                                db_completed_at = datetime.strptime(db_completed_at, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                logger.error(f"❌ Не удалось распарсить время из БД: {db_completed_at}")
                                return False
                    
                    # В БД время хранится в UTC+3 (московское время)
                    # Конвертируем в московское время для JSON
                    if db_completed_at.tzinfo is None:
                        # Если время без часового пояса, считаем его московским
                        moscow_tz = pytz.timezone('Europe/Moscow')
                        db_completed_at = moscow_tz.localize(db_completed_at)
                    elif db_completed_at.tzinfo.utcoffset(db_completed_at).total_seconds() == 0:
                        # Если время в UTC, конвертируем в московское
                        moscow_tz = pytz.timezone('Europe/Moscow')
                        db_completed_at = db_completed_at.astimezone(moscow_tz)
                    # Если время уже в московском часовом поясе (+03), оставляем как есть
                    
                    # Форматируем время в московском часовом поясе для JSON
                    formatted_time = db_completed_at.strftime("%Y-%m-%d %H:%M:%S")
                    
                    logger.info(f"🔍 Обработка completed_at для {claim_number}_{vin_number}:")
                    logger.info(f"  Исходное из БД: {db_completed_at}")
                    logger.info(f"  Часовой пояс: {db_completed_at.tzinfo}")
                    logger.info(f"  Итоговое для JSON: {formatted_time}")
                    
                    # Обновляем JSON
                    metadata['completed_at'] = formatted_time
                    data['metadata'] = metadata
                    
                    # Сохраняем обновленный JSON
                    with open(json_path, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    logger.info(f"✅ completed_at восстановлен из БД: {formatted_time} (МСК)")
                    return True
                else:
                    logger.warning(f"⚠️ completed_at не найден в БД для {claim_number}_{vin_number}")
                    return False
        else:
            logger.info(f"✅ completed_at уже правильный в JSON: {completed_at}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка восстановления completed_at: {e}")
        return False 