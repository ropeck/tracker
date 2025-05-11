import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from scripts import logger


@patch("scripts.logger.os.path.exists", return_value=True)
@patch("scripts.logger.storage.Client.from_service_account_json")
@patch("scripts.logger.process_uploads", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_lifespan_runs(mock_worker, mock_client, mock_exists):
    app = logger.app
    async with app.router.lifespan_context(app):
        mock_worker.assert_called_once()


@pytest.mark.asyncio
@patch("scripts.logger.os.path.exists", return_value=True)
@patch("scripts.logger.storage.Client.from_service_account_json")
async def test_gcs_proxy_content_type_fallback(mock_client, mock_exists):
    blob = MagicMock()
    blob.exists.return_value = True
    blob.open.return_value = MagicMock()
    blob.content_type = None
    mock_client.return_value.bucket.return_value.blob.return_value = blob

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/uploads/test.dat")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/octet-stream"


@pytest.mark.asyncio
@patch("scripts.logger.os.path.exists", return_value=True)
@patch(
    "scripts.logger.storage.Client.from_service_account_json",
    side_effect=Exception("fail"),
)
async def test_gcs_proxy_internal_error(mock_client, mock_exists):
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/uploads/shouldfail.jpg")
        assert res.status_code == 500


@pytest.mark.asyncio
async def test_search_query_logic(tmp_path):
    # Create dummy image and thumbnail files
    (tmp_path / "test.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "test.jpg.thumb.jpg").write_bytes(b"\xff\xd8\xff")

    # Set up the test DB
    db_path = tmp_path / "metadata.db"
    logger.BACKUP_DB_PATH = db_path
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE images (id INTEGER PRIMARY KEY, filename TEXT, timestamp TEXT)"
        )
        await db.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT)")
        await db.execute(
            "CREATE TABLE image_tags (id INTEGER PRIMARY KEY, image_id INTEGER, tag_id INTEGER)"
        )
        await db.execute(
            "INSERT INTO images VALUES (1, 'test.jpg', '2025-05-07T01:00:00')"
        )
        await db.execute("INSERT INTO tags VALUES (1, 'power')")
        await db.execute("INSERT INTO image_tags VALUES (1, 1, 1)")
        await db.commit()

    real_connect = aiosqlite.connect

    with (
        patch("scripts.logger.UPLOAD_DIR", tmp_path),
        patch("scripts.logger.aiosqlite.connect") as mock_connect,
    ):
        mock_connect.side_effect = lambda path, *a, **kw: real_connect(
            db_path, *a, **kw
        )

        transport = ASGITransport(app=logger.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/search?q=power")
            assert res.status_code == 200
            assert "/uploads/thumb/test.jpg.thumb.jpg" in res.text


@pytest.mark.asyncio
async def test_cleanup_old_backups(tmp_path):
    old_file = tmp_path / "backup-2000-01-01.sqlite3"
    old_file.write_text("x")
    old_time = datetime.now(timezone.utc) - timedelta(days=365)
    os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

    for i in range(15):
        path = tmp_path / f"backup-2025-05-{i + 1:02d}.sqlite3"
        path.write_text("ok")

    logger.DB_BACKUP_DIR = tmp_path
    await logger.cleanup_old_backups()

    assert not old_file.exists()
