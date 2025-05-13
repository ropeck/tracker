"""Database access and helper functions for image and tag management.

Handles initialization and interaction with the local SQLite database for
storing image metadata, tags, and associations.
"""

from pathlib import Path

import aiofiles
import aiosqlite

from scripts.config import BACKUP_DB_PATH

#: Path to the active application metadata database
DB_PATH = Path("uploads/metadata.db")


async def init_db(schema_path: str = "scripts/schema.sql") -> None:
    """Initialize the SQLite database using the provided schema file."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with aiofiles.open(schema_path) as f:
            schema = await f.read()
            await db.executescript(schema)
        await db.commit()


async def add_image(filename: str, label: str, timestamp: str) -> None:
    """Insert an image record into the database if it doesn't already exist.

    Args:
        filename (str): Name of the uploaded file.
        label (str): Optional label or description.
        timestamp (str): ISO timestamp of the upload.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO images (filename, label, timestamp) "
            "VALUES (?, ?, ?)",
            (filename, label, timestamp),
        )
        await db.commit()


async def add_tag(name: str) -> None:
    """Add a tag to the tags table if it doesn't already exist.

    Args:
        name (str): Tag name to insert.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,)
        )
        await db.commit()


async def link_image_tag(filename: str, tag_name: str) -> None:
    """Associate a tag with an image using their existing database IDs.

    Args:
        filename (str): Filename of the image to tag.
        tag_name (str): Tag name to link to the image.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        # Get image ID
        cursor = await db.execute(
            "SELECT id FROM images WHERE filename = ?", (filename,)
        )
        image = await cursor.fetchone()

        # Get tag ID
        cursor = await db.execute(
            "SELECT id FROM tags WHERE name = ?", (tag_name,)
        )
        tag = await cursor.fetchone()

        if image and tag:
            await db.execute(
                "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",  # noqa: E501
                (image[0], tag[0]),
            )
            await db.commit()


async def get_db() -> aiosqlite.Connection:
    """Yield a database connection using the backup DB path.

    Used as a FastAPI dependency for injecting database access.

    Yields:
        aiosqlite.Connection: An async connection to the backup database.
    """
    async with aiosqlite.connect(BACKUP_DB_PATH) as db:
        yield db
