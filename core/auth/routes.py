"""
Эндпоинты для аутентификации
"""
import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.auth.decorators import get_current_user
from core.security.auth_utils import create_access_token, create_refresh_token
from core.auth.users import UserManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Страница входа в систему"""
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    remember: Optional[str] = Form(None)
):
    """Обработка входа в систему"""
    try:
        # Аутентифицируем пользователя
        user = await UserManager.authenticate_user(username, password, request)
        
        if not user:
            return templates.TemplateResponse(
                "login.html", 
                {
                    "request": request, 
                    "error": "Неверное имя пользователя или пароль"
                },
                status_code=400
            )
        
        # Создаем сессию
        session_token = await UserManager.create_session(user.id, request)
        
        # Создаем JWT токены
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "role": user.role}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )
        
        # Настраиваем ответ
        response = RedirectResponse(url="/", status_code=302)
        
        # Устанавливаем cookie с сессией
        max_age = 86400 * 7 if remember else 86400  # 7 дней или 1 день
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=max_age,
            httponly=True,
            secure=False,  # Установить True для HTTPS
            samesite="lax"
        )
        
        # Устанавливаем JWT токены в cookies для API
        response.set_cookie(
            key="access_token",
            value=access_token,
            max_age=1800,  # 30 минут
            httponly=True,
            secure=False,
            samesite="lax"
        )
        
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            max_age=604800,  # 7 дней
            httponly=True,
            secure=False,
            samesite="lax"
        )
        
        logger.info(f"Успешный вход пользователя: {username}")
        return response
        
    except Exception as e:
        logger.error(f"Ошибка при входе пользователя {username}: {e}")
        return templates.TemplateResponse(
            "login.html", 
            {
                "request": request, 
                "error": "Произошла ошибка при входе в систему"
            },
            status_code=500
        )


@router.post("/logout")
async def logout(request: Request):
    """Выход из системы"""
    try:
        # Получаем токен сессии
        session_token = request.cookies.get("session_token")
        
        if session_token:
            # Удаляем сессию из БД
            await UserManager.delete_session(session_token)
        
        # Создаем ответ с удалением cookies
        response = RedirectResponse(url="/auth/login", status_code=302)
        
        # Удаляем все cookies аутентификации
        response.delete_cookie("session_token")
        response.delete_cookie("access_token")
        response.delete_cookie("refresh_token")
        
        logger.info("Пользователь вышел из системы")
        return response
        
    except Exception as e:
        logger.error(f"Ошибка при выходе из системы: {e}")
        return RedirectResponse(url="/auth/login", status_code=302)


@router.get("/logout")
async def logout_get(request: Request):
    """GET запрос для выхода из системы"""
    return await logout(request)


@router.post("/api/login")
async def api_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """API эндпоинт для входа (возвращает JWT токены)"""
    try:
        # Аутентифицируем пользователя
        user = await UserManager.authenticate_user(username, password, request)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль"
            )
        
        # Создаем JWT токены
        access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "role": user.role}
        )
        refresh_token = create_refresh_token(
            data={"sub": user.username, "user_id": user.id}
        )
        
        logger.info(f"API вход пользователя: {username}")
        
        return JSONResponse({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "email": user.email
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при API входе пользователя {username}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@router.post("/api/refresh")
async def api_refresh_token(request: Request):
    """Обновление JWT токена"""
    try:
        # Получаем refresh token из cookies или заголовка
        refresh_token = request.cookies.get("refresh_token")
        
        if not refresh_token:
            # Пробуем получить из заголовка Authorization
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                refresh_token = auth_header.split(" ")[1]
        
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Отсутствует refresh token"
            )
        
        # Проверяем refresh token
        from core.security.auth_utils import verify_token
        payload = verify_token(refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Недействительный refresh token"
            )
        
        # Получаем пользователя
        user = await UserManager.get_user_by_id(payload.get("user_id"))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Пользователь не найден или неактивен"
            )
        
        # Создаем новый access token
        new_access_token = create_access_token(
            data={"sub": user.username, "user_id": user.id, "role": user.role}
        )
        
        logger.info(f"Обновлен токен для пользователя: {user.username}")
        
        return JSONResponse({
            "access_token": new_access_token,
            "token_type": "bearer"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при обновлении токена: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@router.get("/profile")
async def get_profile(request: Request, current_user = Depends(get_current_user)):
    """Получение профиля текущего пользователя"""
    return JSONResponse({
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "created_at": current_user.created_at.isoformat()
    })


@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user = Depends(get_current_user)
):
    """Смена пароля пользователя"""
    try:
        # Проверяем текущий пароль
        from core.security.auth_utils import verify_password
        if not verify_password(current_password, current_user.hashed_password):
            return templates.TemplateResponse(
                "profile.html", 
                {
                    "request": request, 
                    "error": "Неверный текущий пароль"
                },
                status_code=400
            )
        
        # Меняем пароль
        await UserManager.change_password(current_user.id, new_password)
        
        logger.info(f"Пароль изменен для пользователя: {current_user.username}")
        
        return templates.TemplateResponse(
            "profile.html", 
            {
                "request": request, 
                "success": "Пароль успешно изменен"
            }
        )
        
    except Exception as e:
        logger.error(f"Ошибка при смене пароля: {e}")
        return templates.TemplateResponse(
            "profile.html", 
            {
                "request": request, 
                "error": "Произошла ошибка при смене пароля"
            },
            status_code=500
        )


@router.post("/api/change-password")
async def api_change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user = Depends(get_current_user)
):
    """API эндпоинт для смены пароля"""
    try:
        # Проверяем текущий пароль
        from core.security.auth_utils import verify_password
        if not verify_password(current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный текущий пароль"
            )
        
        # Меняем пароль
        await UserManager.change_password(current_user.id, new_password)
        
        logger.info(f"API смена пароля для пользователя: {current_user.username}")
        
        return JSONResponse({
            "message": "Пароль успешно изменен"
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при API смене пароля: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        ) 