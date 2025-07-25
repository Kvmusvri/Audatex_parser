import logging
import re
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from core.database.models import (
    ParserCarRequestStatus, ParserCarDetailGroupZone, 
    ParserCarDetail, ParserCarOptions
)

logger = logging.getLogger(__name__)

class DatabaseSession:
    """Контекстный менеджер для работы с базой данных"""
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        from core.database.models import async_session
        self.session = async_session()
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type is not None:
                await self.session.rollback()
            else:
                await self.session.commit()
            await self.session.close()

def validate_request_data(request_id: str, vin: str) -> bool:
    """Валидация входных данных"""
    if not request_id or not vin:
        logger.error("❌ request_id и vin обязательны")
        return False
    return True

def is_letter_code(code: str) -> bool:
    """Проверяет, является ли код буквенным (для комплектации)"""
    return bool(re.match(r'^[A-Za-z]', code))

def extract_option_code(option_title: str) -> str:
    """
    Извлекает код опции из названия
    Пример: "AZT - Идентификация производителя ЛКП / поиск кода цвета" -> "AZT"
    """
    if not option_title:
        return ""
    
    # Ищем код в начале названия (обычно 2-4 символа + дефис)
    parts = option_title.split(' - ', 1)
    if len(parts) > 1:
        code = parts[0].strip()
        # Проверяем что это похоже на код (буквы/цифры, 2-6 символов)
        if code and len(code) <= 6 and code.replace(' ', '').isalnum():
            return code
    
    # Если не нашли код в начале, ищем в названии
    # Ищем паттерн: буквы/цифры (2-6 символов) в начале или после пробела
    match = re.search(r'\b[A-Z0-9]{2,6}\b', option_title)
    if match:
        return match.group()
    
    return ""

def clean_option_title(option_title: str) -> str:
    """
    Очищает заголовок опции от кода и дефиса
    Пример: "AZT - Идентификация производителя ЛКП / поиск кода цвета" -> "Идентификация производителя ЛКП / поиск кода цвета"
    """
    if not option_title:
        return ""
    
    # Убираем код в начале (обычно 2-4 символа + дефис)
    parts = option_title.split(' - ', 1)
    if len(parts) > 1:
        code = parts[0].strip()
        # Проверяем что это похоже на код (буквы/цифры, 2-6 символов)
        if code and len(code) <= 6 and code.replace(' ', '').isalnum():
            return parts[1].strip()
    
    # Если не нашли код в начале, возвращаем как есть
    return option_title.strip()

def parse_detail_title(detail_title: str) -> List[Dict[str, str]]:
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
                    result.append({
                        'code': code,
                        'title': title
                    })
        
        return result
    except Exception as e:
        logger.error(f"❌ Ошибка парсинга заголовка '{detail_title}': {e}")
        return []

async def create_request_status_with_vin_status(
    session: AsyncSession, 
    request_id: str, 
    vin: str, 
    vin_status: str, 
    comment: str
) -> bool:
    """Создает запись статуса с vin_status"""
    try:
        if not validate_request_data(request_id, vin):
            return False
            
        status = ParserCarRequestStatus(
            request_id=request_id,
            vin=vin,
            vin_status=vin_status,
            comment=comment
        )
        session.add(status)
        await session.flush()
        
        logger.info(f"✅ Статус создан: request_id={request_id}, vin={vin}, vin_status={vin_status}")
        return True
        
    except IntegrityError as e:
        logger.warning(f"⚠️ Дубликат статуса: {e}")
        return True  # Дубликат не критичен
    except Exception as e:
        logger.error(f"❌ Ошибка создания статуса: {e}")
        return False

async def create_request_status(session: AsyncSession, request_id: str, vin: str, comment: str) -> bool:
    """Создает запись статуса (для обратной совместимости)"""
    return await create_request_status_with_vin_status(session, request_id, vin, "Неизвестно", comment)

