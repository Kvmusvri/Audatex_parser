import logging
import re
import json
import os
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, insert, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from core.database.models import (
    ParserCarRequestStatus, ParserCarDetailGroupZone, 
    ParserCarDetail, ParserCarOptions, ParserScheduleSettings, DatabaseSession, get_moscow_time
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

logger = logging.getLogger(__name__)

# Создаем синхронный движок для аутентификации только если не в контексте документации
sync_engine = None
SyncSessionLocal = None

def _init_engine():
    """Инициализация engine только при необходимости"""
    global sync_engine, SyncSessionLocal
    if sync_engine is None:
        try:
            database_url = os.getenv('DATABASE_URL')
            if database_url:
                sync_engine = create_engine(database_url.replace('+asyncpg', '+psycopg2'))
                SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)
        except Exception as e:
            logger.warning(f"Не удалось создать engine: {e}")
            # Создаем dummy engine для документации
            sync_engine = create_engine('sqlite:///:memory:')
            SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

def get_db() -> Session:
    """Получение синхронной сессии БД"""
    _init_engine()
    db = SyncSessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise

def validate_request_data(data: Dict[str, Any]) -> bool:
    """Валидация входных данных"""
    required_fields = ['request_id', 'vin']
    return all(field in data and data[field] for field in required_fields)

def is_letter_code(code: str) -> bool:
    """Проверяет, содержит ли код буквы"""
    try:
        int(code)
        return False
    except ValueError:
        return True

def parse_detail_title(detail_title: str) -> List[tuple[str, str]]:
    """Парсит заголовок детали на код и название"""
    try:
        # Разделяем по запятым
        parts = [part.strip() for part in detail_title.split(',')]
        result = []
        
        for part in parts:
            if not part:
                continue
                
            # Ищем код в начале (цифры и буквы)
            code_match = re.match(r'^([A-Za-z0-9]+)', part)
            if code_match:
                code = code_match.group(1)
                title = part[len(code):].strip().strip('- ')
                if title:
                    result.append((code, title))
                else:
                    # Если нет названия после кода, используем весь текст как название
                    result.append((code, part))
            else:
                # Если нет кода в начале, используем весь текст как название
                result.append(('', part))
        
        return result
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга заголовка '{detail_title}': {e}")
        return []

def extract_option_code(title: str) -> str:
    """Извлекает код опции из заголовка"""
    match = re.match(r'^([A-Z0-9]+)', title)
    return match.group(1) if match else ''

def clean_option_title(title: str) -> str:
    """Очищает заголовок опции от кода"""
    return re.sub(r'^[A-Z0-9]+\s*[-–—]\s*', '', title).strip()

def normalize_path_for_os(path: str) -> str:
    if not path:
        logger.debug("Пустой путь, возвращаем пустую строку")
        return ""
    original = path
    normalized = str(Path(path))
    if original != normalized:
        logger.info(f"Путь нормализован: '{original}' -> '{normalized}'")
    return normalized

async def upsert_request_status(session, claim_number: str, vin: str, status_data: dict):
    """UPSERT для статуса заявки"""
    # Нормализуем file_path под текущую ОС
    file_path = status_data.get('file_path', None)
    if file_path:
        file_path = normalize_path_for_os(file_path)
    
    await session.execute(
        pg_insert(ParserCarRequestStatus).values(
            request_id=claim_number,
            vin=vin,
            vin_status=status_data.get('vin_status', 'Неизвестно'),
            comment=status_data.get('comment', ''),
            is_success=status_data.get('is_success', True),
            file_path=file_path,  # Нормализованный путь
            started_at=status_data.get('started_at'),
            completed_at=status_data.get('completed_at'),
            created_date=func.current_date()
        ).on_conflict_do_update(
            index_elements=['request_id', 'vin', 'created_date'],
            set_={
                'vin_status': status_data.get('vin_status', 'Неизвестно'),
                'comment': status_data.get('comment', ''),
                'is_success': status_data.get('is_success', True),
                'file_path': file_path,  # Нормализованный путь
                'started_at': status_data.get('started_at'),
                'completed_at': status_data.get('completed_at')
            }
        )
    )

async def save_details_batch(session, claim_number: str, vin: str, details: List[dict]):
    """Batch сохранение деталей"""
    if not details:
        return
    
    batch_data = []
    current_date = date.today()
    
    for detail in details:
        batch_data.append({
            "request_id": claim_number,
            "vin": vin,
            "group_zone": detail.get("group_zone", ""),
            "code": detail.get("code", ""),
            "title": detail.get("title", ""),
            "source_from": detail.get("source_from", ""),
            "svg_path": normalize_path_for_os(detail.get("svg_path", None)),  # Нормализованный путь к SVG детали
            "created_date": current_date
        })
    
    await session.execute(insert(ParserCarDetail), batch_data)
    logger.info(f"✅ Batch сохранено {len(batch_data)} деталей")

