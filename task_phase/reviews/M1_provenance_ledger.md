# M1 Provenance Ledger

This ledger records durable M1 task-to-commit evidence from local git history and current refs. It also records explicit policy exceptions where implementation landed directly on `main`.

## Task-to-Commit Mapping (T1-T17)

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

## Policy Exception Record (Direct-On-Main)

M1 policy requires branch-scoped implementation and merge flow. The following M1 implementation commits were applied directly on `main` and are recorded as explicit exceptions due to first-generation orchestration/legacy waiver constraints.

- `cf8f12e` (T2)
- `5a05f95` (T3)
- `9153778` (T4)
- `5c5bab5` (T5)
- `3d83609` (T6)
- `77b3b6f` (T7)
- `a03bab1` (T8)
- `055bace` (T9)
- `ab60240` (T10)
- `10f00b4` (T11)
- `531af22` (T12)
- `46e7608` (T13)
- `182b768` (T14)
- `c5beede` (T15)
- `b37a27e` (T16)
- `78e4bc1` (T17)

## Verification Notes

- Ledger coverage check: tasks `T1` through `T17` all mapped.
- SHA resolvability check: each listed SHA resolves in local clone.
- Branch provenance is marked `unavailable from current refs` where no durable branch pointer is present.
