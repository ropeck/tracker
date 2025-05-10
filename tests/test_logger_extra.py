import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import pytest
from httpx import ASGITransport, AsyncClient

from scripts import db as db_module
from scripts import logger
from scripts.config import BACKUP_DB_PATH
from scripts.db import get_db
from scripts.db import get_db as logger_get_db
from scripts.logger import get_current_user


@pytest.mark.asyncio
async def test_rebuild_route():
    logger.app.dependency_overrides[get_current_user] = lambda: {
        "email": "fogcat5@gmail.com"
    }
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "scripts.logger.rebuild_db_from_gcs", new_callable=AsyncMock
        ) as mock_rebuild:
            res = await client.get("/rebuild")
            assert res.status_code == 200
            assert mock_rebuild.called


@pytest.mark.asyncio
@patch("scripts.logger.os.path.exists", return_value=True)
@patch("scripts.logger.storage.Client.from_service_account_json")
async def test_gcs_proxy_file_found(mock_client, mock_exists):
    blob = MagicMock()
    blob.exists.return_value = True
    blob.open.return_value = MagicMock()
    blob.content_type = "image/jpeg"
    mock_client.return_value.bucket.return_value.blob.return_value = blob

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/uploads/test.jpg")
        assert res.status_code == 200


@pytest.mark.asyncio
@patch("scripts.logger.storage.Client")
@patch("os.path.exists", return_value=False)
async def test_gcs_proxy_not_found(mock_os, mock_client):
    blob = MagicMock()
    blob.exists.return_value = False

    mock_client.return_value.bucket.return_value.blob.return_value = blob

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/uploads/missing.jpg")
        assert res.status_code == 404


from scripts import db as db_module
from scripts.db import get_db as logger_get_db


def override_get_db(db_path):
    async def _get_db():
        async with aiosqlite.connect(db_path) as db:
            yield db

    return _get_db


@pytest.mark.asyncio
@patch("scripts.logger.call_openai_chat", new_callable=AsyncMock)
async def test_search_query_response(mock_call, tmp_path):
    db_path = tmp_path / "test.db"
    db_path = db_path.resolve()

    async with aiosqlite.connect(db_path) as db:
        await db.execute("CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT)")
        await db.execute("INSERT INTO tags (name) VALUES ('usb'), ('audio')")
        await db.commit()

    db_module.DB_PATH = db_path

    logger.app.dependency_overrides.clear()
    logger.app.dependency_overrides[logger_get_db] = override_get_db(db_path)

    (tmp_path / "test.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "test.jpg.thumb.jpg").write_bytes(b"\xff\xd8\xff")
    mock_call.return_value = json.dumps(["usb", "audio"])

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/search/query", data={"prompt": "Where are my USB cables?"}
        )
        assert res.status_code == 200
        assert "usb" in res.text or "audio" in res.text


@pytest.mark.asyncio
@patch("scripts.logger.upload_file_to_gcs")
async def test_backup_now_success(mock_upload, tmp_path):
    logger.app.dependency_overrides[get_current_user] = lambda: {
        "email": "fogcat5@gmail.com"
    }
    os.environ["ALLOWED_USER_EMAILS"] = "fogcat5@gmail.com"
    test_db_path = tmp_path / "test.db"

    with patch("scripts.config.BACKUP_DB_PATH", test_db_path):
        async for db in get_db():
            # await db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
            await db.commit()

    backup_path = tmp_path / "backup-2025-05-07.sqlite3"
    backup_path.write_text("different_content")

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("scripts.logger.utc_now_iso", return_value="2025-05-07T00:00:00"):
            res = await client.get("/backup-now")
            assert res.status_code == 200
            assert mock_upload.called
