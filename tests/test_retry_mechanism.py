import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import json
from unittest.mock import Mock, patch
from core.queue.queue_processor import QueueProcessor
from core.queue.redis_manager import RedisQueueManager

async def test_retry_mechanism():
    """Тест механизма повторных попыток"""
    
    # Создаем тестовые данные заявки
    test_request = {
        "claim_number": "12345",
        "vin_number": "ABC123",
        "svg_collection": True,
        "username": "test_user",
        "password": "test_pass"
    }
    
    # Мокаем Redis
    with patch('core.queue.redis_manager.redis.Redis') as mock_redis:
        # Настраиваем мок Redis
        mock_redis_instance = Mock()
        mock_redis.from_url.return_value = mock_redis_instance
        mock_redis_instance.ping.return_value = True
        mock_redis_instance.hget.return_value = "0"  # Начальный счетчик ошибок
        mock_redis_instance.hset.return_value = True
        mock_redis_instance.lpush.return_value = True
        mock_redis_instance.hdel.return_value = True
        
        # Создаем экземпляры
        redis_manager = RedisQueueManager()
        processor = QueueProcessor()
        
        # Тестируем обработку ошибки парсера
        print("🧪 Тестируем механизм retry...")
        
        # Симулируем ошибку парсера
        await processor._handle_parser_error(test_request, "Таблица не загрузилась")
        
        # Проверяем, что заявка была добавлена обратно в очередь
        mock_redis_instance.lpush.assert_called_once()
        
        print("✅ Тест механизма retry пройден успешно!")
        print("📊 Заявка была возвращена в очередь для повторной попытки")

if __name__ == "__main__":
    asyncio.run(test_retry_mechanism()) 