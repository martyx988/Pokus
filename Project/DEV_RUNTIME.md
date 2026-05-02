# Development Runtime (Current)

Current local development runtime is Docker Desktop with:

- `Project/docker-compose.dev.yml`
- PostgreSQL service `pokus-postgres-dev`
- optional worker runtime container `pokus-dev-worker`

This runtime is for local development and validation only. It is intentionally replaceable when moving to production VPS.

## Replaceability Rule

- Application code must stay environment-driven (`DATABASE_URL`, tokens, ports).
- Do not hardcode Docker-only hostnames or container assumptions into business logic.
- VPS deployment may replace this compose file with a different topology (service names, volumes, networking, secrets), while keeping the same app-level environment contract.

## Quick Start

```powershell
cd Project
Copy-Item .env.example .env
docker compose -f docker-compose.dev.yml up -d postgres
```

Then use:

- `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pokus`

## Milestone 3.1 rerun contract

Credentials are environment-driven only. Keep provider keys in local `.env`; do not store real secrets in source control.

Required keyed credentials:

- `EODHD_API_KEY`
- `FMP_API_KEY`
- `FINNHUB_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `TIINGO_API_KEY`
- `MARKETSTACK_API_KEY`
- `POLYGON_API_KEY`
- `TWELVE_DATA_API_KEY`

Optional:

- `OPENFIGI_API_KEY` (probe still runs without it, but can have tighter quota/rate behavior)

## Milestone 3.1 rerun commands

1. Migrate database schema:

```powershell
cd Project
$env:PYTHONPATH = "src"
$env:DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/pokus"
python -m pokus_backend.db --migrate
```

2. Live source probes (Docker worker runtime path):

```powershell
cd Project
docker compose -f docker-compose.dev.yml run --rm dev-worker --run-live-source-probes --source-probe-run-key m31-live-docker-2026-05-02 --source-probe-sources YFINANCE,STOOQ,AKSHARE,EODHD,FMP,FINNHUB,ALPHA_VANTAGE,TIINGO,MARKETSTACK,POLYGON,TWELVE_DATA,NASDAQ_TRADER,NYSE,PSE_PSE_EDGE,OPENFIGI,NASDAQ_DATA_LINK
```

3. Combined universe loader (Docker worker runtime path):

```powershell
cd Project
docker compose -f docker-compose.dev.yml run --rm dev-worker --run-combined-universe-loader
```

Expected evidence output:

- live probes print per-source `worker-live-source-probe-result` lines and persist `source_validation_record` entries by run key
- combined loader prints `worker-combined-universe-loader-ok` with persisted candidate/listing summary
