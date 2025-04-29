import aiosqlite

DB_PATH = "uploads/metadata.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        with open("scripts/schema.sql") as f:
            await db.executescript(f.read())
        await db.commit()


async def add_image(filename, label, timestamp):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO images (filename, label, timestamp) VALUES (?, ?, ?)",
            (filename, label, timestamp),
        )
        await db.commit()


async def add_tag(name):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        await db.commit()


async def link_image_tag(filename, tag_name):
    async with aiosqlite.connect(DB_PATH) as db:
        # Get image id
        cursor = await db.execute(
            "SELECT id FROM images WHERE filename = ?", (filename,)
        )
        image = await cursor.fetchone()

        # Get tag id
        cursor = await db.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag = await cursor.fetchone()

        if image and tag:
            await db.execute(
                "INSERT OR IGNORE INTO image_tags (image_id, tag_id) VALUES (?, ?)",
                (image[0], tag[0]),
            )
            await db.commit()
