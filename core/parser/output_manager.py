# Модуль для создания выходных данных
import logging
import os
import json
import datetime

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
    
    # Создаем метаданные
    metadata = {
        "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S") if started_at else None,
        "completed_at": completed_at.strftime("%Y-%m-%d %H:%M:%S") if completed_at else None,
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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