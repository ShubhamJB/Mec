"""
Public Garage Endpoints (/garages/{garage_id}).
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_optional_user
from app.db.session import get_db
from app.models.enums import AnalyticsEventType
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.garage_profile import AvailabilityResponse
from app.schemas.photo import PhotoRead
from app.schemas.public_garage import (
    PublicGarageProfileResponse,
    PublicOperatingHoursResponse,
)
from app.services import public_garage_service

router = APIRouter()


@router.get(
    "/garages/{garage_id}",
    response_model=PublicGarageProfileResponse,
    summary="Get complete public garage profile (strict privacy: no owner email)",
)
async def get_public_garage(
    garage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PublicGarageProfileResponse:
    return await public_garage_service.get_public_garage_profile(
        db=db, garage_id=garage_id
    )


@router.get(
    "/garages/{garage_id}/operating-hours",
    response_model=PublicOperatingHoursResponse,
    summary="Get garage's 7-day operating hours and timezone",
)
async def get_public_operating_hours(
    garage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PublicOperatingHoursResponse:
    return await public_garage_service.get_public_operating_hours(
        db=db, garage_id=garage_id
    )


@router.get(
    "/garages/{garage_id}/availability",
    response_model=AvailabilityResponse,
    summary="Get garage's current real-time availability status",
)
async def get_public_availability(
    garage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AvailabilityResponse:
    return await public_garage_service.get_public_availability(
        db=db, garage_id=garage_id
    )


@router.get(
    "/garages/{garage_id}/photos",
    response_model=list[PhotoRead],
    summary="Get active photos for a publicly visible garage",
)
async def get_public_photos(
    garage_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[PhotoRead]:
    return await public_garage_service.get_public_photos(
        db=db, garage_id=garage_id
    )


@router.post(
    "/garages/{garage_id}/analytics/profile-view",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record profile view analytics event (debounced, non-blocking)",
)
async def record_profile_view(
    garage_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    customer_id = current_user.id if current_user else None
    await public_garage_service.record_analytics_event(
        db=db,
        garage_id=garage_id,
        event_type=AnalyticsEventType.PROFILE_VIEW,
        customer_id=customer_id,
    )
    return MessageResponse(message="Profile view recorded.")


@router.post(
    "/garages/{garage_id}/analytics/call-click",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Record call button click event (opens tel: immediately on frontend)",
)
async def record_call_click(
    garage_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    customer_id = current_user.id if current_user else None
    await public_garage_service.record_analytics_event(
        db=db,
        garage_id=garage_id,
        event_type=AnalyticsEventType.CALL_CLICK,
        customer_id=customer_id,
    )
    return MessageResponse(message="Call click recorded.")

