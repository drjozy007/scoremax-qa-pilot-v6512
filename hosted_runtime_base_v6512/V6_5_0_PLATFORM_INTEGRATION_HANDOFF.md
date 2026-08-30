# ScoreMax V6.5.0 — Return to Three-System Integration Control

## Decision

ScoreMax's side of frozen Integration Contract v1 is implemented as an additive V6.5.0 child of the exact V6.4.0 parent.

**Status to return:** `PLATFORM_SIDE_INTEGRATION_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION`

This platform workstream does **not** declare `THREE-SYSTEM INTEGRATED FOUNDATION ACCEPTED`.

## Parent

- ScoreMax V6.4.0 — Live Pilot UX & Operations Candidate
- SHA-256: `25dee1e56bfb517e032387fed566e4cfb9335a74c04b47c0e18e63a4a03ef64e`

## Implemented ScoreMax contract sides

### A — `PH_SM_APPROVED_CONTENT_V1`
- Permanent governed API admission separate from Emergency Direct Intake.
- Immutable release/question/stimulus snapshots.
- Exact opaque IDs preserved.
- Ready/rights/hold/R2/source-check gates enforced.
- Dependent/recovery zero independent mastery weight enforced.
- Shared stimuli and rubric-only constructed responses preserved.
- Current learner projection activated only through the normal live gate.
- Active learner sessions pin exact PH release/question version/checksum and marking snapshot.
- Later change/withdrawal affects future inventory only.

### B — `PH_SM_ASSESSMENT_BLUEPRINT_V1`
- Immutable versioned admission and duplicate protection.
- Fail-safe `IMMUTABLE_ONLY` state when a deterministic legacy projection identity is unavailable.

### C — `SM_PH_DELIVERY_EVIDENCE_V1`
- Privacy-minimised question-version aggregate evidence outbox.
- Minimum-N suppression.
- No learner IDs or raw learner answers.

### D — `SM_PH_CONTENT_REQUIREMENT_V1`
- Governed business-idempotent content requirement outbox.

### E — `SM_GE_PRODUCT_EVENT_V1`
- Existing ScoreMax product/payment/referral facts projected into the common governed integration outbox.
- Cleared payment, refund/reversal, renewal and one-upstream teacher lineage retained.
- Business event ID/idempotency prevents duplicate receiver effects.

## Common integration controls

- Inbound message ledger and receipts.
- Outbound transactional outbox.
- Dispatch attempt history.
- Quarantine for identity/checksum conflicts.
- Retry/backoff and outage persistence.
- Scoped bearer + HMAC authentication.
- Current/previous credential support for controlled rotation.
- Clock-skew replay protection.
- Existing Admin extended with integration health; no new standalone dashboard.

## Platform-side evidence

- 653/653 deterministic checks PASS.
- 48/48 focused integration checks PASS.
- 24 concurrent PH deliveries -> one release.
- 24 concurrent Growth queues -> one business event.
- 300 and 1,500 canonical-contract release admissions PASS.
- Emergency 3,000 direct intake remains green.
- Mastery simulation remains green with zero QA -> LIVE leakage.
- Additive V6.5 database can be opened by the exact V6.4 rollback parent in the tested SQLite path.

## Defect disposition from Integration Control

ScoreMax-side work addresses the ScoreMax components of:
- INT-P1-001 dispatcher/delivery lifecycle
- INT-P1-002 immutable business idempotency
- INT-P1-003 permanent PH machine admission (receiver side)
- INT-P1-004 PH exact version pinning
- INT-P1-005 ScoreMax -> PH evidence/requirements
- INT-P1-016 ScoreMax service authentication/HMAC/replay/rotation

Cross-system tickets remain open until counterpart implementations and E2E acceptance exist. Integration Control owns their final closure.

## Required next Integration Control actions

1. Receive the Power House and Growth Engine implementation candidates.
2. Resolve/version the frozen v1 `MANIFEST_PULL` schema contradiction rather than asking a platform to reinterpret it locally.
3. Run one real Power House approved chapter through the actual exporter -> ScoreMax admission -> learner attempt -> exact-version evidence -> Power House return path.
4. Run real ScoreMax payment/referral events into the Growth Engine receiver and verify one receiver effect under retries/refunds.
5. Prove Growth demand signal -> Power House as advisory-only.
6. Run cross-system outage/replay, 300/1,500 real heterogeneous release, hosted service-secret, managed persistence and rollback gates.
7. Freeze the integrated candidate, then run the separate adversarial audit without editing it.

## Must remain untouched

Do not reopen ScoreMax learner UX/mastery/referral/payment architecture from the integration workstream unless a cross-system P0/P1 defect proves it necessary.
