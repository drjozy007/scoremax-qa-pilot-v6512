# ScoreMax V6.3.0 — Internal Live & Universal Mastery Foundation

**Parent:** ScoreMax V6.2.8.1 Power House V3 Import Compatibility  
**Parent SHA-256:** `c7ac74df423f2edb536c8a34b71e672c4d726f7b34ab742e37a081432afe47a2`  
**Architecture:** Universal Mastery Architecture v0.8 / governance reference v1.2  
**Purpose:** functionality-first internal-live descendant for ScoreMax testing.

## Important system boundary

Academic reviewing is now owned by **Power House**. The inherited ScoreMax reviewer code remains in the package only for rollback/audit compatibility and is hidden from the V6.3 forward admin navigation. V6.3 does not depend on the Power House reviewer-spreadsheet/batch-generation workflow.

Growth Engine integration is deliberately asynchronous: ScoreMax writes governed product events to `universal_growth_event_outbox`. Growth Engine is not allowed to alter academic truth or learner mastery.

## What V6.3 adds

- First-class Knowledge Nodes, Claim Families, Claim-Family Gates and Reasoning Seeds.
- Separate question variants/dependencies and independent mastery weight.
- Separate learner node/family/seed states.
- Mandatory gate block/reopen behaviour.
- Assistance exclusion from mastery closure.
- Unseen-transfer requirements.
- Prerequisite graph and causal recovery routing.
- Structured error telemetry and high-confidence-wrong escalation.
- Response timing, confidence and exam-context evidence model.
- Separate exam-specific seed readiness and source-locked rule sets.
- MDCAT / NEET / JEE Main format-specific scoring configuration.
- Retention / maintenance-due / reopen states.
- Deterministic mastery decision logs and replay.
- SYLLABUS_NOVEL protection.
- Repair-cost cold-start governance and learner-history phase-in.
- Learner-goal target policy without rank/admission promises.
- Full-exam execution opportunity kept separate from content mastery.
- Feature flags and evidence-schema versioning.
- Pakistan / India market-adapter foundations.
- Growth Engine event outbox.
- Universal recovery and maintenance queues feed the existing Study Plan when the pilot flag is enabled.
- Existing V6.2.8.1 assessment completion shadow-feeds the universal engine only where governed question mappings exist. Unmapped questions are skipped rather than assigned invented identities.

## Safety posture for internal live

The **legacy ScoreMax mastery engine remains authoritative** in this candidate. Universal Mastery runs alongside it under a controlled pilot flag so we can attack and compare the new evidence logic without silently rewriting historical learner progress.

Synthetic QA evidence uses `QA_SANDBOX_ONLY` and is physically partitioned from `LIVE` evidence.

## Start on Windows

First install the inherited requirements if needed:

```text
python -m pip install -r requirements.txt
```

Then double-click:

```text
start_scoremax_v6_3_internal_live.bat
```

The launcher creates a persistent private database under `internal_live_data/`, creates/reuses a persistent session secret, enables the universal mastery pilot flag, and starts ScoreMax at:

```text
http://127.0.0.1:5000
```

This launcher is for **private/local internal testing**, not public Internet exposure.

## Backup / restore

Use:

```text
BACKUP_SCOREMAX_V6_3.bat
```

Backups are SQLite online backups with an integrity check and SHA-256 manifest.

To restore:

```text
RESTORE_SCOREMAX_V6_3.bat path\to\backup.db
```

The current database is backed up before restore and the restore candidate is integrity-checked before replacement.

## Acceptance

Run:

```text
RUN_SCOREMAX_V6_3_ACCEPTANCE.bat
```

Release-build evidence currently records:

- 441 / 441 inherited V5.5 → V6.2.8.1 regression checks passed.
- 55 / 55 V6.3 Universal Mastery foundation checks passed.
- 10 / 10 V6.3 application-wiring checks passed.
- 10,000 full synthetic learner journeys across 14 adversarial learner profiles: 0 failures.
- 200,000 randomized invariant checks: 0 failures.
- 29,337 QA response events processed in the large simulation.
- 0 simulation events leaked into LIVE evidence.

See `V6_3_0_SIMULATION_RESULTS.json` and `V6_3_0_ACCEPTANCE.md`.

## Still intentionally not claimed by this candidate

- Public production/cloud deployment is not completed by this package.
- Student-facing V6.3 UX refinement is the next workstream.
- The Power House reviewer spreadsheet/batch parser issue is external to this ScoreMax release.
- Advanced psychometrics, learned retention models, calibrated execution-loss prediction and rank/percentile prediction remain evidence-gated.
- Power House-approved universal academic packages are not fabricated by ScoreMax; academic mappings must arrive through the governed Power House release path.
