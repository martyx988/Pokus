# Development Runtime (Current)

Current local development runtime is Docker Desktop with:

- `Project/docker-compose.dev.yml`
- PostgreSQL service `pokus-postgres-dev`

This runtime is for local development and validation only. It is intentionally replaceable when moving to production VPS.

## Replaceability Rule

- Application code must stay environment-driven (`DATABASE_URL`, tokens, ports).
- Do not hardcode Docker-only hostnames or container assumptions into business logic.
- VPS deployment may replace this compose file with a different topology (service names, volumes, networking, secrets), while keeping the same app-level environment contract.

## Quick Start

```powershell
cd Project
docker compose -f docker-compose.dev.yml up -d
```

Then use:

- `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pokus`
