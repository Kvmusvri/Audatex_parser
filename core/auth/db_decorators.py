"""
Декораторы для аутентификации через базу данных
"""
import logging
from functools import wraps
from typing import Callable

from fastapi import HTTPException, Request, status, Depends
from core.auth.db_auth import validate_session

logger = logging.getLogger(__name__)


def require_auth(redirect_to_login: bool = True):
    """Декоратор для проверки аутентификации"""
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
                    detail="Request объект не найден"
                )
            
            # Проверяем токен сессии
            session_token = request.cookies.get("session_token")
            if not session_token:
                if redirect_to_login:
                    from fastapi.responses import RedirectResponse
                    return RedirectResponse(url="/auth/login", status_code=302)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Не авторизован"
                    )
            
            # Проверяем сессию
            user_data = validate_session(session_token)
            if not user_data:
                if redirect_to_login:
                    from fastapi.responses import RedirectResponse
                    return RedirectResponse(url="/auth/login", status_code=302)
                else:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Недействительная сессия"
                    )
            
            # Добавляем пользователя в request.state
            request.state.user = user_data
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(required_role: str):
    """Декоратор для проверки роли пользователя"""
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
                    detail="Request объект не найден"
                )
            
            # Проверяем токен сессии
            session_token = request.cookies.get("session_token")
            if not session_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Не авторизован"
                )
            
            # Проверяем сессию
            user_data = validate_session(session_token)
            if not user_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Недействительная сессия"
                )
            
            # Проверяем роль
            if user_data['role'] != required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Требуется роль: {required_role}"
                )
            
            # Добавляем пользователя в request.state
            request.state.user = user_data
            
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    
    # Проверяем сессию
    user_data = validate_session(token)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительная сессия"
        )
    
    return user_data


async def get_current_admin(request: Request):
    """Получение текущего администратора для использования с Depends"""
    user_data = await get_current_user(request)
    
    if user_data['role'] != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права администратора"
        )
    
    return user_data


async def get_current_api_user(request: Request):
    """Получение текущего API пользователя для использования с Depends"""
    user_data = await get_current_user(request)
    
    if user_data['role'] not in ['api', 'admin']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права API пользователя"
        )
    
    return user_data 