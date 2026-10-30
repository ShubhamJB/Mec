"""
Service layer for Public Garage Profiles and Analytics Events (Profile View / Call Click).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from geoalchemy2.functions import ST_X, ST_Y
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent
from app.models.catalog import (
    GarageService,
    GarageVehicleType,
    OperatingHours,
    Service,
    VehicleType,
)
from app.models.enums import (
    AccountStatus,
    AnalyticsEventType,
    ApprovalStatus,
    ReviewStatus,
)
from app.models.garage import Garage
from app.models.photo import GaragePhoto
from app.models.review import Review
from app.models.user import User
from app.schemas.catalog import ServiceRead, VehicleTypeRead
from app.schemas.garage_profile import AvailabilityResponse
from app.schemas.garage_registration import OperatingHourItem
from app.schemas.photo import PhotoRead
from app.schemas.public_garage import (
    PublicGarageProfileResponse,
    PublicOperatingHoursResponse,
)
from app.utils.availability import calculate_garage_availability


async def verify_public_garage(db: AsyncSession, garage_id: uuid.UUID) -> Garage:
    """
    Ensures the garage is eligible for public presentation:
    - approval_status == APPROVED
    - is_suspended == False
    - deleted_at is NULL
    - owner account_status == ACTIVE and not deleted
    Raises 404 NOT FOUND otherwise to avoid leaking moderation/existence details.
    """
    stmt = (
        select(Garage)
        .join(User, Garage.owner_id == User.id)
        .where(
            Garage.id == garage_id,
            Garage.approval_status == ApprovalStatus.APPROVED,
            Garage.is_suspended.is_(False),
            Garage.deleted_at.is_(None),
            User.account_status == AccountStatus.ACTIVE,
            User.deleted_at.is_(None),
        )
    )
    garage = (await db.execute(stmt)).scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garage not found or not publicly available.",
        )
    return garage


async def _get_garage_coordinates(db: AsyncSession, garage_id: uuid.UUID) -> tuple[float, float]:
    stmt = select(
        ST_Y(Garage.location.cast(func.geometry())),
        ST_X(Garage.location.cast(func.geometry())),
    ).where(Garage.id == garage_id)
    row = (await db.execute(stmt)).first()
    if row and row[0] is not None and row[1] is not None:
        return float(row[0]), float(row[1])
    return 0.0, 0.0


async def get_public_garage_profile(
    db: AsyncSession,
    garage_id: uuid.UUID,
) -> PublicGarageProfileResponse:
    garage = await verify_public_garage(db, garage_id)
    lat, lng = await _get_garage_coordinates(db, garage_id)

    # 1. Operating hours
    hours_stmt = (
        select(OperatingHours)
        .where(OperatingHours.garage_id == garage.id)
        .order_by(OperatingHours.day_of_week.asc())
    )
    hours = list((await db.execute(hours_stmt)).scalars().all())

    # 2. Services
    services_stmt = (
        select(Service)
        .join(GarageService, GarageService.service_id == Service.id)
        .where(GarageService.garage_id == garage.id, Service.is_active.is_(True))
        .order_by(Service.name.asc())
    )
    services = list((await db.execute(services_stmt)).scalars().all())

    # 3. Vehicle types
    vt_stmt = (
        select(VehicleType)
        .join(GarageVehicleType, GarageVehicleType.vehicle_type_id == VehicleType.id)
        .where(GarageVehicleType.garage_id == garage.id, VehicleType.is_active.is_(True))
        .order_by(VehicleType.name.asc())
    )
    vehicle_types = list((await db.execute(vt_stmt)).scalars().all())

    # 4. Photos
    photos_stmt = (
        select(GaragePhoto)
        .where(GaragePhoto.garage_id == garage.id, GaragePhoto.deleted_at.is_(None))
        .order_by(GaragePhoto.display_order.asc())
    )
    photos = list((await db.execute(photos_stmt)).scalars().all())

    # 5. Reviews summary
    rev_stmt = (
        select(
            func.round(func.avg(Review.rating), 1).label("avg_rating"),
            func.count(Review.id).label("rev_count"),
        )
        .where(
            Review.garage_id == garage.id,
            Review.deleted_at.is_(None),
            Review.status == ReviewStatus.PUBLISHED,
        )
    )
    rev_row = (await db.execute(rev_stmt)).first()
    avg_rating = float(rev_row[0]) if rev_row and rev_row[0] is not None else None
    rev_count = int(rev_row[1]) if rev_row and rev_row[1] is not None else 0

    # 6. Real-time availability
    avail_data = calculate_garage_availability(
        is_temporarily_unavailable=garage.is_temporarily_unavailable,
        temporary_unavailability_message=garage.temporary_unavailability_message,
        timezone_str=garage.timezone,
        operating_hours=hours,
    )

    return PublicGarageProfileResponse(
        id=garage.id,
        name=garage.name,
        description=garage.description,
        phone=garage.phone,
        address=garage.address,
        latitude=lat,
        longitude=lng,
        timezone=garage.timezone,
        average_rating=avg_rating,
        review_count=rev_count,
        availability=AvailabilityResponse(**avail_data),
        services=[ServiceRead.model_validate(s) for s in services],
        vehicle_types=[VehicleTypeRead.model_validate(vt) for vt in vehicle_types],
        operating_hours=[
            OperatingHourItem(
                day_of_week=h.day_of_week,
                is_closed=h.is_closed,
                opening_time=h.opening_time,
                closing_time=h.closing_time,
            )
            for h in hours
        ],
        photos=[PhotoRead.model_validate(p) for p in photos],
        created_at=garage.created_at,
    )


async def get_public_operating_hours(
    db: AsyncSession,
    garage_id: uuid.UUID,
) -> PublicOperatingHoursResponse:
    garage = await verify_public_garage(db, garage_id)
    hours_stmt = (
        select(OperatingHours)
        .where(OperatingHours.garage_id == garage.id)
        .order_by(OperatingHours.day_of_week.asc())
    )
    hours = list((await db.execute(hours_stmt)).scalars().all())
    return PublicOperatingHoursResponse(
        timezone=garage.timezone,
        hours=[
            OperatingHourItem(
                day_of_week=h.day_of_week,
                is_closed=h.is_closed,
                opening_time=h.opening_time,
                closing_time=h.closing_time,
            )
            for h in hours
        ],
    )


async def get_public_availability(
    db: AsyncSession,
    garage_id: uuid.UUID,
) -> AvailabilityResponse:
    garage = await verify_public_garage(db, garage_id)
    hours_stmt = (
        select(OperatingHours)
        .where(OperatingHours.garage_id == garage.id)
        .order_by(OperatingHours.day_of_week.asc())
    )
    hours = list((await db.execute(hours_stmt)).scalars().all())

    avail_dict = calculate_garage_availability(
        is_temporarily_unavailable=garage.is_temporarily_unavailable,
        temporary_unavailability_message=garage.temporary_unavailability_message,
        timezone_str=garage.timezone,
        operating_hours=hours,
    )
    return AvailabilityResponse(**avail_dict)


async def get_public_photos(
    db: AsyncSession,
    garage_id: uuid.UUID,
) -> list[PhotoRead]:
    garage = await verify_public_garage(db, garage_id)
    stmt = (
        select(GaragePhoto)
        .where(GaragePhoto.garage_id == garage.id, GaragePhoto.deleted_at.is_(None))
        .order_by(GaragePhoto.display_order.asc())
    )
    photos = list((await db.execute(stmt)).scalars().all())
    return [PhotoRead.model_validate(p) for p in photos]


# ── Analytics Events (PROFILE_VIEW / CALL_CLICK) ──────────────────────────────

async def record_analytics_event(
    db: AsyncSession,
    garage_id: uuid.UUID,
    event_type: AnalyticsEventType,
    customer_id: uuid.UUID | None = None,
) -> None:
    garage = await verify_public_garage(db, garage_id)

    # Simple debounce: If customer recorded same event in last 15 mins, skip duplicate
    if customer_id is not None:
        cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=15)
        check_stmt = select(AnalyticsEvent).where(
            AnalyticsEvent.garage_id == garage.id,
            AnalyticsEvent.customer_id == customer_id,
            AnalyticsEvent.event_type == event_type,
            AnalyticsEvent.created_at >= cutoff,
        )
        if (await db.execute(check_stmt)).scalar_one_or_none():
            return  # debounced

    event = AnalyticsEvent(
        garage_id=garage.id,
        customer_id=customer_id,
        event_type=event_type,
    )
    db.add(event)
    await db.flush()

