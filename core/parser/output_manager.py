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
        if not zone["graphics_not_available"] and zone.get("svg_path"):
            table_html += f'<a href="{zone["svg_path"]}" download class="svg-download" title="Скачать SVG"><span class="download-icon">⬇</span></a>'
        table_html += '</div>'
    if not zone_data:
        table_html += '<p>Зоны не найдены</p>'
    table_html += '</div>'
    logger.info("HTML-таблица зон создана")
    return table_html


# Сохраняет данные в JSON
def save_data_to_json(vin_value, zone_data, main_screenshot_path, main_svg_path, zones_table, all_svgs_zip, data_dir, claim_number, options_data=None):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(data_dir, f"data_{timestamp}.json")
    data = {
        "vin_value": vin_value,
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
        "options_data": options_data if options_data else {"success": False, "zones": []}
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Данные сохранены в {json_path}")
    if options_data and options_data.get("success"):
        stats = options_data.get("statistics", {})
        logger.info(f"💾 Опции сохранены: {stats.get('total_selected', 0)}/{stats.get('total_options', 0)} в {stats.get('total_zones', 0)} зонах")
    return json_path 