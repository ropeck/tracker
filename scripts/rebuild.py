import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

import aiosqlite
from google.cloud import storage

from scripts.db import DB_PATH, add_image, add_tag, init_db, link_image_tag
from scripts.util import clean_tag_name, parse_utc_timestamp, utc_now_iso

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def should_rebuild_db(force: bool = False) -> bool:
    """
    Determines whether the local DB should be rebuilt from GCS.

    This function checks:
    - The `force` argument passed explicitly to override all checks
    - The `FORCE_REBUILD` environment variable (treated as truthy unless set
        to "", "0", "false", "no", or "off")
    - Whether the DB file already exists on disk

    Returns:
        bool: True if a rebuild should be performed, False otherwise.
    """

    force_env = os.environ.get("FORCE_REBUILD", "")
    env_forced = force_env.strip().lower() not in ("", "0", "false", "no", "off")

    if force_env or force:
        logger.info("🔄 Forcing DB rebuild from GCS.")
        return True

    if os.path.exists(DB_PATH):
        logger.info("📦 DB already exists, skipping rebuild from GCS.")
        return False

    return True


async def rebuild_db_from_gcs(
    bucket_name: str,
    prefix: str,
    force: bool = False,
    since_timestamp: str | None = None,
) -> None:
    """
    Rebuilds the local image/tag database from summary files stored in GCS.

    Args:
        bucket_name (str): The name of the Google Cloud Storage bucket.
        prefix (str): The GCS path prefix where summary files are stored.
        force (bool, optional): If True, forces a rebuild even if the DB exists.
        since_timestamp (str, optional): ISO timestamp; only process files newer than this.
    """

    if not since_timestamp and not should_rebuild_db(force):
        return None

    logger.info("🔁 Starting rebuild from GCS...")

    if not os.path.exists(DB_PATH):
        logging.info(f"DB file does not exist, creating: {DB_PATH}")
        await init_db()

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=f"{prefix}/summary"))
        logging.info(f"🔁 Found {len(blobs)} summary files in GCS")

        # Optional time filtering
        if since_timestamp:
            try:
                cutoff_dt = parse_utc_timestamp(since_timestamp)

                blobs = [b for b in blobs if b.updated.astimezone(UTC) > cutoff_dt]
                logging.info(
                    f"🔍 Filtered to {len(blobs)} summary files after {since_timestamp}"
                )
            except Exception as e:
                logging.warning(
                    f"⚠️ Failed to parse since_timestamp '{since_timestamp}': {e}"
                )

        for blob in blobs:
            filename = os.path.basename(blob.name).replace(".summary.txt", "")
            logging.info(f"🔁 Processing {filename}")
            contents = blob.download_as_text()

            await add_image(filename, label="", timestamp=utc_now_iso())
            for line in contents.splitlines():
                tag = clean_tag_name(line)
                if tag:
                    await add_tag(tag)
                    await link_image_tag(filename, tag)

        logging.info("✅ DB rebuilt from GCS summaries")
    except Exception as e:
        logging.exception(f"🔥 Failed to rebuild DB from GCS: {e}")


async def restore_db_from_gcs_snapshot(
    bucket_name: str, snapshot_prefix: str = "db-backups/"
) -> bool:
    """
    Restore the most recent .sqlite3 snapshot from GCS and apply any deltas via summary.txt.

    Returns:
        Timestamp of most recent GCS backup or False if no snapshots found.
    """
    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        blobs = list(bucket.list_blobs(prefix=snapshot_prefix))
        sqlite_blobs = [b for b in blobs if b.name.endswith(".sqlite3")]

        if not sqlite_blobs:
            logging.warning("❌ No SQLite snapshots found in GCS.")
            return False

        # Sort by timestamp in filename (e.g., backup-2025-05-05.sqlite3)
        def extract_date(blob):
            match = re.search(r"(\d{4}-\d{2}-\d{2})", blob.name)
            if match:
                return datetime.strptime(match.group(1), "%Y-%m-%d")
            return datetime.min

        sqlite_blobs.sort(key=extract_date, reverse=True)
        latest_blob = sqlite_blobs[0]
        snapshot_ts = extract_date(latest_blob)

        logging.info(f"📦 Restoring DB snapshot: {latest_blob.name}")

        # Download snapshot
        latest_blob.download_to_filename(DB_PATH)

        # Connect to DB and get latest image timestamp
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT MAX(timestamp) FROM images")
            row = await cursor.fetchone()
            latest_ts = row[0]
        if latest_ts:
            # Make sure it's timezone-aware
            ts = datetime.fromisoformat(latest_ts)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            else:
                ts = ts.astimezone(UTC)

            # Pass string version forward
            latest_ts = ts.isoformat(timespec="seconds")

        logging.info(f"🔍 Latest DB image timestamp: {latest_ts or 'None'}")

        # Rebuild DB with only newer summary files
        await rebuild_db_from_gcs(
            bucket_name=bucket_name,
            prefix="upload",
            force=False,
            since_timestamp=latest_ts,
        )

        return latest_ts

    except Exception as e:
        logging.exception(f"🔥 Failed to restore snapshot: {e}")
        return False
