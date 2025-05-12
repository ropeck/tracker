import contextlib
import json
from typing import NoReturn

from scripts import logger_nfc


def test_log_tag_creates_entry(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "log.json"

    # Patch the module-level LOG_PATH
    monkeypatch.setattr(logger_nfc, "LOG_PATH", log_path)

    logger_nfc.log_tag("abc123", location="garage")

    assert log_path.exists()
    lines = log_path.read_text().splitlines()
    assert len(lines) == 1

    entry = json.loads(lines[0])
    assert entry["tag"] == "abc123"
    assert entry["location"] == "garage"
    assert "timestamp" in entry


def test_log_tag_appends_multiple_entries(tmp_path, monkeypatch) -> None:
    log_path = tmp_path / "log.json"
    monkeypatch.setattr(logger_nfc, "LOG_PATH", log_path)

    logger_nfc.log_tag("tag1")
    logger_nfc.log_tag("tag2", location="desk")

    lines = log_path.read_text().splitlines()
    assert len(lines) == 2  # noqa: PLR2004

    entry1 = json.loads(lines[0])
    entry2 = json.loads(lines[1])
    assert entry1["tag"] == "tag1"
    assert entry2["tag"] == "tag2"
    assert entry2["location"] == "desk"


def test_read_tag_is_placeholder() -> None:
    assert logger_nfc.read_tag() is None


def test_run_logs_tag_once(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(logger_nfc, "LOG_PATH", tmp_path / "log.json")
    monkeypatch.setattr(logger_nfc, "read_tag", lambda: "abc123")

    # Patch log_tag to only run once then break
    calls = []

    def fake_log_tag(tag_id, location="unknown") -> NoReturn:
        calls.append(tag_id)
        raise KeyboardInterrupt  # simulate stopping the loop

    monkeypatch.setattr(logger_nfc, "log_tag", fake_log_tag)

    with contextlib.suppress(KeyboardInterrupt):
        logger_nfc.run()

    assert calls == ["abc123"]
