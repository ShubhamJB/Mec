"""
Pagination helpers — shared across all list endpoints.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=10, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    limit: int
    total_items: int
    total_pages: int

    @classmethod
    def build(
        cls,
        items: list[T],
        total_items: int,
        page: int,
        limit: int,
    ) -> "PaginatedResponse[T]":
        total_pages = max(1, -(-total_items // limit))  # ceiling division
        return cls(
            items=items,
            page=page,
            limit=limit,
            total_items=total_items,
            total_pages=total_pages,
        )

