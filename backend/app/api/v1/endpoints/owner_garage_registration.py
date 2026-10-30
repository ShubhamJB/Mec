"""
Endpoints for Garage Registration by verified owners (/owner/garage-registration).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_verified_owner
from app.db.session import get_db
from app.models.user import User
from app.schemas.garage_registration import (
    GarageRegistrationCreate,
    GarageRegistrationHistoryItem,
    GarageRegistrationPatch,
    GarageRegistrationStatusResponse,
)
from app.services import garage_registration_service

router = APIRouter()


@router.post(
    "/garage-registration",
    response_model=GarageRegistrationStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new garage registration (one non-deleted garage per owner)",
)
async def create_garage_registration(
    body: GarageRegistrationCreate,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> GarageRegistrationStatusResponse:
    return await garage_registration_service.submit_garage_registration(
        db=db, owner_id=current_user.id, dto=body
    )


@router.get(
    "/garage-registration",
    response_model=GarageRegistrationStatusResponse,
    summary="Get current garage registration status and latest decision",
)
async def get_garage_registration(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> GarageRegistrationStatusResponse:
    return await garage_registration_service.get_registration_status(
        db=db, owner_id=current_user.id
    )


@router.get(
    "/garage-registration/history",
    response_model=list[GarageRegistrationHistoryItem],
    summary="Get all submission history snapshots and admin decisions",
)
async def get_garage_registration_history(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[GarageRegistrationHistoryItem]:
    history = await garage_registration_service.get_registration_history(
        db=db, owner_id=current_user.id
    )
    return [GarageRegistrationHistoryItem.model_validate(h) for h in history]


@router.put(
    "/garage-registration",
    response_model=GarageRegistrationStatusResponse,
    summary="Resubmit a REJECTED garage registration (creates new snapshot & resets to PENDING)",
)
async def resubmit_garage_registration(
    body: GarageRegistrationCreate,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> GarageRegistrationStatusResponse:
    return await garage_registration_service.resubmit_garage_registration(
        db=db, owner_id=current_user.id, dto=body
    )


@router.patch(
    "/garage-registration",
    response_model=GarageRegistrationStatusResponse,
    summary="Edit editable fields of a PENDING registration (optimistic lock with expected_version)",
)
async def patch_pending_garage_registration(
    body: GarageRegistrationPatch,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> GarageRegistrationStatusResponse:
    return await garage_registration_service.patch_pending_registration(
        db=db, owner_id=current_user.id, dto=body
    )

