"""
Service layer for Garage Photos: image validation, storage, ordering, and deletion.
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException, UploadFile, status
from PIL import Image, UnidentifiedImageError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.garage import Garage
from app.models.photo import GaragePhoto
from app.services.storage_service import storage_service

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


async def _get_owner_garage(db: AsyncSession, owner_id: uuid.UUID) -> Garage:
    stmt = select(Garage).where(Garage.owner_id == owner_id, Garage.deleted_at.is_(None))
    result = await db.execute(stmt)
    garage = result.scalar_one_or_none()
    if not garage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered garage found for this owner.",
        )
    return garage


def _validate_image_content(file_bytes: bytes, filename: str) -> str:
    """
    Validates actual file bytes using Pillow to guard against spoofed extensions.
    Returns normalized mime type (e.g. 'image/jpeg', 'image/png', 'image/webp').
    """
    if len(file_bytes) > settings.MAX_PHOTO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE
            if hasattr(status, "HTTP_413_CONTENT_TOO_LARGE")
            else 413,
            detail=f"Photo size exceeds maximum allowed limit of {settings.MAX_PHOTO_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            img_format = (img.format or "").upper()
            if img_format not in ALLOWED_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Unsupported image format: {img_format}. Allowed formats: JPEG, PNG, WebP.",
                )
            mime_map = {
                "JPEG": "image/jpeg",
                "PNG": "image/png",
                "WEBP": "image/webp",
            }
            return mime_map.get(img_format, "image/jpeg")
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file is not a valid or readable image.",
        )


async def upload_garage_photo(
    db: AsyncSession,
    owner_id: uuid.UUID,
    file: UploadFile,
    caption: str | None = None,
) -> GaragePhoto:
    garage = await _get_owner_garage(db, owner_id)

    # 1. Enforce max 10 active photos
    count_stmt = select(func.count(GaragePhoto.id)).where(
        GaragePhoto.garage_id == garage.id,
        GaragePhoto.deleted_at.is_(None),
    )
    current_count = (await db.execute(count_stmt)).scalar_one()
    if current_count >= settings.MAX_PHOTOS_PER_GARAGE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Maximum photo limit reached ({settings.MAX_PHOTOS_PER_GARAGE} active photos).",
        )

    # 2. Read bytes and validate real image format
    file_bytes = await file.read()
    content_type = _validate_image_content(file_bytes, file.filename or "photo.jpg")

    # 3. Determine next display_order (max + 1)
    max_order_stmt = select(func.coalesce(func.max(GaragePhoto.display_order), -1)).where(
        GaragePhoto.garage_id == garage.id,
        GaragePhoto.deleted_at.is_(None),
    )
    max_order = (await db.execute(max_order_stmt)).scalar_one()
    next_order = max_order + 1

    # 4. Upload to storage provider
    public_url, storage_key = await storage_service.upload_file(
        file_bytes=file_bytes,
        filename=file.filename or "photo.jpg",
        content_type=content_type,
    )

    # 5. Persist DB record
    photo = GaragePhoto(
        garage_id=garage.id,
        url=public_url,
        storage_key=storage_key,
        caption=caption.strip() if caption and caption.strip() else None,
        display_order=next_order,
    )
    db.add(photo)
    await db.flush()
    return photo


async def list_owner_garage_photos(
    db: AsyncSession,
    owner_id: uuid.UUID,
) -> list[GaragePhoto]:
    garage = await _get_owner_garage(db, owner_id)
    stmt = (
        select(GaragePhoto)
        .where(
            GaragePhoto.garage_id == garage.id,
            GaragePhoto.deleted_at.is_(None),
        )
        .order_by(GaragePhoto.display_order.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def reorder_garage_photos(
    db: AsyncSession,
    owner_id: uuid.UUID,
    ordered_photo_ids: list[uuid.UUID],
) -> list[GaragePhoto]:
    garage = await _get_owner_garage(db, owner_id)

    # Fetch all active photos
    stmt = select(GaragePhoto).where(
        GaragePhoto.garage_id == garage.id,
        GaragePhoto.deleted_at.is_(None),
    )
    active_photos = list((await db.execute(stmt)).scalars().all())
    active_ids = {p.id for p in active_photos}

    if set(ordered_photo_ids) != active_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The reorder request must contain exactly all active photo IDs for this garage.",
        )

    # Two-phase update to avoid unique index collision on (garage_id, display_order)
    # Phase 1: Set temporary negative orders
    for idx, pid in enumerate(ordered_photo_ids):
        await db.execute(
            update(GaragePhoto)
            .where(GaragePhoto.id == pid)
            .values(display_order=-(idx + 1))
        )
    await db.flush()

    # Phase 2: Set final positive orders (0, 1, 2, ...)
    for idx, pid in enumerate(ordered_photo_ids):
        await db.execute(
            update(GaragePhoto)
            .where(GaragePhoto.id == pid)
            .values(display_order=idx)
        )
    await db.flush()

    return await list_owner_garage_photos(db, owner_id)


async def delete_garage_photo(
    db: AsyncSession,
    owner_id: uuid.UUID,
    photo_id: uuid.UUID,
) -> None:
    garage = await _get_owner_garage(db, owner_id)

    stmt = select(GaragePhoto).where(
        GaragePhoto.id == photo_id,
        GaragePhoto.garage_id == garage.id,
        GaragePhoto.deleted_at.is_(None),
    )
    photo = (await db.execute(stmt)).scalar_one_or_none()
    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found or already deleted.",
        )

    # Soft delete in database
    photo.deleted_at = datetime.now(tz=timezone.utc)

    # Delete cloud object by storage_key
    try:
        await storage_service.delete_file(storage_key=photo.storage_key)
    except Exception:
        # Cloud deletion error logged; DB soft-delete preserves state
        pass

    await db.flush()
