from datetime import datetime, UTC
import re

from scripts.util import utc_now_iso, parse_utc_timestamp, clean_tag_name


def test_utc_now_iso_format():
    ts = utc_now_iso()
    # Should parse as valid datetime
    dt = datetime.fromisoformat(ts)
    assert dt.tzinfo == UTC
    assert ts.endswith("+00:00")


def test_parse_utc_timestamp_aware():
    ts = "2025-05-07T12:34:56+00:00"
    dt = parse_utc_timestamp(ts)
    assert isinstance(dt, datetime)
    assert dt.tzinfo == UTC


def test_parse_utc_timestamp_naive():
    ts = "2025-05-07T12:34:56"
    dt = parse_utc_timestamp(ts)
    assert isinstance(dt, datetime)
    assert dt.tzinfo == UTC


def test_clean_tag_name_basic():
    assert clean_tag_name("  Hello  ") == "hello"


def test_clean_tag_name_symbols_removed():
    assert clean_tag_name("Cats!") == "cats"
    assert clean_tag_name("tools,") == "tools"
    assert clean_tag_name('"misc"') == "misc"


def test_clean_tag_name_mixed_case_and_spaces():
    assert clean_tag_name("  Mixed   Case   Tag  ") == "mixed case tag"


def test_clean_tag_name_hyphens_and_underscores():
    assert clean_tag_name("Wi-Fi_Adapter") == "wi-fi_adapter"
