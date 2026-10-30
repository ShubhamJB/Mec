"""Unit tests for garage photos validation and reordering."""
import io
import uuid
import pytest
from PIL import Image
from pydantic import ValidationError
from fastapi import HTTPException

from app.schemas.photo import ReorderPhotosRequest
from app.services.photo_service import _validate_image_content
from app.services.storage_service import StubStorageService


def create_test_image_bytes(fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_image_validation_valid_formats():
    png_bytes = create_test_image_bytes("PNG")
    assert _validate_image_content(png_bytes, "test.png") == "image/png"

    jpeg_bytes = create_test_image_bytes("JPEG")
    assert _validate_image_content(jpeg_bytes, "test.jpg") == "image/jpeg"

    webp_bytes = create_test_image_bytes("WEBP")
    assert _validate_image_content(webp_bytes, "test.webp") == "image/webp"


def test_image_validation_corrupted_or_spoofed():
    # Plain text masquerading as an image
    fake_bytes = b"This is not a real image file content."
    with pytest.raises(HTTPException) as exc_info:
        _validate_image_content(fake_bytes, "fake.jpg")
    assert exc_info.value.status_code == 415


def test_image_validation_size_limit():
    # 6MB dummy bytes
    oversized_bytes = b"0" * (6 * 1024 * 1024)
    with pytest.raises(HTTPException) as exc_info:
        _validate_image_content(oversized_bytes, "large.jpg")
    assert exc_info.value.status_code == 413


def test_reorder_request_duplicate_prevention():
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    req = ReorderPhotosRequest(ordered_photo_ids=[id1, id2])
    assert len(req.ordered_photo_ids) == 2

    with pytest.raises(ValidationError):
        ReorderPhotosRequest(ordered_photo_ids=[id1, id2, id1])


@pytest.mark.asyncio
async def test_stub_storage_service():
    storage = StubStorageService()
    url, key = await storage.upload_file(
        file_bytes=b"dummy",
        filename="car.jpg",
        content_type="image/jpeg",
    )
    assert url.startswith("https://storage.findyourmechanic.com/photos/")
    assert key.startswith("garages/")
    assert key.endswith(".jpg")

    success = await storage.delete_file(storage_key=key)
    assert success is True

