"""
Модуль для работы с пользователями
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.security.auth_utils import (
    calculate_lockout_time,
    generate_secure_password,
    generate_secure_token,
    get_client_ip,
    get_password_hash,
    get_user_agent,
    hash_token,
    is_account_locked,
    validate_password_strength,
    verify_password,
)
from core.database.models import User, UserSession, async_session

logger = logging.getLogger(__name__)


class UserManager:
    """Менеджер для работы с пользователями"""
    
    @staticmethod
    async def create_user(
        username: str, 
        password: str, 
        role: str = "api", 
        email: Optional[str] = None
    ) -> User:
        """Создание нового пользователя"""
        async with async_session() as session:
            # Проверяем, что пользователь не существует
            existing_user = await session.execute(
                select(User).where(User.username == username)
            )
            if existing_user.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь с таким именем уже существует"
                )
            
            # Проверяем сложность пароля
            is_valid, message = validate_password_strength(password)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=message
                )
            
            # Создаем пользователя
            hashed_password = get_password_hash(password)
            user = User(
                username=username,
                email=email,
                hashed_password=hashed_password,
                role=role,
                is_active=True
            )
            
            session.add(user)
            await session.commit()
            await session.refresh(user)
            
            logger.info(f"Создан новый пользователь: {username} с ролью {role}")
            return user
    
    @staticmethod
    async def get_user_by_username(username: str) -> Optional[User]:
        """Получение пользователя по имени"""
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def get_user_by_id(user_id: int) -> Optional[User]:
        """Получение пользователя по ID"""
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)
            )
            return result.scalar_one_or_none()
    
    @staticmethod
    async def authenticate_user(username: str, password: str, request) -> Optional[User]:
        """Аутентификация пользователя"""
        async with async_session() as session:
            user = await session.execute(
                select(User).where(User.username == username)
            )
            user = user.scalar_one_or_none()
            
            if not user:
                logger.warning(f"Попытка входа с несуществующим пользователем: {username}")
                return None
            
            if not user.is_active:
                logger.warning(f"Попытка входа в неактивный аккаунт: {username}")
                return None
            
            # Проверяем блокировку
            if is_account_locked(user.failed_login_attempts, user.locked_until):
                logger.warning(f"Попытка входа в заблокированный аккаунт: {username}")
                return None
            
            # Проверяем пароль
            if not verify_password(password, user.hashed_password):
                # Увеличиваем счетчик неудачных попыток
                user.failed_login_attempts += 1
                
                # Блокируем аккаунт при превышении лимита
                if user.failed_login_attempts >= 5:
                    user.locked_until = calculate_lockout_time()
                    logger.warning(f"Аккаунт заблокирован: {username}")
                
                await session.commit()
                logger.warning(f"Неверный пароль для пользователя: {username}")
                
                # Логируем событие безопасности
                try:
                    from core.security.security_monitor import log_security_event
                    log_security_event(
                        "BRUTE_FORCE_ATTEMPT",
                        request,
                        {
                            "username": username,
                            "failed_attempts": user.failed_login_attempts,
                            "account_locked": user.failed_login_attempts >= 5
                        },
                        risk_score=30 + (user.failed_login_attempts * 10)
                    )
                except Exception as e:
                    logger.error(f"Ошибка логирования события безопасности: {e}")
                
                return None
            
            # Сбрасываем счетчик неудачных попыток при успешном входе
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()
            await session.commit()
            
            logger.info(f"Успешная аутентификация пользователя: {username}")
            return user
    
    @staticmethod
    async def create_session(user_id: int, request) -> str:
        """Создание сессии пользователя"""
        async with async_session() as session:
            # Генерируем токен
            token = generate_secure_token()
            token_hash = hash_token(token)
            
            # Создаем сессию
            user_session = UserSession(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=datetime.utcnow() + timedelta(hours=24),
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            
            session.add(user_session)
            await session.commit()
            
            logger.info(f"Создана сессия для пользователя ID: {user_id}")
            return token
    
    @staticmethod
    async def validate_session(token: str) -> Optional[User]:
        """Проверка сессии пользователя"""
        async with async_session() as session:
            token_hash = hash_token(token)
            
            # Находим сессию
            result = await session.execute(
                select(UserSession).where(
                    UserSession.token_hash == token_hash,
                    UserSession.expires_at > datetime.utcnow()
                )
            )
            user_session = result.scalar_one_or_none()
            
            if not user_session:
                logger.warning(f"Сессия не найдена или истекла для токена: {token[:10]}...")
                return None
            
            # Получаем пользователя
            user = await session.execute(
                select(User).where(
                    User.id == user_session.user_id,
                    User.is_active == True
                )
            )
            user = user.scalar_one_or_none()
            
            if not user:
                logger.warning(f"Пользователь не найден или неактивен для сессии: {user_session.id}")
                # Удаляем недействительную сессию
                await session.execute(
                    delete(UserSession).where(UserSession.id == user_session.id)
                )
                await session.commit()
                return None
            
            logger.info(f"Сессия валидна для пользователя: {user.username}")
            return user
    
    @staticmethod
    async def delete_session(token: str) -> bool:
        """Удаление сессии пользователя"""
        async with async_session() as session:
            token_hash = hash_token(token)
            
            result = await session.execute(
                delete(UserSession).where(UserSession.token_hash == token_hash)
            )
            await session.commit()
            
            return result.rowcount > 0
    
    @staticmethod
    async def cleanup_expired_sessions() -> int:
        """Очистка истекших сессий"""
        async with async_session() as session:
            result = await session.execute(
                delete(UserSession).where(UserSession.expires_at <= datetime.utcnow())
            )
            await session.commit()
            
            deleted_count = result.rowcount
            if deleted_count > 0:
                logger.info(f"Удалено {deleted_count} истекших сессий")
            
            return deleted_count
    
    @staticmethod
    async def get_all_users() -> List[User]:
        """Получение всех пользователей"""
        async with async_session() as session:
            result = await session.execute(select(User))
            return result.scalars().all()
    
    @staticmethod
    async def update_user_role(user_id: int, new_role: str) -> bool:
        """Обновление роли пользователя"""
        async with async_session() as session:
            result = await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(role=new_role, updated_at=datetime.utcnow())
            )
            await session.commit()
            
            return result.rowcount > 0
    
    @staticmethod
    async def deactivate_user(user_id: int) -> bool:
        """Деактивация пользователя"""
        async with async_session() as session:
            # Удаляем все сессии пользователя
            await session.execute(
                delete(UserSession).where(UserSession.user_id == user_id)
            )
            
            # Деактивируем пользователя
            result = await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(is_active=False, updated_at=datetime.utcnow())
            )
            await session.commit()
            
            return result.rowcount > 0
    
    @staticmethod
    async def change_password(user_id: int, new_password: str) -> bool:
        """Смена пароля пользователя"""
        # Проверяем сложность пароля
        is_valid, message = validate_password_strength(new_password)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
        
        async with async_session() as session:
            hashed_password = get_password_hash(new_password)
            result = await session.execute(
                update(User)
                .where(User.id == user_id)
                .values(
                    hashed_password=hashed_password,
                    updated_at=datetime.utcnow()
                )
            )
            await session.commit()
            
            return result.rowcount > 0


# Функции для инициализации пользователей по умолчанию
async def create_default_users():
    """Создание пользователей по умолчанию"""
    try:
        # Проверяем, есть ли уже пользователи
        users = await UserManager.get_all_users()
        if users:
            logger.info("Пользователи уже существуют, пропускаем создание по умолчанию")
            return
        
        # Создаем админа
        admin_password = generate_secure_password()
        admin_user = await UserManager.create_user(
            username="admin",
            password=admin_password,
            role="admin",
            email="admin@audotex.local"
        )
        
        # Создаем API пользователя
        api_password = generate_secure_password()
        api_user = await UserManager.create_user(
            username="api_user",
            password=api_password,
            role="api",
            email="api@audotex.local"
        )
        
        logger.info("Созданы пользователи по умолчанию:")
        logger.info(f"Админ: admin / {admin_password}")
        logger.info(f"API: api_user / {api_password}")
        
        # Сохраняем пароли в файл (только для разработки)
        with open("admin_credentials.md", "w", encoding="utf-8") as f:
            f.write("# Учетные данные администратора\n\n")
            f.write("**ВНИМАНИЕ: Измените эти пароли после первого входа!**\n\n")
            f.write(f"## Администратор\n")
            f.write(f"- Логин: `admin`\n")
            f.write(f"- Пароль: `{admin_password}`\n\n")
            f.write(f"## API пользователь\n")
            f.write(f"- Логин: `api_user`\n")
            f.write(f"- Пароль: `{api_password}`\n\n")
            f.write("Эти учетные данные созданы автоматически при первом запуске.\n")
            f.write("Рекомендуется изменить пароли после первого входа в систему.\n")
        
        logger.info("Учетные данные сохранены в файл admin_credentials.md")
        
    except Exception as e:
        logger.error(f"Ошибка создания пользователей по умолчанию: {e}")
        raise 