#!/usr/bin/env python3
"""
Тестовый скрипт для проверки функций обработки опций
"""

import sys
import os

# Добавляем корневую директорию в путь для импортов
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database.requests import extract_option_code, clean_option_title

def test_option_processing():
    """Тестирует функции обработки опций"""
    
    test_cases = [
        {
            "input": "AZT - Идентификация производителя ЛКП / поиск кода цвета",
            "expected_code": "AZT",
            "expected_title": "Идентификация производителя ЛКП / поиск кода цвета"
        },
        {
            "input": "ABC - Тестовая опция",
            "expected_code": "ABC", 
            "expected_title": "Тестовая опция"
        },
        {
            "input": "XYZ123 - Другая опция с цифрами",
            "expected_code": "XYZ123",
            "expected_title": "Другая опция с цифрами"
        },
        {
            "input": "Простая опция без кода",
            "expected_code": "",
            "expected_title": "Простая опция без кода"
        },
        {
            "input": "ABC - Опция с ABC в середине текста",
            "expected_code": "ABC",
            "expected_title": "Опция с ABC в середине текста"
        }
    ]
    
    print("🧪 Тестирование функций обработки опций")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        input_text = test_case["input"]
        expected_code = test_case["expected_code"]
        expected_title = test_case["expected_title"]
        
        # Тестируем извлечение кода
        extracted_code = extract_option_code(input_text)
        
        # Тестируем очистку заголовка
        cleaned_title = clean_option_title(input_text)
        
        # Проверяем результаты
        code_ok = extracted_code == expected_code
        title_ok = cleaned_title == expected_title
        
        status = "✅" if code_ok and title_ok else "❌"
        
        print(f"{status} Тест {i}:")
        print(f"   Вход: '{input_text}'")
        print(f"   Код: '{extracted_code}' (ожидалось: '{expected_code}')")
        print(f"   Заголовок: '{cleaned_title}' (ожидалось: '{expected_title}')")
        print()
    
    print("🎉 Тестирование завершено!")

if __name__ == "__main__":
    test_option_processing() 