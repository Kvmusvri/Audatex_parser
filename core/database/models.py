import os
from sqlalchemy import String, Integer, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from dotenv import load_dotenv

load_dotenv()

engine = create_async_engine(url=os.getenv('DATABASE_URL'))
async_session = async_sessionmaker(engine)

class Base(AsyncAttrs, DeclarativeBase):
    pass

class ParserCarDetail(Base):
    __tablename__ = 'parser_car_detail'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    group_zone: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_from: Mapped[str] = mapped_column(String(50), nullable=False)

class ParserCarDetailGroupZone(Base):
    __tablename__ = 'parser_car_detail_group_zone'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_from: Mapped[str] = mapped_column(String(50), nullable=False)

class ParserCarRequestStatus(Base):
    __tablename__ = 'parser_car_request_status'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin_status: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[str] = mapped_column(String(50), nullable=False)

class ParserCarOptions(Base):
    __tablename__ = 'parser_car_options'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vin: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    zone_name: Mapped[str] = mapped_column(String(100), nullable=False)
    option_code: Mapped[str] = mapped_column(String(50), nullable=False)
    option_title: Mapped[str] = mapped_column(Text, nullable=False)
    is_selected: Mapped[bool] = mapped_column(nullable=False, default=False)
    source_from: Mapped[str] = mapped_column(String(50), nullable=False)

# Индексы для оптимизации запросов
Index('idx_car_detail_request_vin', ParserCarDetail.request_id, ParserCarDetail.vin)
Index('idx_car_group_zone_request_vin', ParserCarDetailGroupZone.request_id, ParserCarDetailGroupZone.vin)
Index('idx_car_request_status_request_vin', ParserCarRequestStatus.request_id, ParserCarRequestStatus.vin)
Index('idx_car_options_request_vin', ParserCarOptions.request_id, ParserCarOptions.vin)

async def start_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()