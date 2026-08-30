# ScoreMax V6.5.6 — Integration Control Return

## Decision

Return one frozen V6.5.6 candidate for independent Integration Control admission.

## Exact parent

ScoreMax V6.5.5 frozen ZIP SHA-256:

`d9cf823392ad405e82e10ca25354d0058e6ae740ef7ea52c811f11bd741a35ab`

## Rectification

Only the explicit-port normalisation defect in the V6.5.5 Power House MANIFEST_PULL origin boundary is changed.

`_https_origin()` now uses HTTPS default port 443 only when `parsed.port is None`. An explicit port is retained as explicit and must be within `1..65535`. Therefore `:0`, `:00`, `:000`, invalid/non-numeric and out-of-range ports fail closed. Package URL validation still occurs before ScoreMax reads `SCOREMAX_TO_POWER_HOUSE_TOKEN` or creates any opener/network request. Redirect validation remains before redirected request construction.

## Permanent evidence

- V6.5.6 explicit-port attacks: 44/44 PASS.
- V6.5.5 origin/security suite: 23/23 PASS.
- V6.5.4 retry/strict-JSON/health suite: 31/31 PASS.
- V6.5.4 central return attacks: confirmed_total=0, P0=0, P1=0, integrity=ok, FK=0.
- V6.5.1 rectification: 23/23 PASS.
- V6.5.1 deep: 24/24 PASS.
- V6.5 focused integration: 48/48 PASS.
- V6.5.3 behavioral admission: 48/48 PASS.
- Canonical integration scale: 300 PASS / 1,500 PASS.
- Inherited ScoreMax deterministic baseline: 605/605 PASS plus synthetic mastery simulation.
- Emergency Direct Intake: 3,000-row end-to-end PASS.
- SQLite integrity: ok.
- Foreign-key violations: 0.

Final gate:

`confirmed_total=0 · P0=0 · P1=0 · integrity=ok · foreign_key_violations=0`

Windows qualification is explicitly separate infrastructure/CI evidence and does not block this rectification return.
