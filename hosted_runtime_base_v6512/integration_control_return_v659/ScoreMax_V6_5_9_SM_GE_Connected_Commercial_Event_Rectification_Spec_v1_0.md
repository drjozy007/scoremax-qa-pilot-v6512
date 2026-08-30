# ScoreMax V6.5.9 — ScoreMax → Growth Engine Connected Commercial Event Rectification

## Parent

Exact parent must be the frozen **ScoreMax V6.5.8** candidate:

`2a7c1b0f57ae230279c67784ad6403d0acb37a281cd3c435a759f592b3547b25`

Do not alter Growth Engine. Do not alter Power House. Do not create a new integration contract.

## Scope

Fix only the two centrally reproduced connected P1s.

### P1-001 — payment metadata key

In ScoreMax's `SM_GE_PRODUCT_EVENT_V1` payment projection, use the frozen governed metadata key:

`payment_provider`

Do not emit the ungoverned key `provider`.

Permanent attacks must prove:

- successful payment from real `record_payment()` → `PAYMENT_CLEARED`;
- exact event validates against ScoreMax schema;
- exact event passes Growth Engine v0.14.3 semantic privacy validation;
- raw provider credential/contact data is not emitted.

### P1-002 — refund/reversal and reward coherence

A ScoreMax payment refund/reversal must not generate a Growth event that simultaneously claims a non-negative reward transition incompatible with the payment state.

Use the existing ScoreMax payment/referral reward authority and existing `reverse_referral_reward()` / reward-ledger machinery. Do not create another reward ledger.

Required semantics:

- `PAYMENT_CLEARED` can carry the currently authoritative positive reward facts.
- `PAYMENT_FAILED` must not create positive reward eligibility.
- `PAYMENT_REFUNDED` / `PAYMENT_REVERSED` must be projected with reward state that is compatible with ScoreMax's authoritative reward ledger.
- If the reward is reversed/ineligible, emit the corresponding negative authoritative reward state and a distinct `REFERRAL_REWARD_ELIGIBILITY_CHANGED` event through the existing change queue.
- Never invent a reversed reward merely to satisfy Growth; the ScoreMax reward ledger must be changed by governed ScoreMax logic first.
- Replay of the same refund/reversal transition must be idempotent.

For partial-refund handling, preserve the existing ScoreMax commercial rule if one exists. If no governed partial-refund reward rule exists, fail closed rather than emitting contradictory payment/reward facts.

## Mandatory connected tests

Against the actual frozen Growth Engine v0.14.3 candidate SHA:

`3c378ea33e06b5421eee6f00047c92c3f7a0add9ba0c8e7e27abf5013416c284`

run one disposable real chain:

1. Teacher A registered.
2. Teacher B registered and attributed to A.
3. Student registered and attributed to B.
4. Programme/product event.
5. Successful payment.
6. Direct and one-upstream reward facts.
7. ScoreMax outbox projection.
8. Growth authenticated intake.
9. Identical replay.
10. Refund/reversal transition using governed ScoreMax logic.
11. Growth receives the terminal payment fact and coherent reward transition.

Expected Growth end state:

- payment projection exactly matches ScoreMax authoritative state;
- referral attribution unchanged;
- direct/upstream reward projections exactly match ScoreMax authoritative reward states;
- duplicate replay produces no extra CRM/payment/reward rows;
- no Growth mutation of ScoreMax financial truth.

## Preservation gates

Rerun at minimum:

- V6.5.8 learner evidence gate;
- V6.5.7 product activation gate;
- V6.5.6 manifest-origin/port security;
- existing 300 connected release gate;
- 1,500 QA_SANDBOX scale gate unaffected;
- DB integrity `ok`;
- FK violations `0`.

## Return

Return one frozen V6.5.9 candidate ZIP + SHA-256 + focused connected evidence.

No broader redesign.
