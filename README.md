# Audatex Parser

Система автоматизации парсинга данных из Audatex с веб-интерфейсом и API.

## Структура проекта

```
├── core/           # Основные модули
│   ├── auth/       # Система аутентификации и авторизации
│   ├── database/   # Работа с базой данных
│   ├── parser/     # Модули парсера Audatex
│   ├── queue/      # Управление очередью заявок
│   └── security/   # Система безопасности
├── static/         # Статические файлы и результаты парсинга
│   ├── css/        # Стили
│   ├── js/         # JavaScript
│   ├── screenshots/ # Скриншоты (создается автоматически)
│   ├── svgs/       # SVG файлы (создается автоматически)
│   └── data/       # JSON данные (создается автоматически)
├── templates/      # HTML шаблоны
├── tests/          # Тесты API и функциональности
├── session_management/  # Ручное управление сессиями авторизации
├── main.py         # Основной файл приложения
├── requirements.txt # Зависимости Python
├── redis_manager.bat # Скрипт управления Redis (Windows)
├── redis_manager.sh # # Скрипт управления Redis (Linux)
├── unban_ip.py     # Утилита разблокировки IP
└── .eslintrc.json  # Конфигурация ESLint
```

## Конфигурация

### Файл .env
Создайте файл `.env` в корне проекта со следующими переменными:

```env
# База данных
DATABASE_URL=postgresql://user:password@localhost:5432/audatex_db

# Учетные данные администратора
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ваш_безопасный_пароль_здесь
ADMIN_EMAIL=admin@example.com

# Учетные данные API пользователя
API_USERNAME=api_user
API_PASSWORD=ваш_безопасный_пароль_здесь
API_EMAIL=api@example.com
```

**ВАЖНО:** Никогда не коммитьте .env файл в git! Добавьте его в .gitignore.

### Основной API
- `POST /api_parse` - Добавление заявки в очередь парсинга

## Формат API запросов

### POST /api_parse
```json
{
  "app_credentials": {
    "username": "user",
    "password": "pass"
  },
  "parser_credentials": {
    "username": "audatex_user",
    "password": "audatex_pass"
  },
  "svg_collection": true,
  "searchList": [
    {
      "claim_number": "12345",
      "vin_number": "ABC123456789"
    }
  ]
}
```

## Установка и запуск

### Установка зависимостей
```bash
# Создание виртуального окружения
python -m venv venv

# Активация виртуального окружения
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt
```

### Запуск Redis
```bash
# Windows
redis_manager.bat start

# Linux/Mac
# Установите и запустите Redis в соответствии с документацией вашей системы
# https://redis.io/docs/getting-started/
```

### Запуск приложения
```bash
# Активация окружения
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Запуск сервера
python main.py
```

Приложение будет доступно по адресу: http://127.0.0.1:8000

## Доступ

- **Веб-интерфейс**: http://127.0.0.1:8000
- **API документация**: http://127.0.0.1:8000/docs
- **Мониторинг очереди**: http://127.0.0.1:8000/queue
- **Мониторинг безопасности**: http://127.0.0.1:8000/security

## Требования

- Python 3.8+

- Redis Server 
