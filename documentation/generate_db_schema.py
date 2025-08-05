#!/usr/bin/env python3
"""
Скрипт для генерации схемы БД из SQLAlchemy моделей
"""
import sys
import os
sys.path.insert(0, os.path.abspath('..'))

from core.database.models import Base
from sqlalchemy import inspect


def get_table_info():
    """Извлекает информацию о таблицах из моделей"""
    tables_info = {}
    
    for table_name in Base.metadata.tables:
        table = Base.metadata.tables[table_name]
        columns = []
        
        for column in table.columns:
            col_info = {
                'name': column.name,
                'type': str(column.type),
                'nullable': column.nullable,
                'primary_key': column.primary_key,
                'foreign_key': bool(column.foreign_keys),
                'default': column.default,
                'index': column.index
            }
            columns.append(col_info)
        
        # Получаем связи
        relationships = []
        for fk in table.foreign_keys:
            relationships.append({
                'from_column': fk.parent.name,
                'to_table': fk.column.table.name,
                'to_column': fk.column.name
            })
        
        tables_info[table_name] = {
            'columns': columns,
            'relationships': relationships,
            'table': table
        }
    
    return tables_info

def generate_rst_schema(tables_info):
    """Генерирует схему БД в формате RST для интеграции в документацию"""
    rst = "Структура базы данных\n"
    rst += "====================\n\n"
    
    for table_name, info in tables_info.items():
        # Заголовок таблицы
        rst += f"{table_name}\n"
        rst += "-" * len(table_name) + "\n\n"
        
        # Описание таблицы (можно добавить позже)
        table_descriptions = {
            'parser_car_detail': 'Детали автомобиля',
            'parser_car_detail_group_zone': 'Группы зон деталей',
            'parser_car_request_status': 'Статус обработки заявок',
            'parser_car_options': 'Опции автомобиля',
            'parser_schedule_settings': 'Настройки расписания',
            'users': 'Пользователи системы',
            'user_sessions': 'Сессии пользователей'
        }
        
        if table_name in table_descriptions:
            rst += f"{table_descriptions[table_name]}\n\n"
        
        # Упрощенная RST таблица
        rst += ".. list-table:: Структура таблицы\n"
        rst += "   :widths: 20 15 10 12 12 8\n"
        rst += "   :header-rows: 1\n\n"
        rst += "   * - Поле\n"
        rst += "     - Тип\n"
        rst += "     - Nullable\n"
        rst += "     - Primary Key\n"
        rst += "     - Foreign Key\n"
        rst += "     - Индекс\n"
        
        for col in info['columns']:
            nullable = "✓" if col['nullable'] else "✗"
            pk = "✓" if col['primary_key'] else ""
            fk = "✓" if col['foreign_key'] else ""
            index = "✓" if col['index'] else ""
            
            rst += f"   * - {col['name']}\n"
            rst += f"     - {col['type']}\n"
            rst += f"     - {nullable}\n"
            rst += f"     - {pk}\n"
            rst += f"     - {fk}\n"
            rst += f"     - {index}\n"
        
        rst += "\n"
        
        # Добавляем связи
        if info['relationships']:
            rst += "**Связи:**\n"
            for rel in info['relationships']:
                rst += f"- {rel['from_column']} → {rel['to_table']}.{rel['to_column']}\n"
            rst += "\n"
    
    return rst

if __name__ == "__main__":
    tables_info = get_table_info()
    
    # Генерируем RST схему
    rst_schema = generate_rst_schema(tables_info)
    with open('database_schema.rst', 'w', encoding='utf-8') as f:
        f.write(rst_schema)
    
    print("Схема БД сгенерирована:")
    print("- database_schema.rst (RST схема БД)") 