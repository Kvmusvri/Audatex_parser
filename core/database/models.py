import os
from sqlalchemy import String, Integer
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

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(50))
    vin: Mapped[str] = mapped_column(String(50))
    group_zone: Mapped[str] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    source_from: Mapped[str] = mapped_column(String(50))

class ParserCarDetailGroupZone(Base):
    __tablename__ = 'parser_car_detail_group_zone'

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(50))
    vin: Mapped[str] = mapped_column(String(50))
    type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    source_from: Mapped[str] = mapped_column(String(50))

class ParserCarRequestStatus(Base):
    __tablename__ = 'parser_car_request_status'

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(50))
    vin: Mapped[str] = mapped_column(String(50))
    comment: Mapped[str] = mapped_column(String(50))



async def start_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()