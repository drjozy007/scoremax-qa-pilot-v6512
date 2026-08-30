# ScoreMax V6.5.1 — Integration Rectification Acceptance

**Candidate status:** `PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION`

This acceptance qualifies the ScoreMax side only. It does not claim that Power House, ScoreMax and Growth Engine have passed the final cross-system integrated foundation gate.

## Acceptance gates

| Gate | Status | Evidence |
|---|---|---|
| SM651-G0 Version/package integrity | PASSED | exact V6.5.0 parent SHA verified; sealed ZIP manifest/hash/hygiene independently verified |
| SM651-G1 Strict contract gateway | PASSED | Draft 2020-12 + format validation; v1.0 INLINE; v1.1 INLINE/MANIFEST_PULL/WITHDRAW; invalid side-effect checks |
| SM651-G2 Academic release integrity | PASSED | missing academic fields, ineligible rights, checksum mismatch, hold/R2/dependency rules fail safe |
| SM651-G3 Immutable version/namespace model | PASSED | independent version/membership stores; 0/50/90/100% unchanged releases; collision safety; active-session snapshot tests |
| SM651-G4 Outbound/receipt integrity | PASSED | generated envelopes validate; UTC Z; ACCEPTED/DUPLICATE only; malformed/wrong/rejected/quarantined state tests |
| SM651-G5 Referral/telemetry correctness | PASSED | stable referral attribution; skipped != incorrect; minimum-N/no learner IDs/raw answers |
| SM651-G6 Performance/outage isolation | PASSED platform-side | bounded source queue; no learner-request scans; queue/restart/outage tests; 300/1500 scale |
| SM651-G7 Security | PASSED platform-side | strict HTTPS/secret preflight, credential rotation, HMAC, replay/clock-skew, no secret-package artifacts required |
| SM651-G8 Regression/scale | PASSED | sealed ZIP replay: 605 + 48 + 22 + 24 = 699 deterministic; 300/1500; emergency 3000; adversarial 18/18 NOT_CONFIRMED |
| SM651-G9 Rollback | PASSED platform-side | exact V6.5.0 DB upgrade; child backup/restore; non-destructive rollback procedure |

## Deterministic tests
- 605/605 inherited V6.4 checks PASS.
- 48/48 V6.5 focused integration checks PASS.
- 22/22 V6.5.1 focused rectification checks PASS.
- 24/24 V6.5.1 deep receipt/mixed-version checks PASS.
- **699/699 total deterministic checks PASS.**

## Adversarial replay
Integration Control supplied `ScoreMax_V6_5_0_Adversarial_Reproduction_v1_1.py` was run against the packaged V6.5.1 child with `--expect rectified`:
- 18/18 defect checks: `NOT_CONFIRMED`
- `confirmed_defects=0`
- process exit: 0

## Scale/performance
- Canonical 300-question PH release: PASS; admission ~0.419 s, duplicate ~0.161 s.
- Canonical 1,500-question PH release: PASS; admission ~2.898 s, duplicate ~0.806 s.
- Emergency 3,000-row XLSX: PASS; latest inherited replay preview ~1.168 s, atomic import ~0.393 s, eligible release ~0.183 s.
- These are synthetic/canonical platform-side evidence; a real governed Power House heterogeneous release remains an Integration Control qualification gate.

## Mastery regression
V6.5.1 simulator identity updated and rerun:
- 10,000 synthetic learners
- 200,000 randomized invariant checks
- 0 detailed failures
- 0 fuzz failures
- 0 QA→LIVE evidence leakage

## Migration / rollback
Exact parent SHA verified. Exact V6.5.0 DB initialized with parent bytes and upgraded to V6.5.1. A genuine migration defect was discovered (missing additive release columns on existing table), fixed systemically, and replayed successfully. V6.5.1 backup→mutate→restore also passed with `PRAGMA integrity_check = ok`.

## Still pending outside ScoreMax-side acceptance
- Actual Power House V6.5.1-compatible counterpart and Growth Engine counterpart end-to-end qualification.
- Real approved heterogeneous PH chapter vertical slice.
- Actual counterparty receipts/outage replay.
- Hosted domain/HTTPS/production database/secrets/SMTP/browser/accessibility live gates.
- Integration Control final freeze and separate integrated adversarial audit.

## Sealed-package verification
The candidate ZIP was extracted to a fresh directory. Every internal manifest/file-checksum entry matched, package hygiene found no runtime DB/cache/upload/session-secret artifacts, inherited + integration + rectification suites replayed successfully from the sealed bytes, the 10,000/200,000 simulator stayed green, and the Integration Control adversarial harness again returned 18/18 NOT_CONFIRMED. The exact sealed ZIP SHA-256 is recorded in the external sidecar and return handoff.
