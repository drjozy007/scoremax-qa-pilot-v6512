# ScoreMax V6.5.7 Acceptance Evidence

## Decision

Platform-side narrow rectification: **PASSED**.

Current status:

`SCOREMAX_PRODUCT_ACTIVATION_GATE_RECTIFIED_CANDIDATE_PENDING_CENTRAL_CONNECTED_REQUALIFICATION`

This is not central connected admission of Batch01. Power House still owns its separate 28-record serialization P1 and the same 300 must be replayed centrally after both sides are ready.

## Proven gates

- V6.5.7 product activation gate: **25/25 PASS**.
- Actual 300 contract state transition: admission -> `STAGED`, 300 memberships, **0 learner projections**; exact ScoreMax authorization -> `ACTIVE`, exactly **300 projections**.
- Null, past and future Power House `effective_at` values cannot independently activate.
- Wrong release ID/version/checksum cannot activate.
- Actor/reason evidence is mandatory and durable; idempotent replay preserves first authorization evidence.
- Direct internal `_activate_release()` cannot bypass product authorization.
- Existing Integration Health admin control activates only the exact staged release and records governed actor/reason evidence.
- Withdrawn staged releases cannot activate.
- V6.5.6 explicit-port security: **44/44 PASS**.
- V6.5.5 manifest-origin security: **23/23 PASS**.
- V6.5.4 central rectification: **31/31 PASS**.
- V6.5.3 behavioral integration: **48/48 PASS**.
- V6.5 focused integration: **48/48 PASS**.
- V6.5.1 deep: **24/24 PASS**.
- V6.5.1 rectification: **23/23 PASS**.
- Inherited ScoreMax baseline: **605/605 deterministic checks PASS** plus synthetic mastery simulation.
- Emergency Direct Intake: **3,000-row end-to-end PASS**.
- Canonical integration scale: **300 PASS / 1,500 PASS**; both prove staged-before-explicit-authorization and exact live count after authorization.
- Python compile: **106 files PASS**.
- Jinja parse: **108 templates PASS**.
- Exact-parent additive migration/rollback: **PASS**; V6.5.6 staged rows survive, new authorization table starts empty, integrity `ok`, FK `0`, untouched parent backup reopens cleanly under V6.5.6.
- Previous V6.5.4 central attacks: `confirmed_total=0`, `P0=0`, `P1=0`, integrity `ok`, FK `0`.

Final platform-side gate:

`confirmed_total=0 · P0=0 · P1=0 · integrity=ok · foreign_key_violations=0`

Full command evidence is retained in `V6_5_7_ACCEPTANCE_EVIDENCE.txt`. Migration evidence is retained in `V6_5_7_MIGRATION_ROLLBACK_EVIDENCE.json`.
