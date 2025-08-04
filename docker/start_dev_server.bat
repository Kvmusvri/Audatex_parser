@echo off
echo 🐳 Запуск сервера разработки...

REM Переходим в папку docker
cd docker

REM Останавливаем и удаляем существующие контейнеры
echo 🧹 Очистка существующих контейнеров...
docker-compose down --remove-orphans 2>nul

REM Пересобираем образ с новыми зависимостями
echo 📦 Пересборка Docker-образа с обновленными зависимостями...
docker-compose build --no-cache

REM Запуск PostgreSQL и Redis
echo 🗄️ Запуск PostgreSQL и Redis...
docker-compose up -d postgres redis

REM Ждем запуска сервисов
echo ⏳ Ожидание запуска сервисов...
timeout /t 5 /nobreak >nul

REM Запуск приложения в интерактивном режиме
echo 🚀 Запуск приложения в режиме разработки...
echo.
echo 💡 Доступные команды:
echo    - python3 main.py          # Запуск основного приложения
echo    - python3 -c "import sys; print(sys.platform)"  # Проверка платформы
echo    - exit                      # Выход из контейнера
echo.
echo 🌐 После запуска main.py сайт будет доступен по адресу: http://localhost:8000
echo.
docker-compose run --rm -p 8000:8000 --build app bash

echo ✅ Сервер разработки завершен
pause 