# Docker Linux-окружение для тестирования

Этот документ описывает, как использовать Docker для создания простого Linux-окружения для тестирования вашего парсера.

## 🎯 Цель

Создать изолированное Linux-окружение для воспроизведения проблем, возникающих на сервере, но не воспроизводящихся на Windows.

## 🚀 Быстрый старт

### Windows
```cmd
docker\start_linux_env.bat
```

### Linux/Mac
```bash
chmod +x docker/start_linux_env.sh
./docker/start_linux_env.sh
```

## 🧹 Очистка

Если возникают проблемы с контейнерами:
```cmd
docker\cleanup.bat
```

## 🔧 Что происходит при запуске

1. **Очистка существующих контейнеров** для избежания конфликтов
2. **Сборка Docker-образа** с Ubuntu 22.04 и Python
3. **Открытие интерактивной Linux-сессии** в контейнере

## 💻 Доступные команды в Linux-окружении

```bash
# Проверка платформы
python3 -c "import sys; print(sys.platform)"

# Установка зависимостей
pip3 install -r requirements.txt

# Запуск основного приложения
python3 main.py

# Выход из контейнера
exit
```

## 📁 Структура проекта в контейнере

```
/app/
├── core/           # Основной код
├── static/         # Статические файлы
├── templates/      # Шаблоны
├── tests/          # Тесты
├── requirements.txt
└── main.py
```

## 🔍 Отладка проблем

### Проблемы с контейнерами
```bash
# Проверка статуса контейнеров
docker ps -a

# Просмотр логов
docker-compose logs app

# Полная очистка
docker\cleanup.bat
```

### Проблемы с зависимостями
```bash
# Установка зависимостей
pip3 install -r requirements.txt

# Проверка установленных пакетов
pip3 list
```

## 🛠️ Управление контейнерами

### Остановка
```bash
# Из папки docker
docker-compose down

# Остановка с удалением данных
docker-compose down -v
```

### Очистка
```bash
# Удаление образов
docker-compose down --rmi all

# Полная очистка
docker system prune -a
```

## 📊 Мониторинг ресурсов

```bash
# Размер образов
docker images

# Размер контейнеров
docker ps -s

# Использование ресурсов
docker stats
```

## 🎯 Тестирование проблемы с VIN

После входа в Linux-окружение:

1. **Установите зависимости:**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Запустите парсер:**
   ```bash
   python3 main.py
   ```

3. **Проверьте логи** на предмет ошибок определения VIN

4. **Сравните поведение** с Windows-версией

## 🔧 Переменные окружения

- `PYTHONUNBUFFERED=1` - Небуферизованный вывод Python

## 📝 Полезные команды

```bash
# Пересборка образа
docker-compose build --no-cache

# Запуск с пересборкой
docker-compose up --build

# Просмотр переменных окружения
docker-compose run --rm app env

# Копирование файлов из контейнера
docker cp audotex_linux_env:/app/logs ./local_logs
```

## ⚠️ Устранение неполадок

### Ошибка "container name already in use"
```cmd
docker\cleanup.bat
```

### Проблемы с правами доступа
```bash
# В Linux-окружении
sudo chown -R $USER:$USER /app
```

### Проблемы с зависимостями
```bash
# Обновление pip
pip3 install --upgrade pip

# Установка зависимостей
pip3 install -r requirements.txt
``` 