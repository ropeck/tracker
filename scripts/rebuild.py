import json
import logging
import os
from datetime import datetime
from pathlib import Path

from google.cloud import storage

from scripts.db import DB_PATH, add_image, add_tag, init_db, link_image_tag
from scripts.util import clean_tag_name

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
    bucket_name: str, prefix: str, force: bool = False
) -> None:
    """
    Rebuilds the local image/tag database from summary files stored in GCS.

    This function checks whether a rebuild is needed based on the presence of the
    local database and the `force` flag. If rebuilding, it:
    - Connects to the specified GCS bucket
    - Lists all `summary.txt` files under the given prefix
    - Parses each file to extract image filenames and associated tags
    - Populates the local database with images and tag relationships

    Args:
        bucket_name (str): The name of the Google Cloud Storage bucket.
        prefix (str): The GCS path prefix where summary files are stored.
        force (bool, optional): If True, forces a rebuild even if the DB exists. Defaults to False.

    Raises:
        Exception: If any error occurs during GCS access or database operations.
    """

    if not should_rebuild_db(force):
        return

    logger.info("🔁 Starting rebuild from GCS...")

    if not os.path.exists(DB_PATH):
        logging.info(f"Db file does not exist, creating: {DB_PATH}")
        await init_db()

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blobs = list(bucket.list_blobs(prefix=f"{prefix}/summary/"))
        logging.info(f"🔁 Found {len(blobs)} summary files in GCS")

        for blob in blobs:
            filename = os.path.basename(blob.name).replace(".summary.txt", "")
            logging.info(f"🔁 Processing {filename}")
            contents = blob.download_as_text()
            timestamp = datetime.utcnow().isoformat(timespec="seconds")

            await add_image(filename, label="", timestamp=timestamp)
            for line in contents.splitlines():
                tag = clean_tag_name(line)
                if tag:
                    await add_tag(tag)
                    await link_image_tag(filename, tag)

        logging.info("✅ DB rebuilt from GCS summaries")
    except Exception as e:
        logging.exception(f"🔥 Failed to rebuild DB from GCS: {e}")
