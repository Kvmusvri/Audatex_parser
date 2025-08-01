
import requests
import json
import sys
import os
import time
from typing import Dict, Any

# Путь к JSON файлу с тестовыми данными
JSON_PATH = os.path.join(os.path.dirname(__file__), "test_json.json")


def main():
    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Ошибка: Файл {JSON_PATH} не найден")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Ошибка: Некорректный формат JSON в {JSON_PATH}: {str(e)}")
        sys.exit(1)

    try:
        response = requests.post(
            "http://127.0.0.1:8000/api_parse",
            json=data,
            headers={"Content-Type": "application/json"},
        )
        
        print(f"Статус-код: {response.status_code}")
        
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("success"):
                print("Тест пройден успешно")
            else:
                print(f"Ошибка: {response_data.get('error', 'Неизвестная ошибка')}")
                sys.exit(1)
        else:
            print(f"Ошибка: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Детали ошибки: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print(f"Текст ответа: {response.text}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"Ошибка подключения: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()