"""
Pydantic schemas for Customer Reviews and Review Reports.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator

from app.models.enums import ReviewReportReason


class CustomerBrief(BaseModel):
    display_name: str


class ReviewRead(BaseModel):
    id: uuid.UUID
    customer: CustomerBrief
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateReviewRequest(BaseModel):
    rating: int = Field(ge=1, le=5, description="Integer rating between 1 and 5")
    comment: str | None = Field(default=None, max_length=2000, description="Optional text comment")

    @model_validator(mode="after")
    def clean_comment(self) -> "CreateReviewRequest":
        if self.comment is not None:
            cleaned = self.comment.strip()
            self.comment = cleaned or None
        return self


class PatchReviewRequest(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "PatchReviewRequest":
        # Check if fields were provided in the incoming payload
        fields_set = self.model_fields_set
        if "rating" not in fields_set and "comment" not in fields_set:
            raise ValueError("At least one field (rating or comment) must be provided in the update.")
        if "comment" in fields_set and self.comment is not None:
            self.comment = self.comment.strip() or None
        return self


class GarageReviewsResponse(BaseModel):
    average_rating: float | None = None
    total_reviews: int = 0
    rating_distribution: dict[str, int]
    page: int
    limit: int
    total_pages: int
    reviews: list[ReviewRead]


ReviewSortOption = Literal["newest", "highest_rating", "lowest_rating"]


class CreateReviewReportRequest(BaseModel):
    reason: ReviewReportReason
    details: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def clean_details(self) -> "CreateReviewReportRequest":
        if self.details is not None:
            cleaned = self.details.strip()
            self.details = cleaned or None
        return self