async def save_zones_batch(session, claim_number: str, vin: str, zones: List[dict]):
    """Batch сохранение зон"""
    if not zones:
        return
    
    batch_data = []
    current_date = date.today()
    
    for zone in zones:
        batch_data.append({
            "request_id": claim_number,
            "vin": vin,
            "type": zone.get("type", ""),
            "title": zone.get("title", ""),
            "source_from": zone.get("source_from", ""),
            "screenshot_path": normalize_path_for_os(zone.get("screenshot_path", None)),  # Нормализованный путь к скриншоту зоны
            "svg_path": normalize_path_for_os(zone.get("svg_path", None)),  # Нормализованный путь к SVG зоны
            "created_date": current_date
        })
    
    await session.execute(insert(ParserCarDetailGroupZone), batch_data)
    logger.info(f"✅ Batch сохранено {len(batch_data)} зон")

async def save_options_batch(session, claim_number: str, vin: str, options: List[dict]):
    """Batch сохранение опций"""
    if not options:
        return
    
    batch_data = []
    current_date = date.today()
    
    for option in options:
        batch_data.append({
            "request_id": claim_number,
            "vin": vin,
            "zone_name": option.get("zone_name", ""),
            "option_code": option.get("option_code", ""),
            "option_title": option.get("option_title", ""),
            "is_selected": option.get("is_selected", False),
            "source_from": option.get("source_from", ""),
            "created_date": current_date
        })
    
    await session.execute(insert(ParserCarOptions), batch_data)
    logger.info(f"✅ Batch сохранено {len(batch_data)} опций")

async def delete_existing_request_data(session, claim_number: str, vin: str):
    """Быстрое удаление всех данных заявки по индексам"""
    await session.execute(
        delete(ParserCarOptions)
        .where(ParserCarOptions.request_id == claim_number)
        .where(ParserCarOptions.vin == vin)
    )
    
    await session.execute(
        delete(ParserCarDetail)
        .where(ParserCarDetail.request_id == claim_number)
        .where(ParserCarDetail.vin == vin)
    )
    
    await session.execute(
        delete(ParserCarDetailGroupZone)
        .where(ParserCarDetailGroupZone.request_id == claim_number)
        .where(ParserCarDetailGroupZone.vin == vin)
    )
    
    await session.execute(
        delete(ParserCarRequestStatus)
        .where(ParserCarRequestStatus.request_id == claim_number)
        .where(ParserCarRequestStatus.vin == vin)
    )

