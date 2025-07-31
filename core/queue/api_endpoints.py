import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.queue.redis_manager import redis_manager
from core.queue.queue_processor import queue_processor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/queue", tags=["queue"])


class QueueRequest(BaseModel):
    """Модель заявки для очереди"""
    claim_number: str = ""
    vin_number: str = ""
    svg_collection: bool = True


class QueueResponse(BaseModel):
    """Модель ответа очереди"""
    success: bool
    message: str
    data: Dict[str, Any] = {}


@router.post("/add", response_model=QueueResponse)
async def add_request_to_queue(request: QueueRequest, request_obj: Request):
    """Добавление заявки в очередь"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request_obj.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Недействительная сессия"
        )
    """Добавление заявки в очередь"""
    try:
        # Проверяем, что хотя бы одно поле заполнено
        if not request.claim_number and not request.vin_number:
            raise HTTPException(status_code=400, detail="Необходимо указать номер дела или VIN")
        
        # Формируем данные заявки
        request_data = {
            "claim_number": request.claim_number,
            "vin_number": request.vin_number,
            "svg_collection": request.svg_collection
        }
        
        # Добавляем в очередь
        success = redis_manager.add_request_to_queue(request_data)
        
        if success:
            queue_length = redis_manager.get_queue_length()
            return QueueResponse(
                success=True,
                message=f"Заявка добавлена в очередь. Позиция в очереди: {queue_length}",
                data={"queue_length": queue_length}
            )
        else:
            raise HTTPException(status_code=500, detail="Ошибка добавления заявки в очередь")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка добавления заявки в очередь: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/start", response_model=QueueResponse)
async def start_queue_processing(request: Request):
    """Запуск обработки очереди"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Недействительная сессия"
        )
    """Запуск обработки очереди"""
    try:
        if queue_processor.is_running:
            return QueueResponse(
                success=False,
                message="Обработка очереди уже запущена"
            )
        
        # Запускаем обработку в фоне
        import asyncio
        asyncio.create_task(queue_processor.start_processing())
        
        return QueueResponse(
            success=True,
            message="Обработка очереди запущена"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска обработки очереди: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.post("/stop", response_model=QueueResponse)
async def stop_queue_processing(request: Request):
    """Остановка обработки очереди"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Недействительная сессия"
        )
    """Остановка обработки очереди"""
    try:
        queue_processor.stop_processing()
        
        return QueueResponse(
            success=True,
            message="Остановка обработки очереди запрошена"
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка остановки обработки очереди: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/status", response_model=QueueResponse)
async def get_queue_status(request: Request):
    """Получение статуса очереди"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Недействительная сессия"
        )
    """Получение статуса очереди"""
    try:
        stats = queue_processor.get_stats()
        
        return QueueResponse(
            success=True,
            message="Статус очереди получен",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения статуса очереди: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/requests", response_model=QueueResponse)
async def get_queue_requests(request: Request):
    """Получение списка заявок в очереди"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Недействительная сессия"
        )
    """Получение списка заявок в очереди"""
    try:
        queue_length = redis_manager.get_queue_length()
        pending_requests = redis_manager.get_pending_requests()
        processing_requests = redis_manager.get_processing_requests()
        completed_requests = redis_manager.get_completed_requests()
        
        return QueueResponse(
            success=True,
            message="Список заявок получен",
            data={
                "queue_length": queue_length,
                "pending_count": len(pending_requests),
                "processing_count": len(processing_requests),
                "completed_count": len(completed_requests),
                "pending_requests": pending_requests,
                "processing_requests": processing_requests,
                "completed_requests": completed_requests
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения списка заявок: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.delete("/clear", response_model=QueueResponse)
async def clear_queue(request: Request):
    """Очистка очереди"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Недействительная сессия"
        )
    """Полная очистка очереди (включая заявки в обработке и завершенные)"""
    try:
        success = redis_manager.clear_queue()
        
        if success:
            return QueueResponse(
                success=True,
                message="Вся очередь полностью очищена (очередь, обработка, завершенные)"
            )
        else:
            raise HTTPException(status_code=500, detail="Ошибка очистки очереди")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка очистки очереди: {e}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")


@router.get("/health", response_model=QueueResponse)
async def check_redis_health(request: Request):
    """Проверка здоровья Redis"""
    # Проверяем токен сессии
    from core.auth.db_auth import validate_session
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Не авторизован"
        )
    
    user_data = validate_session(session_token)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Недействительная сессия"
        )
    """Проверка здоровья Redis"""
    try:
        is_connected = redis_manager.test_connection()
        
        if is_connected:
            return QueueResponse(
                success=True,
                message="Redis подключен и работает",
                data={"redis_status": "connected"}
            )
        else:
            return QueueResponse(
                success=False,
                message="Redis недоступен",
                data={"redis_status": "disconnected"}
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка проверки здоровья Redis: {e}")
        return QueueResponse(
            success=False,
            message="Ошибка проверки Redis",
            data={"redis_status": "error", "error": str(e)}
        ) 