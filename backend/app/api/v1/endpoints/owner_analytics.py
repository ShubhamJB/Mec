"""
Endpoints for Owner Dashboard and Analytics (/owner/dashboard, /owner/analytics/*, /owner/reviews).
"""
from __future__ import annotations

from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_verified_owner
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    EngagementAnalyticsResponse,
    GroupByOption,
    OwnerDashboardResponse,
    RatingsAnalyticsResponse,
)
from app.schemas.review import GarageReviewsResponse, ReviewSortOption
from app.services import owner_analytics_service

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=OwnerDashboardResponse,
    summary="Get owner dashboard summary (approval, real-time availability, total views & calls, ratings)",
)
async def get_owner_dashboard(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> OwnerDashboardResponse:
    return await owner_analytics_service.get_owner_dashboard(
        db=db, owner_id=current_user.id
    )


@router.get(
    "/analytics/engagement",
    response_model=EngagementAnalyticsResponse,
    summary="Get profile views and call clicks time series in garage timezone (daily max 90d, weekly/monthly max 365d)",
)
async def get_engagement_analytics(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    group_by: GroupByOption = Query(default="day", description="Aggregation bucket: 'day', 'week', or 'month'"),
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> EngagementAnalyticsResponse:
    return await owner_analytics_service.get_engagement_analytics(
        db=db,
        owner_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
    )


@router.get(
    "/analytics/ratings",
    response_model=RatingsAnalyticsResponse,
    summary="Get average rating, total count, and 1-5 rating distribution (excludes deleted/removed)",
)
async def get_ratings_analytics(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> RatingsAnalyticsResponse:
    return await owner_analytics_service.get_ratings_analytics(
        db=db, owner_id=current_user.id
    )


@router.get(
    "/reviews",
    response_model=GarageReviewsResponse,
    summary="Get reviews for owner's garage (masks customer private data, display name only)",
)
async def get_owner_reviews(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=50),
    sort: ReviewSortOption = Query(
        default="newest",
        description="Sort by: 'newest', 'highest_rating', or 'lowest_rating'",
    ),
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> GarageReviewsResponse:
    return await owner_analytics_service.get_owner_reviews_list(
        db=db,
        owner_id=current_user.id,
        page=page,
        limit=limit,
        sort_by=sort,
    )


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Compare current period vs immediately preceding equal-length period (views, clicks, reviews, avg rating)",
)
async def get_analytics_summary(
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummaryResponse:
    return await owner_analytics_service.get_analytics_summary(
        db=db,
        owner_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
    )

