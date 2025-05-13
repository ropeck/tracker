import json
from collections.abc import AsyncGenerator
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from scripts import db as db_module
from scripts import logger
from scripts.db import get_db
from scripts.db import get_db as logger_get_db
from scripts.logger import get_current_user


@pytest.mark.asyncio()
async def test_rebuild_route() -> None:
    logger.app.dependency_overrides[get_current_user] = lambda: {
        "email": "fogcat5@gmail.com"
    }
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        with patch(
            "scripts.logger.rebuild_db_from_gcs", new_callable=AsyncMock
        ) as mock_rebuild:
            res = await client.get("/rebuild")
            assert res.status_code == 200  # noqa: PLR2004
            assert mock_rebuild.called


@pytest.mark.asyncio()
@patch("scripts.logger.os.path.exists", return_value=True)
@patch("scripts.logger.storage.Client")
@patch("scripts.logger.storage.Client.from_service_account_json")
async def test_gcs_proxy_file_found_other(
    mock_from_json, mock_client, mock_exists
) -> None:
    # Define a blob that returns proper content and headers
    class FakeBlob:
        def exists(self) -> bool:
            return True

        def open(self, mode="rb") -> BytesIO:
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

    # Apply same return value to both ADC and JSON path
    mock_from_json.return_value = fake_client
    mock_client.return_value = fake_client

    # Run the test
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        res = await client.get("/uploads/test.jpg")

    assert res.status_code == 200  # noqa: PLR2004
    assert res.headers["content-type"] == "image/jpeg"
    assert res.content == b"test content"


@pytest.mark.asyncio()
@patch("scripts.logger.storage.Client")
@patch("pathlib.Path.exists", return_value=False)
async def test_gcs_proxy_not_found(mock_os, mock_client) -> None:
    blob = MagicMock()
    blob.exists.return_value = False
    blob.content_type = "image/jpeg"
    type(blob).content_type = PropertyMock(return_value="image/jpeg")

    mock_client.return_value.bucket.return_value.blob.return_value = blob

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        res = await client.get("/uploads/missing.jpg")
        assert res.status_code == 404  # noqa: PLR2004


def override_get_db(db_path: str) -> callable:
    async def _get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
        async with aiosqlite.connect(db_path) as db:
            yield db

    return _get_db


@pytest.mark.asyncio()
@patch("scripts.logger.call_openai_chat", new_callable=AsyncMock)
async def test_search_query_response(mock_call, tmp_path) -> None:
    db_path = tmp_path / "test.db"
    db_path = db_path.resolve()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS images "
            "(id INTEGER PRIMARY KEY, filename TEXT, timestamp TEXT)"
        )
        await db.execute(
            """CREATE TABLE IF NOT EXISTS tags
            (id INTEGER PRIMARY KEY, name TEXT)"""
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS image_tags "
            "(id INTEGER PRIMARY KEY, image_id INTEGER, tag_id INTEGER)"
        )
        await db.execute(
            "INSERT INTO images (filename, timestamp) "
            "VALUES ('file1.jpg', '2025-05-07T12:00:00')"
        )
        await db.commit()

    db_module.DB_PATH = db_path

    logger.app.dependency_overrides.clear()
    logger.app.dependency_overrides[logger_get_db] = override_get_db(db_path)

    (tmp_path / "test.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "test.jpg.thumb.jpg").write_bytes(b"\xff\xd8\xff")
    mock_call.return_value = json.dumps(["usb", "audio"])

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        res = await client.post(
            "/search/query", data={"prompt": "Where are my USB cables?"}
        )
        assert res.status_code == 200  # noqa: PLR2004
        assert "usb" in res.text or "audio" in res.text


@pytest.mark.asyncio()
@patch("scripts.logger.upload_file_to_gcs")
@patch("scripts.logger.os.getenv")
async def test_backup_now_success(mock_getenv, mock_upload, tmp_path) -> None:
    # Return the user allowlist and service account allowlist
    def getenv_side_effect(key: str, default: str = "") -> str:
        if key == "ALLOWED_USER_EMAILS":
            return "fogcat5@gmail.com"
        if key == "ALLOWED_SERVICE_ACCOUNT_IDS":
            return ""
        return default

    mock_getenv.side_effect = getenv_side_effect

    logger.app.dependency_overrides[get_current_user] = lambda: {
        "email": "fogcat5@gmail.com"
    }

    test_db_path = tmp_path / "test.db"
    with patch("scripts.config.BACKUP_DB_PATH", test_db_path):
        async for db in get_db():
            await db.commit()

    backup_path = tmp_path / "backup-2025-05-07.sqlite3"
    backup_path.write_text("different_content")

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(
        transport=transport, base_url="http://test"
    ) as client:
        with patch(
            "scripts.logger.utc_now_iso", return_value="2025-05-07T00:00:00"
        ):
            res = await client.get("/backup-now")
            assert res.status_code == 200  # noqa: PLR2004
            assert mock_upload.called
