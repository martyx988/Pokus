# M1 T20 Evidence/Waiver Record

Date: 2026-05-01
Decision: Explicit waiver applied for live PostgreSQL M1 integration-gate execution evidence.

## Validation Command

From `Project/`:

`$env:PYTHONPATH='src'; python -m unittest tests.test_entrypoints_smoke tests.test_auth_boundary tests.test_calendar_service tests.test_load_jobs tests.test_health_reporting tests.test_observability tests.test_m1_integration_gate -v`

## Result

- Outcome date: 2026-05-01
- Result: `OK (skipped=1)`
- Skipped test: `tests.test_m1_integration_gate.Milestone1IntegrationGateTests.test_m1_platform_foundation_integration_gate`
- Skip reason: `Set TEST_DATABASE_URL or DATABASE_URL for T17 integration gate tests.`

## Environment Condition

- `TEST_DATABASE_URL`: unset
- `DATABASE_URL`: unset

## Waiver Statement

M1 product gate closure for live PostgreSQL execution evidence is waived for this run due to unavailable reachable PostgreSQL credentials/endpoint with schema-create privileges in the current review environment. This waiver closes the T20 blocker path and is linked in M1 review artifacts.
