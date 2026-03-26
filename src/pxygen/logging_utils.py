"""Logging configuration helpers for CLI and library usage."""
from __future__ import annotations

import logging


def configure_logging(log_level: str = "info") -> None:
    """Configure application logging with a standard detailed format."""
    level = getattr(logging, log_level.upper())
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
