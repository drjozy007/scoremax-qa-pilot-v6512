# ScoreMax V6.5.1 — Return Handoff to Three-System Integration Control

## Decision
ScoreMax-side Integration Rectification is complete and ready to return to Integration Control as:

`PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION`

Do **not** interpret this as three-system acceptance.

## Parent / lineage
- Exact parent: ScoreMax V6.5.0 Three-System Integration Platform Candidate
- Parent SHA-256: `8a32da65da5d389e69b5771f495b81047dee347cbc7705ee5951536aa111f0e2`
- V6.5.0 frozen contract v1.0 bytes preserved.
- Additive approved contract patch v1.1.0 added; no historical rewrite.

## What changed
1. Strict Draft 2020-12 JSON Schema + format gateway for inbound/outbound messages and receipts.
2. Content semantic checksum verification at question/stimulus level and exact MANIFEST_PULL archive/manifest/member verification.
3. Collision-safe local projection: PH opaque question identity stored separately from local ScoreMax DB identity.
4. Immutable question/stimulus versions separated from release membership.
5. v1.1.0 INLINE, MANIFEST_PULL and WITHDRAW release operations supported; v1.0 valid INLINE preserved; v1.0 MANIFEST_PULL contradiction remains explicit fail-safe.
6. Strict blueprint admission.
7. Receipt-aware dispatch: transport success alone does not equal business delivery.
8. Stable referral attribution across referral/payment/refund/reward chain.
9. Skipped answers separated from incorrect in academic telemetry; minimum-N and no learner/raw-answer leakage retained.
10. Incremental source-change queue and bounded worker projection remove unbounded history scans from learner request path.
11. Strict production preflight requires HTTPS and strong non-placeholder peer credentials/secrets.
12. Exact V6.5.0→V6.5.1 additive migration fixed/proven and V6.5.1 backup/restore proven.

## Important migration finding
Independent upgrade testing found a real child-migration defect after the initial code rectification: an existing V6.5.0 `integration_ph_content_releases` table did not gain V6.5.1 columns merely because the CREATE statement changed. V6.5.1 originally read `release_operation` before explicit ALTER/ensure-column migration. This was corrected architecturally by ensuring every new release column before migration/activation. Exact-parent replay then passed. This should remain regression protected.

## Evidence summary
- Inherited V6.4: 605/605 PASS.
- V6.5 integration compatibility: 48/48 PASS.
- V6.5.1 focused rectification: 22/22 PASS.
- V6.5.1 deep receipt/mixed-version: 24/24 PASS.
- Total deterministic: 699/699 PASS.
- Supplied Integration Control adversarial harness: 18/18 NOT_CONFIRMED; 0 confirmed defects.
- 300/1,500 canonical content release gates PASS.
- Emergency 3,000-row direct XLSX fallback remains PASS.
- 10,000/200,000 mastery simulation PASS, 0 QA→LIVE leakage.
- Exact V6.5.0 DB upgrade PASS after migration rectification.
- Backup/restore PASS.

## Contract behavior Integration Control should assume
### PH_SM_APPROVED_CONTENT_V1
- Schema 1.0.0: valid INLINE accepted.
- Schema 1.0.0 MANIFEST_PULL: rejected explicitly because the frozen schema is contradictory; do not patch v1.0.
- Schema 1.1.0: INLINE / MANIFEST_PULL / WITHDRAW supported according to supplied patch.
- null effective_at = immediate durable admission/activation when otherwise eligible.
- source_check_status CLEAR or NOT_REQUIRED accepted.
- generated_clearance_status optional/nullable as specified.
- ineligible rights/held/R2/unready/dependent inflation fail safe.

### Identity/version
- External PH IDs remain opaque strings.
- ScoreMax local DB primary keys/IDs are distinct.
- same immutable question version can belong to multiple releases without duplication/crash.
- changed versions create new immutable version rows.
- active/historical attempts remain pinned to delivered snapshots.

### Delivery receipts
Only a strictly valid matching `ACCEPTED` or `DUPLICATE` receipt can mark outbox delivery. Malformed/mismatched/retryable/rejected/quarantined responses remain durable in the appropriate state.

## Cross-system qualification requested next
Integration Control should now connect this ScoreMax candidate with the exact returned Power House and Growth Engine candidates and run:
1. Real approved PH chapter -> ScoreMax -> learner attempt -> pinned evidence -> Power House aggregate return.
2. Real ScoreMax registration/payment/referral events -> Growth Engine -> strict receipts/idempotent replay.
3. Growth Engine advisory demand signal -> Power House without academic-authority leakage.
4. Peer outage/recovery, duplicate/reordered events and queue replay.
5. Real heterogeneous 300/1,500 content, including constructed response/shared stimulus/opaque IDs.
6. Integrated security/contract/version rollback attack.

## Must stay untouched
- Academic review remains in Power House.
- Growth Engine cannot write mastery or academic truth.
- ScoreMax does not invent governed Node/Family/Seed IDs.
- Emergency Direct Intake remains fallback, not source of academic authority.
- Do not weaken strict validation/checksum/receipt rules merely to make a counterparty pass; reconcile/version the contract if actual counterpart bytes disagree.

## Files to inspect in candidate
- `scoremax_integration_v1.py`
- `scoremax_integration_dispatch_v1.py`
- `integration_contracts/v1_1_0/`
- `integration_examples/v1_1_0/`
- `V6_5_1_ACCEPTANCE.md`
- `V6_5_1_DEFECT_REGISTER.md`
- `V6_5_1_MIGRATION_EVIDENCE_2026_08_21.txt`
- `V6_5_1_BACKUP_RESTORE_EVIDENCE_2026_08_21.txt`
- `V6_5_1_INTEGRATION_CONTROL_ADVERSARIAL_RUN_2026_08_21.txt`
- `V6_5_1_KNOWN_LIMITATIONS.md`
- `V6_5_1_ROLLBACK_EVIDENCE.md`
