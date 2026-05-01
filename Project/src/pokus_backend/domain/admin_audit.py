from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Mapping


class AdminCommandType(StrEnum):
    CONFIGURATION_CHANGE = "configuration_change"
    VALIDATION_TRIGGER = "validation_trigger"
    HISTORICAL_REPROCESS = "historical_reprocess"
    RETENTION_ACTION = "retention_action"
    JOB_RETRY = "job_retry"
    JOB_CANCEL = "job_cancel"
    JOB_MARK_FAILED = "job_mark_failed"


MUTATING_ADMIN_COMMAND_TYPES = frozenset(
    {
        AdminCommandType.CONFIGURATION_CHANGE,
        AdminCommandType.HISTORICAL_REPROCESS,
        AdminCommandType.RETENTION_ACTION,
        AdminCommandType.JOB_RETRY,
        AdminCommandType.JOB_CANCEL,
        AdminCommandType.JOB_MARK_FAILED,
    }
)

_REDACTED_METADATA_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "authorization",
        "cookie",
        "set-cookie",
        "api_key",
    }
)


@dataclass(slots=True)
class AdminCommand:
    id: int | None
    command_type: AdminCommandType
    actor_id: str
    actor_type: str
    reason: str | None = None
    load_job_id: int | None = None
    target_type: str | None = None
    target_id: str | None = None
    request_id: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.command_type in MUTATING_ADMIN_COMMAND_TYPES and not self.reason:
            raise ValueError("Mutating admin commands require a non-empty reason.")


@dataclass(slots=True)
class AuditRecord:
    id: int | None
    action: str
    actor_id: str
    actor_type: str
    metadata: Mapping[str, str] = field(default_factory=dict)
    admin_command_id: int | None = None
    load_job_id: int | None = None
    target_type: str | None = None
    target_id: str | None = None
    request_id: str | None = None
    created_at: datetime | None = None

    def __post_init__(self) -> None:
        normalized = {key.lower() for key in self.metadata}
        blocked = normalized.intersection(_REDACTED_METADATA_KEYS)
        if blocked:
            key_list = ", ".join(sorted(blocked))
            raise ValueError(f"Audit metadata contains sensitive keys: {key_list}")
