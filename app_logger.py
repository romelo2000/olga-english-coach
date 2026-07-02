"""Lightweight logger for Olga English Coach.

Writes to ~/Library/Application Support/OlgaEnglishCoach/app.log
Rotates when file exceeds 500KB (keeps last 200KB).
"""

from __future__ import annotations

import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

_APP_DIR = Path.home() / "Library" / "Application Support" / "OlgaEnglishCoach"
_LOG_PATH = _APP_DIR / "app.log"

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    _APP_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("olga")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    handler = RotatingFileHandler(
        _LOG_PATH, maxBytes=500_000, backupCount=1, encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    _logger = logger
    return logger


def log_exception(exc: BaseException, context: str = "") -> None:
    logger = get_logger()
    msg = f"{context}: {exc}" if context else str(exc)
    logger.exception(msg)


def log_warning(msg: str, context: str = "") -> None:
    logger = get_logger()
    full = f"{context}: {msg}" if context else msg
    logger.warning(full)


def log_info(msg: str) -> None:
    get_logger().info(msg)
