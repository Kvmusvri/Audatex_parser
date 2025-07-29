import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import time

from core.queue.redis_manager import redis_manager
from core.parser.parser import login_audatex
from core.database.requests import save_parser_data_to_db, update_json_with_claim_number, save_updated_json_to_file

logger = logging.getLogger(__name__)


class QueueProcessor:
    """Процессор для обработки очереди заявок"""
    
    def __init__(self):
        self.is_running = False
        self.current_task = None
        self.current_parser_task = None  # Текущая задача парсера
        self.processed_count = 0
        self.failed_count = 0
        self.stop_requested = False  # Флаг запроса остановки
        
    async def start_processing(self):
        """Запуск обработки очереди"""
        if self.is_running:
            logger.warning("⚠️ Обработка очереди уже запущена")
            return
        
        self.is_running = True
        self.stop_requested = False
        logger.info("🚀 Запуск обработки очереди заявок")
        
        # Восстанавливаем прерванные заявки при запуске
        interrupted_requests = redis_manager.restore_interrupted_requests()
        if interrupted_requests:
            logger.info(f"🔄 Восстановлено {len(interrupted_requests)} прерванных заявок")
        
        try:
            while self.is_running and not self.stop_requested:
                # Проверяем очередь
                queue_length = redis_manager.get_queue_length()
                if queue_length == 0:
                    logger.info("📭 Очередь пуста, ожидание...")
                    await asyncio.sleep(5)  # Ждем 5 секунд
                    continue
                
                logger.info(f"📋 Заявок в очереди: {queue_length}")
                
                # Берем следующую заявку
                request_data = redis_manager.get_next_request()
                if not request_data:
                    continue
                
                # Обрабатываем заявку
                await self._process_request(request_data)
                
        except Exception as e:
            logger.error(f"❌ Критическая ошибка в обработке очереди: {e}")
        finally:
            self.is_running = False
            logger.info("🛑 Обработка очереди остановлена")
    
    async def _process_request(self, request_data: Dict[str, Any]):
        """Обработка одной заявки"""
        claim_number = request_data.get('claim_number', '')
        vin_number = request_data.get('vin_number', '')
        svg_collection = request_data.get('svg_collection', True)
        username = request_data.get('username', '')
        password = request_data.get('password', '')
        
        logger.info(f"🔄 Обработка заявки: {claim_number} | VIN: {vin_number}")
        
        try:
            # Запускаем парсер с московским временем
            from core.database.models import get_moscow_time
            started_at = get_moscow_time()
            
            # Создаем задачу для парсера
            self.current_parser_task = asyncio.create_task(
                self._run_parser(claim_number, vin_number, svg_collection, username, password, started_at)
            )
            
            # Ждем завершения без таймаута
            try:
                result = await self.current_parser_task
                
                completed_at = get_moscow_time()
                duration = (completed_at - started_at).total_seconds()
                
                if result:
                    # Обрабатываем результат парсера
                    success = await self._process_parser_result(
                        result, started_at, completed_at, request_data
                    )
                    
                    if success:
                        self.processed_count += 1
                        logger.info(f"✅ Заявка успешно обработана: {claim_number} (время: {duration:.1f}с)")
                        redis_manager.mark_request_completed(request_data, success=True)
                    else:
                        self.failed_count += 1
                        logger.error(f"❌ Ошибка обработки результата парсера: {claim_number}")
                        
                        # Отмечаем как неудачную
                        redis_manager.mark_request_completed(request_data, success=False)
                else:
                    self.failed_count += 1
                    logger.error(f"❌ Парсер вернул пустой результат: {claim_number}")
                    redis_manager.mark_request_completed(request_data, success=False)
                    

                
            except Exception as e:
                self.failed_count += 1
                logger.error(f"❌ Ошибка обработки заявки {claim_number}: {e}")
                redis_manager.mark_request_completed(request_data, success=False)
                
        except Exception as e:
            self.failed_count += 1
            logger.error(f"❌ Ошибка обработки заявки {claim_number}: {e}")
            redis_manager.mark_request_completed(request_data, success=False)
        finally:
            # Очищаем ссылку на текущую задачу парсера
            self.current_parser_task = None
    
    async def _run_parser(self, claim_number: str, vin_number: str, svg_collection: bool, username: str, password: str, started_at: datetime = None) -> Optional[Dict[str, Any]]:
        """Запуск парсера для заявки"""
        try:
            # Запускаем парсер с учетными данными
            result = await login_audatex(username, password, claim_number, vin_number, svg_collection, started_at)
            return result
            
        except Exception as e:
            logger.error(f"❌ Ошибка запуска парсера для {claim_number}: {e}")
            return None
    
    async def _process_parser_result(self, parser_result: Dict[str, Any], 
                                   started_at: datetime, completed_at: datetime,
                                   request_data: Dict[str, Any]) -> bool:
        """Обработка результата парсера"""
        try:
            logger.info(f"🔍 Обрабатываем результат парсера: {parser_result}")
            
            # Проверяем, есть ли ошибка в результате
            if "error" in parser_result:
                error_msg = parser_result['error']
                is_cancelled = parser_result.get('cancelled', False)
                
                # Проверяем, была ли это действительно остановка пользователем
                if is_cancelled and "прерван во время выполнения" in error_msg:
                    if self.stop_requested:
                        logger.info(f"🛑 Парсер был остановлен пользователем: {error_msg}")
                    else:
                        logger.warning(f"⚠️ Парсер был отменен по техническим причинам: {error_msg}")
                elif is_cancelled and "остановлен пользователем" in error_msg:
                    if self.stop_requested:
                        logger.info(f"🛑 Парсер был остановлен пользователем: {error_msg}")
                    else:
                        logger.warning(f"⚠️ Парсер был отменен по техническим причинам: {error_msg}")
                else:
                    logger.error(f"❌ Парсер вернул ошибку: {error_msg}")
                return False
            
            # Получаем извлеченные данные из результата парсера
            extracted_claim_number = parser_result.get("claim_number", "")
            extracted_vin_number = parser_result.get("vin_value", "")
            
            # Очищаем строки от лишних пробелов и символов табуляции
            clean_claim_number = extracted_claim_number.strip() if extracted_claim_number else ""
            clean_vin_number = extracted_vin_number.strip() if extracted_vin_number else ""
            
            logger.info(f"🔍 Используем извлеченные данные: claim_number='{extracted_claim_number}' -> '{clean_claim_number}', vin='{extracted_vin_number}' -> '{clean_vin_number}'")
            
            # Проверяем, что данные не пустые
            if not clean_claim_number and not clean_vin_number:
                logger.error("❌ Извлеченные данные пустые - claim_number и vin_number отсутствуют")
                return False
            
            # Формируем имя папки
            folder_name = f"{clean_claim_number}_{clean_vin_number}"
            folder_path = f"static/data/{folder_name}"
            
            logger.info(f"🔍 Ищем папку: {folder_path}")
            
            # Проверяем существование папки
            import os
            
            # Проверяем существование основной папки static/data
            base_data_dir = "static/data"
            if not os.path.isdir(base_data_dir):
                logger.error(f"❌ Основная папка {base_data_dir} не существует")
                return False
            
            if not os.path.isdir(folder_path):
                logger.error(f"❌ Папка {folder_path} не существует после парсинга")
                
                # Показываем все доступные папки для отладки
                try:
                    all_folders = [d for d in os.listdir(base_data_dir) if os.path.isdir(os.path.join(base_data_dir, d))]
                    logger.info(f"📁 Доступные папки в {base_data_dir}: {all_folders}")
                except Exception as e:
                    logger.error(f"❌ Не удалось прочитать папки: {e}")
                
                # Попробуем найти папку по исходным данным из запроса
                original_claim = request_data.get('claim_number', '').strip()
                original_vin = request_data.get('vin_number', '').strip()
                
                if original_claim or original_vin:
                    fallback_folder = f"{original_claim}_{original_vin}"
                    fallback_path = f"static/data/{fallback_folder}"
                    logger.info(f"🔄 Пробуем найти папку по исходным данным: {fallback_path}")
                    
                    if os.path.isdir(fallback_path):
                        logger.info(f"✅ Найдена папка по исходным данным: {fallback_path}")
                        folder_path = fallback_path
                        folder_name = fallback_folder
                        clean_claim_number = original_claim
                        clean_vin_number = original_vin
                    else:
                        logger.error(f"❌ Папка по исходным данным тоже не найдена: {fallback_path}")
                        return False
                else:
                    return False
            
            # Ищем JSON файлы в папке
            json_files = [f for f in os.listdir(folder_path) if f.endswith(".json")]
            logger.info(f"📁 Найдено JSON файлов в папке {folder_path}: {len(json_files)}")
            
            if not json_files:
                logger.error(f"❌ JSON-файлы не найдены в {folder_path}")
                # Показываем содержимое папки для отладки
                try:
                    all_files = os.listdir(folder_path)
                    logger.error(f"📁 Содержимое папки {folder_path}: {all_files}")
                except Exception as e:
                    logger.error(f"❌ Не удалось прочитать содержимое папки: {e}")
                return False
            
            # Берем самый новый JSON файл
            latest_json = max(json_files, key=lambda f: os.path.getctime(os.path.join(folder_path, f)))
            file_path = os.path.join(folder_path, latest_json)
            
            logger.info(f"✅ Найден JSON файл: {file_path}")
            
            # Читаем JSON файл
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # Обновляем JSON с извлеченным claim_number
            updated_json = update_json_with_claim_number(json_data, clean_claim_number)
            
            # Сохраняем обновленный JSON обратно в файл
            save_success = await save_updated_json_to_file(updated_json, file_path)
            if not save_success:
                logger.error(f"Не удалось сохранить обновленный JSON: {file_path}")
                return False
            
            # Сохраняем данные в БД с временными метками
            db_success = await save_parser_data_to_db(
                updated_json, clean_claim_number, clean_vin_number, 
                is_success=True, started_at=started_at, completed_at=completed_at
            )
            if not db_success:
                logger.error(f"Не удалось сохранить данные в БД: {clean_claim_number}_{clean_vin_number}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки результата парсера: {e}")
            return False
    
    def stop_processing(self):
        """Остановка обработки очереди"""
        self.is_running = False
        self.stop_requested = True
        logger.info("🛑 Запрошена остановка обработки очереди")
        
        # Отменяем текущую задачу парсера, если она запущена
        if self.current_parser_task and not self.current_parser_task.done():
            logger.info("🛑 Отмена текущей задачи парсера")
            self.current_parser_task.cancel()
        
        # Очищаем очередь
        redis_manager.clear_queue()
        logger.info("🗑️ Очередь очищена")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получение статистики обработки"""
        return {
            "is_running": self.is_running,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "queue_length": redis_manager.get_queue_length(),
            "processing_count": len(redis_manager.get_processing_requests())
        }


# Глобальный экземпляр процессора
queue_processor = QueueProcessor() 