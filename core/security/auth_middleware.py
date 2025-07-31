"""
Middleware для аутентификации API эндпоинтов безопасности
"""
import logging
from fastapi import Request, HTTPException, status
from core.auth.users import UserManager

logger = logging.getLogger(__name__)

async def security_api_auth_middleware(request: Request, call_next):
    """Middleware для аутентификации API эндпоинтов безопасности"""
    try:
        # Проверяем только API эндпоинты безопасности
        if request.url.path.startswith("/security/") and request.url.path != "/security":
            # Проверяем токен из cookies
            token = request.cookies.get("session_token")
            if not token:
                logger.warning(f"Отсутствует session_token для {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Не авторизован"
                )
            
            # Проверяем сессию
            user = await UserManager.validate_session(token)
            if not user:
                logger.warning(f"Недействительная сессия для {request.url.path}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительная сессия"
                )
            
            # Добавляем пользователя в request.state
            request.state.user = user
            logger.info(f"API аутентификация успешна для {user.username} на {request.url.path}")
        
        # Продолжаем обработку запроса
        response = await call_next(request)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка в security API auth middleware: {e}")
        return await call_next(request) 