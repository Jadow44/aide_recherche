"""Centralized activity logging for the Semantic Scholar helper tools."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict

_LOGGER: logging.Logger | None = None


def _ensure_logger() -> logging.Logger:
    """Return a configured logger that writes to ``logs/activity.log``."""

    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER

    base_dir = Path(__file__).resolve().parent
    log_dir = base_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "activity.log"

    logger = logging.getLogger("semantic_scraper.activity")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _LOGGER = logger
    return logger


def _serialize_payload(payload: Dict[str, Any]) -> str:
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        return json.dumps(payload, ensure_ascii=False, default=str)


def log_event(marker: str, message: str, **details: Any) -> None:
    """Write a structured log entry tagged with ``marker``."""

    logger = _ensure_logger()
    payload: Dict[str, Any] = {"message": message}
    if details:
        payload["details"] = details
    serialized = _serialize_payload(payload)
    logger.info("[%s] %s", marker, serialized)


def log_exception(marker: str, message: str, exc: Exception, **details: Any) -> None:
    """Convenience helper to log exceptions with contextual data."""

    error_details = dict(details)
    error_details["exception"] = f"{type(exc).__name__}: {exc}"
    log_event(marker, message, **error_details)
