"""General utility functions."""

import re
from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Datetime now in UTC."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def parse_utc_timestamp(ts: str) -> datetime:
    """Make stanard tz datetime from time string.

    Args:
        ts (str): String timestamp

    Returns:
        datetime: time in UTC
    """
    dt = datetime.fromisoformat(ts)
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def clean_tag_name(tag: str) -> str:
    """Make tag standard.

    Normalize a tag by:
    - Lowercasing
    - Stripping whitespace
    - Removing surrounding quotes or commas
    - Removing non-alphanumeric characters (except dashes and underscores)
    """
    tag = tag.strip().lower()
    tag = tag.strip("\"',")  # outer quotes
    tag = re.sub(r"[^\w\- ]", "", tag)  # remove unwanted symbols
    tag = re.sub(r"\s+", " ", tag)  # collapse multiple spaces
    return tag.strip()
