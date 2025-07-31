"""
Скрипт для диагностики проблем с сессиями
"""
import asyncio
import logging
from datetime import datetime
from sqlalchemy import select
from core.database.models import User, UserSession, async_session
from core.security.auth_utils import hash_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def debug_sessions():
    """Диагностика сессий"""
    async with async_session() as session:
        # Получаем все сессии
        result = await session.execute(select(UserSession))
        sessions = result.scalars().all()
        
        logger.info(f"Всего сессий в БД: {len(sessions)}")
        
        for sess in sessions:
            logger.info(f"Сессия ID: {sess.id}")
            logger.info(f"  User ID: {sess.user_id}")
            logger.info(f"  Token Hash: {sess.token_hash[:20]}...")
            logger.info(f"  Expires At: {sess.expires_at}")
            logger.info(f"  IP: {sess.ip_address}")
            logger.info(f"  User Agent: {sess.user_agent[:50]}...")
            logger.info(f"  Created At: {sess.created_at}")
            logger.info("---")
        
        # Получаем всех пользователей
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        logger.info(f"Всего пользователей: {len(users)}")
        for user in users:
            logger.info(f"Пользователь: {user.username} (ID: {user.id}, Active: {user.is_active})")

async def test_token_validation():
    """Тестирование валидации токена"""
    from core.auth.users import UserManager
    
    # Получаем первую сессию
    async with async_session() as session:
        result = await session.execute(select(UserSession).limit(1))
        user_session = result.scalar_one_or_none()
        
        if user_session:
            logger.info(f"Тестируем сессию ID: {user_session.id}")
            logger.info(f"Token Hash: {user_session.token_hash}")
            logger.info(f"Expires At: {user_session.expires_at}")
            logger.info(f"Current Time: {datetime.utcnow()}")
            logger.info(f"Is Expired: {user_session.expires_at <= datetime.utcnow()}")
            
            # Пробуем найти сессию по хешу
            result = await session.execute(
                select(UserSession).where(UserSession.token_hash == user_session.token_hash)
            )
            found_session = result.scalar_one_or_none()
            logger.info(f"Найдена сессия по хешу: {found_session is not None}")

if __name__ == "__main__":
    asyncio.run(debug_sessions())
    print("\n" + "="*50 + "\n")
    asyncio.run(test_token_validation()) 