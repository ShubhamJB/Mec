import asyncio
from pathlib import Path

from app.services.storage_service import LocalStorageService


def test_local_storage_saves_and_deletes(tmp_path: Path):
    service = LocalStorageService(tmp_path, "/api/v1/media/")
    url, key = asyncio.run(
        service.upload_file(file_bytes=b"abc", filename="evil.html", content_type="image/png")
    )
    assert key.endswith(".png")
    assert url == f"/api/v1/media/{key}"
    assert (tmp_path / key).read_bytes() == b"abc"
    assert asyncio.run(service.delete_file(storage_key=key)) is True
    assert not (tmp_path / key).exists()


def test_local_storage_refuses_path_traversal(tmp_path: Path):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("keep")
    service = LocalStorageService(tmp_path / "root", "/media")
    assert asyncio.run(service.delete_file(storage_key="../../outside.txt")) is False
    assert outside.read_text() == "keep"
