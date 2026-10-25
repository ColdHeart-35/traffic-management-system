"""Logging setup. Never log passwords, tokens or identifiable video data."""
from __future__ import annotations

import logging

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    _configured = True
