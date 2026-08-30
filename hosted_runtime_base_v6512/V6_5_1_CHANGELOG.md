# ScoreMax V6.5.1 Changelog

## Parent
Exact immutable parent: ScoreMax V6.5.0 Three-System Integration Platform Candidate, SHA-256 `8a32da65da5d389e69b5771f495b81047dee347cbc7705ee5951536aa111f0e2`.

## Added
- Integration contract schema v1.1.0 files and examples without modifying frozen v1.0 bytes.
- Strict Draft 2020-12 envelope/receipt validation with format checking.
- Immutable PH question/stimulus version stores and independent release-membership tables.
- v1.1.0 manifest/package validation and authenticated HTTPS MANIFEST_PULL support.
- v1.1.0 release withdrawal handling.
- Receipt-aware outbox delivery state machine.
- Incremental local source-change queue and bounded projection.
- V6.5.1 local launch, backup/restore, acceptance runners.
- Focused and deep rectification tests.

## Fixed
- Schema-invalid PH content reaching live projection.
- External PH Question ID collision with legacy local ScoreMax Question IDs.
- Reused immutable question versions crashing later release admission.
- Outbound envelope/date-time non-conformance.
- HTTP 200/202 incorrectly implying delivery without a valid matching receipt.
- `source_check_status=NOT_REQUIRED`, nullable `effective_at`, optional generated clearance handling.
- Strict blueprint admission.
- Skipped responses incorrectly contributing to incorrect counts.
- Weak/non-HTTPS integrated-pilot preflight.
- Referral attribution identity drift across event types.
- Unbounded learner-request-path history projection.
- Additive V6.5.0 DB migration failing because new release columns were assumed after `CREATE TABLE IF NOT EXISTS`.

## Intentionally unchanged
- Frozen v1.0 contract bytes.
- v1.0 MANIFEST_PULL contradiction: remains explicit fail-safe; use schema v1.1.0.
- Power House academic authority and reviewer workflow.
- ScoreMax learner/mastery authority.
- Growth Engine commercial/advisory authority.
- V6.4 student UX and Emergency Direct Intake governance.
