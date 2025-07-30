import requests
import json
import sys
import os
import time

# Путь к JSON файлу с тестовыми данными
JSON_PATH = os.path.join(os.path.dirname(__file__), "test_json.json")

def convert_old_format_to_new(old_data):
    """Конвертирует старый формат JSON в новый формат для API."""
    return {
        "login": old_data["login"],
        "password": old_data["password"],
        "svg_collection": True,
        "items": old_data["searchList"]
    }

def test_endpoint_responses(max_no_response_time=120):
    """Проверяет что эндпоинт отвечает каждые 30 секунд"""
    print(f"Проверка ответов эндпоинта каждые 30 секунд")
    print(f"Таймаут: {max_no_response_time} секунд без ответа")
    
    last_response_time = time.time()
    response_count = 0
    
    while True:
        try:
            # Проверяем статус очереди
            queue_response = requests.get("http://127.0.0.1:8000/api/queue/status", timeout=10)
            if queue_response.status_code == 200:
                queue_data = queue_response.json()
                queue_length = queue_data.get("data", {}).get("queue_length", 0)
                processing_count = queue_data.get("data", {}).get("processing_count", 0)
                processed_count = queue_data.get("data", {}).get("processed_count", 0)
                failed_count = queue_data.get("data", {}).get("failed_count", 0)
                
                response_count += 1
                last_response_time = time.time()
                
                print(f"Ответ #{response_count}: Очередь={queue_length}, Обрабатывается={processing_count}, Завершено={processed_count}, Ошибок={failed_count}")
                
                # Если все заявки обработаны - тест завершен
                if queue_length == 0 and (processed_count > 0 or failed_count > 0):
                    print("Все заявки обработаны")
                    return True
                
            else:
                print(f"Ошибка ответа: {queue_response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"Ошибка подключения: {e}")
        
        # Проверяем таймаут
        if time.time() - last_response_time > max_no_response_time:
            print(f"Таймаут: {max_no_response_time} секунд без ответа")
            return False
        
        # Ждем 30 секунд до следующей проверки
        time.sleep(30)

def main():
    # Проверяем, что сервер уже запущен
    try:
        response = requests.get("http://127.0.0.1:8000/", timeout=2)
        if response.status_code == 200:
            print("Сервер запущен")
        else:
            print("Сервер не отвечает корректно")
            sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("Ошибка: Сервер недоступен")
        sys.exit(1)

    try:
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except FileNotFoundError:
        print(f"Ошибка: Файл {JSON_PATH} не найден")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Ошибка: Некорректный формат JSON в {JSON_PATH}: {str(e)}")
        sys.exit(1)

    # Конвертируем в новый формат
    new_data = convert_old_format_to_new(old_data)
    print("Отправляем данные:")
    print(json.dumps(new_data, indent=2, ensure_ascii=False))

    try:
        # Делаем API запрос к эндпоинту /process_audatex_requests
        print("Отправляем API запрос к /process_audatex_requests")
        response = requests.post(
            "http://127.0.0.1:8000/process_audatex_requests",
            json=new_data,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        print(f"Статус-код: {response.status_code}")
        print("Ответ API:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        
        # Проверяем, что заявки добавлены в очередь
        response_data = response.json()
        if response_data.get("success"):
            print(f"Заявки добавлены в очередь: {response_data.get('queue_length', 0)}")
            
            # Проверяем что эндпоинт отвечает каждые 30 секунд
            if test_endpoint_responses():
                print("Тест пройден: эндпоинт отвечает корректно")
            else:
                print("Тест не пройден: эндпоинт не отвечает")
                sys.exit(1)
        else:
            print(f"Ошибка добавления заявок: {response_data.get('error', 'Неизвестная ошибка')}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке запроса: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()