import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from scripts import rebuild
from scripts.rebuild import should_rebuild_db


@pytest.mark.asyncio
@patch("scripts.rebuild.storage.Client")
async def test_restore_returns_false_when_no_snapshots(mock_storage_client):
    bucket_mock = MagicMock()
    bucket_mock.list_blobs.return_value = []
    mock_storage_client.return_value.bucket.return_value = bucket_mock

    result = await rebuild.restore_db_from_gcs_snapshot("bucket123")
    assert result is False


@pytest.mark.asyncio
@patch("scripts.rebuild.storage.Client")
@patch("scripts.rebuild.rebuild_db_from_gcs")
@patch("scripts.rebuild.aiosqlite.connect")
async def test_restore_db_uses_latest_snapshot(
    mock_connect, mock_rebuild, mock_storage_client
):
    # Setup: mock blobs
    mock_blob1 = MagicMock()
    mock_blob1.name = "db-backups/backup-2025-05-01.sqlite3"

    mock_blob2 = MagicMock()
    mock_blob2.name = "db-backups/backup-2025-05-06.sqlite3"
    mock_blob2.download_to_filename = MagicMock()

    bucket_mock = MagicMock()
    bucket_mock.list_blobs.return_value = [mock_blob1, mock_blob2]

    mock_storage_client.return_value.bucket.return_value = bucket_mock

    # Mock latest timestamp from DB
    db_conn = AsyncMock()
    mock_connect.return_value.__aenter__.return_value = db_conn
    db_conn.execute.return_value.fetchone.return_value = ("2025-05-06T12:00:00+00:00",)

    result = await rebuild.restore_db_from_gcs_snapshot("my-bucket")

    assert result == "2025-05-06T12:00:00+00:00"
    mock_blob2.download_to_filename.assert_called_once()
    mock_rebuild.assert_called_once()
    assert (
        mock_rebuild.call_args.kwargs["since_timestamp"] == "2025-05-06T12:00:00+00:00"
    )


@pytest.mark.asyncio
@patch("scripts.rebuild.storage.Client")
@patch("scripts.rebuild.add_image", new_callable=AsyncMock)
@patch("scripts.rebuild.add_tag", new_callable=AsyncMock)
@patch("scripts.rebuild.link_image_tag", new_callable=AsyncMock)
@patch("scripts.rebuild.init_db", new_callable=AsyncMock)
async def test_rebuild_from_gcs_filters_by_timestamp(
    mock_init, mock_link, mock_add_tag, mock_add_image, mock_storage_client
):
    # Setup: blobs with timestamps
    old_blob = MagicMock()
    old_blob.name = "upload/summary/old_image.summary.txt"
    old_blob.updated = datetime.now(UTC) - timedelta(days=5)
    old_blob.download_as_text.return_value = "Tag1\nTag2"

    new_blob = MagicMock()
    new_blob.name = "upload/summary/new_image.summary.txt"
    new_blob.updated = datetime.now(UTC)
    new_blob.download_as_text.return_value = "Tag3\nTag4"

    bucket_mock = MagicMock()
    bucket_mock.list_blobs.return_value = [old_blob, new_blob]
    mock_storage_client.return_value.bucket.return_value = bucket_mock

    cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat(timespec="seconds")

    await rebuild.rebuild_db_from_gcs("my-bucket", "upload", since_timestamp=cutoff)

    mock_add_image.assert_called_once_with("new_image", label="", timestamp=ANY)
    mock_add_tag.assert_any_call("tag3")
    mock_add_tag.assert_any_call("tag4")
    assert mock_link.call_count == 2  # One for each tag


def test_should_rebuild_db_with_force_env():
    for flag in ("", "0", "false", "no", "off"):
        os.environ["FORCE_REBUILD"] = flag
        assert should_rebuild_db() is False, f"Expected False for FORCE_REBUILD={flag}"
    for flag in ("1", "true", "yes"):
        os.environ["FORCE_REBUILD"] = flag
        logging.info(f"FORCE_REBUILD = {flag}")
        assert should_rebuild_db() is True, f"Expected True for FORCE_REBUILD={flag}"
    os.environ.pop("FORCE_REBUILD")


def test_should_rebuild_db_with_force():
    assert should_rebuild_db(force=True) is True


def test_should_rebuild_db_from_env(monkeypatch):
    monkeypatch.setenv("FORCE_REBUILD", "yes")
    assert should_rebuild_db() is True


@pytest.mark.asyncio
async def test_should_rebuild_db_when_db_exists(tmp_path, monkeypatch):
    dummy_db = tmp_path / "metadata.db"
    dummy_db.touch()

    monkeypatch.setattr("scripts.rebuild.DB_PATH", dummy_db)
    monkeypatch.delenv("FORCE_REBUILD", raising=False)

    assert should_rebuild_db() is False
    assert await rebuild.rebuild_db_from_gcs("my-bucket", "upload") is None


def test_should_rebuild_db_when_no_db(monkeypatch):
    non_existent = Path("/tmp/fake_metadata.db")
    monkeypatch.setattr("scripts.rebuild.DB_PATH", non_existent)
    monkeypatch.delenv("FORCE_REBUILD", raising=False)

    assert should_rebuild_db() is True


@pytest.mark.asyncio
@patch("scripts.rebuild.storage.Client")
@patch("scripts.rebuild.add_image", new_callable=AsyncMock)
@patch("scripts.rebuild.add_tag", new_callable=AsyncMock)
@patch("scripts.rebuild.link_image_tag", new_callable=AsyncMock)
@patch("scripts.rebuild.init_db", new_callable=AsyncMock)
async def test_rebuild_skips_empty_summary(
    mock_init,
    mock_link,
    mock_add_tag,
    mock_add_image,
    mock_storage_client,
    tmp_path,
    monkeypatch,
):
    empty_blob = MagicMock()
    empty_blob.name = "upload/summary/empty_image.summary.txt"
    empty_blob.updated = datetime.now(UTC)
    empty_blob.download_as_text.return_value = ""
    nonexistent_path = tmp_path / "missing.db"
    monkeypatch.setattr("scripts.rebuild.DB_PATH", nonexistent_path)
    await rebuild.rebuild_db_from_gcs("my-bucket", "upload", since_timestamp=None)

    bucket_mock = MagicMock()
    bucket_mock.list_blobs.return_value = [empty_blob]
    mock_storage_client.return_value.bucket.return_value = bucket_mock

    await rebuild.rebuild_db_from_gcs("my-bucket", "upload", since_timestamp=None)

    mock_add_image.assert_called_once_with("empty_image", label="", timestamp=ANY)
    mock_add_tag.assert_not_called()
    mock_link.assert_not_called()


@pytest.mark.asyncio
@patch("scripts.rebuild.storage.Client")
async def test_restore_returns_false_when_no_snapshots(mock_storage_client):
    bucket_mock = MagicMock()
    bucket_mock.list_blobs.return_value = []
    mock_storage_client.return_value.bucket.return_value = bucket_mock

    result = await rebuild.restore_db_from_gcs_snapshot("bucket123")
    assert result is False