async def create_group_zone(
    session: AsyncSession, 
    request_id: str, 
    vin: str, 
    zone_type: str, 
    title: str
) -> int:
    """Создает зону деталей"""
    try:
        if not validate_request_data(request_id, vin):
            return None
            
        zone = ParserCarDetailGroupZone(
            request_id=request_id,
            vin=vin,
            type=zone_type,
            title=title,
            source_from="AUDATEX"
        )
        session.add(zone)
        await session.flush()
        await session.refresh(zone)
        
        logger.info(f"✅ Зона создана: {zone_type} - {title}")
        return zone.id
        
    except IntegrityError as e:
        logger.warning(f"⚠️ Дубликат зоны: {e}")
        # Пытаемся найти существующую зону
        stmt = select(ParserCarDetailGroupZone).where(
            and_(
                ParserCarDetailGroupZone.request_id == request_id,
                ParserCarDetailGroupZone.vin == vin,
                ParserCarDetailGroupZone.type == zone_type,
                ParserCarDetailGroupZone.title == title
            )
        )
        result = await session.execute(stmt)
        existing_zone = result.scalar_one_or_none()
        return existing_zone.id if existing_zone else None
    except Exception as e:
        logger.error(f"❌ Ошибка создания зоны: {e}")
        return None

async def create_car_detail(
    session: AsyncSession, 
    request_id: str, 
    vin: str, 
    group_zone: str, 
    code: str, 
    title: str
) -> bool:
    """Создает запись детали автомобиля"""
    try:
        if not validate_request_data(request_id, vin):
            return False
            
        detail = ParserCarDetail(
            request_id=request_id,
            vin=vin,
            group_zone=group_zone,
            code=code,
            title=title,
            source_from="AUDATEX"
        )
        session.add(detail)
        await session.flush()
        
        logger.debug(f"✅ Деталь создана: {code} - {title}")
        return True
        
    except IntegrityError as e:
        logger.warning(f"⚠️ Дубликат детали: {e}")
        return True  # Дубликат не критичен
    except Exception as e:
        logger.error(f"❌ Ошибка создания детали: {e}")
        return False

async def create_car_option(
    session: AsyncSession,
    request_id: str,
    vin: str,
    zone_name: str,
    option_code: str,
    option_title: str,
    is_selected: bool = False
) -> bool:
    """Создает запись опции автомобиля"""
    try:
        if not validate_request_data(request_id, vin):
            return False
            
        option = ParserCarOptions(
            request_id=request_id,
            vin=vin,
            zone_name=zone_name,
            option_code=option_code,
            option_title=option_title,
            is_selected=is_selected,
            source_from="AUDATEX"
        )
        session.add(option)
        await session.flush()
        
        logger.debug(f"✅ Опция создана: {option_code} - {option_title}")
        return True
        
    except IntegrityError as e:
        logger.warning(f"⚠️ Дубликат опции: {e}")
        return True  # Дубликат не критичен
    except Exception as e:
        logger.error(f"❌ Ошибка создания опции: {e}")
        return False

