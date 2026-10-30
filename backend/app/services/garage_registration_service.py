"""
Service layer for Garage Registration and Pending Edits.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import (
    GarageService,
    GarageVehicleType,
    OperatingHours,
    Service,
    VehicleType,
)
from app.models.enums import ApprovalStatus, RegistrationHistoryStatus
from app.models.garage import Garage, GarageRegistrationHistory
from app.schemas.garage_registration import (
    GarageRegistrationCreate,
    GarageRegistrationPatch,
    GarageRegistrationStatusResponse,
    LatestDecisionBrief,
)
from app.utils.geo import derive_timezone, point_from_coords


async def get_owner_garage(db: AsyncSession, owner_id: uuid.UUID) -> Garage:
    stmt = select(Garage).where(Garage.owner_id == owner_id, Garage.deleted_at.is_(None))
    result = await db.execute(stmt)
    garage = result.scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registration found for this garage owner.",
        )
    return garage


async def _resolve_services(
    db: AsyncSession,
    service_ids: list[uuid.UUID],
    custom_services: list[str],
    user_id: uuid.UUID,
) -> list[Service]:
    resolved: list[Service] = []

    # 1. Existing service IDs
    if service_ids:
        stmt = select(Service).where(Service.id.in_(service_ids), Service.is_active.is_(True))
        found = list((await db.execute(stmt)).scalars().all())
        found_ids = {s.id for s in found}
        missing = [str(sid) for sid in service_ids if sid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"The following service IDs are invalid or inactive: {', '.join(missing)}",
            )
        resolved.extend(found)

    # 2. Custom services
    for name in custom_services:
        norm_name = " ".join(name.strip().split())
        stmt = select(Service).where(func.lower(func.trim(Service.name)) == norm_name.lower())
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            if existing.is_active and existing not in resolved:
                resolved.append(existing)
        else:
            new_service = Service(
                name=norm_name,
                is_predefined=False,
                created_by_user_id=user_id,
                is_active=True,
            )
            db.add(new_service)
            await db.flush()
            resolved.append(new_service)

    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one active service is required.",
        )
    return resolved


async def _resolve_vehicle_types(
    db: AsyncSession,
    vehicle_type_ids: list[uuid.UUID],
    custom_vehicle_types: list[str],
    user_id: uuid.UUID,
) -> list[VehicleType]:
    resolved: list[VehicleType] = []

    if vehicle_type_ids:
        stmt = select(VehicleType).where(
            VehicleType.id.in_(vehicle_type_ids), VehicleType.is_active.is_(True)
        )
        found = list((await db.execute(stmt)).scalars().all())
        found_ids = {vt.id for vt in found}
        missing = [str(vid) for vid in vehicle_type_ids if vid not in found_ids]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"The following vehicle type IDs are invalid or inactive: {', '.join(missing)}",
            )
        resolved.extend(found)

    for name in custom_vehicle_types:
        norm_name = " ".join(name.strip().split())
        stmt = select(VehicleType).where(func.lower(func.trim(VehicleType.name)) == norm_name.lower())
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            if existing.is_active and existing not in resolved:
                resolved.append(existing)
        else:
            new_vt = VehicleType(
                name=norm_name,
                is_predefined=False,
                created_by_user_id=user_id,
                is_active=True,
            )
            db.add(new_vt)
            await db.flush()
            resolved.append(new_vt)

    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one active vehicle type is required.",
        )
    return resolved


# ── Registration Submission ───────────────────────────────────────────────────

async def submit_garage_registration(
    db: AsyncSession,
    owner_id: uuid.UUID,
    dto: GarageRegistrationCreate,
) -> GarageRegistrationStatusResponse:
    # 1. Enforce: One non-deleted garage per owner
    existing_stmt = select(Garage).where(Garage.owner_id == owner_id, Garage.deleted_at.is_(None))
    if (await db.execute(existing_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have an active or pending garage registered.",
        )

    # 2. Resolve catalogs
    services = await _resolve_services(db, dto.service_ids, dto.custom_services, owner_id)
    vehicle_types = await _resolve_vehicle_types(
        db, dto.vehicle_type_ids, dto.custom_vehicle_types, owner_id
    )

    # 3. Derive timezone and PostGIS point
    tz = derive_timezone(dto.latitude, dto.longitude)
    location_point = point_from_coords(dto.latitude, dto.longitude)

    # 4. Create Garage
    garage = Garage(
        owner_id=owner_id,
        name=dto.name,
        description=dto.description,
        phone=dto.phone,
        address=dto.address,
        location=location_point,
        timezone=tz,
        approval_status=ApprovalStatus.PENDING,
        is_suspended=False,
        is_temporarily_unavailable=False,
        registration_version=1,
    )
    db.add(garage)
    await db.flush()

    # 5. Operating hours
    for item in dto.operating_hours:
        db.add(
            OperatingHours(
                garage_id=garage.id,
                day_of_week=item.day_of_week,
                is_closed=item.is_closed,
                opening_time=item.opening_time,
                closing_time=item.closing_time,
            )
        )

    # 6. Associations
    for s in services:
        db.add(GarageService(garage_id=garage.id, service_id=s.id))
    for vt in vehicle_types:
        db.add(GarageVehicleType(garage_id=garage.id, vehicle_type_id=vt.id))

    # 7. Immutable history snapshot
    now = datetime.now(tz=timezone.utc)
    snapshot = {
        "name": dto.name,
        "description": dto.description,
        "phone": dto.phone,
        "address": dto.address,
        "latitude": dto.latitude,
        "longitude": dto.longitude,
        "timezone": tz,
        "services": [{"id": str(s.id), "name": s.name} for s in services],
        "vehicle_types": [{"id": str(vt.id), "name": vt.name} for vt in vehicle_types],
        "operating_hours": [item.model_dump(mode="json") for item in dto.operating_hours],
    }

    history = GarageRegistrationHistory(
        garage_id=garage.id,
        reviewed_by=None,
        status=RegistrationHistoryStatus.PENDING,
        submission_data=snapshot,
        rejection_reason=None,
        submitted_at=now,
    )
    db.add(history)
    await db.flush()

    return GarageRegistrationStatusResponse(
        garage_id=garage.id,
        approval_status=garage.approval_status,
        registration_version=garage.registration_version,
        submitted_at=history.submitted_at,
        latest_decision=None,
    )


# ── Registration Status & History ─────────────────────────────────────────────

async def get_registration_status(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> GarageRegistrationStatusResponse:
    garage = await get_owner_garage(db, owner_id)

    # Fetch latest history item
    stmt = (
        select(GarageRegistrationHistory)
        .where(GarageRegistrationHistory.garage_id == garage.id)
        .order_by(GarageRegistrationHistory.submitted_at.desc())
    )
    latest_hist = (await db.execute(stmt)).scalars().first()

    latest_decision = None
    submitted_at = garage.created_at
    if latest_hist:
        submitted_at = latest_hist.submitted_at
        if latest_hist.status in (RegistrationHistoryStatus.APPROVED, RegistrationHistoryStatus.REJECTED):
            latest_decision = LatestDecisionBrief(
                status=latest_hist.status,
                rejection_reason=latest_hist.rejection_reason,
                reviewed_at=latest_hist.reviewed_at,
            )

    return GarageRegistrationStatusResponse(
        garage_id=garage.id,
        approval_status=garage.approval_status,
        registration_version=garage.registration_version,
        submitted_at=submitted_at,
        latest_decision=latest_decision,
    )


async def get_registration_history(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[GarageRegistrationHistory]:
    garage = await get_owner_garage(db, owner_id)
    stmt = (
        select(GarageRegistrationHistory)
        .where(GarageRegistrationHistory.garage_id == garage.id)
        .order_by(GarageRegistrationHistory.submitted_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Resubmission (Only for REJECTED garages) ───────────────────────────────────

async def resubmit_garage_registration(
    db: AsyncSession,
    owner_id: uuid.UUID,
    dto: GarageRegistrationCreate,
) -> GarageRegistrationStatusResponse:
    garage = await get_owner_garage(db, owner_id)

    if garage.approval_status != ApprovalStatus.REJECTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Registration resubmission is only allowed for REJECTED garages. Current status: {garage.approval_status}.",
        )

    services = await _resolve_services(db, dto.service_ids, dto.custom_services, owner_id)
    vehicle_types = await _resolve_vehicle_types(
        db, dto.vehicle_type_ids, dto.custom_vehicle_types, owner_id
    )

    tz = derive_timezone(dto.latitude, dto.longitude)
    location_point = point_from_coords(dto.latitude, dto.longitude)

    # Update garage fields
    garage.name = dto.name
    garage.description = dto.description
    garage.phone = dto.phone
    garage.address = dto.address
    garage.location = location_point
    garage.timezone = tz
    garage.approval_status = ApprovalStatus.PENDING
    garage.registration_version += 1

    # Replace operating hours
    await db.execute(delete(OperatingHours).where(OperatingHours.garage_id == garage.id))
    for item in dto.operating_hours:
        db.add(
            OperatingHours(
                garage_id=garage.id,
                day_of_week=item.day_of_week,
                is_closed=item.is_closed,
                opening_time=item.opening_time,
                closing_time=item.closing_time,
            )
        )

    # Replace associations
    await db.execute(delete(GarageService).where(GarageService.garage_id == garage.id))
    for s in services:
        db.add(GarageService(garage_id=garage.id, service_id=s.id))

    await db.execute(delete(GarageVehicleType).where(GarageVehicleType.garage_id == garage.id))
    for vt in vehicle_types:
        db.add(GarageVehicleType(garage_id=garage.id, vehicle_type_id=vt.id))

    # Add new immutable history snapshot
    now = datetime.now(tz=timezone.utc)
    snapshot = {
        "name": dto.name,
        "description": dto.description,
        "phone": dto.phone,
        "address": dto.address,
        "latitude": dto.latitude,
        "longitude": dto.longitude,
        "timezone": tz,
        "services": [{"id": str(s.id), "name": s.name} for s in services],
        "vehicle_types": [{"id": str(vt.id), "name": vt.name} for vt in vehicle_types],
        "operating_hours": [item.model_dump(mode="json") for item in dto.operating_hours],
    }

    history = GarageRegistrationHistory(
        garage_id=garage.id,
        reviewed_by=None,
        status=RegistrationHistoryStatus.PENDING,
        submission_data=snapshot,
        rejection_reason=None,
        submitted_at=now,
    )
    db.add(history)
    await db.flush()

    return GarageRegistrationStatusResponse(
        garage_id=garage.id,
        approval_status=garage.approval_status,
        registration_version=garage.registration_version,
        submitted_at=history.submitted_at,
        latest_decision=None,
    )


# ── Pending Edits (Only for PENDING garages) ───────────────────────────────────

async def patch_pending_registration(
    db: AsyncSession,
    owner_id: uuid.UUID,
    dto: GarageRegistrationPatch,
) -> GarageRegistrationStatusResponse:
    garage = await get_owner_garage(db, owner_id)

    if garage.approval_status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Registration edits are only permitted while status is PENDING. Current status: {garage.approval_status}.",
        )

    if dto.expected_version != garage.registration_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Version mismatch. Expected version {dto.expected_version}, but current version is {garage.registration_version}.",
        )

    # Update editable fields
    if dto.name is not None:
        garage.name = dto.name
    if dto.description is not None:
        garage.description = dto.description
    if dto.phone is not None:
        garage.phone = dto.phone
    if dto.address is not None:
        garage.address = dto.address
    if dto.latitude is not None and dto.longitude is not None:
        garage.location = point_from_coords(dto.latitude, dto.longitude)
        garage.timezone = derive_timezone(dto.latitude, dto.longitude)

    if dto.operating_hours is not None:
        await db.execute(delete(OperatingHours).where(OperatingHours.garage_id == garage.id))
        for item in dto.operating_hours:
            db.add(
                OperatingHours(
                    garage_id=garage.id,
                    day_of_week=item.day_of_week,
                    is_closed=item.is_closed,
                    opening_time=item.opening_time,
                    closing_time=item.closing_time,
                )
            )

    if dto.service_ids is not None:
        services = await _resolve_services(db, dto.service_ids, [], owner_id)
        await db.execute(delete(GarageService).where(GarageService.garage_id == garage.id))
        for s in services:
            db.add(GarageService(garage_id=garage.id, service_id=s.id))

    if dto.vehicle_type_ids is not None:
        vehicle_types = await _resolve_vehicle_types(db, dto.vehicle_type_ids, [], owner_id)
        await db.execute(delete(GarageVehicleType).where(GarageVehicleType.garage_id == garage.id))
        for vt in vehicle_types:
            db.add(GarageVehicleType(garage_id=garage.id, vehicle_type_id=vt.id))

    # Increment version
    garage.registration_version += 1
    await db.flush()

    return await get_registration_status(db, owner_id)

