"""
Service layer for Services and Vehicle Types catalogs.
"""
from __future__ import annotations

import uuid
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.catalog import GarageService, GarageVehicleType, Service, VehicleType
from app.models.garage import Garage
from app.models.user import User
from app.models.enums import AccountStatus, ApprovalStatus


# ── Shared helper: get active garage for owner ───────────────────────────────

async def get_owner_garage(db: AsyncSession, owner_id: uuid.UUID) -> Garage:
    stmt = (
        select(Garage)
        .where(
            Garage.owner_id == owner_id,
            Garage.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    garage = result.scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered garage found for this owner.",
        )
    return garage


async def verify_public_garage(db: AsyncSession, garage_id: uuid.UUID) -> Garage:
    """
    Public eligibility rule:
    Approved AND not garage-suspended AND not deleted AND owner ACTIVE.
    """
    stmt = (
        select(Garage)
        .join(User, Garage.owner_id == User.id)
        .where(
            Garage.id == garage_id,
            Garage.deleted_at.is_(None),
            Garage.approval_status == ApprovalStatus.APPROVED,
            Garage.is_suspended.is_(False),
            User.account_status == AccountStatus.ACTIVE,
            User.deleted_at.is_(None),
        )
    )
    result = await db.execute(stmt)
    garage = result.scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garage not found or not publicly visible.",
        )
    return garage


# ── Services ──────────────────────────────────────────────────────────────────

async def list_services(
    db: AsyncSession,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[Service], int]:
    base_query = select(Service).where(Service.is_active.is_(True))
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base_query = base_query.where(func.lower(Service.name).like(term))

    # Count
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_count = (await db.execute(count_stmt)).scalar_one()

    # Paginate
    stmt = base_query.order_by(Service.name.asc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return items, total_count


async def create_custom_service(
    db: AsyncSession,
    name: str,
    user_id: uuid.UUID,
) -> Service:
    # Check normalized case-insensitive uniqueness against predefined/custom
    stmt = select(Service).where(func.lower(func.trim(Service.name)) == name.lower())
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A service with name '{name}' already exists in catalog.",
        )

    service = Service(
        name=name,
        is_predefined=False,
        created_by_user_id=user_id,
        is_active=True,
    )
    db.add(service)
    await db.flush()
    return service


async def get_garage_services(db: AsyncSession, garage_id: uuid.UUID) -> list[Service]:
    await verify_public_garage(db, garage_id)
    stmt = (
        select(Service)
        .join(GarageService, GarageService.service_id == Service.id)
        .where(
            GarageService.garage_id == garage_id,
            Service.is_active.is_(True),
        )
        .order_by(Service.name.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_owner_garage_services(
    db: AsyncSession,
    owner_id: uuid.UUID,
    service_ids: list[uuid.UUID],
) -> list[Service]:
    garage = await get_owner_garage(db, owner_id)

    # Verify all service_ids exist and are active
    stmt = select(Service).where(
        Service.id.in_(service_ids),
        Service.is_active.is_(True),
    )
    active_services = list((await db.execute(stmt)).scalars().all())
    active_ids = {s.id for s in active_services}

    invalid_ids = [str(sid) for sid in service_ids if sid not in active_ids]
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"The following service IDs are invalid or inactive: {', '.join(invalid_ids)}",
        )

    # Replace existing associations
    await db.execute(delete(GarageService).where(GarageService.garage_id == garage.id))
    for sid in active_ids:
        db.add(GarageService(garage_id=garage.id, service_id=sid))
    await db.flush()

    return active_services


async def remove_owner_garage_service(
    db: AsyncSession,
    owner_id: uuid.UUID,
    service_id: uuid.UUID,
) -> None:
    garage = await get_owner_garage(db, owner_id)

    # Check if association exists
    assoc_stmt = select(GarageService).where(
        GarageService.garage_id == garage.id,
        GarageService.service_id == service_id,
    )
    assoc = (await db.execute(assoc_stmt)).scalar_one_or_none()
    if not assoc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not associated with this garage.",
        )

    # If garage is APPROVED, cannot remove final active service
    if garage.approval_status == ApprovalStatus.APPROVED:
        count_stmt = (
            select(func.count(GarageService.service_id))
            .join(Service, GarageService.service_id == Service.id)
            .where(
                GarageService.garage_id == garage.id,
                Service.is_active.is_(True),
            )
        )
        active_count = (await db.execute(count_stmt)).scalar_one()
        if active_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the final active service from an approved garage.",
            )

    await db.delete(assoc)
    await db.flush()


