#!/bin/bash

echo "🐳 Запуск Linux-окружения для тестирования..."

# Переходим в папку docker
cd docker

# Сборка Docker-образа
echo "📦 Сборка Docker-образа..."
docker-compose build

# Запуск Redis
echo "🔴 Запуск Redis..."
docker-compose up -d redis

# Ждем запуска Redis
echo "⏳ Ожидание запуска Redis..."
sleep 5

# Запуск Linux-окружения в интерактивном режиме
echo "🚀 Запуск Linux-окружения..."
echo ""
echo "💡 Теперь вы в Linux-окружении. Доступные команды:"
echo "   - python3 main.py          # Запуск основного приложения"
echo "   - python3 -c \"import sys; print(sys.platform)\"  # Проверка платформы"
echo "   - exit                      # Выход из контейнера"
echo ""
docker-compose run --rm app bash

echo "✅ Linux-окружение завершено" 