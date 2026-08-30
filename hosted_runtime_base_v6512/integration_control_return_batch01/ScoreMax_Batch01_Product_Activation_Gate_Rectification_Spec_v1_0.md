# ScoreMax — Batch 01 Product Activation Gate Rectification Spec

## Scope

Fix only `INT-PHSM-B01-P0-002`, discovered during the first real connected Power House → ScoreMax qualification. Do not redesign mastery, student UX, payments, referrals, reviewer functionality, or the admitted manifest-origin security work.

## Required authority boundary

A valid `PH_SM_APPROVED_CONTENT_V1` package must establish academic/content admission only. After checksum/schema/governance validation and immutable staging, the release must remain:

`local_status = STAGED`

and **0 learner-facing Power House projections may be active** until a separate ScoreMax-owned product activation authorization is recorded.

Power House `effective_at` may be retained as academic release metadata/scheduling evidence, but it must not by itself authorize learner activation.

## Minimal governed mechanism

Reuse the existing release/staging model. Add the smallest explicit ScoreMax-owned activation control necessary, with durable actor/time/reason evidence. The activation path must be idempotent and must activate the exact staged release/version/checksum only.

`activate_due_releases()` and `/healthz` must not bypass the ScoreMax product-activation authorization.

## Permanent regression gate

Prove:

- valid PH event → ACCEPTED receipt + STAGED release + 300 staged memberships + 0 active learner projections;
- identical event replay → no duplicate state;
- PH `effective_at = null`, past, or future cannot independently authorize learner activation;
- explicit ScoreMax activation of the exact staged release → ACTIVE once, with exact 300 projections;
- repeated activation authorization is idempotent;
- wrong release/version/checksum cannot activate;
- withdrawal/supersession and historical attempt pins remain correct;
- all V6.5.6 security and integration gates remain green.

Do not touch unrelated ScoreMax subsystems.
