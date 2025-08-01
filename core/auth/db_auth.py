"""
Безопасная аутентификация через базу данных с солеными хешами
"""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import select
from core.database.models import User, UserSession
from core.database.requests import get_db

logger = logging.getLogger(__name__)

# Настройка контекста для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Хранилище активных сессий (в памяти для быстрого доступа)
active_sessions = {}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет пароль против хеша"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Создает хеш пароля с солью"""
    return pwd_context.hash(password)


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Аутентифицирует пользователя по логину и паролю"""
    try:
        logger.info(f"Попытка аутентификации пользователя: {username}")
        db = get_db()
        try:
            # Используем ORM для поиска пользователя
            from sqlalchemy import select
            from core.database.models import User
            stmt = select(User).where(User.username == username)
            user = db.execute(stmt).scalar_one_or_none()
            
            if not user:
                logger.warning(f"Пользователь не найден: {username}")
                return None
            
            logger.info(f"Пользователь найден: {username}, проверяем пароль")
            
            # Проверяем пароль
            if not verify_password(password, user.hashed_password):
                logger.warning(f"Неверный пароль для пользователя: {username}")
                return None
            
            # Проверяем, что пользователь активен
            if not user.is_active:
                logger.warning(f"Пользователь неактивен: {username}")
                return None
            
            logger.info(f"Успешная аутентификация: {username}")
            return {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка аутентификации: {e}")
        return None


def create_session(user_data: Dict[str, Any]) -> str:
    """Создает сессию для пользователя"""
    try:
        # Генерируем уникальный токен
        session_token = secrets.token_urlsafe(32)
        
        # Сохраняем сессию в базе данных
        db = get_db()
        try:
            from core.database.models import UserSession
            from core.security.auth_utils import hash_token
            
            expires_at = datetime.now() + timedelta(hours=24)
            token_hash = hash_token(session_token)
            
            # Создаем новую сессию с использованием ORM
            new_session = UserSession(
                user_id=user_data['id'],
                token_hash=token_hash,
                expires_at=expires_at,
                ip_address="127.0.0.1",
                user_agent="Unknown"
            )
            
            db.add(new_session)
            db.commit()
            
            # Также сохраняем в памяти для быстрого доступа
            active_sessions[session_token] = {
                'user_data': user_data,
                'created_at': datetime.now(),
                'expires_at': expires_at
            }
            
            logger.info(f"Создана сессия для пользователя: {user_data['username']}")
            return session_token
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка создания сессии: {e}")
        return None


def validate_session(session_token: str) -> Optional[Dict[str, Any]]:
    """Проверяет валидность сессии"""
    try:
        # Сначала проверяем в памяти
        if session_token in active_sessions:
            session = active_sessions[session_token]
            
            # Проверяем срок действия
            if datetime.now() > session['expires_at']:
                # Удаляем истекшую сессию
                del active_sessions[session_token]
                return None
            
            return session['user_data']
        
        # Если нет в памяти, проверяем в базе данных
        db = get_db()
        try:
            from sqlalchemy import select
            from core.database.models import UserSession, User
            from core.security.auth_utils import hash_token
            
            token_hash = hash_token(session_token)
            
            # Используем ORM для поиска сессии с пользователем
            stmt = select(UserSession).where(UserSession.token_hash == token_hash)
            result = db.execute(stmt).scalar_one_or_none()
            
            if not result:
                return None
            
            # Проверяем срок действия
            if datetime.now() > result.expires_at:
                # Удаляем истекшую сессию
                db.delete(result)
                db.commit()
                return None
            
            # Получаем пользователя отдельным запросом
            user_stmt = select(User).where(User.id == result.user_id)
            user_result = db.execute(user_stmt).scalar_one_or_none()
            
            if not user_result:
                return None
            
            # Проверяем, что пользователь активен
            if not user_result.is_active:
                return None
            
            # Обновляем сессию в памяти
            user_data = {
                'id': user_result.id,
                'username': user_result.username,
                'email': user_result.email,
                'role': user_result.role,
                'is_active': user_result.is_active
            }
            
            active_sessions[session_token] = {
                'user_data': user_data,
                'created_at': result.created_at,
                'expires_at': result.expires_at
            }
            
            return user_data
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка валидации сессии: {e}")
        return None


def delete_session(session_token: str) -> bool:
    """Удаляет сессию пользователя"""
    try:
        # Удаляем из памяти
        if session_token in active_sessions:
            del active_sessions[session_token]
        
        # Удаляем из базы данных
        db = get_db()
        try:
            from sqlalchemy import select
            from core.database.models import UserSession
            from core.security.auth_utils import hash_token
            
            token_hash = hash_token(session_token)
            
            # Находим сессию и удаляем её
            stmt = select(UserSession).where(UserSession.token_hash == token_hash)
            session = db.execute(stmt).scalar_one_or_none()
            
            if session:
                db.delete(session)
                db.commit()
                logger.info("Сессия удалена из базы данных")
                return True
            return False
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка удаления сессии: {e}")
        return False


def cleanup_expired_sessions():
    """Очищает истекшие сессии"""
    try:
        current_time = datetime.now()
        
        # Очищаем из памяти
        expired_tokens = []
        for token, session in active_sessions.items():
            if current_time > session['expires_at']:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del active_sessions[token]
        
        # Очищаем из базы данных
        db = get_db()
        try:
            from sqlalchemy import select
            from core.database.models import UserSession
            stmt = select(UserSession).where(UserSession.expires_at < current_time)
            expired_sessions = db.execute(stmt).scalars().all()
            
            for session in expired_sessions:
                db.delete(session)
            
            db.commit()
            
            if expired_tokens or expired_sessions:
                logger.info(f"Удалено {len(expired_tokens)} сессий из памяти и {len(expired_sessions)} из БД")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка очистки сессий: {e}")


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Получает пользователя по имени"""
    try:
        db = get_db()
        try:
            from sqlalchemy import select
            from core.database.models import User
            stmt = select(User).where(User.username == username)
            user = db.execute(stmt).scalar_one_or_none()
            
            if user:
                return {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'role': user.role,
                    'is_active': user.is_active
                }
            return None
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка получения пользователя: {e}")
        return None


