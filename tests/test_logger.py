import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from httpx import ASGITransport, AsyncClient

from scripts import logger


@pytest.fixture
def app():
    return logger.app


@pytest.mark.asyncio
async def test_healthz_ok(tmp_path):
    db_path = tmp_path / "metadata.db"
    db_path.write_text("")  # touch file
    logger.BACKUP_DB_PATH = db_path

    async with logger.aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT)"
        )
        await db.execute(
            "INSERT INTO images (timestamp) VALUES ('2025-05-07T12:00:00')"
        )
        await db.commit()

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/healthz")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_root_returns_template():
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        assert "html" in res.headers["content-type"]


@patch("scripts.logger.Image.open")
@patch("scripts.logger.upload_file_to_gcs")
@patch("scripts.logger.analyze_image_with_openai")
@patch("scripts.logger.add_image", new_callable=AsyncMock)
@patch("scripts.logger.add_tag", new_callable=AsyncMock)
@patch("scripts.logger.link_image_tag", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_process_image_success(
    mock_link,
    mock_tag,
    mock_add,
    mock_ai,
    mock_upload,
    mock_open,
    tmp_path,
):
    file_path = tmp_path / "test_image.jpg"
    file_path.write_bytes(b"\xff\xd8\xff")  # Minimal JPEG header
    thumb_path = file_path.parent / "test_image.jpg.thumb.jpg"
    thumb_path.write_bytes(b"\x89PNG\r\n\x1a\n")  # Fake PNG thumbnail
    mock_ai.return_value = {"summary": "cable\npower\nswitch"}
    mock_open.return_value.__enter__.return_value = MagicMock()

    with patch("scripts.logger.UPLOAD_DIR", new_callable=lambda: tmp_path):
        await logger.process_image((file_path, "test_image.jpg", "Test"))
    assert mock_add.called


def test_upload_file_to_gcs_mocked(tmp_path):
    f = tmp_path / "mock.txt"
    f.write_text("dummy")
    with f.open("rb") as fh:
        with patch(
            "scripts.logger.storage.Client.from_service_account_json"
        ) as mock_from_json:
            mock_blob = MagicMock()
            mock_from_json.return_value.bucket.return_value.blob.return_value = (
                mock_blob
            )

            path = logger.upload_file_to_gcs("my-bucket", "dest.txt", fh)

            assert path == "dest.txt"
            assert mock_blob.upload_from_file.called


@pytest.mark.asyncio
async def test_trigger_backup_no_db():
    with patch("scripts.logger.BACKUP_DB_PATH", Path("nonexistent.db")):
        with pytest.raises(Exception):
            await logger.perform_backup()


@pytest.mark.asyncio
async def test_unauthorized_page():
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/unauthorized")
        assert res.status_code == 200
        assert "403" in res.text


@pytest.mark.asyncio
@patch("scripts.logger.get_db")
@patch("scripts.logger.storage.Client")
async def test_get_photos_route_runs(mock_client, mock_get_db, tmp_path):
    db_path = tmp_path / "metadata.db"
    db_path.write_text("")  # touch it

    async def override():
        async with aiosqlite.connect(db_path) as db:
            yield db

    mock_get_db.side_effect = override

    async with logger.aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, timestamp TEXT)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS tags (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS image_tags (id INTEGER PRIMARY KEY AUTOINCREMENT, image_id INTEGER, tag_id INTEGER)"
        )
        await db.execute(
            "INSERT INTO images (filename, timestamp) VALUES ('file1.jpg', '2025-05-07T12:00:00')"
        )
        await db.commit()

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/photos")
        assert res.status_code == 200
