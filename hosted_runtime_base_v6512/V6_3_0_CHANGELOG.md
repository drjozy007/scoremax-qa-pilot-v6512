# ScoreMax V6.3.0 Changelog

**Date:** 17 August 2026  
**Release posture:** Internal-live functionality candidate  
**Parent:** V6.2.8.1, SHA-256 `c7ac74df423f2edb536c8a34b71e672c4d726f7b34ab742e37a081432afe47a2`

## Universal Mastery runtime

Added `universal_mastery_engine.py` implementing the v0.8 / governance v1.2 foundation as a feature-flagged parallel runtime. The existing mastery engine remains authoritative during the internal pilot.

Key additions include Knowledge Node, Claim Family, Claim-Family Gate, Reasoning Seed, question architecture, independent/dependent mastery weighting, learner evidence/state history, prerequisite graph, error/confidence/assistance telemetry, transfer gates, retention, exam profiles, source-locked exam rule sets, decision replay, syllabus novelty, score opportunity, repair-cost phase-in, learner goal policy and full-exam execution opportunity.

## ScoreMax application integration

- Universal schema initializes with the existing application database.
- `SCOREMAX_UNIVERSAL_MASTERY=1` enables the pilot flag.
- Assessment completion shadow-feeds the universal runtime only for questions with governed mappings.
- Unmapped legacy questions are skipped; V6.3 never invents academic identities.
- Universal recovery/maintenance queues can feed the existing Study Plan.
- Internal admin runtime-status endpoint added.
- Health payload preserves the inherited `version=6.2.8.1` compatibility marker while exposing `release_version=6.3.0` and `universal_mastery_architecture=0.8`.

## Power House boundary

Academic reviewing is no longer a ScoreMax forward dependency. The inherited reviewer implementation remains for rollback/audit compatibility, but the Reviewer Workspace link is hidden from V6.3 forward admin navigation. Power House remains the academic review authority.

## Growth Engine boundary

Added asynchronous `universal_growth_event_outbox`. Initial ScoreMax events include registration, login, assessment completion and Study Plan creation. No Growth Engine process can write mastery or academic truth through this boundary.

## Internal-live operations

Added:

- `scoremax_internal_live.py`
- `start_scoremax_v6_3_internal_live.bat`
- `scoremax_internal_live_backup.py`
- `BACKUP_SCOREMAX_V6_3.bat`
- `RESTORE_SCOREMAX_V6_3.bat`
- `run_v6_3_acceptance.py`
- `RUN_SCOREMAX_V6_3_ACCEPTANCE.bat`

The local launcher creates a fresh persistent database and persistent session secret under `internal_live_data/`.

## Test assets

Added:

- `smoke_tests_v6_3.py` — 55 Universal Mastery foundation checks.
- `smoke_tests_v6_3_app.py` — 10 application wiring checks.
- `scoremax_v6_3_simulator.py` — adversarial synthetic learner simulator.
- `V6_3_0_SIMULATION_RESULTS.json` — recorded large simulation evidence.
