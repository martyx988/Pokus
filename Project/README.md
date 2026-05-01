# Backend Skeleton

This folder contains the initial backend skeleton for a modular monolith with separate runtime roles:

- API/web role: `pokus_backend.api`
- Worker/scheduler role: `pokus_backend.worker`

## Local prerequisites

- Python 3.11+

## Shared environment variables

- `APP_ENV` (default: `local`)
- `DATABASE_URL` (default: `postgresql://postgres:postgres@localhost:5432/pokus`)
- `API_HOST` (default: `127.0.0.1`)
- `API_PORT` (default: `8000`)
- `WORKER_POLL_SECONDS` (default: `5`)

## Start API role

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.api
```

Health endpoint: `GET /health`

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

## Smoke checks

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m unittest discover -s tests -v
```

