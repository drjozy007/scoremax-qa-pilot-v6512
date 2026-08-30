# ScoreMax V6.5.7 — Central Connected Requalification Handoff

## Decision

Return one frozen ScoreMax V6.5.7 candidate to Integration Control for requalification of the **same reserved PH->ScoreMax Batch01 300** after Power House separately rectifies `INT-PHSM-B01-P1-001`.

## Exact parent

ScoreMax V6.5.6 frozen ZIP SHA-256:

`64244e5d64d5df2bbeb262b0554b3c5e0b69b3f31378e8c338c71e5fb378cdb2`

## ScoreMax finding closed

`INT-PHSM-B01-P0-002` is rectified.

A valid Power House event now ends at:

- receipt/admission accepted;
- release `local_status=STAGED`;
- immutable release membership retained;
- zero learner projections until separate ScoreMax-owned product authorization.

ScoreMax activation is bound to the exact release ID, release version and package checksum and preserves durable actor/time/reason evidence. Power House `effective_at` is not activation authority. Startup, `/healthz` and request housekeeping cannot bypass the authorization gate.

## Power House finding remains separate

`INT-PHSM-B01-P1-001` — 28 `TWO_TIER_DIAGNOSTIC` records serialized with text key while retaining option IDs — remains owned by Power House. ScoreMax does not rewrite or silently compensate for those governed source records.

Integration Control should therefore use the **same reserved 300** after the Power House reissue; no academic reselection is required.

## Acceptance evidence

- V6.5.7 activation gate 25/25 PASS.
- Existing security/integration suites 44/44, 23/23, 31/31, 48/48, 48/48, 24/24 and 23/23 PASS.
- Inherited 605 + synthetic mastery PASS.
- Emergency 3,000 PASS.
- Canonical 300/1,500 PASS with staged-before-activation semantics.
- Migration/rollback PASS.
- SQLite integrity `ok`; FK violations `0`.

Final platform-side gate:

`confirmed_total=0 · P0=0 · P1=0 · integrity=ok · foreign_key_violations=0`

## Next gate

Central Integration Control must re-run the same connected Batch01 300 against the rectified Power House package and this frozen V6.5.7 candidate. **Do not start the real 1,500 connected batch before Batch01 passes central connected requalification.**

Windows remains a separate infrastructure/CI gate and is not another product rectification prerequisite.
