"""
Service layer for Customer Reviews and Review Reports.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ReviewReportStatus, ReviewStatus
from app.models.garage import Garage
from app.models.review import Review, ReviewReport
from app.models.user import User
from app.schemas.review import (
    CreateReviewReportRequest,
    CreateReviewRequest,
    CustomerBrief,
    GarageReviewsResponse,
    PatchReviewRequest,
    ReviewRead,
    ReviewSortOption,
)
from app.services.public_garage_service import verify_public_garage


async def submit_review(
    db: AsyncSession,
    customer: User,
    garage_id: uuid.UUID,
    dto: CreateReviewRequest,
) -> ReviewRead:
    # 1. Garage must be publicly eligible
    garage = await verify_public_garage(db, garage_id)

    # 2. Cannot review own garage
    if garage.owner_id == customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot submit a review for your own garage.",
        )

    # 3. Exactly one active published review per customer per garage
    existing_stmt = select(Review).where(
        Review.garage_id == garage.id,
        Review.customer_id == customer.id,
        Review.deleted_at.is_(None),
        Review.status == ReviewStatus.PUBLISHED,
    )
    if (await db.execute(existing_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted an active review for this garage. You can edit your existing review.",
        )

    review = Review(
        garage_id=garage.id,
        customer_id=customer.id,
        rating=dto.rating,
        comment=dto.comment,
        status=ReviewStatus.PUBLISHED,
    )
    db.add(review)
    await db.flush()

    return ReviewRead(
        id=review.id,
        customer=CustomerBrief(display_name=customer.full_name),
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


async def get_garage_reviews(
    db: AsyncSession,
    garage_id: uuid.UUID,
    page: int = 1,
    limit: int = 10,
    sort_by: ReviewSortOption = "newest",
) -> GarageReviewsResponse:
    # Garage must be publicly eligible
    await verify_public_garage(db, garage_id)

    # 1. Compute aggregate average and 1-5 distribution for active published reviews
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
            Review.garage_id == garage_id,
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

    # 2. Query paginated reviews with customer display name (never private account details)
    base_query = (
        select(Review, User.full_name)
        .join(User, Review.customer_id == User.id)
        .where(
            Review.garage_id == garage_id,
            Review.deleted_at.is_(None),
            Review.status == ReviewStatus.PUBLISHED,
        )
    )

    if sort_by == "highest_rating":
        base_query = base_query.order_by(Review.rating.desc(), Review.created_at.desc())
    elif sort_by == "lowest_rating":
        base_query = base_query.order_by(Review.rating.asc(), Review.created_at.desc())
    else:
        # Default: newest
        base_query = base_query.order_by(Review.created_at.desc())

    paginated_query = base_query.offset((page - 1) * limit).limit(limit)
    items = list((await db.execute(paginated_query)).all())

    review_reads = [
        ReviewRead(
            id=r[0].id,
            customer=CustomerBrief(display_name=r[1]),
            rating=r[0].rating,
            comment=r[0].comment,
            created_at=r[0].created_at,
            updated_at=r[0].updated_at,
        )
        for r in items
    ]

    total_pages = max(1, -(-total_reviews // limit)) if total_reviews > 0 else 1

    return GarageReviewsResponse(
        average_rating=avg_rating,
        total_reviews=total_reviews,
        rating_distribution=distribution,
        page=page,
        limit=limit,
        total_pages=total_pages,
        reviews=review_reads,
    )


async def patch_review(
    db: AsyncSession,
    customer: User,
    review_id: uuid.UUID,
    dto: PatchReviewRequest,
) -> ReviewRead:
    stmt = (
        select(Review, User.full_name)
        .join(User, Review.customer_id == User.id)
        .where(Review.id == review_id, Review.deleted_at.is_(None))
    )
    result = (await db.execute(stmt)).first()
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or already deleted.",
        )

    review, user_name = result[0], result[1]

    if review.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own reviews.",
        )

    if review.status == ReviewStatus.REMOVED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This review was removed by an administrator and cannot be modified or restored.",
        )

    if "rating" in dto.model_fields_set and dto.rating is not None:
        review.rating = dto.rating
    if "comment" in dto.model_fields_set:
        review.comment = dto.comment

    review.updated_at = datetime.now(tz=timezone.utc)
    await db.flush()

    return ReviewRead(
        id=review.id,
        customer=CustomerBrief(display_name=user_name),
        rating=review.rating,
        comment=review.comment,
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


async def delete_review(
    db: AsyncSession,
    customer: User,
    review_id: uuid.UUID,
) -> None:
    stmt = select(Review).where(Review.id == review_id, Review.deleted_at.is_(None))
    review = (await db.execute(stmt)).scalar_one_or_none()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or already deleted.",
        )

    if review.customer_id != customer.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own reviews.",
        )

    review.deleted_at = datetime.now(tz=timezone.utc)
    await db.flush()


async def report_review(
    db: AsyncSession,
    customer: User,
    review_id: uuid.UUID,
    dto: CreateReviewReportRequest,
) -> None:
    stmt = select(Review).where(Review.id == review_id, Review.deleted_at.is_(None))
    review = (await db.execute(stmt)).scalar_one_or_none()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found or already deleted.",
        )

    if review.customer_id == customer.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot report your own review.",
        )

    # One report per reporter per review
    existing_stmt = select(ReviewReport).where(
        ReviewReport.review_id == review.id,
        ReviewReport.reporter_id == customer.id,
    )
    if (await db.execute(existing_stmt)).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already submitted a report for this review.",
        )

    report = ReviewReport(
        review_id=review.id,
        reporter_id=customer.id,
        reason=dto.reason,
        details=dto.details,
        status=ReviewReportStatus.PENDING,
    )
    db.add(report)
    await db.flush()

