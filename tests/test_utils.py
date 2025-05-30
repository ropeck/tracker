from datetime import UTC, datetime

from scripts.util import clean_tag_name, parse_utc_timestamp, utc_now_iso


def test_utc_now_iso_format() -> None:
    ts = utc_now_iso()
    # Should parse as valid datetime
    dt = datetime.fromisoformat(ts)
    assert dt.tzinfo == UTC
    assert ts.endswith("+00:00")


def test_parse_utc_timestamp_aware() -> None:
    ts = "2025-05-07T12:34:56+00:00"
    dt = parse_utc_timestamp(ts)
    assert isinstance(dt, datetime)
    assert dt.tzinfo == UTC


def test_parse_utc_timestamp_naive() -> None:
    ts = "2025-05-07T12:34:56"
    dt = parse_utc_timestamp(ts)
    assert isinstance(dt, datetime)
    assert dt.tzinfo == UTC


def test_clean_tag_name_basic() -> None:
    assert clean_tag_name("  Hello  ") == "hello"


def test_clean_tag_name_symbols_removed() -> None:
    assert clean_tag_name("Cats!") == "cats"
    assert clean_tag_name("tools,") == "tools"
    assert clean_tag_name('"misc"') == "misc"


def test_clean_tag_name_mixed_case_and_spaces() -> None:
    assert clean_tag_name("  Mixed   Case   Tag  ") == "mixed case tag"


def test_clean_tag_name_hyphens_and_underscores() -> None:
    assert clean_tag_name("Wi-Fi_Adapter") == "wi-fi_adapter"
