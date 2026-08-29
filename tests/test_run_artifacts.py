import logging
from datetime import UTC, datetime
from pathlib import Path

from oracle_relationship_discovery.cli import configure_logging, create_run_directory


def test_run_directory_contains_exact_timestamp_and_mode(tmp_path: Path):
    started = datetime(2026, 8, 29, 10, 20, 30, 123456, tzinfo=UTC)
    run_directory = create_run_directory(tmp_path / "output", "metadata-only", started)

    assert run_directory.is_dir()
    assert run_directory.name == "2026-08-29_10-20-30-123456_+0000_metadata-only"


def test_console_logging_is_appended_to_one_comprehensive_log(tmp_path: Path):
    log_path = tmp_path / "logs" / "oracle-relationship-discovery.log"
    configure_logging(False, log_path)
    logging.getLogger("test.operation").info("first run marker")
    configure_logging(False, log_path)
    logging.getLogger("test.operation").info("second run marker")
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_path.read_text(encoding="utf-8")
    assert "first run marker" in content
    assert "second run marker" in content
