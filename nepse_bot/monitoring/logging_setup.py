"""
Centralized logging setup.

Creates console + rotating file handlers under logs/.
Safe to call multiple times; subsequent calls are no-ops unless force=True.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

_CONFIGURED = False


def setup_logging(
    level: str = "INFO",
    log_dir: str | Path = "logs",
    name: str = "nepse_bot",
    force: bool = False,
) -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger(name)

    if _CONFIGURED and not force:
        return logger

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(logger.level)
    logger.addHandler(console)

    file_handler = TimedRotatingFileHandler(
        filename=log_path / "nepse_bot.log",
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logger.level)
    logger.addHandler(file_handler)

    _CONFIGURED = True
    logger.info("Logging initialized | level=%s | dir=%s", level.upper(), log_path)
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    base = "nepse_bot"
    if name:
        return logging.getLogger(f"{base}.{name}")
    return logging.getLogger(base)
