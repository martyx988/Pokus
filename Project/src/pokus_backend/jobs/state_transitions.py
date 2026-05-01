from __future__ import annotations

from pokus_backend.jobs.load_job import LoadJobState


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
    return target

