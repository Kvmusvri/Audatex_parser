#!/usr/bin/env python3
"""
Основной скрипт для сборки документации с автоматическим обновлением схемы БД
"""
import os
import sys
import subprocess

def main():
    """Основная функция сборки документации"""
    print("=== Автоматическая сборка документации ===\n")
    
    # Проверяем, что мы в виртуальном окружении
    if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("⚠️  Предупреждение: Виртуальное окружение не активировано")
        print("Убедитесь, что вы запускаете скрипт с активированным виртуальным окружением")
    
    # Шаг 1: Обновление схемы БД
    print("1. Обновление схемы базы данных...")
    try:
        result = subprocess.run([sys.executable, 'update_database_docs.py'], 
                              capture_output=True, text=True, check=True)
        print("✓ Схема БД обновлена успешно")
    except subprocess.CalledProcessError as e:
        print(f"✗ Ошибка при обновлении схемы БД: {e}")
        print(f"Вывод: {e.stdout}")
        print(f"Ошибки: {e.stderr}")
        return False
    
    # Шаг 2: Сборка документации
    print("\n2. Сборка HTML документации...")
    try:
        result = subprocess.run([sys.executable, '-m', 'sphinx.cmd.build', '-b', 'html', '.', '_build/html'], 
                              capture_output=True, text=True, check=True)
        print("✓ Документация собрана успешно")
        
        # Выводим предупреждения, если есть
        if result.stderr:
            print("\nПредупреждения:")
            print(result.stderr)
            
    except subprocess.CalledProcessError as e:
        print(f"✗ Ошибка при сборке документации: {e}")
        print(f"Вывод: {e.stdout}")
        print(f"Ошибки: {e.stderr}")
        return False
    
    print("\n=== Сборка завершена успешно! ===")
    print("HTML документация доступна в папке: _build/html/")
    print("Откройте _build/html/index.html в браузере для просмотра")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 