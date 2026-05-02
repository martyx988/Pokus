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
- keyed probe credentials (required for full keyed-source runs):
  - `EODHD_API_KEY`
  - `FMP_API_KEY`
  - `FINNHUB_API_KEY`
  - `ALPHA_VANTAGE_API_KEY`
  - `TIINGO_API_KEY`
  - `MARKETSTACK_API_KEY`
  - `POLYGON_API_KEY`
  - `TWELVE_DATA_API_KEY`
- optional probe credential:
  - `OPENFIGI_API_KEY` (optional, improves probe quota/availability)

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

Run concrete M4 runtime trust loop (scheduler -> outcome aggregation -> publication/read-model refresh):

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.worker --run-opening-trust-loop --trust-loop-date 2026-05-01 --trust-loop-exchanges NYSE
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

## Milestone 3.1 rerun path (live probes + combined loader)

Required setup:

```powershell
cd Project
Copy-Item .env.example .env
```

Fill real API keys only in local `.env` (never commit).

### Local dev path

Run migrations:

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.db --migrate
```

Run live source probes through worker runtime:

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.worker --run-live-source-probes --source-probe-run-key m31-live-local-2026-05-02 --source-probe-sources YFINANCE,STOOQ,AKSHARE,EODHD,FMP,FINNHUB,ALPHA_VANTAGE,TIINGO,MARKETSTACK,POLYGON,TWELVE_DATA,NASDAQ_TRADER,NYSE,PSE_PSE_EDGE,OPENFIGI,NASDAQ_DATA_LINK
```

Run combined universe loader through worker runtime:

```powershell
cd Project
$env:PYTHONPATH = "src"
python -m pokus_backend.worker --run-combined-universe-loader
```

Expected evidence outputs:

- DB `source_validation_record` rows for the run key
- worker stdout `worker-live-source-probe-result ...` lines
- worker stdout `worker-combined-universe-loader-ok ...` summary

### Docker path

Start DB:

```powershell
cd Project
docker compose -f docker-compose.dev.yml up -d postgres
```

Run migrations from host against Docker DB:

```powershell
cd Project
$env:PYTHONPATH = "src"
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/pokus"
python -m pokus_backend.db --migrate
```

Run live probes in Docker worker service:

```powershell
cd Project
docker compose -f docker-compose.dev.yml run --rm dev-worker --run-live-source-probes --source-probe-run-key m31-live-docker-2026-05-02 --source-probe-sources YFINANCE,STOOQ,AKSHARE,EODHD,FMP,FINNHUB,ALPHA_VANTAGE,TIINGO,MARKETSTACK,POLYGON,TWELVE_DATA,NASDAQ_TRADER,NYSE,PSE_PSE_EDGE,OPENFIGI,NASDAQ_DATA_LINK
```

Run combined loader in Docker worker service:

```powershell
cd Project
docker compose -f docker-compose.dev.yml run --rm dev-worker --run-combined-universe-loader
```

