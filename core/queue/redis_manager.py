import redis
import json
import logging
import asyncio
import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from core.database.requests import save_parser_data_to_db
from core.database.models import get_moscow_time

logger = logging.getLogger(__name__)


class RedisQueueManager:
    """Менеджер очереди Redis для парсера"""
    
    def __init__(self, host: str = None, port: int = None, db: int = 0):
        # Используем переменную окружения REDIS_URL или fallback на localhost
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        
        if host and port:
            # Если переданы host и port, используем их
            self.redis_client = redis.Redis(host=host, port=port, db=db, decode_responses=True)
        else:
            # Используем URL из переменной окружения
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.queue_key = "parser_queue"
        self.processing_key = "parser_processing"
        self.completed_key = "parser_completed"
        self.error_count_key = "parser_error_count"  # Счетчик ошибок для заявок
        
        # Проверяем подключение
        try:
            self.redis_client.ping()
            logger.info("✅ Подключение к Redis установлено")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Redis: {e}")
            raise
    
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
            request_data['added_at'] = get_moscow_time().isoformat()
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
                request_data['started_at'] = get_moscow_time().isoformat()
                
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
            request_data['completed_at'] = get_moscow_time().isoformat()
            request_data['success'] = success
            
            # Удаляем из обработки
            key = f"{request_data.get('claim_number', '')}_{request_data.get('vin_number', '')}"
            self.redis_client.hdel(self.processing_key, key)
            
            # Если неуспешно, увеличиваем счетчик ошибок
            if not success:
                self._increment_error_count(key)
                
                # Проверяем, достигли ли лимита ошибок (10 раз)
                error_count = self._get_error_count(key)
                if error_count >= 10:
                    logger.warning(f"⚠️ Заявка {key} достигла лимита ошибок ({error_count}), записываем в БД как nsvg")
                    # Записываем в БД как nsvg
                    self._save_failed_request_to_db(request_data)
                    # Очищаем счетчик ошибок
                    self._clear_error_count(key)
            
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
    
    def _increment_error_count(self, key: str) -> int:
        """Увеличивает счетчик ошибок для заявки"""
        try:
            current_count = self.redis_client.hget(self.error_count_key, key)
            new_count = int(current_count or 0) + 1
            self.redis_client.hset(self.error_count_key, key, new_count)
            logger.debug(f"📊 Счетчик ошибок для {key}: {new_count}")
            return new_count
        except Exception as e:
            logger.error(f"❌ Ошибка увеличения счетчика ошибок: {e}")
            return 0
    
    def _get_error_count(self, key: str) -> int:
        """Получает текущий счетчик ошибок для заявки"""
        try:
            count = self.redis_client.hget(self.error_count_key, key)
            return int(count or 0)
        except Exception as e:
            logger.error(f"❌ Ошибка получения счетчика ошибок: {e}")
            return 0
    
    def _clear_error_count(self, key: str) -> bool:
        """Очищает счетчик ошибок для заявки"""
        try:
            self.redis_client.hdel(self.error_count_key, key)
            logger.debug(f"🧹 Счетчик ошибок очищен для {key}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка очистки счетчика ошибок: {e}")
            return False
    
    def _save_failed_request_to_db(self, request_data: Dict[str, Any]) -> bool:
        """Сохраняет неудачную заявку в БД как nsvg"""
        try:
            # Создаем данные для сохранения в БД
            claim_number = request_data.get('claim_number', '')
            vin_number = request_data.get('vin_number', '')
            
            # Создаем пустой результат с пометкой nsvg
            failed_result = {
                "claim_number": claim_number,
                "vin_number": vin_number,
                "vin_status": "Нет",
                "comment": "nsvg",
                "error": "Превышен лимит ошибок (10 попыток)",
                "success": False
            }
            
            # Получаем текущее время
            started_at = get_moscow_time()
            completed_at = get_moscow_time()
            
            # Сохраняем в БД
            async def save_to_db():
                return await save_parser_data_to_db(
                    failed_result, 
                    claim_number, 
                    vin_number, 
                    is_success=False, 
                    started_at=started_at, 
                    completed_at=completed_at
                )
            
            # Запускаем асинхронную функцию
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success = loop.run_until_complete(save_to_db())
                logger.info(f"💾 Неудачная заявка {claim_number} сохранена в БД как nsvg: {success}")
                return success
            finally:
                loop.close()
                
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения неудачной заявки в БД: {e}")
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
            # Очищаем счетчик ошибок
            self.redis_client.delete(self.error_count_key)
            
            logger.info("✅ Вся очередь полностью очищена (очередь, обработка, завершенные, счетчик ошибок)")
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