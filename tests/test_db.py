# tests/test_db.py

import os
import tempfile
from unittest.mock import patch

import aiosqlite
import pytest
import pytest_asyncio

from scripts import db as db_module
from scripts.db import get_db


@pytest_asyncio.fixture
async def temp_db(monkeypatch):
    """Set up a temporary sqlite DB for testing."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db_module, "DB_PATH", path)
    await db_module.init_db("scripts/schema.sql")
    yield path
    os.remove(path)


@pytest.mark.asyncio
async def test_add_and_link_image_tag(temp_db) -> None:
    await db_module.add_image("cat.jpg", "Cute Cat", "2025-05-07")
    await db_module.add_tag("adorable")
    await db_module.link_image_tag("cat.jpg", "adorable")

    async with aiosqlite.connect(temp_db) as db:
        # Confirm image was added
        cursor = await db.execute(
            "SELECT * FROM images WHERE filename = ?", ("cat.jpg",)
        )
        image = await cursor.fetchone()
        assert image is not None

        # Confirm tag was added
        cursor = await db.execute(
            "SELECT * FROM tags WHERE name = ?", ("adorable",)
        )
        tag = await cursor.fetchone()
        assert tag is not None

        # Confirm link was added
        cursor = await db.execute(
            "SELECT * FROM image_tags WHERE image_id = ? AND tag_id = ?",
            (image[0], tag[0]),
        )
        link = await cursor.fetchone()
        assert link is not None


@pytest.mark.asyncio
async def test_ignore_duplicate_inserts(temp_db) -> None:
    await db_module.add_tag("sunny")
    await db_module.add_tag("sunny")  # Should be ignored

    async with aiosqlite.connect(temp_db) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM tags WHERE name = 'sunny'"
        )
        count = await cursor.fetchone()
        assert count[0] == 1

    await db_module.add_image("beach.png", "Beach Day", "2025-05-07")
    await db_module.add_image(
        "beach.png", "Beach Day", "2025-05-07"
    )  # Duplicate

    async with aiosqlite.connect(temp_db) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM images WHERE filename = 'beach.png'"
        )
        count = await cursor.fetchone()
        assert count[0] == 1


@pytest.mark.asyncio
async def test_tags_are_linked_correctly(temp_db) -> None:
    await db_module.add_image("cloud.jpg", "Sky Scene", "2025-05-07")
    await db_module.add_tag("sky")
    await db_module.add_tag("weather")
    await db_module.link_image_tag("cloud.jpg", "sky")
    await db_module.link_image_tag("cloud.jpg", "weather")

    async with aiosqlite.connect(temp_db) as db:
        cursor = await db.execute(
            """
            SELECT t.name
            FROM tags t
            JOIN image_tags it ON t.id = it.tag_id
            JOIN images i ON i.id = it.image_id
            WHERE i.filename = ?
        """,
            ("cloud.jpg",),
        )
        tags = [row[0] for row in await cursor.fetchall()]
        assert set(tags) == {"sky", "weather"}


@pytest.mark.asyncio
async def test_get_db_yields_connection(tmp_path) -> None:
    test_db_path = tmp_path / "test.db"

    with patch("scripts.db.BACKUP_DB_PATH", test_db_path):
        async for db in get_db():
            assert isinstance(db, aiosqlite.Connection)

            await db.execute(
                "CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)"
            )
            await db.execute("INSERT INTO test (value) VALUES ('hello')")
            await db.commit()

            async with db.execute("SELECT value FROM test") as cursor:
                row = await cursor.fetchone()
                assert row[0] == "hello"
