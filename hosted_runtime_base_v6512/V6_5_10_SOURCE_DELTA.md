# V6.5.10 Source Delta

Exact parent: frozen ScoreMax V6.5.9 SHA-256
`fae57ad5adb0be5373ff9943c263f0bce350c9b25dc936303ada956a5fd167d0`

## Production files changed

1. `app.py`
   - release/build identity;
   - fail-closed payment lifecycle classifier;
   - governed full-refund/reversal helpers now reject unsupported terminal transitions before mutation.

2. `scoremax_integration_v1.py`
   - integration release identity;
   - payment projection now requires a coherent `(status, refund_status, refund_amount_minor, net_amount_minor)` tuple;
   - contradictory/unsupported terminal tuples stay pending and emit no outbound payment event.

No other production module is intentionally changed.

## Existing test files changed

Only descendant-version compatibility allowlists were widened so the inherited tests continue to execute against V6.5.10:

- `smoke_tests_v6_3_app.py`
- `smoke_tests_v6_3_1_ux.py`
- `smoke_tests_v6_3_2_chapter_identity.py`
- `smoke_tests_v6_4.py`
- `smoke_tests_v6_5_1_rectification.py`
- `smoke_tests_v6_5_integration.py`
- `smoke_tests_v6_5_3_integration_admission.py`
- `smoke_tests_v6_5_4_central_rectification.py`
- `smoke_tests_v6_5_5_manifest_origin_security.py`
- `smoke_tests_v6_5_6_explicit_port_normalisation.py`
- `smoke_tests_v6_5_9_sm_ge_commercial.py`

Their behavioural expectations were not weakened.

## Added test/evidence/provenance

- `smoke_tests_v6_5_10_terminal_payment_state.py`
- `run_v6_5_10_acceptance.py`
- V6.5.10 README/changelog/acceptance/handoff/gate evidence
- `integration_control_return_v6510/` exact Central findings/specification

## Deleted parent files

None.

## Parent-child counts before release-manifest generation

- Parent files modified: **13**
- Production files modified: **2**
- Test-compatibility files modified: **11**
- Files added before this source-delta document and release manifest: **16**
- Parent files deleted: **0**

## Frozen contract

`SM_GE_PRODUCT_EVENT_V1` schema bytes remain SHA-256:
`b42ae2a0fd1965ec83e561c43e60d68e84395687de1f257948af7b87319019bb`
