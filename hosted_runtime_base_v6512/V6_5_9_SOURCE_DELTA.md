# V6.5.9 Source Delta

Exact parent: frozen ScoreMax V6.5.8 SHA-256
`2a7c1b0f57ae230279c67784ad6403d0acb37a281cd3c435a759f592b3547b25`

## Production files changed

1. `app.py`
   - release/build identity;
   - atomic governed full-refund / reversal helpers;
   - existing reward reversal can participate in the same transaction.
2. `scoremax_integration_v1.py`
   - `payment_provider` metadata key;
   - fail-closed payment/reward coherence checks;
   - integration release identity.

No other production module is intentionally changed.

## Existing test files changed

Only descendant-version compatibility and the inherited refund smoke expectation are updated:

- `smoke_tests_v6_3_app.py`
- `smoke_tests_v6_3_1_ux.py`
- `smoke_tests_v6_3_2_chapter_identity.py`
- `smoke_tests_v6_4.py`
- `smoke_tests_v6_5_1_rectification.py`
- `smoke_tests_v6_5_3_integration_admission.py`
- `smoke_tests_v6_5_4_central_rectification.py`
- `smoke_tests_v6_5_5_manifest_origin_security.py`
- `smoke_tests_v6_5_6_explicit_port_normalisation.py`
- `smoke_tests_v6_5_integration.py`

## Added evidence/tests

- `smoke_tests_v6_5_9_sm_ge_commercial.py`
- `scale_test_v6_5_9_qa_sandbox_1500.py`
- `integration_control_return_v659/` central findings/specification
- V6.5.9 release documents/evidence/manifest

## Deleted parent files

None.

## Independently computed parent-child file counts before seal

- Parent files modified: **12** total, of which **2 are production code** and **10 are active regression-test compatibility/expectation files**.
- Files added: **14** before release manifest/gate summary.
- Parent files deleted: **0**.
