"""
Маршруты для аутентификации через базу данных
"""
import logging
from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.auth.db_auth import authenticate_user, create_session, validate_session, delete_session

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
        user_data = authenticate_user(username, password)
        
        if not user_data:
            return templates.TemplateResponse(
                "login.html", 
                {
                    "request": request, 
                    "error": "Неверное имя пользователя или пароль"
                },
                status_code=400
            )
        
        # Создаем сессию
        session_token = create_session(user_data)
        if not session_token:
            return templates.TemplateResponse(
                "login.html", 
                {
                    "request": request, 
                    "error": "Ошибка создания сессии"
                },
                status_code=500
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
            secure=False,
            samesite="lax"
        )
        
        logger.info(f"Успешный вход пользователя: {user_data['username']}")
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
            # Удаляем сессию
            delete_session(session_token)
        
        # Создаем ответ с удалением cookies
        response = RedirectResponse(url="/auth/login", status_code=302)
        
        # Удаляем cookie сессии
        response.delete_cookie("session_token")
        
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
    """API эндпоинт для входа"""
    try:
        # Аутентифицируем пользователя
        user_data = authenticate_user(username, password)
        
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль"
            )
        
        # Создаем сессию
        session_token = create_session(user_data)
        if not session_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ошибка создания сессии"
            )
        
        logger.info(f"API вход пользователя: {username}")
        
        return JSONResponse({
            "access_token": session_token,
            "token_type": "session",
            "user": {
                "id": user_data['id'],
                "username": user_data['username'],
                "role": user_data['role'],
                "email": user_data['email']
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


@router.get("/profile")
async def get_profile(request: Request):
    """Получение профиля текущего пользователя"""
    try:
        # Получаем токен сессии
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
        
        return JSONResponse({
            "id": user_data['id'],
            "username": user_data['username'],
            "email": user_data['email'],
            "role": user_data['role'],
            "is_active": user_data['is_active']
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения профиля: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        ) 