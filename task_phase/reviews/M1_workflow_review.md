# M1 Workflow Review

Verdict: blocked

## Provenance Evidence

- Canonical task-to-commit and branch/merge provenance ledger: `task_phase/reviews/M1_provenance_ledger.md`.
- Direct-on-main policy exceptions for M1 are explicitly recorded in the same ledger under `## Policy Exception Record (Direct-On-Main)`.

## Process Gate

- Legacy waiver applied per user instruction for M1 process-branch policy (first-generation orchestration run).
- `one task = one subagent branch`: **waived for M1**
- `no direct subagent implementation on main`: **waived for M1**
- `each task has traceable commit(s)`: **passed via M1 provenance ledger**
- `each task file marked done with short summary`: **partial/failed**
  - Most tasks include done summaries, but completion formatting is inconsistent (`### Status` block missing in some files).
- `merges to origin/main complete/coherent`: **passed**
  - M1 task commits are present on `origin/main`.

## Product Gate

- Milestone scope coverage: **passed**
  - T1-T17 artifacts exist and map to M1 scope.
- Focused validation/integration evidence: **passed via explicit waiver**
  - Integration suite rerun on 2026-05-01 and returned `OK (skipped=1)` for live PostgreSQL gate.
  - Explicit waiver recorded: `task_phase/reviews/M1_T20_live_gate_waiver_2026-05-01.md`.
- Open questions: **passed**
  - none (live DB evidence requirement closed by dated explicit waiver decision).

## Failed Checks

1. Inconsistent task completion-status formatting in some M1 task files.
2. Live PostgreSQL integration gate execution unavailable in current environment; closed by explicit waiver record.

## Open Questions

- none

## Gap Tasks Added

- `task_phase/tasks/M1/T18.md` (provenance ledger + direct-on-main exception record)
- `task_phase/tasks/M1/T19.md` (status block normalization across M1 task files)
- `task_phase/tasks/M1/T20.md` (live PostgreSQL integration evidence or explicit waiver path)

## Final Recommendation

Keep M1 in `in progress` until process-formatting gap is closed. Product live-gate evidence blocker is resolved by T20 waiver path.
