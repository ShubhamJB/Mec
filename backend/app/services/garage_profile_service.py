"""
Service layer for Owner Garage Profile, Operating Hours, Availability, and Change Requests.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_X, ST_Y

from app.models.catalog import (
    GarageService,
    GarageVehicleType,
    OperatingHours,
    Service,
    VehicleType,
)
from app.models.garage import Garage, GarageProfileChangeRequest
from app.schemas.catalog import ServiceRead, VehicleTypeRead
from app.schemas.garage_profile import (
    AvailabilityResponse,
    CreateProfileChangeRequest,
    OwnerGarageProfileResponse,
    PatchAvailabilityRequest,
    PatchOwnerGarageMinor,
    ProfileChangeRequestResponse,
    PutOperatingHoursRequest,
)
from app.schemas.garage_registration import OperatingHourItem
from app.utils.availability import calculate_garage_availability


async def _get_owner_garage(db: AsyncSession, owner_id: uuid.UUID) -> Garage:
    stmt = select(Garage).where(Garage.owner_id == owner_id, Garage.deleted_at.is_(None))
    result = await db.execute(stmt)
    garage = result.scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered garage found for this owner.",
        )
    return garage


async def _get_garage_coordinates(db: AsyncSession, garage_id: uuid.UUID) -> tuple[float, float]:
    """Extract (latitude, longitude) from PostGIS geography point."""
    stmt = select(
        ST_Y(Garage.location.cast(Geometry)),
        ST_X(Garage.location.cast(Geometry)),
    ).where(Garage.id == garage_id)
    row = (await db.execute(stmt)).first()
    if row and row[0] is not None and row[1] is not None:
        return float(row[0]), float(row[1])
    return 0.0, 0.0


async def get_owner_garage_full(db: AsyncSession, owner_id: uuid.UUID) -> OwnerGarageProfileResponse:
    garage = await _get_owner_garage(db, owner_id)
    lat, lng = await _get_garage_coordinates(db, garage.id)

    # Operating hours
    hours_stmt = (
        select(OperatingHours)
        .where(OperatingHours.garage_id == garage.id)
        .order_by(OperatingHours.day_of_week.asc())
    )
    hours = list((await db.execute(hours_stmt)).scalars().all())

    # Services
    services_stmt = (
        select(Service)
        .join(GarageService, GarageService.service_id == Service.id)
        .where(GarageService.garage_id == garage.id, Service.is_active.is_(True))
        .order_by(Service.name.asc())
    )
    services = list((await db.execute(services_stmt)).scalars().all())

    # Vehicle types
    vt_stmt = (
        select(VehicleType)
        .join(GarageVehicleType, GarageVehicleType.vehicle_type_id == VehicleType.id)
        .where(GarageVehicleType.garage_id == garage.id, VehicleType.is_active.is_(True))
        .order_by(VehicleType.name.asc())
    )
    vehicle_types = list((await db.execute(vt_stmt)).scalars().all())

    # Availability
    avail_data = calculate_garage_availability(
        is_temporarily_unavailable=garage.is_temporarily_unavailable,
        temporary_unavailability_message=garage.temporary_unavailability_message,
        timezone_str=garage.timezone,
        operating_hours=hours,
    )

    return OwnerGarageProfileResponse(
        id=garage.id,
        name=garage.name,
        description=garage.description,
        phone=garage.phone,
        address=garage.address,
        latitude=lat,
        longitude=lng,
        timezone=garage.timezone,
        approval_status=garage.approval_status.value,
        is_suspended=garage.is_suspended,
        registration_version=garage.registration_version,
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
    )


async def patch_owner_garage_minor(
    db: AsyncSession,
    owner_id: uuid.UUID,
    dto: PatchOwnerGarageMinor,
) -> OwnerGarageProfileResponse:
    garage = await _get_owner_garage(db, owner_id)
    if dto.phone is not None:
        garage.phone = dto.phone
    if dto.description is not None:
        garage.description = dto.description
    await db.flush()
    return await get_owner_garage_full(db, owner_id)


# ── Critical Profile Change Requests ─────────────────────────────────────────

async def submit_profile_change_request(
    db: AsyncSession,
    owner_id: uuid.UUID,
    dto: CreateProfileChangeRequest,
) -> ProfileChangeRequestResponse:
    garage = await _get_owner_garage(db, owner_id)

    # 1. Enforce only one PENDING change request per garage
    pending_stmt = select(GarageProfileChangeRequest).where(
        GarageProfileChangeRequest.garage_id == garage.id,
        GarageProfileChangeRequest.status == "PENDING",
    )
    if (await db.execute(pending_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is already a pending profile change request for this garage. Please wait for admin review.",
        )

    # 2. Extract current coordinates for no-op check
    curr_lat, curr_lng = await _get_garage_coordinates(db, garage.id)

    proposed: dict[str, Any] = {}
    if dto.name and dto.name != garage.name:
        proposed["name"] = dto.name
    if dto.address and dto.address != garage.address:
        proposed["address"] = dto.address
    if dto.latitude is not None and dto.longitude is not None:
        if abs(dto.latitude - curr_lat) > 1e-6 or abs(dto.longitude - curr_lng) > 1e-6:
            proposed["latitude"] = dto.latitude
            proposed["longitude"] = dto.longitude

    if not proposed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Proposed changes are identical to the current garage profile (no-op).",
        )

    req = GarageProfileChangeRequest(
        garage_id=garage.id,
        submitted_by=owner_id,
        proposed_changes=proposed,
        status="PENDING",
    )
    db.add(req)
    await db.flush()

    return ProfileChangeRequestResponse.model_validate(req)


async def list_profile_change_requests(
    db: AsyncSession,
    owner_id: uuid.UUID,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[GarageProfileChangeRequest], int]:
    garage = await _get_owner_garage(db, owner_id)

    base_query = select(GarageProfileChangeRequest).where(
        GarageProfileChangeRequest.garage_id == garage.id
    )
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = (
        base_query.order_by(GarageProfileChangeRequest.submitted_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_profile_change_request_detail(
    db: AsyncSession,
    owner_id: uuid.UUID,
    request_id: uuid.UUID,
) -> ProfileChangeRequestResponse:
    garage = await _get_owner_garage(db, owner_id)
    stmt = select(GarageProfileChangeRequest).where(
        GarageProfileChangeRequest.id == request_id,
        GarageProfileChangeRequest.garage_id == garage.id,
    )
    req = (await db.execute(stmt)).scalar_one_or_none()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile change request not found.",
        )
    return ProfileChangeRequestResponse.model_validate(req)


# ── Operating Hours ───────────────────────────────────────────────────────────

async def get_owner_operating_hours(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[OperatingHourItem]:
    garage = await _get_owner_garage(db, owner_id)
    stmt = (
        select(OperatingHours)
        .where(OperatingHours.garage_id == garage.id)
        .order_by(OperatingHours.day_of_week.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return [
        OperatingHourItem(
            day_of_week=r.day_of_week,
            is_closed=r.is_closed,
            opening_time=r.opening_time,
            closing_time=r.closing_time,
        )
        for r in rows
    ]


async def replace_owner_operating_hours(
    db: AsyncSession,
    owner_id: uuid.UUID,
    dto: PutOperatingHoursRequest,
) -> list[OperatingHourItem]:
    garage = await _get_owner_garage(db, owner_id)

    # Delete existing 7 records and re-create
    await db.execute(delete(OperatingHours).where(OperatingHours.garage_id == garage.id))
    for item in dto.hours:
        db.add(
            OperatingHours(
                garage_id=garage.id,
                day_of_week=item.day_of_week,
                is_closed=item.is_closed,
                opening_time=item.opening_time,
                closing_time=item.closing_time,
            )
        )
    await db.flush()
    return await get_owner_operating_hours(db, owner_id)


# ── Availability ──────────────────────────────────────────────────────────────

async def get_owner_availability(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> AvailabilityResponse:
    garage = await _get_owner_garage(db, owner_id)
    stmt = (
        select(OperatingHours)
        .where(OperatingHours.garage_id == garage.id)
        .order_by(OperatingHours.day_of_week.asc())
    )
    hours = list((await db.execute(stmt)).scalars().all())

    data = calculate_garage_availability(
        is_temporarily_unavailable=garage.is_temporarily_unavailable,
        temporary_unavailability_message=garage.temporary_unavailability_message,
        timezone_str=garage.timezone,
        operating_hours=hours,
    )
    return AvailabilityResponse(**data)


async def patch_owner_availability(
    db: AsyncSession,
    owner_id: uuid.UUID,
    dto: PatchAvailabilityRequest,
) -> AvailabilityResponse:
    garage = await _get_owner_garage(db, owner_id)
    garage.is_temporarily_unavailable = dto.is_temporarily_unavailable
    garage.temporary_unavailability_message = dto.message  # null when unavailable is False
    await db.flush()
    return await get_owner_availability(db, owner_id)

