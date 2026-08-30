# ScoreMax V6.5.9 — ScoreMax→Growth Connected Commercial Event Rectification

Narrow child of the exact frozen ScoreMax V6.5.8 candidate.

Parent SHA-256:
`2a7c1b0f57ae230279c67784ad6403d0acb37a281cd3c435a759f592b3547b25`

This release closes only the two centrally reproduced ScoreMax-owned P1s in the real ScoreMax→Growth thin connected slice:

- `SM-GE-CONN-P1-001` — payment metadata used `provider` instead of governed `payment_provider`.
- `SM-GE-CONN-P1-002` — refund/reversal projection could carry a non-negative reward state.

No Growth Engine or Power House code is included or changed.

## Rectification

- `PAYMENT_*` events now use `metadata.payment_provider` only.
- Provider transaction references, payment methods, credentials and contact data remain inside ScoreMax.
- Existing `reverse_referral_reward()` remains the reward authority; it gained an optional transaction-join mode so payment and reward terminal transitions can commit atomically.
- Governed full-refund and payment-reversal helpers update the payment truth and the existing direct/one-upstream reward ledger in one commit.
- The producer fails closed if a refunded/reversed/failed payment still carries incompatible positive reward authority.
- Partial refund fails closed because no governed partial-refund reward rule currently exists.
- No new reward ledger, integration contract, payment truth store or CRM surface was created.

## Preserved

V6.5.8 learner/mastery/delivery-evidence semantics, V6.5.7 ScoreMax activation authority, V6.5.5/6 manifest-origin and explicit-port security, learner UX, reviewer boundaries, payments/referrals outside the narrow transition helper, Power House ingestion, QA Mastery Laboratory isolation, and Emergency Direct Intake.

## Cross-system status

The exact Growth Engine v0.14.3 candidate bytes were not physically included in the central return package supplied to this ScoreMax chat. ScoreMax therefore does not claim an independent receiver-runtime acceptance here. The focused producer tests reproduce the exact central semantic requirements and preserve the frozen `SM_GE_PRODUCT_EVENT_V1` schema SHA; Central/3-in-1 should perform the independent connected receiver replay against its frozen Growth candidate.
