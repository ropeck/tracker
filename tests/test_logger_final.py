from __future__ import annotations

import importlib
import os
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    import aiosqlite

from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

_real_connect = importlib.import_module("aiosqlite").connect

from scripts import logger  # noqa: E402


@patch("scripts.logger.os.path.exists", return_value=True)
@patch("scripts.logger.storage.Client.from_service_account_json")
@patch("scripts.logger.process_uploads", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_lifespan_runs(mock_worker, mock_client, mock_exists) -> None:
    app = logger.app
    async with app.router.lifespan_context(app):
        mock_worker.assert_called_once()



@pytest.mark.asyncio
@patch("scripts.logger.os.path.exists", return_value=True)
@patch("scripts.logger.storage.Client")
@patch("scripts.logger.storage.Client.from_service_account_json")
async def test_gcs_proxy_file_found(
    mock_from_json, mock_client, mock_exists) -> None:
    class FakeBlob:
        def exists(self) -> bool:
            return True

        def open(self, mode: str = "rb") -> BytesIO:
            del mode
            return BytesIO(b"test content")

        @property
        def content_type(self) -> str:
            return "image/jpeg"

    class FakeBucket:
        def blob(self, name: str) -> FakeBlob:
            del name
            return FakeBlob()

    class FakeClient:
        def bucket(self, name: str) -> FakeBucket:
            del name
            return FakeBucket()

    fake_client = FakeClient()
    mock_from_json.return_value = fake_client
    mock_client.return_value = fake_client

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(
        transport=transport, base_url="http://test") as client:
        res = await client.get("/uploads/test.jpg")
        assert res.status_code == 200  # noqa: PLR2004
        assert res.headers["content-type"] == "image/jpeg"
        assert res.content == b"test content"

@pytest.mark.asyncio
@patch("scripts.logger.os.path.exists", return_value=True)
@patch(
    "scripts.logger.storage.Client.from_service_account_json",
    side_effect=Exception("fail"),
)
async def test_gcs_proxy_internal_error(mock_client, mock_exists) -> None:
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        res = await client.get("/uploads/shouldfail.jpg")
        assert res.status_code == 500  # noqa: PLR2004


@pytest.mark.asyncio
async def test_search_query_logic(tmp_path: logger.Path) -> None:
    # Create dummy image and thumbnail files
    (tmp_path / "test.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "test.jpg.thumb.jpg").write_bytes(b"\xff\xd8\xff")

    # Set up the test DB
    db_path = tmp_path / "metadata.db"
    logger.BACKUP_DB_PATH = db_path
    async with _real_connect(db_path) as db:
        await db.execute(
            "CREATE TABLE images "
            "(id INTEGER PRIMARY KEY, filename TEXT, timestamp TEXT)"
        )
        await db.execute(
            "CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT)"
        )
        await db.execute(
            "CREATE TABLE image_tags "
            "(id INTEGER PRIMARY KEY, image_id INTEGER, tag_id INTEGER)"
        )
        await db.execute(
            "INSERT INTO images VALUES (1, 'test.jpg', '2025-05-07T01:00:00')"
        )
        await db.execute("INSERT INTO tags VALUES (1, 'power')")
        await db.execute("INSERT INTO image_tags VALUES (1, 1, 1)")
        await db.commit()

    class FakeDB:
        def __init__(self, db_path: Path) -> None:
            self.db_path = db_path
            self.conn: aiosqlite.Connection | None = None

        async def __aenter__(self) -> aiosqlite.Connection:
            self.conn = await _real_connect(self.db_path)
            return self.conn

        async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: Any | None,  # noqa: ANN401, PYI036
        ) -> None:
            await self.conn.close()

    def patched_connect(path: str, *args: Any, **kwargs: Any) -> FakeDB:  # noqa: ANN401
        return FakeDB(db_path)

    with (
        patch("scripts.logger.UPLOAD_DIR", tmp_path),
        patch("scripts.logger.aiosqlite.connect", new=patched_connect),
    ):
        transport = ASGITransport(app=logger.app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            res = await client.get("/search?q=power")
            assert res.status_code == 200  # noqa: PLR2004
            assert "/uploads/thumb/test.jpg.thumb.jpg" in res.text


@pytest.mark.asyncio
async def test_cleanup_old_backups(tmp_path: logger.Path) -> None:
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
