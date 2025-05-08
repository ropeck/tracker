import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from scripts import logger


@pytest.mark.asyncio
@patch("scripts.logger.get_current_user", return_value={"email": "fogcat5@gmail.com"})
async def test_rebuild_route(mock_user):
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch(
            "scripts.logger.rebuild_db_from_gcs", new_callable=AsyncMock
        ) as mock_rebuild:
            res = await client.get("/rebuild")
            assert res.status_code == 200
            assert mock_rebuild.called


@pytest.mark.asyncio
@patch("scripts.logger.storage.Client")
async def test_gcs_proxy_file_found(mock_client):
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
async def test_gcs_proxy_not_found(mock_client):
    blob = MagicMock()
    blob.exists.return_value = False
    mock_client.return_value.bucket.return_value.blob.return_value = blob

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/uploads/missing.jpg")
        assert res.status_code == 404


@pytest.mark.asyncio
@patch("scripts.logger.call_openai_chat", new_callable=AsyncMock)
async def test_search_query_response(mock_call):
    mock_call.return_value = ["usb", "audio"]
    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/search/query", data={"prompt": "Where are my USB cables?"}
        )
        assert res.status_code == 200
        assert "usb" in res.text


@pytest.mark.asyncio
@patch("scripts.logger.get_current_user", return_value={"email": "fogcat5@gmail.com"})
@patch("scripts.logger.upload_file_to_gcs")
async def test_backup_now_success(mock_upload, mock_user, tmp_path):
    os.environ["ALLOWED_USER_EMAILS"] = "fogcat5@gmail.com"
    logger.BACKUP_DB_PATH = tmp_path / "metadata.db"
    logger.BACKUP_DB_PATH.write_text("content1")

    backup_path = logger.DB_BACKUP_DIR / "backup-2025-05-07.sqlite3"
    backup_path.write_text("different_content")

    transport = ASGITransport(app=logger.app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("scripts.logger.utc_now_iso", return_value="2025-05-07T00:00:00"):
            res = await client.get("/backup-now")
            assert res.status_code == 200
            assert mock_upload.called
