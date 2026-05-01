from __future__ import annotations

from pokus_backend.jobs.load_job import LoadJobState
from pokus_backend.observability.logging import log_job_event


class InvalidLoadJobTransition(ValueError):
    pass


ALLOWED_LOAD_JOB_STATE_TRANSITIONS: dict[LoadJobState, frozenset[LoadJobState]] = {
    LoadJobState.QUEUED: frozenset({LoadJobState.RUNNING, LoadJobState.CANCELLED}),
    LoadJobState.RUNNING: frozenset(
        {
            LoadJobState.RETRY_WAIT,
            LoadJobState.SUCCEEDED,
            LoadJobState.FAILED,
            LoadJobState.CANCELLED,
            LoadJobState.STALE_ABANDONED,
        }
    ),
    LoadJobState.RETRY_WAIT: frozenset(
        {
            LoadJobState.QUEUED,
            LoadJobState.FAILED,
            LoadJobState.CANCELLED,
            LoadJobState.STALE_ABANDONED,
        }
    ),
    LoadJobState.STALE_ABANDONED: frozenset(
        {
            LoadJobState.QUEUED,
            LoadJobState.FAILED,
            LoadJobState.CANCELLED,
        }
    ),
    LoadJobState.SUCCEEDED: frozenset(),
    LoadJobState.FAILED: frozenset(),
    LoadJobState.CANCELLED: frozenset(),
}


def can_transition_load_job_state(current: LoadJobState, target: LoadJobState) -> bool:
    if current == target:
        return True
    return target in ALLOWED_LOAD_JOB_STATE_TRANSITIONS[current]


def transition_load_job_state(current: LoadJobState, target: LoadJobState) -> LoadJobState:
    if not can_transition_load_job_state(current, target):
        raise InvalidLoadJobTransition(f"invalid load job transition: {current.value} -> {target.value}")
    event = _event_name_for_transition(current=current, target=target)
    if event is not None:
        log_job_event(event, job_id=None, state=target.value, previous_state=current.value)
    return target


def _event_name_for_transition(current: LoadJobState, target: LoadJobState) -> str | None:
    if current == target:
        return None
    names: dict[LoadJobState, str] = {
        LoadJobState.QUEUED: "job.created",
        LoadJobState.RUNNING: "job.started",
        LoadJobState.SUCCEEDED: "job.finished",
        LoadJobState.FAILED: "job.failed",
        LoadJobState.RETRY_WAIT: "job.retry_scheduled",
        LoadJobState.CANCELLED: "job.cancelled",
        LoadJobState.STALE_ABANDONED: "job.stale_abandoned",
    }
    return names[target]

