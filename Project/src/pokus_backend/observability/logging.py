from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_LOGGER_NAME = "pokus_backend.observability"
_REDACT_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "authorization",
        "cookie",
        "set-cookie",
        "api_key",
        "key",
    }
)


def configure_logging() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_event(event: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "ts": datetime.now(UTC).isoformat(),
        "event": event,
        **_redact_mapping(fields),
    }
    configure_logging().info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    return payload


def log_job_event(event: str, *, job_id: int | None, state: str, **fields: Any) -> dict[str, Any]:
    return log_event(event, category="job_lifecycle", job_id=job_id, state=state, **fields)


def log_admin_command_event(event: str, *, command_type: str, actor_id: str, **fields: Any) -> dict[str, Any]:
    return log_event(event, category="admin_command", command_type=command_type, actor_id=actor_id, **fields)


def log_job_lock_event(event: str, *, job_id: int | None, lock_token: str | None, **fields: Any) -> dict[str, Any]:
    return log_event(event, category="job_lock", job_id=job_id, lock_token=lock_token, **fields)


def _redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, item in value.items():
        if key.lower() in _REDACT_KEYS:
            redacted[key] = "***"
        elif isinstance(item, Mapping):
            redacted[key] = _redact_mapping(item)
        elif isinstance(item, list):
            redacted[key] = [_redact_value(v) for v in item]
        else:
            redacted[key] = _redact_value(item)
    return redacted


def _redact_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(v) for v in value]
    return value
