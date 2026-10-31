from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.garage import Garage
from app.models.staff import GarageStaff
from app.schemas.staff import StaffCreate, StaffPatch


async def _get_owner_garage(db: AsyncSession, owner_id: uuid.UUID) -> Garage:
    result = await db.execute(
        select(Garage).where(Garage.owner_id == owner_id, Garage.deleted_at.is_(None))
    )
    garage = result.scalar_one_or_none()
    if garage is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered garage found.",
        )
    return garage


async def list_staff(db: AsyncSession, owner_id: uuid.UUID) -> list[GarageStaff]:
    garage = await _get_owner_garage(db, owner_id)
    result = await db.execute(
        select(GarageStaff)
        .where(GarageStaff.garage_id == garage.id)
        .order_by(GarageStaff.is_active.desc(), GarageStaff.full_name.asc(), GarageStaff.id)
    )
    return list(result.scalars().all())


async def _get_staff(db: AsyncSession, owner_id: uuid.UUID, staff_id: uuid.UUID) -> GarageStaff:
    garage = await _get_owner_garage(db, owner_id)
    result = await db.execute(
        select(GarageStaff).where(
            GarageStaff.id == staff_id,
            GarageStaff.garage_id == garage.id,
        )
    )
    staff = result.scalar_one_or_none()
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found.")
    return staff


async def create_staff(
    db: AsyncSession, owner_id: uuid.UUID, dto: StaffCreate
) -> GarageStaff:
    garage = await _get_owner_garage(db, owner_id)
    staff = GarageStaff(
        garage_id=garage.id,
        full_name=dto.full_name,
        phone=dto.phone,
        role_title=dto.role_title,
        is_active=True,
    )
    db.add(staff)
    await db.flush()
    return staff


async def get_staff(
    db: AsyncSession, owner_id: uuid.UUID, staff_id: uuid.UUID
) -> GarageStaff:
    return await _get_staff(db, owner_id, staff_id)


async def update_staff(
    db: AsyncSession, owner_id: uuid.UUID, staff_id: uuid.UUID, dto: StaffPatch
) -> GarageStaff:
    staff = await _get_staff(db, owner_id, staff_id)
    for field, value in dto.model_dump(exclude_unset=True).items():
        setattr(staff, field, value)
    await db.flush()
    await db.refresh(staff)
    return staff


async def deactivate_staff(
    db: AsyncSession, owner_id: uuid.UUID, staff_id: uuid.UUID
) -> GarageStaff:
    staff = await _get_staff(db, owner_id, staff_id)
    staff.is_active = False
    await db.flush()
    await db.refresh(staff)
    return staff
