"""Logging configuration helpers for CLI and library usage."""
from __future__ import annotations

import logging


def configure_logging(log_level: str = "info") -> None:
    """Configure application logging with a simple terminal-friendly format."""
    level = getattr(logging, log_level.upper())
    logging.basicConfig(level=level, format="%(message)s", force=True)
