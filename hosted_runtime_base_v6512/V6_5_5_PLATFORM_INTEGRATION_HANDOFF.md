# ScoreMax V6.5.5 — Integration Control Return

## Decision

Narrow rectification of **INT-SM654-P0-001** only.

## Exact parent

ScoreMax V6.5.4 frozen ZIP SHA-256:

`5c86d0fc9c703c5fd4c50b01442311a5f9e0897d0fbc45983b0a2794dbbcb7ee`

## Change

`scoremax_integration_v1.py` now validates every Power House manifest package URL against the deployment-controlled `SCOREMAX_POWER_HOUSE_BASE_URL` origin before credential access or network activity. Cross-origin redirects are blocked at redirect construction time. Same-origin authenticated package pulls continue to use existing checksum and staging controls.

## Explicitly untouched

Mastery, learner UX, reviewer architecture, payments, referrals, Emergency Direct Intake, blueprint semantics, question admission semantics, retry-cycle behavior, strict JSON handling, and Integration Health behavior are unchanged except for release identity/test compatibility.

## Required gate

`confirmed_total=0 · P0=0 · P1=0 · integrity=ok · foreign_key_violations=0`

See `V6_5_5_TEST_EVIDENCE.json` and `smoke_tests_v6_5_5_manifest_origin_security.py`.