# ── Vehicle Types ─────────────────────────────────────────────────────────────

async def list_vehicle_types(
    db: AsyncSession,
    search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> tuple[list[VehicleType], int]:
    base_query = select(VehicleType).where(VehicleType.is_active.is_(True))
    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        base_query = base_query.where(func.lower(VehicleType.name).like(term))

    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_count = (await db.execute(count_stmt)).scalar_one()

    stmt = base_query.order_by(VehicleType.name.asc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    items = list(result.scalars().all())
    return items, total_count


async def create_custom_vehicle_type(
    db: AsyncSession,
    name: str,
    user_id: uuid.UUID,
) -> VehicleType:
    stmt = select(VehicleType).where(func.lower(func.trim(VehicleType.name)) == name.lower())
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A vehicle type with name '{name}' already exists in catalog.",
        )

    vehicle_type = VehicleType(
        name=name,
        is_predefined=False,
        created_by_user_id=user_id,
        is_active=True,
    )
    db.add(vehicle_type)
    await db.flush()
    return vehicle_type


async def get_garage_vehicle_types(db: AsyncSession, garage_id: uuid.UUID) -> list[VehicleType]:
    await verify_public_garage(db, garage_id)
    stmt = (
        select(VehicleType)
        .join(GarageVehicleType, GarageVehicleType.vehicle_type_id == VehicleType.id)
        .where(
            GarageVehicleType.garage_id == garage_id,
            VehicleType.is_active.is_(True),
        )
        .order_by(VehicleType.name.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_owner_garage_vehicle_types(
    db: AsyncSession,
    owner_id: uuid.UUID,
    vehicle_type_ids: list[uuid.UUID],
) -> list[VehicleType]:
    garage = await get_owner_garage(db, owner_id)

    stmt = select(VehicleType).where(
        VehicleType.id.in_(vehicle_type_ids),
        VehicleType.is_active.is_(True),
    )
    active_types = list((await db.execute(stmt)).scalars().all())
    active_ids = {vt.id for vt in active_types}

    invalid_ids = [str(vid) for vid in vehicle_type_ids if vid not in active_ids]
    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"The following vehicle type IDs are invalid or inactive: {', '.join(invalid_ids)}",
        )

    await db.execute(delete(GarageVehicleType).where(GarageVehicleType.garage_id == garage.id))
    for vid in active_ids:
        db.add(GarageVehicleType(garage_id=garage.id, vehicle_type_id=vid))
    await db.flush()

    return active_types


async def remove_owner_garage_vehicle_type(
    db: AsyncSession,
    owner_id: uuid.UUID,
    vehicle_type_id: uuid.UUID,
) -> None:
    garage = await get_owner_garage(db, owner_id)

    assoc_stmt = select(GarageVehicleType).where(
        GarageVehicleType.garage_id == garage.id,
        GarageVehicleType.vehicle_type_id == vehicle_type_id,
    )
    assoc = (await db.execute(assoc_stmt)).scalar_one_or_none()
    if not assoc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vehicle type not associated with this garage.",
        )

    if garage.approval_status == ApprovalStatus.APPROVED:
        count_stmt = (
            select(func.count(GarageVehicleType.vehicle_type_id))
            .join(VehicleType, GarageVehicleType.vehicle_type_id == VehicleType.id)
            .where(
                GarageVehicleType.garage_id == garage.id,
                VehicleType.is_active.is_(True),
            )
        )
        active_count = (await db.execute(count_stmt)).scalar_one()
        if active_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove the final active vehicle type from an approved garage.",
            )

    await db.delete(assoc)
    await db.flush()

