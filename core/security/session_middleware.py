"""
Middleware для обработки сессий в API эндпоинтах
"""
import logging
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

async def session_middleware(request: Request, call_next):
    """Middleware для обработки сессий"""
    try:
        # Проверяем только API эндпоинты безопасности
        if request.url.path.startswith("/security/") and request.url.path != "/security":
            # Проверяем токен из cookies
            token = request.cookies.get("session_token")
            if not token:
                logger.warning(f"Отсутствует session_token для {request.url.path}")
                # Не блокируем запрос, просто логируем
                pass
            else:
                try:
                    # Проверяем сессию
                    from core.auth.users import UserManager
                    user = await UserManager.validate_session(token)
                    if user:
                        # Добавляем пользователя в request.state
                        request.state.user = user
                        logger.info(f"API аутентификация успешна для {user.username} на {request.url.path}")
                    else:
                        logger.warning(f"Недействительная сессия для {request.url.path}")
                        # Не блокируем запрос, просто логируем
                except Exception as e:
                    logger.error(f"Ошибка проверки сессии для {request.url.path}: {e}")
                    # Не блокируем запрос при ошибке
        
        # Продолжаем обработку запроса
        response = await call_next(request)
        return response
        
    except Exception as e:
        logger.error(f"Ошибка в session middleware: {e}")
        return await call_next(request) 