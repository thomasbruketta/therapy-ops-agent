"""Structured JSON logging helpers for workflow events."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


class JsonFormatter(logging.Formatter):
    """Format log records as JSON with required workflow fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workflow_step": getattr(record, "workflow_step", "unknown"),
            "client_name": mask_client_name(getattr(record, "client_name", "")),
            "idempotency_key": getattr(record, "idempotency_key", None),
            "status": getattr(record, "status", record.levelname.lower()),
        }

        error_code = getattr(record, "error_code", None)
        error_message = getattr(record, "error_message", None)
        if error_code is not None:
            payload["error_code"] = error_code
        if error_message is not None:
            payload["error_message"] = error_message

        message = record.getMessage()
        if message:
            payload["message"] = message

        return json.dumps(payload, ensure_ascii=False)


def mask_client_name(name: str) -> str:
    """Mask a client name while keeping enough entropy for debugging."""
    if not name:
        return ""

    visible = 1
    if len(name) <= visible:
        return "*"
    return f"{name[:visible]}{'*' * (len(name) - visible)}"


def get_structured_logger(name: str = "therapy_ops") -> logging.Logger:
    """Return a logger configured to emit JSON records."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_workflow_event(
    logger: logging.Logger,
    *,
    workflow_step: str,
    client_name: str,
    idempotency_key: str,
    status: str,
    message: str = "",
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Emit a structured workflow event."""
    extra: dict[str, Any] = {
        "workflow_step": workflow_step,
        "client_name": client_name,
        "idempotency_key": idempotency_key,
        "status": status,
        "error_code": error_code,
        "error_message": error_message,
    }
    logger.info(message, extra=extra)
