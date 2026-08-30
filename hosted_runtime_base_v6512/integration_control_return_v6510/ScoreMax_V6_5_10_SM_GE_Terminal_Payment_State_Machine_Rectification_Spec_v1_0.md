# ScoreMax V6.5.10 — SM → Growth Terminal Payment State-Machine Rectification

## Exact parent

Build directly from frozen ScoreMax V6.5.9 SHA-256:

`fae57ad5adb0be5373ff9943c263f0bce350c9b25dc936303ada956a5fd167d0`

Do not alter Growth Engine. Do not alter Power House. Do not change `SM_GE_PRODUCT_EVENT_V1`. Do not create another payment or reward ledger.

## Scope

Close only:

`SM-GE-CONN-P1-003 — terminal payment state transitions are not fail-closed`

V6.5.9 already closed the `payment_provider` metadata mismatch and normal refund/reward coherence. Preserve those changes exactly.

## Required payment-state rule

ScoreMax currently has no governed rule authorising transitions between incompatible terminal payment states. Therefore fail closed.

### Allowed

- `successful/cleared/paid → refunded` through the governed full-refund helper;
- `successful/cleared/paid → reversed` through the governed reversal helper;
- exact repeat of an already completed identical terminal operation → idempotent no-op.

### Must fail closed unless a separately governed future rule is introduced

- `refunded → reversed`;
- `reversed/voided → refunded`;
- `failed/declined → refunded`;
- `failed/declined → reversed`;
- partial refund while no governed partial-refund reward rule exists;
- any payment row whose `status`, `refund_status` and `refund_amount_minor` form an internally contradictory lifecycle.

A blocked transition must leave the payment row, reward ledger and integration source-change state unchanged except for safe audit evidence if an existing audit path is reused.

## Synchronizer hardening

Do not infer `PAYMENT_REFUNDED` merely because `refund_amount_minor > 0` while ignoring the authoritative status.

Compile a payment event only from a coherent state tuple. At minimum:

- successful/cleared/paid + zero refund → `PAYMENT_CLEARED`;
- failed/declined + zero refund → `PAYMENT_FAILED`;
- refunded + governed full refund amount → `PAYMENT_REFUNDED`;
- reversed/voided + coherent reversal fields → `PAYMENT_REVERSED`;
- contradictory/unsupported combinations → no outbound event; leave the source change pending/fail closed.

Do not mark a contradictory source change as successfully projected.

## Permanent attacks

Add deterministic tests for:

1. successful payment → full refund → coherent ScoreMax + Growth `REFUNDED`;
2. successful payment → reversal → coherent ScoreMax + Growth `REVERSED`;
3. refund → reversal attempt is rejected and ScoreMax remains `REFUNDED`;
4. reversal → refund attempt is rejected and ScoreMax remains `REVERSED`;
5. failed payment → refund attempt is rejected;
6. failed payment → reversal attempt is rejected;
7. partial refund remains rejected;
8. raw contradictory terminal row produces no Growth event and remains pending;
9. identical full refund repeat is idempotent;
10. identical reversal repeat is idempotent;
11. terminal transitions do not change referral attribution, direct reward ID, upstream reward ID or reward amounts;
12. exact Growth v0.14.3 replay leaves payment/reward/CRM counts unchanged.

## Mandatory connected rerun

Use exact Growth Engine v0.14.3 SHA-256:

`3c378ea33e06b5421eee6f00047c92c3f7a0add9ba0c8e7e27abf5013416c284`

Run the same real chain:

Teacher A → Teacher B → Student → programme selection → successful payment → direct/upstream rewards → replay → full refund; plus a separate successful payment → reversal.

Then run the terminal-ordering attacks above.

Growth must end exactly aligned with ScoreMax authoritative terminal states.

## Preservation gates

Rerun at minimum:

- V6.5.9 commercial semantics;
- V6.5.8 learner evidence;
- V6.5.7 activation gate;
- V6.5.6/5 origin security;
- 300/1,500 integration scale;
- QA_SANDBOX_ONLY 1,500 isolation;
- SQLite integrity `ok`;
- FK violations `0`.

## Return

Return one frozen **ScoreMax V6.5.10** ZIP + SHA-256 + focused evidence.

No broader redesign.
