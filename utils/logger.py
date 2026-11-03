"""Execution log setup."""

import logging
from datetime import datetime
from pathlib import Path

FILE_ONLY = {"console": False}


def _console_allowed(record: logging.LogRecord) -> bool:
    return getattr(record, "console", True)


def run_stamp(moment: datetime | None = None) -> str:
    """Timestamp for file names: YYYY-MM-DD_HHMMSS.

    Includes the time so that two runs on the same day never overwrite each other.
    """
    return (moment or datetime.now()).strftime("%Y-%m-%d_%H%M%S")


def setup_logger(log_path: Path | None, level: str = "INFO") -> logging.Logger:
    """Send technical detail to the log file and only WARNING+ to the console.

    With `log_path=None` no log file is created (see the TODO in etf_checker.main).

    Records logged with `extra=FILE_ONLY` go to the file only (used for the
    per-ETF result line, which the CLI already prints, and its technical detail).
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(getattr(logging, level, logging.INFO))
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
        )
        root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter("    [%(levelname)s] %(message)s"))
    console_handler.addFilter(_console_allowed)
    root.addHandler(console_handler)

    # Keep third-party library noise out of the log
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return logging.getLogger("etf_checker")
