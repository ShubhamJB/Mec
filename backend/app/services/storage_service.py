"""
Storage provider interface and stub implementation.
Easily swappable with S3, Cloudinary, GCS, or Supabase.
"""
from __future__ import annotations

import os
import uuid
from typing import Protocol

from app.core.config import settings


class StorageProvider(Protocol):
    async def upload_file(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[str, str]:
        """Uploads file content and returns (public_url, storage_key)."""
        ...

    async def delete_file(self, *, storage_key: str) -> bool:
        """Deletes file by its unique storage key."""
        ...


class StubStorageService:
    """
    Default stub storage provider.
    Generates deterministic pseudo-URLs and storage keys without requiring
    external cloud credentials, suitable for development and automated testing.
    """

    def __init__(self, base_url: str = "https://storage.findyourmechanic.com/photos"):
        self.base_url = base_url

    async def upload_file(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[str, str]:
        ext = os.path.splitext(filename)[1].lower() or ".jpg"
        storage_key = f"garages/{uuid.uuid4()}{ext}"
        public_url = f"{self.base_url}/{storage_key}"
        return public_url, storage_key

    async def delete_file(self, *, storage_key: str) -> bool:
        # Stub deletion succeeds
        return True


def get_storage_service() -> StorageProvider:
    # Switch on settings.STORAGE_PROVIDER if S3 / Cloudinary added later
    return StubStorageService()


storage_service = get_storage_service()

