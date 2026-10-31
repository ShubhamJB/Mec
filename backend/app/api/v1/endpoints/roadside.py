"""Customer and owner roadside assistance endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_optional_user, require_customer, require_verified_owner
from app.models.enums import UserRole
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.roadside import (
    EligibleGaragesResponse,
    RoadsideLocationLabelRead,
    GuestRoadsideRequestStatusRead,
    RoadsideContactCheckCreate,
    RoadsideCapabilityRead,
    RoadsideCapabilityUpdate,
    RoadsideRequestAction,
    RoadsideRequestCreate,
    RoadsideRequestProgress,
    RoadsideRequestRead,
)
from app.services import roadside_service

customer_router = APIRouter(prefix="/roadside", tags=["roadside"])
owner_router = APIRouter(prefix="/owner/roadside", tags=["owner-roadside"])


@customer_router.get("/eligible-garages", response_model=EligibleGaragesResponse)
async def eligible_garages(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    vehicle_type_id: uuid.UUID = Query(...),
    service_id: uuid.UUID = Query(...),
    search_radius_km: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> EligibleGaragesResponse:
    return await roadside_service.eligible_garages(
        db, latitude, longitude, vehicle_type_id, service_id, search_radius_km
    )


@customer_router.get("/location-label", response_model=RoadsideLocationLabelRead)
@limiter.limit("20/minute")
async def roadside_location_label(
    request: Request,
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
) -> RoadsideLocationLabelRead:
    label = await roadside_service.resolve_location_label(latitude, longitude)
    return RoadsideLocationLabelRead(location_label=label)


@customer_router.post(
    "/requests", response_model=RoadsideRequestRead, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/hour")
async def create_request(
    request: Request,
    body: RoadsideRequestCreate,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> RoadsideRequestRead:
    if current_user is not None and current_user.role != UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Only customers can request roadside help.")
    if current_user is not None and not current_user.email_verified:
        raise HTTPException(status_code=403, detail="Verify your email or continue without signing in.")
    return await roadside_service.create_request(db, current_user, body)


@customer_router.get(
    "/requests/{request_id}/guest-status", response_model=GuestRoadsideRequestStatusRead
)
@limiter.limit("10/minute")
async def guest_request_status(
    request: Request,
    request_id: uuid.UUID,
    contact_phone: str = Query(..., min_length=9, max_length=16),
    db: AsyncSession = Depends(get_db),
) -> GuestRoadsideRequestStatusRead:
    return await roadside_service.get_guest_request_status(db, request_id, contact_phone)


@customer_router.post(
    "/requests/{request_id}/contact-check", response_model=GuestRoadsideRequestStatusRead
)
@limiter.limit("10/minute")
async def customer_contact_check(
    request: Request,
    request_id: uuid.UUID,
    body: RoadsideContactCheckCreate,
    contact_phone: str | None = Query(default=None, min_length=9, max_length=16),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> GuestRoadsideRequestStatusRead:
    if current_user is not None and current_user.role != UserRole.CUSTOMER:
        raise HTTPException(status_code=403, detail="Only customers can answer this call check.")
    return await roadside_service.record_customer_contact_check(
        db, request_id, body.garage_called, current_user, contact_phone
    )


@customer_router.get("/requests", response_model=list[RoadsideRequestRead])
async def customer_requests(
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> list[RoadsideRequestRead]:
    return await roadside_service.list_requests(db, current_user, owner=False)


@customer_router.get("/requests/{request_id}", response_model=RoadsideRequestRead)
async def customer_request_detail(
    request_id: uuid.UUID,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> RoadsideRequestRead:
    return await roadside_service.get_request(db, current_user, request_id, owner=False)


@customer_router.post("/requests/{request_id}/cancel", response_model=RoadsideRequestRead)
async def cancel_request(
    request_id: uuid.UUID,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> RoadsideRequestRead:
    return await roadside_service.cancel_request(db, current_user.id, request_id)


@owner_router.get("/capability", response_model=RoadsideCapabilityRead)
async def get_capability(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> RoadsideCapabilityRead:
    return await roadside_service.get_capability(db, current_user.id)


@owner_router.patch("/capability", response_model=RoadsideCapabilityRead)
async def patch_capability(
    body: RoadsideCapabilityUpdate,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> RoadsideCapabilityRead:
    return await roadside_service.patch_capability(db, current_user.id, body)


@owner_router.get("/requests", response_model=list[RoadsideRequestRead])
async def owner_requests(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[RoadsideRequestRead]:
    return await roadside_service.list_requests(db, current_user, owner=True)


@owner_router.get("/requests/{request_id}", response_model=RoadsideRequestRead)
async def owner_request_detail(
    request_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> RoadsideRequestRead:
    return await roadside_service.get_request(db, current_user, request_id, owner=True)


@owner_router.post("/requests/{request_id}/calling", response_model=RoadsideRequestRead)
async def owner_calling_rider(
    request_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> RoadsideRequestRead:
    return await roadside_service.owner_calling_rider(db, current_user.id, request_id)


@owner_router.post("/requests/{request_id}/accept", response_model=RoadsideRequestRead)
async def accept_request(
    request_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> RoadsideRequestRead:
    return await roadside_service.owner_action(db, current_user.id, request_id, "accept")


@owner_router.post("/requests/{request_id}/decline", response_model=RoadsideRequestRead)
async def decline_request(
    request_id: uuid.UUID,
    body: RoadsideRequestAction,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> RoadsideRequestRead:
    return await roadside_service.owner_action(
        db, current_user.id, request_id, "decline", body.reason
    )


@owner_router.patch("/requests/{request_id}", response_model=RoadsideRequestRead)
async def progress_request(
    request_id: uuid.UUID,
    body: RoadsideRequestProgress,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> RoadsideRequestRead:
    return await roadside_service.update_progress(db, current_user.id, request_id, body)
