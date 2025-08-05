"""
Скрипт для инициализации базы данных
"""
import asyncio
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database.models import Base, User, UserSession
from core.auth.db_auth import create_default_users, get_password_hash
from dotenv import load_dotenv

load_dotenv()

def create_database_engine():
    """Создание engine для базы данных с обработкой ошибок"""
    try:
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            return create_engine(database_url.replace('+asyncpg', '+psycopg2'))
        else:
            # Создаем dummy engine для документации
            return create_engine('sqlite:///:memory:')
    except Exception as e:
        print(f"⚠️ Предупреждение: Не удалось создать engine: {e}")
        # Создаем dummy engine для документации
        return create_engine('sqlite:///:memory:')

def init_database():
    """Инициализация базы данных"""
    print("🔄 Инициализация базы данных...")
    
    try:
        # Создаем синхронный движок
        engine = create_database_engine()
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=engine)
        print("✅ Таблицы созданы")
        
        # Создаем сессию
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Очищаем существующих пользователей
            db.execute(db.query(UserSession).delete())
            db.execute(db.query(User).delete())
            db.commit()
            print("✅ Существующие пользователи удалены")
            
            # Создаем пользователей по умолчанию
            create_default_users()
            print("✅ Пользователи по умолчанию созданы")
            
        finally:
            db.close()
        
        print("✅ База данных успешно инициализирована")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка инициализации базы данных: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1) 