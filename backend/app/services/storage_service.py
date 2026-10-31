"""
Storage provider interface and stub implementation.
Easily swappable with S3, Cloudinary, GCS, or Supabase.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
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


IMAGE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class LocalStorageService:
    """
    Saves files to a directory on disk and serves them through the API's /media mount.
    Intended for development and single-node deployments.
    """

    def __init__(self, root: Path, public_prefix: str):
        self.root = root
        self.public_prefix = public_prefix.rstrip("/")

    async def upload_file(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> tuple[str, str]:
        extension = IMAGE_EXTENSIONS.get(content_type, ".bin")
        storage_key = f"garages/{uuid.uuid4()}{extension}"
        destination = self.root / storage_key
        await asyncio.to_thread(self._write, destination, file_bytes)
        return f"{self.public_prefix}/{storage_key}", storage_key

    async def delete_file(self, *, storage_key: str) -> bool:
        target = (self.root / storage_key).resolve()
        if not target.is_relative_to(self.root.resolve()):
            return False
        await asyncio.to_thread(target.unlink, True)
        return True

    @staticmethod
    def _write(destination: Path, data: bytes) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)


def get_storage_service() -> StorageProvider:
    if settings.STORAGE_PROVIDER == "local":
        return LocalStorageService(Path(settings.UPLOAD_DIR), settings.MEDIA_URL_PREFIX)
    return StubStorageService()


storage_service = get_storage_service()