def create_user(username: str, password: str, role: str = "api", email: str = None) -> bool:
    """Создает нового пользователя"""
    try:
        db = get_db()
        try:
            # Проверяем, существует ли пользователь
            from sqlalchemy import select
            from core.database.models import User
            stmt = select(User).where(User.username == username)
            existing_user = db.execute(stmt).scalar_one_or_none()
            
            if existing_user:
                logger.warning(f"Пользователь {username} уже существует")
                return False
            
            # Создаем хеш пароля
            password_hash = get_password_hash(password)
            
            # Создаем нового пользователя с использованием ORM
            from core.database.models import User
            new_user = User(
                username=username,
                hashed_password=password_hash,
                role=role or 'api',
                email=email or f"{username}@example.com",
                is_active=True
            )
            
            db.add(new_user)
            db.commit()
            
            logger.info(f"Создан новый пользователь: {username}")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка создания пользователя: {e}")
        return False


def change_password(username: str, new_password: str) -> bool:
    """Меняет пароль пользователя"""
    try:
        db = get_db()
        try:
            from sqlalchemy import select
            from core.database.models import User
            stmt = select(User).where(User.username == username)
            user = db.execute(stmt).scalar_one_or_none()
            
            if not user:
                logger.warning(f"Пользователь {username} не найден")
                return False
            
            # Создаем новый хеш пароля
            password_hash = get_password_hash(new_password)
            user.hashed_password = password_hash
            db.commit()
            
            logger.info(f"Пароль изменен для пользователя: {username}")
            return True
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка смены пароля: {e}")
        return False


def create_default_users():
    """Создает пользователей по умолчанию из переменных окружения"""
    try:
        import os
        
        # Получаем данные администратора из .env
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_password = os.getenv('ADMIN_PASSWORD')
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        
        # Получаем данные API пользователя из .env
        api_username = os.getenv('API_USERNAME', 'api_user')
        api_password = os.getenv('API_PASSWORD')
        api_email = os.getenv('API_EMAIL', 'api@example.com')
        
        logger.info(f"Попытка создания пользователей: admin={admin_username}, api={api_username}")
        logger.info(f"Пароли установлены: admin={bool(admin_password)}, api={bool(api_password)}")
        
        # Создаем администратора
        if admin_password:
            if not create_user(
                username=admin_username,
                password=admin_password,
                role="admin",
                email=admin_email
            ):
                logger.warning("Администратор уже существует")
            else:
                logger.info(f"Администратор {admin_username} создан успешно")
        else:
            logger.warning("ADMIN_PASSWORD не установлен в .env файле")
        
        # Создаем API пользователя
        if api_password:
            if not create_user(
                username=api_username,
                password=api_password,
                role="api",
                email=api_email
            ):
                logger.warning("API пользователь уже существует")
            else:
                logger.info(f"API пользователь {api_username} создан успешно")
        else:
            logger.warning("API_PASSWORD не установлен в .env файле")
        
        logger.info("Создание пользователей по умолчанию завершено")
        
    except Exception as e:
        logger.error(f"Ошибка создания пользователей по умолчанию: {e}") 