#!/usr/bin/env python3
"""
Проверка текущих сессий
"""

import asyncio
from core.database.models import async_session, UserSession, User
from sqlalchemy import select
from datetime import datetime

async def check_sessions():
    """Проверка текущих сессий"""
    print("🔍 Проверка текущих сессий...")
    
    try:
        async with async_session() as session:
            # Получаем все активные сессии
            result = await session.execute(
                select(UserSession).where(UserSession.expires_at > datetime.utcnow())
            )
            active_sessions = result.scalars().all()
            
            print(f"📊 Активных сессий: {len(active_sessions)}")
            
            for s in active_sessions:
                # Получаем пользователя
                user_result = await session.execute(
                    select(User).where(User.id == s.user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if user:
                    print(f"  - ID: {s.id}, User: {user.username}, Expires: {s.expires_at}")
                else:
                    print(f"  - ID: {s.id}, User: {s.user_id} (не найден), Expires: {s.expires_at}")
            
            # Получаем все сессии (включая истекшие)
            result = await session.execute(select(UserSession))
            all_sessions = result.scalars().all()
            
            print(f"\n📊 Всего сессий в БД: {len(all_sessions)}")
            
            if len(all_sessions) > len(active_sessions):
                print("⚠️  Есть истекшие сессии, которые нужно очистить")
                
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_sessions()) 