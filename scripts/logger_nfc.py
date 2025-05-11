# logger.py — Read and log NFC tag scans
import datetime
import json
from pathlib import Path

LOG_PATH = Path("data/log.json")


def log_tag(tag_id, location="unknown"):
    now = datetime.datetime.now().isoformat()
    entry = {"tag": tag_id, "timestamp": now, "location": location}
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# Placeholder
def read_tag():
    # Replace this with actual NFC read logic
    return None


def run():
    while True:
        tag = read_tag()
        if tag:
            log_tag(tag)
