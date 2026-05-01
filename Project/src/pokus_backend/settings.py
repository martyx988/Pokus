from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    api_host: str
    api_port: int
    worker_poll_seconds: float


def load_settings() -> Settings:
    return Settings(
        environment=os.getenv("APP_ENV", "local"),
        database_url=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pokus"),
        api_host=os.getenv("API_HOST", "127.0.0.1"),
        api_port=int(os.getenv("API_PORT", "8000")),
        worker_poll_seconds=float(os.getenv("WORKER_POLL_SECONDS", "5")),
    )

