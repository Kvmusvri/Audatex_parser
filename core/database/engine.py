from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv
import os

load_dotenv()

engine = create_async_engine(os.getenv('DATABASE_URL'), echo=True, pool_pre_ping=True)