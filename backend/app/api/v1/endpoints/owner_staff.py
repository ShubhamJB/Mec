from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_verified_owner
from app.db.session import get_db
from app.models.user import User
from app.schemas.staff import StaffCreate, StaffPatch, StaffRead
from app.services import staff_service

router = APIRouter()


@router.get(
    "/staff",
    response_model=list[StaffRead],
    summary="List private staff for owner's garage",
)
async def list_staff(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[StaffRead]:
    rows = await staff_service.list_staff(db=db, owner_id=current_user.id)
    return [StaffRead.model_validate(row) for row in rows]


@router.post(
    "/staff",
    response_model=StaffRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add a staff member to owner's garage",
)
async def create_staff(
    body: StaffCreate,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> StaffRead:
    row = await staff_service.create_staff(db=db, owner_id=current_user.id, dto=body)
    return StaffRead.model_validate(row)


@router.get("/staff/{staff_id}", response_model=StaffRead, summary="Get a private staff record")
async def get_staff(
    staff_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> StaffRead:
    row = await staff_service.get_staff(db=db, owner_id=current_user.id, staff_id=staff_id)
    return StaffRead.model_validate(row)


@router.patch(
    "/staff/{staff_id}",
    response_model=StaffRead,
    summary="Update a private staff record",
)
async def update_staff(
    staff_id: uuid.UUID,
    body: StaffPatch,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> StaffRead:
    row = await staff_service.update_staff(
        db=db, owner_id=current_user.id, staff_id=staff_id, dto=body
    )
    return StaffRead.model_validate(row)


@router.delete("/staff/{staff_id}", response_model=StaffRead, summary="Deactivate a staff record")
async def delete_staff(
    staff_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> StaffRead:
    row = await staff_service.deactivate_staff(
        db=db, owner_id=current_user.id, staff_id=staff_id
    )
    return StaffRead.model_validate(row)
