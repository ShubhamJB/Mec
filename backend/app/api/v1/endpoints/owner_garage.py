"""
Endpoints for Owner Garage Profile, Availability, Hours, and Change Requests (/owner/garage).
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_verified_owner
from app.core.pagination import PaginatedResponse
from app.db.session import get_db
from app.models.user import User
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
from app.services import garage_profile_service

router = APIRouter()


# ── Garage Profile (Minor edits & Full view) ─────────────────────────────────

@router.get(
    "/garage",
    response_model=OwnerGarageProfileResponse,
    summary="Get owner's garage profile (catalogs, schedule, real-time availability, coords)",
)
async def get_owner_garage(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> OwnerGarageProfileResponse:
    return await garage_profile_service.get_owner_garage_full(
        db=db, owner_id=current_user.id
    )


@router.patch(
    "/garage",
    response_model=OwnerGarageProfileResponse,
    summary="Update minor profile fields immediately (phone and description only)",
)
async def patch_owner_garage(
    body: PatchOwnerGarageMinor,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> OwnerGarageProfileResponse:
    return await garage_profile_service.patch_owner_garage_minor(
        db=db, owner_id=current_user.id, dto=body
    )


# ── Critical Profile Change Requests ─────────────────────────────────────────

@router.post(
    "/garage/profile-change-requests",
    response_model=ProfileChangeRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a critical profile change request (name, address, coordinates; max 1 pending)",
)
async def create_profile_change_request(
    body: CreateProfileChangeRequest,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> ProfileChangeRequestResponse:
    return await garage_profile_service.submit_profile_change_request(
        db=db, owner_id=current_user.id, dto=body
    )


@router.get(
    "/garage/profile-change-requests",
    response_model=PaginatedResponse[ProfileChangeRequestResponse],
    summary="List owner's profile change requests",
)
async def list_profile_change_requests(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[ProfileChangeRequestResponse]:
    items, total = await garage_profile_service.list_profile_change_requests(
        db=db, owner_id=current_user.id, page=page, limit=limit
    )
    return PaginatedResponse.build(
        items=[ProfileChangeRequestResponse.model_validate(i) for i in items],
        total_items=total,
        page=page,
        limit=limit,
    )


@router.get(
    "/garage/profile-change-requests/{request_id}",
    response_model=ProfileChangeRequestResponse,
    summary="Get detail of a specific profile change request",
)
async def get_profile_change_request(
    request_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> ProfileChangeRequestResponse:
    return await garage_profile_service.get_profile_change_request_detail(
        db=db, owner_id=current_user.id, request_id=request_id
    )


# ── Operating Hours ───────────────────────────────────────────────────────────

@router.get(
    "/garage/operating-hours",
    response_model=list[OperatingHourItem],
    summary="Get owner garage's 7-day schedule",
)
async def get_owner_operating_hours(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[OperatingHourItem]:
    return await garage_profile_service.get_owner_operating_hours(
        db=db, owner_id=current_user.id
    )


@router.put(
    "/garage/operating-hours",
    response_model=list[OperatingHourItem],
    summary="Replace owner garage's 7-day operating schedule",
)
async def replace_owner_operating_hours(
    body: PutOperatingHoursRequest,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[OperatingHourItem]:
    return await garage_profile_service.replace_owner_operating_hours(
        db=db, owner_id=current_user.id, dto=body
    )


# ── Real-time Availability ────────────────────────────────────────────────────

@router.get(
    "/garage/availability",
    response_model=AvailabilityResponse,
    summary="Get owner garage's real-time availability status",
)
async def get_owner_availability(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityResponse:
    return await garage_profile_service.get_owner_availability(
        db=db, owner_id=current_user.id
    )


@router.patch(
    "/garage/availability",
    response_model=AvailabilityResponse,
    summary="Toggle temporary unavailability override and optional message",
)
async def patch_owner_availability(
    body: PatchAvailabilityRequest,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> AvailabilityResponse:
    return await garage_profile_service.patch_owner_availability(
        db=db, owner_id=current_user.id, dto=body
    )

