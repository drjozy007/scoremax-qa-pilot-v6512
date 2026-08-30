# V6.5.10 Changelog

## Exact parent
ScoreMax V6.5.9 SHA-256:
`fae57ad5adb0be5373ff9943c263f0bce350c9b25dc936303ada956a5fd167d0`

## Production changes

### `app.py`
- Release/build identity advanced to `6.5.10`.
- Added one internal lifecycle classifier for existing payment rows; no new payment ledger/table.
- `refund_payment_transaction()` now permits only coherent CLEARED → REFUNDED or an exact already-completed REFUNDED replay.
- `reverse_payment_transaction()` now permits only coherent CLEARED → REVERSED or an exact already-completed REVERSED replay.
- Unsupported cross-terminal, failed-terminal and contradictory source states reject before payment/reward/source-change mutation.
- Reversal explicitly preserves coherent zero refund amount.

### `scoremax_integration_v1.py`
- Integration release identity advanced to `6.5.10`.
- Payment projection now reads `refund_status` as part of the authoritative lifecycle tuple.
- PAYMENT_CLEARED / PAYMENT_FAILED / PAYMENT_REFUNDED / PAYMENT_REVERSED compile only from coherent state tuples.
- Contradictory/unsupported terminal tuples emit no event and leave the source-change row pending.
- Existing V6.5.9 reward-coherence and privacy rules are preserved.
- Frozen `SM_GE_PRODUCT_EVENT_V1` schema bytes are unchanged.

## Permanent attacks
Added `smoke_tests_v6_5_10_terminal_payment_state.py` covering:
- successful → full refund;
- successful → reversal;
- refund → reversal rejection;
- reversal → refund rejection;
- failed → refund/reversal rejection;
- partial refund rejection;
- contradictory raw terminal tuples;
- exact refund/reversal idempotency;
- referral/reward identity and amount preservation;
- producer synchronization replay;
- DB integrity/FK.

## Test compatibility only
Historical descendant-version allowlists were widened to include V6.5.10. Their behavioural assertions were not weakened.

## No broader change
No Growth Engine source, Power House source, integration schema, learner/mastery logic, reviewer architecture, payment ledger, reward ledger or referral topology was redesigned.