async def save_parser_data_to_db(
    json_data: Dict[str, Any], 
    request_id: str, 
    vin: str,
    is_success: bool = True
) -> bool:
    """
    Сохраняет данные из JSON в базу данных
    
    Args:
        json_data: Данные из JSON файла
        request_id: ID запроса (из собранных данных)
        vin: VIN номер (из собранных данных)
        is_success: Успешность парсинга
    
    Returns:
        bool: True если сохранение прошло успешно
    """
    try:
        async with DatabaseSession() as session:
            # Определяем данные для записи в статус
            if is_success:
                # Используем собранные данные
                status_request_id = request_id
                status_vin = vin
                comment = "ysvg"
            else:
                # Используем данные из формы (входные данные)
                status_request_id = json_data.get('original_request_id', request_id)
                status_vin = json_data.get('original_vin', vin)
                comment = "nsvg"
            
            # Записываем статус запроса
            vin_status = json_data.get('vin_status', 'Неизвестно')
            await create_request_status_with_vin_status(
                session, status_request_id, status_vin, vin_status, comment
            )
            
            # Создаем зоны
            zone_ids = {}
            equipment_zone_id = None
            
            # Обрабатываем zone_data
            for zone in json_data.get('zone_data', []):
                zone_title = zone.get('title', '')
                has_pictograms = zone.get('has_pictograms', False)
                
                # Определяем тип зоны
                if has_pictograms:
                    zone_type = "WORKS"
                else:
                    zone_type = "DETAILS"
                
                # Создаем зону
                zone_id = await create_group_zone(
                    session, request_id, vin, zone_type, zone_title
                )
                zone_ids[zone_title] = zone_id
                
                # Обрабатываем детали в зоне
                for detail in zone.get('details', []):
                    detail_title = detail.get('title', '')
                    parsed_details = parse_detail_title(detail_title)
                    
                    for parsed_detail in parsed_details:
                        code = parsed_detail['code']
                        title = parsed_detail['title']
                        
                        # Определяем, к какой зоне относится деталь
                        if is_letter_code(code):
                            # Детали с буквенными кодами идут в EQUIPMENT
                            if equipment_zone_id is None:
                                equipment_zone_id = await create_group_zone(
                                    session, request_id, vin, "EQUIPMENT", "Комплектация"
                                )
                            group_zone = str(equipment_zone_id)
                        else:
                            # Обычные детали идут в текущую зону
                            group_zone = str(zone_id)
                        
                        # Создаем запись детали
                        await create_car_detail(
                            session, request_id, vin, group_zone, code, title
                        )
            
            # Создаем зону EQUIPMENT если её еще нет
            if equipment_zone_id is None:
                equipment_zone_id = await create_group_zone(
                    session, request_id, vin, "EQUIPMENT", "Комплектация"
                )
            
            # Обрабатываем опции автомобиля
            options_data = json_data.get('options_data', {})
            if options_data and options_data.get('success'):
                for zone in options_data.get('zones', []):
                    zone_title = zone.get('zone_title', '')  # Используем zone_title вместо zone_name
                    for option in zone.get('options', []):
                        option_title = option.get('title', '')
                        is_selected = option.get('is_selected', False)
                        
                        # Специальная обработка только для зоны "ПОДГОТОВКА К ОКРАСКЕ AZT"
                        if "ПОДГОТОВКА К ОКРАСКЕ AZT" in zone_title:
                            option_code = extract_option_code(option_title)  # Извлекаем код из названия
                            option_title = clean_option_title(option_title)  # Очищаем заголовок от кода
                        else:
                            # Для всех остальных зон используем код из поля code
                            option_code = option.get('code', '')
                        
                        # Берем статус выбора из поля selected (не is_selected)
                        is_selected = option.get('selected', False)
                        
                        await create_car_option(
                            session, request_id, vin, zone_title, 
                            option_code, option_title, is_selected
                        )
            
            logger.info(f"✅ Данные успешно сохранены в БД для request_id={request_id}, vin={vin}")
            return True
            
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных в БД: {e}")
        return False

def update_json_with_claim_number(json_data: Dict[str, Any], claim_number: str) -> Dict[str, Any]:
    """
    Обновляет JSON данные, добавляя claim_number рядом с vin_value
    
    Args:
        json_data: Исходные JSON данные
        claim_number: Номер заявки для добавления
    
    Returns:
        Dict[str, Any]: Обновленные JSON данные
    """
    try:
        # Создаем копию данных
        updated_data = json_data.copy()
        
        # Добавляем claim_number рядом с vin_value
        updated_data['claim_number'] = claim_number
        
        logger.info(f"✅ JSON обновлен с claim_number: {claim_number}")
        return updated_data
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления JSON с claim_number: {e}")
        return json_data

async def save_updated_json_to_file(json_data: Dict[str, Any], file_path: str) -> bool:
    """
    Сохраняет обновленный JSON в файл
    
    Args:
        json_data: JSON данные для сохранения
        file_path: Путь к файлу
    
    Returns:
        bool: True если сохранение прошло успешно
    """
    try:
        import json
        import os
        
        # Создаем директорию если её нет
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ JSON сохранен в файл: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения JSON в файл: {e}")
        return False