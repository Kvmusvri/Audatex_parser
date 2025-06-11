import requests
import json
import subprocess
import time
import sys
import os
import socket
import threading

# Путь к корневой директории проекта (где находится main.py и папка static)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MAIN_PY_PATH = os.path.join(PROJECT_ROOT, "main.py")
JSON_PATH = os.path.join(os.path.dirname(__file__), "test_json.json")

def check_port(port=8000):
    """Проверяет, свободен ли порт."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

def start_server():
    """Запускает сервер FastAPI через main.py."""
    if not os.path.exists(MAIN_PY_PATH):
        print(f"Ошибка: Файл {MAIN_PY_PATH} не найден")
        sys.exit(1)
    server_process = subprocess.Popen(
        [sys.executable, MAIN_PY_PATH],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
        cwd=PROJECT_ROOT
    )
    return server_process

def log_reader(server_process):
    """Читает и выводит логи сервера в реальном времени."""
    if server_process.stdout:
        for line in iter(server_process.stdout.readline, ''):
            print(f"Лог сервера: {line.strip()}")

def wait_for_server(server_process):
    """Ожидает, пока сервер станет доступен."""
    max_attempts = 60
    attempt = 1
    while attempt <= max_attempts:
        try:
            response = requests.get("http://127.0.0.1:8000/", timeout=2)
            if response.status_code == 200:
                print("Сервер успешно запущен")
                return True
        except requests.exceptions.ConnectionError:
            print(f"Ожидание запуска сервера... Попытка {attempt}/{max_attempts}")
            time.sleep(1)
            attempt += 1
    print("Ошибка: Сервер не запустился за отведённое время")
    return False

def main():
    if not check_port(8000):
        print("Ошибка: Порт 8000 занят другим процессом")
        sys.exit(1)

    server_process = start_server()
    # Запускаем чтение логов в отдельном потоке
    log_thread = threading.Thread(target=log_reader, args=(server_process,), daemon=True)
    log_thread.start()

    try:
        if not wait_for_server(server_process):
            print("Не удалось запустить сервер")
            server_process.terminate()
            sys.exit(1)

        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            print(f"Ошибка: Файл {JSON_PATH} не найден")
            server_process.terminate()
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Ошибка: Некорректный формат JSON в {JSON_PATH}: {str(e)}")
            server_process.terminate()
            sys.exit(1)

        try:
            response = requests.post(
                "http://127.0.0.1:8000/process_audatex_requests/",
                json=data,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            print(f"Статус-код: {response.status_code}")
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except requests.exceptions.RequestException as e:
            print(f"Ошибка при отправке запроса: {str(e)}")

    finally:
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
            print("Сервер остановлен")
        except subprocess.TimeoutExpired:
            print("Принудительное завершение сервера")
            server_process.kill()

if __name__ == "__main__":
    main()