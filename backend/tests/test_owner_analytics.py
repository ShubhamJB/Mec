"""Unit tests for owner dashboard and analytics calculations."""
import uuid
from datetime import date
import pytest
from fastapi import HTTPException

from app.schemas.analytics import MetricComparison, OwnerDashboardResponse
from app.schemas.garage_profile import AvailabilityResponse
from app.services.owner_analytics_service import _calc_metric


def test_metric_comparison_calculation():
    # Increase from 10 to 15 (+50%)
    m1 = _calc_metric(15.0, 10.0)
    assert m1.current == 15.0
    assert m1.previous == 10.0
    assert m1.change == 5.0
    assert m1.percentage_change == 50.0

    # Decrease from 20 to 10 (-50%)
    m2 = _calc_metric(10.0, 20.0)
    assert m2.change == -10.0
    assert m2.percentage_change == -50.0

    # Previous was 0 -> percentage is None
    m3 = _calc_metric(5.0, 0.0)
    assert m3.change == 5.0
    assert m3.percentage_change is None


def test_owner_dashboard_schema():
    dash = OwnerDashboardResponse(
        garage_id=uuid.uuid4(),
        name="Apex Motors",
        approval_status="APPROVED",
        availability=AvailabilityResponse(
            status="OPEN",
            is_temporarily_unavailable=False,
            message=None,
            timezone="UTC",
            local_time="2026-10-30T10:00:00Z",
            next_status_change="2026-10-30T18:00:00Z",
        ),
        total_profile_views=140,
        total_call_clicks=32,
        average_rating=4.7,
        review_count=19,
    )
    assert dash.name == "Apex Motors"
    assert dash.total_profile_views == 140
    assert dash.total_call_clicks == 32

