# Backend Skeleton

This folder contains the initial backend skeleton for a modular monolith with separate runtime roles:

- API/web role: `pokus_backend.api`
- Worker/scheduler role: `pokus_backend.worker`

## Local prerequisites

- Python 3.11+
- Docker Desktop (for local PostgreSQL runtime)

## Shared environment variables

- `APP_ENV` (default: `local`)
- `DATABASE_URL` (default: `postgresql://postgres:postgres@localhost:5432/pokus`)
- `API_HOST` (default: `127.0.0.1`)
- `API_PORT` (default: `8000`)
- `WORKER_POLL_SECONDS` (default: `5`)
- `APP_READ_TOKEN` (default: `dev-app-token`)
- `OPERATOR_SESSION_TOKEN` (default: `dev-operator-token`)
- `ADMIN_SESSION_TOKEN` (default: `dev-admin-token`)

Copy `.env.example` to your local environment before running checks.

## Start local PostgreSQL (Docker)

```powershell
cd Project
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml ps
```

Stop it:

```powershell
cd Project
docker compose -f docker-compose.dev.yml down
```

## Start API role

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.api
```

Health endpoint: `GET /health`

Auth boundary placeholder endpoints:

- `GET /app/*` with `X-App-Token: <APP_READ_TOKEN>`
- `GET /operator/*` with `X-Private-Session: <OPERATOR_SESSION_TOKEN|ADMIN_SESSION_TOKEN>`
- `GET /admin/*` with `X-Private-Session: <ADMIN_SESSION_TOKEN>`

## Start worker role

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.worker
```

Run one worker cycle:

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.worker --once
```

## Database checks and migrations

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.api --check
python -m pokus_backend.worker --check
python -m pokus_backend.db --check
python -m pokus_backend.db --migrate
```

## Smoke checks

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

## Concrete provider runtime validation path (M3)

Run this focused non-mock test to execute validation runtime against a live provider adapter and persist provider-attempt/candidate evidence:

```powershell
cd Project
$env:PYTHONPATH = "src"
$env:RUN_CONCRETE_PROVIDER_TEST = "1"
python -m pytest -q tests/test_validation_concrete_provider_runtime.py
```

The command calls the concrete Stooq adapter (`AAPL.US`) through the normal validation orchestrator path and writes runtime evidence to `provider_attempt` and `candidate_price_value`.

