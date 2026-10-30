"""Unit tests for review schemas, ratings range, and reporting."""
import uuid
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from app.models.enums import ReviewReportReason
from app.schemas.review import (
    CreateReviewReportRequest,
    CreateReviewRequest,
    CustomerBrief,
    PatchReviewRequest,
    ReviewRead,
)


def test_create_review_rating_range():
    # Valid rating only
    r1 = CreateReviewRequest(rating=5)
    assert r1.rating == 5
    assert r1.comment is None

    # Valid rating with comment
    r2 = CreateReviewRequest(rating=3, comment="  Decent service.  ")
    assert r2.comment == "Decent service."

    # Rating 0 should fail
    with pytest.raises(ValidationError):
        CreateReviewRequest(rating=0)

    # Rating 6 should fail
    with pytest.raises(ValidationError):
        CreateReviewRequest(rating=6)


def test_patch_review_validation():
    # Update rating only
    p1 = PatchReviewRequest(rating=4)
    assert p1.rating == 4

    # Update comment only
    p2 = PatchReviewRequest(comment="Updated comment")
    assert p2.comment == "Updated comment"

    # Clearing comment with empty string
    p3 = PatchReviewRequest(comment="   ")
    assert p3.comment is None

    # Empty patch should fail
    with pytest.raises(ValidationError):
        PatchReviewRequest()


def test_review_report_reasons():
    for reason in ReviewReportReason:
        req = CreateReviewReportRequest(reason=reason, details="Test details")
        assert req.reason == reason

    with pytest.raises(ValidationError):
        CreateReviewReportRequest(reason="INVALID_REASON")


def test_review_privacy_guarantee():
    review = ReviewRead(
        id=uuid.uuid4(),
        customer=CustomerBrief(display_name="Sarah Connor"),
        rating=5,
        comment="Quick battery replacement!",
        created_at=datetime.now(tz=timezone.utc),
        updated_at=datetime.now(tz=timezone.utc),
    )
    dumped = review.model_dump()
    assert dumped["customer"]["display_name"] == "Sarah Connor"
    assert "email" not in dumped["customer"]
    assert "phone" not in dumped["customer"]
    assert "user_id" not in dumped["customer"]

