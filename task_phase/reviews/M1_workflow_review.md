# M1 Workflow Review

Verdict: blocked

## Process Gate

- Legacy waiver applied per user instruction for M1 process-branch policy (first-generation orchestration run).
- `one task = one subagent branch`: **waived for M1**
- `no direct subagent implementation on main`: **waived for M1**
- `each task has traceable commit(s)`: **waived for M1**
- `each task file marked done with short summary`: **partial/failed**
  - Most tasks include done summaries, but completion formatting is inconsistent (`### Status` block missing in some files).
- `merges to origin/main complete/coherent`: **passed**
  - M1 task commits are present on `origin/main`.

## Product Gate

- Milestone scope coverage: **passed**
  - T1-T17 artifacts exist and map to M1 scope.
- Focused validation/integration evidence: **partial/failed**
  - Integration suite exists and passed with one documented skip.
  - Live PostgreSQL integration path is env-gated and not executed without `TEST_DATABASE_URL`/`DATABASE_URL`.
- Open questions: **failed**
  - `none` is not yet true due unresolved live DB gate execution evidence.

## Failed Checks

1. Inconsistent task completion-status formatting in some M1 task files.
2. Live PostgreSQL integration gate still pending environment-backed execution evidence.

## Open Questions

- Can CI/local review environment provide reachable PostgreSQL and schema-create privileges so `tests.test_m1_integration_gate` runs unskipped?

## Gap Tasks Added

- `task_phase/tasks/M1/T18.md` (provenance ledger + direct-on-main exception record)
- `task_phase/tasks/M1/T19.md` (status block normalization across M1 task files)
- `task_phase/tasks/M1/T20.md` (live PostgreSQL integration evidence or explicit waiver path)

## Final Recommendation

Keep M1 in `in progress`. Resolve process and live-gate evidence gaps via follow-up tasks, then rerun workflow review.
