import os
from datetime import datetime, date
from sqlalchemy import String, Integer, Text, Index, DateTime, Date, func, PrimaryKeyConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from dotenv import load_dotenv
import pytz

load_dotenv()

# Оптимизированный connection pool
engine = create_async_engine(
    url=os.getenv('DATABASE_URL'),
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=False,  # Локальная БД
    echo=False
)
async_session = async_sessionmaker(engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class ParserCarDetail(Base):
    __tablename__ = 'parser_car_detail'
    __table_args__ = (
        Index('idx_car_detail_request_vin_date', 'request_id', 'vin', 'created_date'),
        Index('idx_car_detail_created_date', 'created_date'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    group_zone: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_from: Mapped[str] = mapped_column(String(50), nullable=False)
    created_date: Mapped[date] = mapped_column(Date, default=func.current_date())

class ParserCarDetailGroupZone(Base):
    __tablename__ = 'parser_car_detail_group_zone'
    __table_args__ = (
        Index('idx_car_group_zone_request_vin_date', 'request_id', 'vin', 'created_date'),
        Index('idx_car_group_zone_created_date', 'created_date'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_from: Mapped[str] = mapped_column(String(50), nullable=False)
    created_date: Mapped[date] = mapped_column(Date, default=func.current_date())

class ParserCarRequestStatus(Base):
    __tablename__ = 'parser_car_request_status'
    __table_args__ = (
        Index('idx_car_request_status_request_vin_date', 'request_id', 'vin', 'created_date'),
        Index('idx_car_request_status_created_date', 'created_date'),
        Index('idx_car_request_status_unique', 'request_id', 'vin', 'created_date', unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin_status: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_date: Mapped[date] = mapped_column(Date, default=func.current_date())

class ParserCarOptions(Base):
    __tablename__ = 'parser_car_options'
    __table_args__ = (
        Index('idx_car_options_request_vin_date', 'request_id', 'vin', 'created_date'),
        Index('idx_car_options_created_date', 'created_date'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False)
    option_code: Mapped[str] = mapped_column(String(50), nullable=False)
    option_title: Mapped[str] = mapped_column(Text, nullable=False)
    is_selected: Mapped[bool] = mapped_column(nullable=False, default=False)
    source_from: Mapped[str] = mapped_column(String(50), nullable=False)
    created_date: Mapped[date] = mapped_column(Date, default=func.current_date())

async def start_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()

async def close_db():
    await engine.dispose()

class DatabaseSession:
    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = async_session()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.session.rollback()
        else:
            await self.session.commit()
        await self.session.close()

def get_moscow_time() -> datetime:
    """Возвращает текущее время в московском часовом поясе"""
    moscow_tz = pytz.timezone('Europe/Moscow')
    utc_now = datetime.now(pytz.UTC)
    return utc_now.astimezone(moscow_tz)