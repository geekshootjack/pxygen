"""Logging configuration helpers for CLI and library usage."""
from __future__ import annotations

import logging
from pathlib import Path


def configure_logging(log_level: str = "info", log_file: str | None = None) -> None:
    """Configure application logging with a standard detailed format."""
    level = getattr(logging, log_level.upper())
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )
