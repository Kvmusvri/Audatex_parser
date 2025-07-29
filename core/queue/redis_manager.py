import redis
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class RedisQueueManager:
    """Менеджер для работы с очередью заявок в Redis"""
    
    def __init__(self, host: str = 'localhost', port: int = 6379, db: int = 0):
        """Инициализация подключения к Redis"""
        self.redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        self.queue_key = "parser_queue"
        self.processing_key = "parser_processing"
        self.completed_key = "parser_completed"
        
    def test_connection(self) -> bool:
        """Проверка подключения к Redis"""
        try:
            self.redis_client.ping()
            logger.info("✅ Подключение к Redis успешно")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Redis: {e}")
            return False
    
    def add_request_to_queue(self, request_data: Dict[str, Any]) -> bool:
        """Добавление заявки в очередь"""
        try:
            request_data['added_at'] = datetime.now().isoformat()
            request_data['status'] = 'pending'
            
            # Добавляем в очередь (список)
            self.redis_client.lpush(self.queue_key, json.dumps(request_data))
            logger.info(f"✅ Заявка добавлена в очередь: {request_data.get('claim_number', 'N/A')}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка добавления заявки в очередь: {e}")
            return False
    
    def get_next_request(self) -> Optional[Dict[str, Any]]:
        """Получение следующей заявки из очереди"""
        try:
            # Берем заявку из очереди (справа - FIFO)
            request_json = self.redis_client.rpop(self.queue_key)
            if request_json:
                request_data = json.loads(request_json)
                request_data['status'] = 'processing'
                request_data['started_at'] = datetime.now().isoformat()
                
                # Сохраняем в обработке
                self.redis_client.hset(
                    self.processing_key,
                    f"{request_data.get('claim_number', '')}_{request_data.get('vin_number', '')}",
                    json.dumps(request_data)
                )
                
                logger.info(f"✅ Заявка взята в обработку: {request_data.get('claim_number', 'N/A')}")
                return request_data
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения заявки из очереди: {e}")
            return None
    
    def mark_request_completed(self, request_data: Dict[str, Any], success: bool = True) -> bool:
        """Отметка заявки как завершенной"""
        try:
            request_data['status'] = 'completed' if success else 'failed'
            request_data['completed_at'] = datetime.now().isoformat()
            request_data['success'] = success
            
            # Удаляем из обработки
            key = f"{request_data.get('claim_number', '')}_{request_data.get('vin_number', '')}"
            self.redis_client.hdel(self.processing_key, key)
            
            # Добавляем в завершенные
            self.redis_client.hset(
                self.completed_key,
                key,
                json.dumps(request_data)
            )
            
            logger.info(f"✅ Заявка завершена: {request_data.get('claim_number', 'N/A')} (успех: {success})")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отметки заявки как завершенной: {e}")
            return False
    
    def get_queue_length(self) -> int:
        """Получение длины очереди"""
        try:
            return self.redis_client.llen(self.queue_key)
        except Exception as e:
            logger.error(f"❌ Ошибка получения длины очереди: {e}")
            return 0
    
    def get_processing_requests(self) -> List[Dict[str, Any]]:
        """Получение списка заявок в обработке"""
        try:
            processing_data = self.redis_client.hgetall(self.processing_key)
            return [json.loads(data) for data in processing_data.values()]
        except Exception as e:
            logger.error(f"❌ Ошибка получения заявок в обработке: {e}")
            return []
    
    def get_completed_requests(self) -> List[Dict[str, Any]]:
        """Получение списка завершенных заявок"""
        try:
            completed_data = self.redis_client.hgetall(self.completed_key)
            return [json.loads(data) for data in completed_data.values()]
        except Exception as e:
            logger.error(f"❌ Ошибка получения завершенных заявок: {e}")
            return []
    
    def get_pending_requests(self) -> List[Dict[str, Any]]:
        """Получение списка заявок в очереди (ожидающих обработки)"""
        try:
            # Получаем все заявки из очереди (список)
            queue_data = self.redis_client.lrange(self.queue_key, 0, -1)
            return [json.loads(data) for data in queue_data]
        except Exception as e:
            logger.error(f"❌ Ошибка получения заявок в очереди: {e}")
            return []
    
    def clear_queue(self) -> bool:
        """Очистка всей очереди, включая заявки в обработке и завершенные"""
        try:
            # Очищаем очередь
            self.redis_client.delete(self.queue_key)
            # Очищаем заявки в обработке
            self.redis_client.delete(self.processing_key)
            # Очищаем завершенные заявки
            self.redis_client.delete(self.completed_key)
            
            logger.info("✅ Вся очередь полностью очищена (очередь, обработка, завершенные)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки очереди: {e}")
            return False
    
    def clear_queue_only(self) -> bool:
        """Очистка только очереди (без заявок в обработке и завершенных)"""
        try:
            self.redis_client.delete(self.queue_key)
            logger.info("✅ Очередь очищена (заявки в обработке сохранены)")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки очереди: {e}")
            return False
    
    def restore_interrupted_requests(self) -> List[Dict[str, Any]]:
        """Восстановление прерванных заявок при перезапуске"""
        try:
            interrupted_requests = self.get_processing_requests()
            if interrupted_requests:
                logger.info(f"🔄 Найдено {len(interrupted_requests)} прерванных заявок")
                
                # Возвращаем прерванные заявки в очередь
                for request in interrupted_requests:
                    request['status'] = 'pending'
                    request['restored_at'] = datetime.now().isoformat()
                    self.redis_client.lpush(self.queue_key, json.dumps(request))
                
                # Очищаем список обработки
                self.redis_client.delete(self.processing_key)
                
                logger.info("✅ Прерванные заявки восстановлены в очереди")
                return interrupted_requests
            
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка восстановления прерванных заявок: {e}")
            return []
    
    def close(self):
        """Закрытие соединения с Redis"""
        try:
            self.redis_client.close()
            logger.info("✅ Соединение с Redis закрыто")
        except Exception as e:
            logger.error(f"❌ Ошибка закрытия соединения с Redis: {e}")


# Глобальный экземпляр менеджера
redis_manager = RedisQueueManager() 