#!/usr/bin/env python3
"""
Скрипт для очистки старых сессий
"""
import asyncio
from sqlalchemy import delete
from core.database.models import UserSession, async_session

async def clear_all_sessions():
    """Очищает все сессии из БД"""
    async with async_session() as session:
        result = await session.execute(delete(UserSession))
        await session.commit()
        print(f"Удалено {result.rowcount} сессий")

if __name__ == "__main__":
    asyncio.run(clear_all_sessions()) 