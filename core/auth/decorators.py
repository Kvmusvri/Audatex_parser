"""
Декораторы для защиты эндпоинтов
"""
import logging
from functools import wraps
from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from core.security.auth_utils import verify_token
from core.auth.users import UserManager

logger = logging.getLogger(__name__)


def require_auth(redirect_to_login: bool = True):
    """
    Декоратор для проверки аутентификации
    
    Args:
        redirect_to_login: Если True, перенаправляет на страницу входа для веб-интерфейса
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Извлекаем request из аргументов
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found"
                )
            
            # Проверяем токен из cookies
            token = request.cookies.get("session_token")
            if not token:
                if redirect_to_login:
                    return RedirectResponse(url="/auth/login", status_code=302)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Не авторизован"
                    )
            
            # Проверяем сессию
            user = await UserManager.validate_session(token)
            if not user:
                if redirect_to_login:
                    response = RedirectResponse(url="/auth/login", status_code=302)
                    response.delete_cookie("session_token")
                    return response
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Недействительная сессия"
                    )
            
            # Добавляем пользователя в request
            request.state.user = user
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_role(required_role: str):
    """
    Декоратор для проверки роли пользователя
    
    Args:
        required_role: Требуемая роль ('admin' или 'api')
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Извлекаем request из аргументов
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break
            
            if not request:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Request object not found"
                )
            
            # Проверяем, что пользователь есть в request
            if not hasattr(request.state, 'user'):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Пользователь не авторизован"
                )
            
            user = request.state.user
            
            # Проверяем роль
            if user.role != required_role and user.role != 'admin':
                logger.warning(f"Попытка доступа к защищенному ресурсу: {user.username} (роль: {user.role})")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Недостаточно прав"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def require_admin(func: Callable):
    """Декоратор для проверки прав администратора"""
    return require_role('admin')(func)


def require_api_user(func: Callable):
    """Декоратор для проверки прав API пользователя"""
    return require_role('api')(func)


# Функции для использования с Depends
async def get_current_user(request: Request):
    """Получение текущего пользователя для использования с Depends"""
    # Проверяем токен из cookies
    token = request.cookies.get("session_token")
    if not token:
        logger.warning(f"Отсутствует session_token в cookies для {request.url.path}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    
    # Проверяем сессию
    user = await UserManager.validate_session(token)
    if not user:
        logger.warning(f"Недействительная сессия для токена: {token[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная сессия"
        )
    
    logger.info(f"Успешная аутентификация для пользователя {user.username} на {request.url.path}")
    return user


async def get_current_admin(request: Request):
    """Получение текущего администратора для использования с Depends"""
    user = await get_current_user(request)
    
    if user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )
    
    return user


async def get_current_api_user(request: Request):
    """Получение текущего API пользователя для использования с Depends"""
    user = await get_current_user(request)
    
    if user.role not in ['api', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права API пользователя"
        )
    
    return user


# Функции для проверки JWT токенов в API запросах
async def verify_api_token(request: Request):
    """Проверка JWT токена для API запросов"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Отсутствует токен авторизации"
        )
    
    token = auth_header.split(" ")[1]
    payload = verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен"
        )
    
    # Получаем пользователя
    user = await UserManager.get_user_by_id(payload.get("user_id"))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или неактивен"
        )
    
    return user


async def verify_api_admin_token(request: Request):
    """Проверка JWT токена администратора для API запросов"""
    user = await verify_api_token(request)
    
    if user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )
    
    return user 