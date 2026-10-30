"""
Customer Reviews and Reports Endpoints (/garages/{garage_id}/reviews, /reviews/{review_id}).
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_customer
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.review import (
    CreateReviewReportRequest,
    CreateReviewRequest,
    GarageReviewsResponse,
    PatchReviewRequest,
    ReviewRead,
    ReviewSortOption,
)
from app.services import review_service

router = APIRouter()


# ── Public & Customer Garage Reviews ──────────────────────────────────────────

@router.post(
    "/garages/{garage_id}/reviews",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a review for a public garage (verified customer only, rating 1-5, comment optional)",
)
async def create_review(
    garage_id: uuid.UUID,
    body: CreateReviewRequest,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> ReviewRead:
    return await review_service.submit_review(
        db=db,
        customer=current_user,
        garage_id=garage_id,
        dto=body,
    )


@router.get(
    "/garages/{garage_id}/reviews",
    response_model=GarageReviewsResponse,
    summary="Get paginated published reviews with 1-5 distribution and average rating",
)
async def list_garage_reviews(
    garage_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    sort: ReviewSortOption = Query(
        default="newest",
        description="Sort by: 'newest', 'highest_rating', or 'lowest_rating'",
    ),
    db: AsyncSession = Depends(get_db),
) -> GarageReviewsResponse:
    return await review_service.get_garage_reviews(
        db=db,
        garage_id=garage_id,
        page=page,
        limit=limit,
        sort_by=sort,
    )


# ── Review Author Actions ─────────────────────────────────────────────────────

@router.patch(
    "/reviews/{review_id}",
    response_model=ReviewRead,
    summary="Edit own review (rating or comment independently; no time limit; cannot edit removed reviews)",
)
async def patch_review(
    review_id: uuid.UUID,
    body: PatchReviewRequest,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> ReviewRead:
    return await review_service.patch_review(
        db=db,
        customer=current_user,
        review_id=review_id,
        dto=body,
    )


@router.delete(
    "/reviews/{review_id}",
    response_model=MessageResponse,
    summary="Soft-delete own review (preserves history; permits submitting a new review later)",
)
async def delete_review(
    review_id: uuid.UUID,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await review_service.delete_review(
        db=db,
        customer=current_user,
        review_id=review_id,
    )
    return MessageResponse(message="Review deleted successfully.")


# ── Review Reporting ──────────────────────────────────────────────────────────

@router.post(
    "/reviews/{review_id}/reports",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a review (verified customer; cannot report own review; max 1 report per reporter/review)",
)
async def report_review(
    review_id: uuid.UUID,
    body: CreateReviewReportRequest,
    current_user: User = Depends(require_customer),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await review_service.report_review(
        db=db,
        customer=current_user,
        review_id=review_id,
        dto=body,
    )
    return MessageResponse(message="Review report submitted for moderation review.")

