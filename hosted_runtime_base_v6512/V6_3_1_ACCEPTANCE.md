# ScoreMax V6.3.1 — Student UX V2 Acceptance

**Candidate status:** `STUDENT_UX_V2_CANDIDATE_PENDING_WINDOWS_BROWSER_ACCEPTANCE`  
**Date:** 17 August 2026

## Automated gates

| Gate | Status | Evidence |
|---|---|---|
| Parent / rollback preserved | PASSED | V6.3.0 RC2 SHA-256 retained; V6.3.1 built separately |
| Python compilation | PASSED | 7 core Python files |
| Jinja syntax | PASSED | 107/107 templates parse |
| Inherited regression | PASSED | 441/441 current descendant checks |
| V6.3 mastery/application | PASSED | 82/82 |
| V6.3.1 UX V2 | PASSED | 27/27 |
| Total deterministic | PASSED | **550/550** |
| Large synthetic mastery attack | PASSED | 10,000 learners; 200,000 randomized invariant checks; 0 detailed failures; 0 fuzz failures; 0 QA→LIVE leakage |
| Backup → mutate → restore | PASSED | restored probe state + SQLite integrity `ok` |
| Reviewer forward dependency | PASSED | disabled from forward shell |
| Runtime/cache/privacy package hygiene | PASSED at packaging gate | no DB/cache/upload/secret artifacts included |
| Real Windows launch | **PENDING** | must be run on user's Windows machine |
| Real browser visual acceptance | **PENDING** | Edge/Chrome + mobile width + keyboard + 200% zoom |
| Public Internet production deployment | N/A | this is an internal-live UX candidate, not public release |

## Important interpretation

The 441 inherited count remains numerically unchanged. Five historical V6.2.x test files contained explicit assertions for the old eight-tab / contextual-row UX and one V6.3.0 test pinned the older release marker. Their original versions are frozen under `frozen_legacy_ux_assertions/` and `frozen_legacy_release_assertions/`; only the deliberately superseded presentation assertions were updated. See `V6_3_1_SUPERSEDED_UX_ASSERTIONS.md`.

## Large simulation evidence

`V6_3_1_SIMULATION_RESULTS.json`:

- 10,000 synthetic learners
- 200,000 randomized invariant checks
- 30,019 QA response events
- 92,274 mastery decision-log rows
- 4,170 recovery rows
- 0 detailed failures
- 0 fuzz failures
- 0 LIVE response events from simulation

Synthetic QA evidence remains non-student and non-mastery evidence.

## Remaining acceptance risk

The principal open gate is **visual/interaction acceptance in the real browser**. This environment does not contain Flask and has no Internet access to install the declared package, so this candidate has not been represented as real-browser accepted here. Windows/browser replay is intentionally the next gate.
