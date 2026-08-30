# ScoreMax V6.3.0 — Internal Live & Universal Mastery Foundation Build Report

**Build date:** 17 August 2026  
**Status:** FUNCTIONALITY_CANDIDATE — ready for internal learner-UX testing, not public release  
**Parent:** ScoreMax V6.2.8.1  
**Verified parent SHA-256:** `c7ac74df423f2edb536c8a34b71e672c4d726f7b34ab742e37a081432afe47a2`

## 1. Build objective

Create a safe, working descendant for private ScoreMax testing this week without waiting for the Power House reviewer-spreadsheet parser issue, without duplicating academic review inside ScoreMax, and without throwing away the mature V6.2.8.1 learner product.

## 2. Architecture basis

The build targets Universal Mastery Architecture v0.8 / governance reference v1.2, including the 69 canonical software requirements (39 P0) and the first-class Claim Family correction introduced by the independent audit.

The runtime preserves the central separation:

`Knowledge Node -> Claim Family -> Reasoning Seed -> Question Variant`

and keeps learner content mastery, exam readiness and full-exam execution opportunity separate.

## 3. Migration posture

V6.3 is **parallel and feature-flagged**, not destructive:

- V6.2.8.1 legacy mastery remains authoritative for the internal-live candidate.
- Universal evidence is stored in new `universal_*` tables.
- Existing learner history is not rewritten.
- Existing Pakistan question IDs are not regenerated.
- Existing questions only enter the new runtime if a governed universal mapping exists.
- QA simulation evidence is stored under `QA_SANDBOX_ONLY`, never LIVE.

## 4. Implemented engine areas

### Content/evidence model

Stable source/authority registries; Claim Families; Knowledge Nodes; Reasoning Seeds; node/seed maps; mandatory gates; prerequisites; question purpose/layer/type/context; independent weight; exam profiles; evidence schema versions.

### Learner evidence and mastery

Canonical response events; assistance; confidence; timing; error events; node/family/seed evidence; lifecycle states; retention scheduling; reopened/at-risk handling; causal recovery; deterministic decision logs/replay.

### Exam governance

Versioned market/exam rule sets with format rows. Pilot configs distinguish MDCAT 2026 (+1/0/0), NEET 2026 (+4/-1/0) and JEE Main 2026 MCQ/numerical (+4/-1/0) without one global negative-marking switch.

### Study Plan / recovery

Universal recovery and maintenance queues can feed the mature existing Study Plan under the pilot flag. Legacy weak-area/reconfirmation planning remains intact.

### Growth boundary

Registration, login, assessment completion and Study Plan creation write asynchronous governed outbox events. No synchronous Growth Engine dependency was introduced.

## 5. Power House boundary

Academic Reviewer Workspace is not part of the V6.3 forward design. Historical reviewer code is retained only for compatibility/rollback and hidden from the normal V6.3 admin navigation. Power House remains responsible for reviewer assignment, review, adjudication and approved academic release.

The current Power House reviewer-spreadsheet/batch-generation defect therefore does not block this internal ScoreMax build.

## 6. Internal-live operations

The private local launcher creates its own fresh persistent DB and secret. Backup/restore tooling uses SQLite online backup, `PRAGMA integrity_check` and SHA-256 manifests. A backup followed by database mutation and restore was replay-tested successfully; restored integrity returned `ok` and the original test value was recovered.

## 7. Acceptance results

- **Inherited regression:** 441/441 PASS.
- **V6.3 Universal Mastery deterministic checks:** 55/55 PASS.
- **V6.3 app integration checks:** 10/10 PASS.
- **Python compileall:** PASS across the package Python sources.
- **Synthetic learner simulation:** 10,000 full journeys, 14 adversarial profiles, 0 failures.
- **Randomized invariant checks:** 200,000, 0 failures.
- **QA evidence generated in large simulation:** 29,337 response events.
- **QA -> LIVE leakage:** 0 events.

## 8. What is deliberately left for the next steps

- Student-facing V6.3 UX refinement and terminology review.
- Real browser/mobile/keyboard/zoom acceptance.
- Larger concurrency and load testing.
- Public/cloud deployment, HTTPS edge, managed database and monitoring choices.
- Real learner calibration and advanced psychometrics.
- Production Power House -> ScoreMax approved universal academic package contract.

Those are follow-on acceptance/improvement tasks; they do not require rebuilding the core functionality delivered here.
