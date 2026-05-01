# M1 Workflow Review

Verdict: passed

Review date: 2026-05-01
Rerun branch: `task/m1-t56-rerun-m1-live-gate`

## Provenance Evidence

- Canonical task-to-commit and branch/merge mapping (T1-T17) with direct-on-main exception record remains embedded below.
- Fresh rerun of the milestone integration gate was executed on the review branch.

## Process Gate

- Legacy waiver applied per user instruction for M1 process-branch policy (first-generation orchestration run).
- `one task = one subagent branch`: **waived for M1**
- `no direct subagent implementation on main`: **waived for M1**
- `each task has traceable commit(s)`: **passed**
- `each task file uses canonical completion format`: **passed**
  - Resolved by T19 normalization; M1 task files use canonical completion status blocks.
- `merges to origin/main complete/coherent`: **passed**
  - M1 task commits are present on `origin/main`.

## Product Gate

- Milestone scope coverage: **passed**
  - T1-T17 artifacts exist and map to M1 scope.
- Focused validation/integration evidence: **passed**
  - Fresh rerun on 2026-05-01 completed successfully against live PostgreSQL.
  - Migration startup blocker is resolved; gate reaches full M1 integration assertions and returns `OK`.
- Open questions: **passed**
  - none; the blocker is concrete and reproducible.

## Failed Checks

- none

## Open Questions

- none

## Rerun Evidence

- Command run from `Project/`:
  - `$env:PYTHONPATH='src'; $env:TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/pokus'; python -m unittest tests.test_m1_integration_gate -v`
- Result on 2026-05-01: `OK`
- Environment assumptions:
  - Local PostgreSQL is reachable at `postgresql://postgres:postgres@localhost:5432/pokus`.
  - Command executed from `Project/` with `PYTHONPATH=src`.

## Embedded Evidence: Task-to-Commit Mapping (T1-T17)

| Task | Implementation Commit SHA | Commit Subject | Branch Provenance | Merge Path to `main` |
| --- | --- | --- | --- | --- |
| T1 | `4da49bd` | feat(t1): scaffold backend api and worker roles | `origin/task/t1-backend-skeleton` (auditable) | Merge commit `0df03e8` into `main` |
| T2 | `cf8f12e` | feat: add postgres migration baseline for T2 | unavailable from current refs | direct commit on `main` |
| T3 | `5a05f95` | Add exchange and instrument type reference schema | `task/m1-t3-reference-schema` (local ref retained) | direct commit on `main` |
| T4 | `9153778` | feat: add instrument identity and listing schema | unavailable from current refs | direct commit on `main` |
| T5 | `5c5bab5` | feat: add universe change audit schema | `task/M1-T5-universe-change-audit-schema` (local ref retained) | direct commit on `main` |
| T6 | `3d83609` | Implement T6 provider attempt evidence schema | unavailable from current refs | direct commit on `main` |
| T7 | `77b3b6f` | feat: add price record schema | unavailable from current refs | direct commit on `main` |
| T8 | `a03bab1` | Implement load job model and transition semantics | unavailable from current refs | direct commit on `main` |
| T9 | `055bace` | Implement T9 exchange-day load outcome schema | unavailable from current refs | direct commit on `main` |
| T10 | `ab60240` | Add publication and quality evidence schema | `task/M1-T10-publication-quality-schema` (local ref retained) | direct commit on `main` |
| T11 | `10f00b4` | Add durable signal event and statistic schema | `task/M1-T11-signal-schema` (local ref retained) | direct commit on `main` |
| T12 | `531af22` | Add admin command and audit record schema | unavailable from current refs | direct commit on `main` |
| T13 | `46e7608` | Implement M1 T13 exchange calendar abstraction | `task/M1-T13-calendar-abstraction` (local ref retained) | direct commit on `main` |
| T14 | `182b768` | feat(m1): complete T14 auth boundary foundations | unavailable from current refs | direct commit on `main` |
| T15 | `c5beede` | Implement T15 internal platform health reporting | unavailable from current refs | direct commit on `main` |
| T16 | `b37a27e` | Implement M1 T16 observability plumbing | unavailable from current refs | direct commit on `main` |
| T17 | `78e4bc1` | test: add milestone 1 integration gate for T17 | unavailable from current refs | direct commit on `main` |

## Embedded Evidence: Policy Exception Record (Direct-On-Main)

Direct-on-main M1 implementation commits recorded as explicit legacy exceptions:

`cf8f12e`, `5a05f95`, `9153778`, `5c5bab5`, `3d83609`, `77b3b6f`, `a03bab1`, `055bace`, `ab60240`, `10f00b4`, `531af22`, `46e7608`, `182b768`, `c5beede`, `b37a27e`, `78e4bc1`

## Final Recommendation

M1 live PostgreSQL integration gate evidence is now current and reproducible; the prior migration-startup blocker is closed.
