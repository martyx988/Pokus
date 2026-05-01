from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MetricsStore:
    counters: dict[str, float] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    timers: dict[str, list[float]] = field(default_factory=dict)

    def reset(self) -> None:
        self.counters.clear()
        self.gauges.clear()
        self.timers.clear()


STORE = MetricsStore()


def increment(name: str, value: float = 1.0) -> None:
    STORE.counters[name] = STORE.counters.get(name, 0.0) + value


def set_gauge(name: str, value: float) -> None:
    STORE.gauges[name] = value


def observe_seconds(name: str, value: float) -> None:
    STORE.timers.setdefault(name, []).append(value)


def record_api_health(ok: bool) -> None:
    set_gauge("api.health", 1.0 if ok else 0.0)


def record_database_connectivity(ok: bool) -> None:
    set_gauge("database.connectivity", 1.0 if ok else 0.0)


def record_worker_heartbeat(ok: bool) -> None:
    set_gauge("worker.heartbeat", 1.0 if ok else 0.0)


def record_scheduler_heartbeat(ok: bool) -> None:
    set_gauge("scheduler.heartbeat", 1.0 if ok else 0.0)


def record_queue_depth(depth: int) -> None:
    set_gauge("queue.depth", float(depth))


def record_pending_job_age(seconds: float | None) -> None:
    if seconds is None:
        return
    set_gauge("queue.oldest_pending_age_seconds", seconds)


def record_job_state_count(state: str, count: int) -> None:
    set_gauge(f"jobs.state_count.{state}", float(count))


def record_api_error(status_code: int) -> None:
    increment("api.errors")
    increment(f"api.errors.{status_code}")
