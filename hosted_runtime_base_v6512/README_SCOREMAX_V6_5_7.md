# ScoreMax V6.5.7 — Batch01 Product Activation Gate Rectification

V6.5.7 is a narrow descendant of the exact frozen ScoreMax V6.5.6 candidate whose ZIP SHA-256 is:

`64244e5d64d5df2bbeb262b0554b3c5e0b69b3f31378e8c338c71e5fb378cdb2`

## Scope lock

This release rectifies only central connected finding `INT-PHSM-B01-P0-002`: accepted Power House content must not become learner-active merely because Power House supplied a null or due `effective_at` value.

Power House content admission now ends at `STAGED`. The existing immutable release/question/stimulus stores and release membership remain the staging system of record. Learner projection requires a separate ScoreMax-owned product activation authorization bound to the exact `release_id`, `release_version` and `package_checksum_sha256`, with durable actor, time and reason evidence.

`activate_due_releases()` is retained for compatibility but is now recovery for already-authorized staged releases only. Startup, request housekeeping and `/healthz` therefore cannot use Power House schedule metadata as activation authority.

The existing Integration Health admin surface is extended with the smallest activation control. No parallel dashboard or release engine is introduced.

## Explicitly unchanged

No mastery logic, learner UX, reviewer architecture, payments, referrals, Emergency Direct Intake, Power House manifest-origin security, explicit-port security, retry-cycle semantics, strict JSON, blueprint execution, withdrawal/supersession semantics or historical evidence pins are redesigned.

The separate Power House finding `INT-PHSM-B01-P1-001` (28 two-tier serialization records) is not a ScoreMax code defect and is not rectified here.

## Release status

`SCOREMAX_PRODUCT_ACTIVATION_GATE_RECTIFIED_CANDIDATE_PENDING_CENTRAL_CONNECTED_REQUALIFICATION`

The same reserved Batch01 300 must be re-run after Power House separately rectifies its 28 two-tier records. No academic reselection is required. The real 1,500 connected batch must not start until Batch01 central connected requalification passes.

Windows qualification remains a separate infrastructure/CI gate, not a V6.5.7 product rectification blocker.
