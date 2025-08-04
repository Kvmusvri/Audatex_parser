import os
import secrets
from datetime import datetime, date, timedelta
from sqlalchemy import String, Integer, Text, Index, DateTime, Date, func, PrimaryKeyConstraint, Boolean, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
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
    svg_path: Mapped[str] = mapped_column(Text, nullable=True)  # Путь к SVG детали
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
    screenshot_path: Mapped[str] = mapped_column(Text, nullable=True)  # Путь к скриншоту зоны
    svg_path: Mapped[str] = mapped_column(Text, nullable=True)  # Путь к SVG зоны
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
    file_path: Mapped[str] = mapped_column(Text, nullable=True)  # Путь к файлу из JSON
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

class ParserScheduleSettings(Base):
    __tablename__ = 'parser_schedule_settings'
    __table_args__ = (
        Index('idx_schedule_settings_active', 'is_active'),
        Index('idx_schedule_settings_updated', 'updated_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)    # HH:MM
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = 'users'
    __table_args__ = (
        Index('idx_users_username', 'username', unique=True),
        Index('idx_users_email', 'email'),
        Index('idx_users_role', 'role'),
        Index('idx_users_is_active', 'is_active'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(100), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default='api')  # 'admin' или 'api'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    # Связь с сессиями
    sessions: Mapped[list['UserSession']] = relationship('UserSession', back_populates='user', cascade='all, delete-orphan')


class UserSession(Base):
    __tablename__ = 'user_sessions'
    __table_args__ = (
        Index('idx_user_sessions_user_id', 'user_id'),
        Index('idx_user_sessions_token_hash', 'token_hash', unique=True),
        Index('idx_user_sessions_expires_at', 'expires_at'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str] = mapped_column(String(45), nullable=True)  # IPv6 support
    user_agent: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    
    # Связь с пользователем
    user: Mapped[User] = relationship('User', back_populates='sessions')

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