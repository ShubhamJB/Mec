"""
Pydantic schemas for Owner Dashboard and Analytics.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field

from app.schemas.garage_profile import AvailabilityResponse

GroupByOption = Literal["day", "week", "month"]


class OwnerDashboardResponse(BaseModel):
    garage_id: uuid.UUID
    name: str
    approval_status: str
    availability: AvailabilityResponse
    total_profile_views: int = 0
    total_call_clicks: int = 0
    average_rating: float | None = None
    review_count: int = 0


class EngagementDataPoint(BaseModel):
    period: str
    views: int
    call_clicks: int


class EngagementAnalyticsResponse(BaseModel):
    timezone: str
    group_by: str
    series: list[EngagementDataPoint]


class RatingsAnalyticsResponse(BaseModel):
    average_rating: float | None = None
    total_reviews: int = 0
    rating_distribution: dict[str, int]


class MetricComparison(BaseModel):
    current: float
    previous: float
    change: float
    percentage_change: float | None = None


class AnalyticsSummaryResponse(BaseModel):
    current_period: dict[str, str]
    previous_period: dict[str, str]
    profile_views: MetricComparison
    call_clicks: MetricComparison
    new_reviews: MetricComparison
    average_rating: MetricComparison

