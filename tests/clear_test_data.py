import asyncio
from sqlalchemy import text
from core.database.models import async_session

async def clear_test_data():
    """Очищает все тестовые данные из базы данных каскадно"""
    
    async with async_session() as session:
        try:
            # Отключаем проверку внешних ключей для каскадного удаления
            await session.execute(text("SET session_replication_role = replica;"))
            
            # Очищаем все таблицы в правильном порядке
            tables = [
                'parser_car_options',
                'parser_car_detail_group_zone', 
                'parser_car_detail',
                'parser_car_request_status',
                'user_sessions',
                'users'
            ]
            
            for table in tables:
                await session.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"))
                print(f"Очищена таблица: {table}")
            
            # Включаем обратно проверку внешних ключей
            await session.execute(text("SET session_replication_role = DEFAULT;"))
            
            await session.commit()
            print("Все тестовые данные успешно удалены из базы данных")
            
        except Exception as e:
            await session.rollback()
            print(f"Ошибка при очистке данных: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(clear_test_data()) 