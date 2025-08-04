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

def generate_plantuml_er_diagram(tables_info):
    """Генерирует ER-диаграмму в формате PlantUML"""
    plantuml = """@startuml database_schema
!define TABLE(name,desc) class name as "desc" << (T,#FFAAAA) >>
!define PK(x) <b>x</b>
!define FK(x) <i>x</i>

"""
    
    # Добавляем таблицы
    for table_name, info in tables_info.items():
        plantuml += f"TABLE({table_name}, {table_name})\n"
        for col in info['columns']:
            if col['primary_key']:
                plantuml += f"  PK({col['name']}) : {col['type']}\n"
            elif col['foreign_key']:
                plantuml += f"  FK({col['name']}) : {col['type']}\n"
            else:
                nullable = "" if col['nullable'] else " NOT NULL"
                plantuml += f"  {col['name']} : {col['type']}{nullable}\n"
        plantuml += "\n"
    
    # Добавляем связи
    for table_name, info in tables_info.items():
        for rel in info['relationships']:
            plantuml += f"{table_name} ||--o{{ {rel['to_table']} : {rel['from_column']} -> {rel['to_column']}\n"
    
    plantuml += "@enduml"
    return plantuml

def generate_markdown_schema(tables_info):
    """Генерирует текстовое описание схемы в формате Markdown"""
    md = "# Структура базы данных\n\n"
    
    for table_name, info in tables_info.items():
        md += f"## {table_name}\n\n"
        
        md += "| Поле | Тип | Nullable | Primary Key | Foreign Key | Индекс |\n"
        md += "|------|-----|----------|-------------|-------------|--------|\n"
        
        for col in info['columns']:
            nullable = "✓" if col['nullable'] else "✗"
            pk = "✓" if col['primary_key'] else ""
            fk = "✓" if col['foreign_key'] else ""
            index = "✓" if col['index'] else ""
            
            md += f"| {col['name']} | {col['type']} | {nullable} | {pk} | {fk} | {index} |\n"
        
        if info['relationships']:
            md += "\n**Связи:**\n"
            for rel in info['relationships']:
                md += f"- `{rel['from_column']}` → `{rel['to_table']}.{rel['to_column']}`\n"
        
        md += "\n"
    
    return md

if __name__ == "__main__":
    tables_info = get_table_info()
    
    # Генерируем ER-диаграмму
    er_diagram = generate_plantuml_er_diagram(tables_info)
    with open('database_schema.puml', 'w', encoding='utf-8') as f:
        f.write(er_diagram)
    
    # Генерируем текстовое описание
    md_schema = generate_markdown_schema(tables_info)
    with open('database_schema.md', 'w', encoding='utf-8') as f:
        f.write(md_schema)
    
    print("Схема БД сгенерирована:")
    print("- database_schema.puml (ER-диаграмма)")
    print("- database_schema.md (текстовое описание)") 