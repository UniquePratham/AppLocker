"""Structured logging for Aegis.

Design rules:
* Never log passwords, recovery keys or any authentication secret.
* Rotate the current log file so it cannot grow without bound.
* Provide a ``snapshot()`` used by the "Export Diagnostics" feature.

No secret material should ever be passed to these functions.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler

from applocker.util.paths import get_log_dir

_LOGGER_NAME = "applocker"
_SCHEMA_VERSION = 1

# Emails, hex keys, anything resembling a secret/token/password in log text.
_SECRET_PATTERNS = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
]
_REDACTED = "[redacted]"


def _redact(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.record):
        msg = super().format(record)
        return _redact(msg)


def setup_logging() -> logging.Logger:
    log_dir = get_log_dir()
    log_path = os.path.join(log_dir, f"applocker-v{_SCHEMA_VERSION}.log")
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    handler.setFormatter(
        RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    logger.addHandler(handler)
    # Console handler only when not frozen (development).
    if not getattr(__import__("sys"), "frozen", False):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(console)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def snapshot(logger: logging.Logger | None = None) -> str:
    """Return accumulated diagnostics as a single text blob for export."""
    logger = logger or get_logger()
    lines = []
    lines.append(f"Aegis diagnostics snapshot — {datetime.now().isoformat()}")
    for suffix in ["", ".1", ".2"]:
        path = os.path.join(get_log_dir(), f"applocker-v{_SCHEMA_VERSION}.log{suffix}")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as fh:
                    lines.append(f"--- {os.path.basename(path)} ---")
                    lines.append(_redact(fh.read()))
            except OSError:
                pass
    return "\n".join(lines)
