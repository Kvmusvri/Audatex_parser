"""
Утилиты для аутентификации и авторизации
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple

from fastapi import Request
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# Настройки безопасности
SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# Контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля"""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Ошибка проверки пароля: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Хеширование пароля"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT токена доступа"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """Создание JWT токена обновления"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    """Проверка JWT токена"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Ошибка проверки токена: {e}")
        return None


def generate_secure_token() -> str:
    """Генерация безопасного токена для сессий"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Хеширование токена для хранения в БД"""
    return hashlib.sha256(token.encode()).hexdigest()


def get_client_ip(request: Request) -> str:
    """Получение IP адреса клиента"""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def get_user_agent(request: Request) -> str:
    """Получение User-Agent клиента"""
    return request.headers.get("User-Agent", "unknown")


def is_account_locked(failed_attempts: int, locked_until: Optional[datetime]) -> bool:
    """Проверка блокировки аккаунта"""
    if failed_attempts >= MAX_LOGIN_ATTEMPTS and locked_until:
        return datetime.utcnow() < locked_until
    return False


def calculate_lockout_time() -> datetime:
    """Расчет времени блокировки"""
    return datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)


def generate_secure_password(length: int = 16) -> str:
    """Генерация безопасного пароля"""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        # Проверяем, что пароль содержит хотя бы одну букву, цифру и символ
        if (any(c.islower() for c in password) and 
            any(c.isupper() for c in password) and 
            any(c.isdigit() for c in password) and 
            any(c in "!@#$%^&*" for c in password)):
            return password


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """Проверка сложности пароля"""
    if len(password) < 8:
        return False, "Пароль должен содержать минимум 8 символов"
    
    if not any(c.islower() for c in password):
        return False, "Пароль должен содержать хотя бы одну строчную букву"
    
    if not any(c.isupper() for c in password):
        return False, "Пароль должен содержать хотя бы одну заглавную букву"
    
    if not any(c.isdigit() for c in password):
        return False, "Пароль должен содержать хотя бы одну цифру"
    
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        return False, "Пароль должен содержать хотя бы один специальный символ"
    
    return True, "Пароль соответствует требованиям безопасности" 