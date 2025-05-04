import json
import logging
import os
from datetime import datetime
from pathlib import Path

from google.cloud import storage

from scripts.db import DB_PATH, add_image, add_tag, link_image_tag
from scripts.util import clean_tag_name


async def rebuild_db_from_gcs(bucket_name: str, prefix: str):
    if Path(DB_PATH).exists():
        logging.info("📦 DB already exists, skipping rebuild from GCS.")
        return

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
