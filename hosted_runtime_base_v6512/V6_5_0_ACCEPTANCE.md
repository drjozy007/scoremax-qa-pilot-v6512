# ScoreMax V6.5.0 Platform-Side Acceptance

**Date:** 21 August 2026  
**Status:** PASSED for platform-side integration candidate; cross-system qualification remains pending.

## Deterministic regression

- V5.5 -> V6.2.8.1 inherited: **441/441 PASS**
- V6.3 Universal Mastery/application: **82/82 PASS**
- V6.3.1 Student UX V2: **27/27 PASS**
- V6.3.2 chapter identity: **14/14 PASS**
- V6.4 Live Pilot UX & Operations: **41/41 PASS**
- V6.5 focused integration: **48/48 PASS**

**Total: 653/653 deterministic checks PASS.**

## Additional gates

- 1,000 synthetic learners + 10,000 randomized mastery attacks: PASS; 0 QA -> LIVE leakage.
- Emergency Direct Intake 3,000-row XLSX: PASS; Draft/inactive import and governed release retained.
- Canonical Power House integration release 300 rows: PASS; admission about 2.3 s in container test.
- Canonical Power House integration release 1,500 rows: PASS; admission about 11.1 s in container test.
- Duplicate 300/1,500 release replay: idempotent.
- 24-way concurrent Power House delivery: one admitted release.
- 24-way concurrent Growth event queue: one business event.
- Exact opaque question/version IDs: preserved.
- Held/R2/source-check-required questions: excluded.
- Dependent/recovery independent mastery inflation: blocked.
- Shared stimulus and rubric-only constructed response: preserved.
- Active-session exact question/release snapshot survives changed/withdrawn future content.
- Payment/refund/renewal and one-upstream teacher referral lineage: preserved.
- Service auth/HMAC/current+previous secret rotation/stale replay: PASS.
- Minimum-N delivery evidence contains no learner IDs or raw answers.
- Queue persistence across restart/outage: PASS.

Full console evidence: `V6_5_0_ACCEPTANCE_RUN_2026_08_21.txt`.

## Gate classification

- Correctness / regression: **PASSED**
- ScoreMax-side PH content admission: **PASSED on canonical contract fixtures**
- ScoreMax-side PH blueprint admission: **PASSED; immutable fail-safe storage**
- ScoreMax -> PH outbox: **PASSED locally**
- ScoreMax -> Growth outbox: **PASSED locally**
- Security / privacy contract controls: **PASSED locally**
- Idempotency / concurrency / replay: **PASSED locally**
- 300/1,500 canonical integration scale: **PASSED**
- Emergency 3,000 fallback regression: **PASSED**
- Real governed Power House chapter end-to-end: **PENDING Integration Control**
- Counterparty receipts from Power House/Growth: **PENDING Integration Control**
- Hosted PostgreSQL/domain/browser/SMTP: **PENDING Production Reality Audit**
- Separate integrated adversarial audit: **PENDING**