async def save_parser_data_to_db(parser_data: dict, claim_number: str, vin: str, is_success: bool = True, started_at=None, completed_at=None, file_path: str = None, svg_collection: bool = True) -> bool:
    """Оптимизированное сохранение данных парсера с batch операциями"""
    try:
        async with DatabaseSession() as session:
            # Удаляем существующие данные
            await delete_existing_request_data(session, claim_number, vin)
            
            # Подготавливаем данные для batch операций
            details = []
            zones = []
            options = []
            
            # Создаем зоны и получаем их ID
            zone_ids = {}
            equipment_zone_id = None
            
            # Обрабатываем зоны и детали
            for zone in parser_data.get("zone_data", []):
                zone_title = zone.get('title', '')
                has_pictograms = zone.get('has_pictograms', False)
                
                # Определяем тип зоны
                if has_pictograms:
                    zone_type = "WORKS"
                else:
                    zone_type = "DETAILS"
                
                # Создаем зону с нормализованными путями
                screenshot_path = zone.get("screenshot_path", None)
                svg_path = zone.get("svg_path", None)
                
                # Нормализуем пути под текущую ОС
                screenshot_path = normalize_path_for_os(screenshot_path)
                svg_path = normalize_path_for_os(svg_path)
                
                zone_data = {
                    "request_id": claim_number,
                    "vin": vin,
                    "type": zone_type,
                    "title": zone_title,
                    "source_from": "AUDATEX",
                    "screenshot_path": screenshot_path,
                    "svg_path": svg_path,
                    "created_date": date.today()
                }
                zones.append(zone_data)
                logger.info(f"✅ Зона '{zone_title}' сохранена с путями: screenshot={screenshot_path}, svg={svg_path}")
                
                # Сохраняем зону и получаем ID
                await session.execute(insert(ParserCarDetailGroupZone), [zone_data])
                await session.flush()
                
                # Получаем ID созданной зоны
                result = await session.execute(
                    select(ParserCarDetailGroupZone.id)
                    .where(ParserCarDetailGroupZone.request_id == claim_number)
                    .where(ParserCarDetailGroupZone.vin == vin)
                    .where(ParserCarDetailGroupZone.title == zone_title)
                    .order_by(ParserCarDetailGroupZone.id.desc())
                )
                zone_id = result.scalar()
                zone_ids[zone_title] = str(zone_id)
                
                # Обрабатываем детали в зоне
                for detail in zone.get('details', []):
                    # Детали приходят в формате {"title": "название детали", "svg_path": "путь"}
                    detail_title = detail.get('title', '')
                    
                    # Парсим заголовок детали на код и название
                    parsed_details = parse_detail_title(detail_title)
                    
                    for parsed_detail in parsed_details:
                        code = parsed_detail[0]
                        title = parsed_detail[1]
                        
                        # Определяем, к какой зоне относится деталь
                        if is_letter_code(code):
                            # Детали с буквенными кодами идут в EQUIPMENT
                            if equipment_zone_id is None:
                                equipment_zone_data = {
                                    "request_id": claim_number,
                                    "vin": vin,
                                    "type": "EQUIPMENT",
                                    "title": "Комплектация",
                                    "source_from": "AUDATEX",
                                    "screenshot_path": None,  # У зоны комплектации нет скриншота
                                    "svg_path": None,  # У зоны комплектации нет SVG
                                    "created_date": date.today()
                                }
                                await session.execute(insert(ParserCarDetailGroupZone), [equipment_zone_data])
                                await session.flush()
                                
                                result = await session.execute(
                                    select(ParserCarDetailGroupZone.id)
                                    .where(ParserCarDetailGroupZone.request_id == claim_number)
                                    .where(ParserCarDetailGroupZone.vin == vin)
                                    .where(ParserCarDetailGroupZone.title == "Комплектация")
                                )
                                equipment_zone_id = str(result.scalar())
                            
                            group_zone = equipment_zone_id
                        else:
                            # Обычные детали идут в текущую зону
                            group_zone = str(zone_id)
                        
                        # Нормализуем путь к SVG детали
                        detail_svg_path = normalize_path_for_os(detail.get("svg_path", None))
                        
                        detail_data = {
                            "request_id": claim_number,
                            "vin": vin,
                            "group_zone": group_zone,
                            "code": code,
                            "title": title,
                            "source_from": "AUDATEX",
                            "svg_path": detail_svg_path,
                            "created_date": date.today()
                        }
                        details.append(detail_data)
                        logger.info(f"✅ Деталь '{title}' сохранена с SVG: {detail_svg_path}")
            
            # Обрабатываем опции автомобиля
            options_data = parser_data.get('options_data', {})
            if options_data and options_data.get('success'):
                for zone in options_data.get('zones', []):
                    zone_title = zone.get('zone_title', '')
                    for option in zone.get('options', []):
                        option_title = option.get('title', '')
                        
                        # Специальная обработка только для зоны "ПОДГОТОВКА К ОКРАСКЕ AZT"
                        if "ПОДГОТОВКА К ОКРАСКЕ AZT" in zone_title:
                            option_code = extract_option_code(option_title)
                            option_title = clean_option_title(option_title)
                        else:
                            # Для всех остальных зон используем код из поля code
                            option_code = option.get('code', '')
                        
                        # Берем статус выбора из поля selected (не is_selected)
                        is_selected = option.get('selected', False)
                        
                        option_data = {
                            "request_id": claim_number,
                            "vin": vin,
                            "zone_name": zone_title,
                            "option_code": option_code,
                            "option_title": option_title,
                            "is_selected": is_selected,
                            "source_from": "AUDATEX",
                            "created_date": date.today()
                        }
                        options.append(option_data)
            
            # Используем переданные временные метки или текущее время
            if started_at is None:
                started_at = get_moscow_time()
            if completed_at is None:
                completed_at = get_moscow_time()
            
            # Определяем comment на основе успешности и состояния SVG
            if is_success and svg_collection:
                comment = "ysvg"
            else:
                comment = "nsvg"
            
            status_data = {
                "vin_status": parser_data.get("vin_status", "Неизвестно"),
                "comment": comment,
                "is_success": is_success,
                "started_at": started_at,
                "completed_at": completed_at,
                "file_path": normalize_path_for_os(file_path) if file_path else None  # Нормализуем путь
            }
            
            # Batch операции
            await upsert_request_status(session, claim_number, vin, status_data)
            await save_details_batch(session, claim_number, vin, details)
            await save_options_batch(session, claim_number, vin, options)
            
            logger.info(f"✅ Данные успешно сохранены: {claim_number}_{vin}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения в БД: {e}")
        return False

def update_json_with_claim_number(json_data: Dict[str, Any], claim_number: str) -> Dict[str, Any]:
    """Обновляет JSON данные, добавляя claim_number"""
    try:
        updated_data = json_data.copy()
        updated_data['claim_number'] = claim_number
        logger.info(f"✅ JSON обновлен с claim_number: {claim_number}")
        return updated_data
    except Exception as e:
        logger.error(f"❌ Ошибка обновления JSON с claim_number: {e}")
        return json_data

