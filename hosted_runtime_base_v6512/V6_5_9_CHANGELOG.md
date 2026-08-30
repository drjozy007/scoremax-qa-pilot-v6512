# V6.5.9 Changelog

## Production changes

### `app.py`
- Release identity advanced to `6.5.9`.
- `reverse_referral_reward()` now supports `commit=False` so the existing reward ledger can participate in one atomic payment terminal-state transaction without creating a second reward authority.
- Added `refund_payment_transaction()` for governed **full refunds only**. It updates the payment row and reverses direct/one-upstream reward state in one commit.
- Added `reverse_payment_transaction()` for governed payment reversal using the same authoritative reward ledger.
- Partial refunds fail closed because no governed partial-refund reward rule exists.

### `scoremax_integration_v1.py`
- Integration release identity advanced to `6.5.9`.
- Payment metadata key changed from ungoverned `provider` to governed `payment_provider`.
- Terminal payment projection now fails closed when authoritative reward state is incoherent.
- Direct/raw partial-refund projection fails closed.
- `PAYMENT_FAILED` cannot project positive reward eligibility.

## Test/evidence changes
- Added `smoke_tests_v6_5_9_sm_ge_commercial.py`.
- Added `scale_test_v6_5_9_qa_sandbox_1500.py`.
- Existing descendant-version assertions widened to include V6.5.9; behavioural expectations are otherwise preserved.
- Existing V6.5 integration refund smoke now uses the governed full-refund path instead of raw SQL mutation.
- Central return evidence is preserved under `integration_control_return_v659/`.
