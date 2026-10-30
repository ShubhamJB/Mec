"""
Endpoints for Owner Garage Photos (/owner/garage/photos).
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_verified_owner
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageResponse
from app.schemas.photo import PhotoRead, ReorderPhotosRequest
from app.services import photo_service

router = APIRouter()


@router.get(
    "/garage/photos",
    response_model=list[PhotoRead],
    summary="List active photos for owner's garage",
)
async def list_owner_photos(
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[PhotoRead]:
    photos = await photo_service.list_owner_garage_photos(
        db=db, owner_id=current_user.id
    )
    return [PhotoRead.model_validate(p) for p in photos]


@router.post(
    "/garage/photos",
    response_model=PhotoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a new garage photo (multipart/form-data, max 5MB, JPEG/PNG/WebP, max 10 active)",
)
async def upload_owner_photo(
    file: UploadFile = File(..., description="Image file (JPEG, PNG, WebP)"),
    caption: str | None = Form(default=None, max_length=300),
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> PhotoRead:
    photo = await photo_service.upload_garage_photo(
        db=db, owner_id=current_user.id, file=file, caption=caption
    )
    return PhotoRead.model_validate(photo)


@router.patch(
    "/garage/photos/reorder",
    response_model=list[PhotoRead],
    summary="Reorder all active photos for owner's garage",
)
async def reorder_owner_photos(
    body: ReorderPhotosRequest,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> list[PhotoRead]:
    photos = await photo_service.reorder_garage_photos(
        db=db, owner_id=current_user.id, ordered_photo_ids=body.ordered_photo_ids
    )
    return [PhotoRead.model_validate(p) for p in photos]


@router.delete(
    "/garage/photos/{photo_id}",
    response_model=MessageResponse,
    summary="Soft-delete a garage photo and delete cloud object by storage key",
)
async def delete_owner_photo(
    photo_id: uuid.UUID,
    current_user: User = Depends(require_verified_owner),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await photo_service.delete_garage_photo(
        db=db, owner_id=current_user.id, photo_id=photo_id
    )
    return MessageResponse(message="Photo deleted successfully.")

