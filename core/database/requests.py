from sqlalchemy.ext.asyncio import AsyncSession
from core.database.models import ParserCarRequestStatus, ParserCarDetailGroupZone, ParserCarDetail

async def create_request_status(session: AsyncSession, request_id: str, vin: str, comment: str):
    status = ParserCarRequestStatus(
        request_id=request_id,
        vin=vin,
        comment=comment
    )
    session.add(status)
    await session.commit()

async def create_equipment_zone(session: AsyncSession, request_id: str, vin: str) -> int:
    zone = ParserCarDetailGroupZone(
        request_id=request_id,
        vin=vin,
        type="EQUIPMENT",
        title="ЗОНА КОМПЛЕКТАЦИИ",
        source_from="AUDATEX"
    )
    session.add(zone)
    await session.commit()
    await session.refresh(zone)
    return zone.id

async def create_group_zone(session: AsyncSession, request_id: str, vin: str, has_pictograms: bool, title: str) -> int:
    zone = ParserCarDetailGroupZone(
        request_id=request_id,
        vin=vin,
        type="WORKS" if has_pictograms else "DETAILS",
        title=title,
        source_from="AUDATEX"
    )
    session.add(zone)
    await session.commit()
    await session.refresh(zone)
    return zone.id

async def create_car_detail(session: AsyncSession, request_id: str, group_zone_id: int, vin: str, code: str, title: str):
    detail = ParserCarDetail(
        request_id=request_id,
        group_zone=group_zone_id,
        vin=vin,
        code=code,
        title=title,
        source_from="AUDATEX"
    )
    session.add(detail)
    await session.commit()