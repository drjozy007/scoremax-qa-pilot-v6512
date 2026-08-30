# ScoreMax V6.5.3 — Three-System Integration Admission Rectification Candidate

Status: `PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION`

V6.5.3 is a behavioral rectification of the exact rejected V6.5.2 parent. It preserves the accepted ScoreMax learner platform and hardens the shared ScoreMax integration boundary rather than adding a parallel service, parser, mastery engine, reviewer workflow, or referral ledger.

## What changed
- Semantic academic compilation now runs before release/version/question side effects.
- Governed numerical/tolerance, multiple-select, text, boolean, partial and negative marking data are preserved and executed.
- Learner-facing stimulus projection is deterministic and excludes internal provenance/reviewer metadata while immutable source evidence remains retained internally.
- Session/attempt evidence is scoped only from immutable pins rather than the current mutable question projection.
- Release and blueprint identity use ScoreMax-computed semantic checksums; exact replay returns the original receipt and same-ID/version semantic mutation is quarantined.
- Outbound dispatch rejects HTTP before credentials/network construction, validates receiver binding, preserves governed receipts, uses atomic leases and fair contract scheduling, and supports audited requeue.
- A bounded worker is wired for hosted and Windows operation with heartbeat/backlog observability.
- RELEASED Power House blueprints extend the existing ScoreMax blueprint runtime and govern future assembly, timing, marking and permitted inventory.
- The previously external manifest fixture is packaged inside the release.

## Protected boundaries
Student UX, Universal Mastery, Emergency Direct Intake, learner/payment/referral authority and the Power House reviewer boundary are not redesigned by this release. Power House remains academic authority; ScoreMax remains learner-delivery/mastery authority; Growth Engine remains commercial/advisory.

## Local qualification
Run `RUN_SCOREMAX_V6_5_3_ACCEPTANCE.bat` on Windows or `python run_v6_5_3_acceptance.py` from the extracted candidate. Cross-system/live qualification remains separate and must not be inferred from a local pass.

## V6.5.2 database upgrade behaviour
The additive schema upgrade does not trust prior integration admission state. Pre-V6.5.3 content lacking ScoreMax semantic identity is revalidated from immutable retained evidence and either safely reprojected or quarantined. Pre-V6.5.3 `IMMUTABLE_ONLY` blueprints are either activated into the existing blueprint runtime after V6.5.3 validation or quarantined. This reconciliation is idempotent and does not modify the immutable rollback ZIP.
