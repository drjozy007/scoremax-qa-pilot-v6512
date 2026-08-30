# ScoreMax V6.5.0 — Three-System Integration Adapter

**Parent:** ScoreMax V6.4.0 — Live Pilot UX & Operations Candidate  
**Parent SHA-256:** `25dee1e56bfb517e032387fed566e4cfb9335a74c04b47c0e18e63a4a03ef64e`  
**Status:** `PLATFORM_SIDE_INTEGRATION_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION`

V6.5.0 is an additive child of V6.4.0 implementing only ScoreMax's side of frozen Three-System Integration Contract v1. Learner UX, mastery gates, Study Plan, Progress, Emergency Direct Intake, referral/payment authority, and historical reviewer compatibility remain intact.

## Added

- Power House approved-content admission with immutable external release/question-version snapshots.
- Exact Power House release/question/checksum pinning in assessment sessions, attempts and answer evidence.
- Power House assessment-blueprint immutable admission with fail-safe projection.
- ScoreMax -> Power House aggregate delivery-evidence and content-requirement outbox.
- ScoreMax -> Growth Engine idempotent product/payment/referral event outbox.
- Common dispatcher with retry, receipt, attempt history, quarantine and health state.
- Scoped bearer + HMAC service authentication, replay clock-skew protection and controlled secret rotation.
- Admin integration-health surface extending the existing admin system.
- Windows V6.5 internal-live, backup/restore and acceptance launchers.

## Important boundaries

- Power House remains academic authority.
- ScoreMax remains learner/payment/referral transaction authority.
- Growth Engine receives product/commercial facts but cannot alter mastery, payments or academic truth.
- Academic Reviewer Workspace is not a forward dependency.
- Emergency 3,000-question Direct Intake remains a business-continuity fallback and is not repurposed as the Power House machine contract.

See `V6_5_0_PLATFORM_INTEGRATION_HANDOFF.md`, `V6_5_0_ACCEPTANCE.md` and `V6_5_0_KNOWN_LIMITATIONS.md`.
