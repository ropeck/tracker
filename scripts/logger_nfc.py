"""logger.py — Read and log NFC tag scans."""
import json
from datetime import datetime, timezone
from pathlib import Path

LOG_PATH = Path("data/log.json")


def log_tag(tag_id: str, location: str="unknown") -> None:
    """Save the location of a tag.

    Args:
        tag_id (_type_): _description_
        location (str, optional): _description_. Defaults to "unknown".
    """
    now = datetime.now(timezone.utc).isoformat()
    entry = {"tag": tag_id, "timestamp": now, "location": location}
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


# Placeholder
def read_tag() -> None:
    """Read and return tag UID."""
    return None  # noqa: RET501


def run() -> None:
    """Executive loop reading and logging tags."""
    while True:
        tag = read_tag()
        if tag:
            log_tag(tag)
