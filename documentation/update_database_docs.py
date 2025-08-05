#!/usr/bin/env python3
"""
Скрипт для автоматического обновления документации БД
Интегрирует сгенерированные данные в RST файлы
"""
import os
import sys
import re

def update_database_rst():
    """Обновляет database.rst с актуальными данными"""
    
    # Читаем сгенерированную схему
    with open('database_schema.rst', 'r', encoding='utf-8') as f:
        generated_schema = f.read()
    
    # Читаем текущий database.rst
    with open('modules/database.rst', 'r', encoding='utf-8') as f:
        current_content = f.read()
    
    # Находим границы статического блока схемы
    schema_start = current_content.find('Структура базы данных')
    
    if schema_start == -1:
        print("Ошибка: Не найден блок 'Структура базы данных'")
        return False
    
    # Находим конец блока схемы (конец файла или начало следующего блока)
    schema_end = len(current_content)
    
    # Ищем начало следующего блока после схемы
    next_blocks = ['core.database.models', 'core.database.requests', 'core.database.init_db']
    for block in next_blocks:
        pos = current_content.find(block, schema_start + 1)
        if pos != -1:
            schema_end = pos
            break
    
    # Создаем новое содержимое
    new_content = current_content[:schema_start] + generated_schema
    
    # Записываем обновленный файл
    with open('modules/database.rst', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Файл modules/database.rst обновлен")
    return True

def main():
    """Основная функция"""
    print("Обновление документации БД...")
    
    # Сначала генерируем актуальные данные
    os.system('python generate_db_schema.py')
    
    # Затем обновляем RST файл
    if update_database_rst():
        print("Документация успешно обновлена!")
    else:
        print("Ошибка при обновлении документации")

if __name__ == "__main__":
    main() 