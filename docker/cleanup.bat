@echo off
echo 🧹 Полная очистка Docker-окружения...

REM Переходим в папку docker
cd docker

REM Останавливаем и удаляем контейнеры
echo 📦 Остановка контейнеров...
docker-compose down --remove-orphans
docker stop audotex_linux_env 2>nul
docker rm audotex_linux_env 2>nul

REM Удаляем образы
echo 🗑️ Удаление образов...
docker-compose down --rmi all

REM Очищаем неиспользуемые ресурсы
echo 🧽 Очистка неиспользуемых ресурсов...
docker system prune -f

echo ✅ Очистка завершена
pause 