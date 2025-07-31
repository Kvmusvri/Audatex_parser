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
        db = get_db()
        try:
            # Простой защищенный запрос с параметризацией
            from sqlalchemy import text
            query = text("SELECT id, username, email, hashed_password, role, is_active FROM users WHERE username = :username")
            result = db.execute(query, {"username": username}).fetchone()
            
            if not result:
                logger.warning(f"Пользователь не найден: {username}")
                return None
            
            # Проверяем пароль
            if not verify_password(password, result.hashed_password):
                logger.warning(f"Неверный пароль для пользователя: {username}")
                return None
            
            # Проверяем, что пользователь активен
            if not result.is_active:
                logger.warning(f"Пользователь неактивен: {username}")
                return None
            
            logger.info(f"Успешная аутентификация: {username}")
            return {
                'id': result.id,
                'username': result.username,
                'email': result.email,
                'role': result.role,
                'is_active': result.is_active
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
            from sqlalchemy import text
            query = text("""
                INSERT INTO user_sessions (user_id, token_hash, expires_at, ip_address, user_agent, created_at)
                VALUES (:user_id, :token_hash, :expires_at, :ip_address, :user_agent, :created_at)
            """)
            
            expires_at = datetime.now() + timedelta(hours=24)
            created_at = datetime.now()
            
            # Хешируем токен для сохранения в БД
            from core.security.auth_utils import hash_token
            token_hash = hash_token(session_token)
            
            db.execute(query, {
                "user_id": user_data['id'],
                "token_hash": token_hash,
                "expires_at": expires_at,
                "ip_address": "127.0.0.1",
                "user_agent": "Unknown",
                "created_at": created_at
            })
            db.commit()
            
            # Также сохраняем в памяти для быстрого доступа
            active_sessions[session_token] = {
                'user_data': user_data,
                'created_at': created_at,
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
            from sqlalchemy import text
            query = text("""
                SELECT us.user_id, us.expires_at, us.created_at,
                       u.username, u.email, u.role, u.is_active
                FROM user_sessions us
                JOIN users u ON us.user_id = u.id
                WHERE us.token_hash = :token_hash
            """)
            
            # Хешируем токен для поиска в БД
            from core.security.auth_utils import hash_token
            token_hash = hash_token(session_token)
            
            result = db.execute(query, {"token_hash": token_hash}).fetchone()
            
            if not result:
                return None
            
            # Проверяем срок действия
            if datetime.now() > result.expires_at:
                # Удаляем истекшую сессию
                delete_query = text("DELETE FROM user_sessions WHERE token_hash = :token_hash")
                db.execute(delete_query, {"token_hash": token_hash})
                db.commit()
                return None
            
            # Проверяем, что пользователь активен
            if not result.is_active:
                return None
            
            # Обновляем сессию в памяти
            user_data = {
                'id': result.user_id,
                'username': result.username,
                'email': result.email,
                'role': result.role,
                'is_active': result.is_active
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
            from sqlalchemy import text
            # Хешируем токен для удаления из БД
            from core.security.auth_utils import hash_token
            token_hash = hash_token(session_token)
            
            query = text("DELETE FROM user_sessions WHERE token_hash = :token_hash")
            result = db.execute(query, {"token_hash": token_hash})
            db.commit()
            
            if result.rowcount > 0:
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
            from sqlalchemy import text
            check_query = text("SELECT id FROM users WHERE username = :username")
            existing_user = db.execute(check_query, {"username": username}).fetchone()
            
            if existing_user:
                logger.warning(f"Пользователь {username} уже существует")
                return False
            
            # Создаем хеш пароля
            password_hash = get_password_hash(password)
            
            # Создаем нового пользователя
            insert_query = text("""
                INSERT INTO users (username, hashed_password, role, email, is_active, created_at, updated_at)
                VALUES (:username, :hashed_password, :role, :email, :is_active, :created_at, :updated_at)
            """)
            
            now = datetime.now()
            db.execute(insert_query, {
                "username": username,
                "hashed_password": password_hash,
                "role": role,
                "email": email or f"{username}@example.com",
                "is_active": True,
                "created_at": now,
                "updated_at": now
            })
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
    """Создает пользователей по умолчанию"""
    try:
        # Создаем администратора
        if not create_user(
            username="admin",
            password="V@mZTI&i6Q3#9U$N",
            role="admin",
            email="admin@example.com"
        ):
            logger.warning("Администратор уже существует")
        
        # Создаем API пользователя
        if not create_user(
            username="api_user",
            password="VxWRF@7HCK0oFtZR",
            role="api",
            email="api@example.com"
        ):
            logger.warning("API пользователь уже существует")
        
        logger.info("Пользователи по умолчанию созданы")
        
    except Exception as e:
        logger.error(f"Ошибка создания пользователей по умолчанию: {e}") 