async def save_updated_json_to_file(json_data: Dict[str, Any], file_path: str) -> bool:
    """Сохраняет обновленный JSON в файл"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ JSON успешно обновлен и сохранен: {file_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения JSON: {e}")
        return False

# Функции для работы с настройками расписания парсера

async def get_schedule_settings(session: AsyncSession) -> Dict[str, Any]:
    """Получает текущие настройки расписания парсера"""
    try:
        result = await session.execute(
            select(ParserScheduleSettings)
            .where(ParserScheduleSettings.is_active == True)
            .order_by(ParserScheduleSettings.updated_at.desc())
            .limit(1)
        )
        
        settings = result.scalar_one_or_none()
        
        if settings:
            return {
                'start_time': settings.start_time,
                'end_time': settings.end_time,
                'is_active': settings.is_active,
                'updated_at': settings.updated_at.isoformat() if settings.updated_at else None
            }
        else:
            # Возвращаем дефолтные настройки если нет сохраненных
            return {
                'start_time': '09:00',
                'end_time': '18:00',
                'is_active': False,
                'updated_at': None
            }
            
    except Exception as e:
        logger.error(f"❌ Ошибка получения настроек расписания: {e}")
        return {
            'start_time': '09:00',
            'end_time': '18:00',
            'is_active': False,
            'updated_at': None
        }

async def save_schedule_settings(session: AsyncSession, start_time: str, end_time: str) -> bool:
    """Сохраняет настройки расписания парсера"""
    try:
        # Деактивируем все предыдущие настройки
        await session.execute(
            ParserScheduleSettings.__table__.update()
            .where(ParserScheduleSettings.is_active == True)
            .values(is_active=False)
        )
        
        # Создаем новые настройки
        new_settings = ParserScheduleSettings(
            start_time=start_time,
            end_time=end_time,
            is_active=True
        )
        
        session.add(new_settings)
        await session.commit()
        
        logger.info(f"✅ Настройки расписания сохранены: {start_time} - {end_time}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения настроек расписания: {e}")
        await session.rollback()
        return False

def is_time_in_working_hours(start_time: str, end_time: str) -> bool:
    """Проверяет, находится ли текущее время в рабочем диапазоне"""
    try:
        moscow_time = get_moscow_time()
        current_time = moscow_time.strftime('%H:%M')
        
        # Конвертируем время в минуты для сравнения
        def time_to_minutes(time_str: str) -> int:
            hours, minutes = map(int, time_str.split(':'))
            return hours * 60 + minutes
        
        current_minutes = time_to_minutes(current_time)
        start_minutes = time_to_minutes(start_time)
        end_minutes = time_to_minutes(end_time)
        
        if start_minutes <= end_minutes:
            # Обычный случай: 09:00 - 18:00
            return start_minutes <= current_minutes <= end_minutes
        else:
            # Переход через полночь: 21:46 - 23:00
            # Рабочее время: с 21:46 до 23:00 (включая переход через полночь)
            return current_minutes >= start_minutes or current_minutes <= end_minutes
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки рабочего времени: {e}")
        return False

def get_time_to_start(start_time: str) -> int:
    """Возвращает количество минут до начала работы"""
    try:
        moscow_time = get_moscow_time()
        current_time = moscow_time.strftime('%H:%M')
        
        def time_to_minutes(time_str: str) -> int:
            hours, minutes = map(int, time_str.split(':'))
            return hours * 60 + minutes
        
        current_minutes = time_to_minutes(current_time)
        start_minutes = time_to_minutes(start_time)
        
        # Если текущее время меньше времени начала, ждем до начала
        if current_minutes < start_minutes:
            return start_minutes - current_minutes
        else:
            # Если текущее время больше времени начала, 
            # то начало уже прошло сегодня, ждем до завтра
            return (24 * 60) - current_minutes + start_minutes
            
    except Exception as e:
        logger.error(f"❌ Ошибка расчета времени до начала: {e}")
        return 0

def get_time_to_end(end_time: str) -> int:
    """Возвращает количество минут до окончания работы"""
    try:
        moscow_time = get_moscow_time()
        current_time = moscow_time.strftime('%H:%M')
        
        def time_to_minutes(time_str: str) -> int:
            hours, minutes = map(int, time_str.split(':'))
            return hours * 60 + minutes
        
        current_minutes = time_to_minutes(current_time)
        end_minutes = time_to_minutes(end_time)
        
        if current_minutes <= end_minutes:
            return end_minutes - current_minutes
        else:
            # До следующего дня
            return (24 * 60) - current_minutes + end_minutes
            
    except Exception as e:
        logger.error(f"❌ Ошибка расчета времени до окончания: {e}")
        return 0