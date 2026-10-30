"""
Service layer for Owner Dashboard, Engagement Time Series, and Comparative Analytics.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent
from app.models.catalog import OperatingHours
from app.models.enums import AnalyticsEventType, ReviewStatus
from app.models.garage import Garage
from app.models.review import Review
from app.schemas.analytics import (
    AnalyticsSummaryResponse,
    EngagementAnalyticsResponse,
    EngagementDataPoint,
    GroupByOption,
    MetricComparison,
    OwnerDashboardResponse,
    RatingsAnalyticsResponse,
)
from app.schemas.garage_profile import AvailabilityResponse
from app.schemas.review import GarageReviewsResponse, ReviewSortOption
from app.services.review_service import get_garage_reviews
from app.utils.availability import calculate_garage_availability


async def _get_owner_garage(db: AsyncSession, owner_id: uuid.UUID) -> Garage:
    stmt = select(Garage).where(Garage.owner_id == owner_id, Garage.deleted_at.is_(None))
    garage = (await db.execute(stmt)).scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered garage found for this owner.",
        )
    return garage


# ── GET /owner/dashboard ──────────────────────────────────────────────────────

async def get_owner_dashboard(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> OwnerDashboardResponse:
    garage = await _get_owner_garage(db, owner_id)

    # 1. Operating hours for availability
    hours_stmt = (
        select(OperatingHours)
        .where(OperatingHours.garage_id == garage.id)
        .order_by(OperatingHours.day_of_week.asc())
    )
    hours = list((await db.execute(hours_stmt)).scalars().all())

    avail_data = calculate_garage_availability(
        is_temporarily_unavailable=garage.is_temporarily_unavailable,
        temporary_unavailability_message=garage.temporary_unavailability_message,
        timezone_str=garage.timezone,
        operating_hours=hours,
    )

    # 2. Total analytics counts
    events_stmt = (
        select(
            func.count(AnalyticsEvent.id)
            .filter(AnalyticsEvent.event_type == AnalyticsEventType.PROFILE_VIEW)
            .label("views"),
            func.count(AnalyticsEvent.id)
            .filter(AnalyticsEvent.event_type == AnalyticsEventType.CALL_CLICK)
            .label("clicks"),
        )
        .where(AnalyticsEvent.garage_id == garage.id)
    )
    row_ev = (await db.execute(events_stmt)).first()
    views_total = int(row_ev[0]) if row_ev and row_ev[0] is not None else 0
    clicks_total = int(row_ev[1]) if row_ev and row_ev[1] is not None else 0

    # 3. Reviews stats
    rev_stmt = (
        select(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("total_count"),
        )
        .where(
            Review.garage_id == garage.id,
            Review.deleted_at.is_(None),
            Review.status == ReviewStatus.PUBLISHED,
        )
    )
    row_rev = (await db.execute(rev_stmt)).first()
    avg_rating = round(float(row_rev[0]), 1) if row_rev and row_rev[0] is not None else None
    rev_count = int(row_rev[1]) if row_rev and row_rev[1] is not None else 0

    return OwnerDashboardResponse(
        garage_id=garage.id,
        name=garage.name,
        approval_status=garage.approval_status.value,
        availability=AvailabilityResponse(**avail_data),
        total_profile_views=views_total,
        total_call_clicks=clicks_total,
        average_rating=avg_rating,
        review_count=rev_count,
    )


# ── GET /owner/analytics/engagement ───────────────────────────────────────────

async def get_engagement_analytics(
    db: AsyncSession,
    owner_id: uuid.UUID,
    start_date: date,
    end_date: date,
    group_by: GroupByOption = "day",
) -> EngagementAnalyticsResponse:
    garage = await _get_owner_garage(db, owner_id)

    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be greater than or equal to start_date.",
        )

    day_span = (end_date - start_date).days + 1
    if group_by == "day" and day_span > 90:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Daily engagement queries are limited to a maximum of 90 days.",
        )
    if group_by in ("week", "month") and day_span > 365:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{group_by.capitalize()} engagement queries are limited to a maximum of 365 days.",
        )

    # Garage local timezone boundaries converted to UTC timestamps
    try:
        tz = ZoneInfo(garage.timezone)
    except Exception:
        tz = ZoneInfo("UTC")

    dt_start = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    dt_end = datetime.combine(end_date, time.max, tzinfo=tz).astimezone(timezone.utc)

    # Fetch events within range
    stmt = (
        select(AnalyticsEvent.event_type, AnalyticsEvent.created_at)
        .where(
            AnalyticsEvent.garage_id == garage.id,
            AnalyticsEvent.created_at >= dt_start,
            AnalyticsEvent.created_at <= dt_end,
        )
    )
    events = list((await db.execute(stmt)).all())

    # Bucket events by period in garage local timezone
    buckets: dict[str, dict[str, int]] = {}

    # Initialize buckets with 0
    curr = start_date
    while curr <= end_date:
        if group_by == "day":
            key = curr.strftime("%Y-%m-%d")
            curr += timedelta(days=1)
        elif group_by == "week":
            # Monday of current week
            mon = curr - timedelta(days=curr.weekday())
            key = mon.strftime("%Y-%m-%d")
            curr += timedelta(days=7)
        else:
            # First of month
            key = curr.strftime("%Y-%m-01")
            # advance to next month
            next_month = curr.month + 1 if curr.month < 12 else 1
            next_year = curr.year if curr.month < 12 else curr.year + 1
            curr = date(next_year, next_month, 1)

        if key not in buckets:
            buckets[key] = {"views": 0, "call_clicks": 0}

    # Populate bucket counts from events
    for ev_type, ev_created in events:
        local_ev_dt = ev_created.astimezone(tz)
        local_date = local_ev_dt.date()

        if group_by == "day":
            b_key = local_date.strftime("%Y-%m-%d")
        elif group_by == "week":
            b_key = (local_date - timedelta(days=local_date.weekday())).strftime("%Y-%m-%d")
        else:
            b_key = local_date.strftime("%Y-%m-01")

        if b_key in buckets:
            if ev_type == AnalyticsEventType.PROFILE_VIEW:
                buckets[b_key]["views"] += 1
            elif ev_type == AnalyticsEventType.CALL_CLICK:
                buckets[b_key]["call_clicks"] += 1

    series = [
        EngagementDataPoint(period=k, views=v["views"], call_clicks=v["call_clicks"])
        for k, v in sorted(buckets.items())
    ]

    return EngagementAnalyticsResponse(
        timezone=garage.timezone,
        group_by=group_by,
        series=series,
    )


# ── GET /owner/analytics/ratings ──────────────────────────────────────────────

async def get_ratings_analytics(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> RatingsAnalyticsResponse:
    garage = await _get_owner_garage(db, owner_id)

    stats_stmt = (
        select(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("total_count"),
            func.count(Review.id).filter(Review.rating == 1).label("c1"),
            func.count(Review.id).filter(Review.rating == 2).label("c2"),
            func.count(Review.id).filter(Review.rating == 3).label("c3"),
            func.count(Review.id).filter(Review.rating == 4).label("c4"),
            func.count(Review.id).filter(Review.rating == 5).label("c5"),
        )
        .where(
            Review.garage_id == garage.id,
            Review.deleted_at.is_(None),
            Review.status == ReviewStatus.PUBLISHED,
        )
    )
    row = (await db.execute(stats_stmt)).first()
    avg_rating = round(float(row[0]), 1) if row and row[0] is not None else None
    total_reviews = int(row[1]) if row and row[1] is not None else 0
    distribution = {
        "1": int(row[2]) if row else 0,
        "2": int(row[3]) if row else 0,
        "3": int(row[4]) if row else 0,
        "4": int(row[5]) if row else 0,
        "5": int(row[6]) if row else 0,
    }

    return RatingsAnalyticsResponse(
        average_rating=avg_rating,
        total_reviews=total_reviews,
        rating_distribution=distribution,
    )


# ── GET /owner/reviews ────────────────────────────────────────────────────────

async def get_owner_reviews_list(
    db: AsyncSession,
    owner_id: uuid.UUID,
    page: int = 1,
    limit: int = 10,
    sort_by: ReviewSortOption = "newest",
) -> GarageReviewsResponse:
    garage = await _get_owner_garage(db, owner_id)
    return await get_garage_reviews(
        db=db,
        garage_id=garage.id,
        page=page,
        limit=limit,
        sort_by=sort_by,
    )


# ── GET /owner/analytics/summary ──────────────────────────────────────────────

def _calc_metric(curr_val: float, prev_val: float) -> MetricComparison:
    chg = curr_val - prev_val
    pct = round((chg / prev_val) * 100.0, 1) if prev_val > 0 else None
    return MetricComparison(
        current=round(curr_val, 2),
        previous=round(prev_val, 2),
        change=round(chg, 2),
        percentage_change=pct,
    )


async def get_analytics_summary(
    db: AsyncSession,
    owner_id: uuid.UUID,
    start_date: date,
    end_date: date,
) -> AnalyticsSummaryResponse:
    garage = await _get_owner_garage(db, owner_id)

    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_date must be greater than or equal to start_date.",
        )

    span = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span - 1)

    try:
        tz = ZoneInfo(garage.timezone)
    except Exception:
        tz = ZoneInfo("UTC")

    curr_dt_start = datetime.combine(start_date, time.min, tzinfo=tz).astimezone(timezone.utc)
    curr_dt_end = datetime.combine(end_date, time.max, tzinfo=tz).astimezone(timezone.utc)

    prev_dt_start = datetime.combine(prev_start, time.min, tzinfo=tz).astimezone(timezone.utc)
    prev_dt_end = datetime.combine(prev_end, time.max, tzinfo=tz).astimezone(timezone.utc)

    async def _query_metrics(t_start: datetime, t_end: datetime) -> tuple[int, int, int, float]:
        ev_q = (
            select(
                func.count(AnalyticsEvent.id)
                .filter(AnalyticsEvent.event_type == AnalyticsEventType.PROFILE_VIEW)
                .label("views"),
                func.count(AnalyticsEvent.id)
                .filter(AnalyticsEvent.event_type == AnalyticsEventType.CALL_CLICK)
                .label("clicks"),
            )
            .where(
                AnalyticsEvent.garage_id == garage.id,
                AnalyticsEvent.created_at >= t_start,
                AnalyticsEvent.created_at <= t_end,
            )
        )
        row_ev = (await db.execute(ev_q)).first()
        views = int(row_ev[0]) if row_ev and row_ev[0] is not None else 0
        clicks = int(row_ev[1]) if row_ev and row_ev[1] is not None else 0

        rev_q = (
            select(
                func.count(Review.id).label("rev_count"),
                func.avg(Review.rating).label("avg_rating"),
            )
            .where(
                Review.garage_id == garage.id,
                Review.deleted_at.is_(None),
                Review.status == ReviewStatus.PUBLISHED,
                Review.created_at >= t_start,
                Review.created_at <= t_end,
            )
        )
        row_rev = (await db.execute(rev_q)).first()
        rev_cnt = int(row_rev[0]) if row_rev and row_rev[0] is not None else 0
        avg_rt = float(row_rev[1]) if row_rev and row_rev[1] is not None else 0.0

        return views, clicks, rev_cnt, avg_rt

    c_views, c_clicks, c_revs, c_avg = await _query_metrics(curr_dt_start, curr_dt_end)
    p_views, p_clicks, p_revs, p_avg = await _query_metrics(prev_dt_start, prev_dt_end)

    return AnalyticsSummaryResponse(
        current_period={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        previous_period={"start_date": prev_start.isoformat(), "end_date": prev_end.isoformat()},
        profile_views=_calc_metric(float(c_views), float(p_views)),
        call_clicks=_calc_metric(float(c_clicks), float(p_clicks)),
        new_reviews=_calc_metric(float(c_revs), float(p_revs)),
        average_rating=_calc_metric(c_avg, p_avg),
    )

