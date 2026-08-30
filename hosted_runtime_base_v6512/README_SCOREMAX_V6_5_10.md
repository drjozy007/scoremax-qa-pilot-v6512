# ScoreMax V6.5.10 — ScoreMax→Growth Terminal Payment State-Machine Rectification

Narrow child of the exact frozen ScoreMax V6.5.9 candidate.

Parent SHA-256:
`fae57ad5adb0be5373ff9943c263f0bce350c9b25dc936303ada956a5fd167d0`

This release closes only:

- `SM-GE-CONN-P1-003` — terminal payment state transitions were not fail-closed.

The two V6.5.9 findings remain closed:
- governed `metadata.payment_provider`;
- coherent normal successful-payment → refund/reversal payment+reward projection.

No Growth Engine or Power House code is changed. The frozen `SM_GE_PRODUCT_EVENT_V1` contract bytes are unchanged.

## Rectification

ScoreMax now enforces a governed terminal state machine before any terminal helper mutates authoritative state.

Allowed:
- `successful/cleared/paid → refunded` through the full-refund helper;
- `successful/cleared/paid → reversed` through the reversal helper;
- exact repeat of the same completed terminal operation → idempotent no-op.

Fail closed:
- `refunded → reversed`;
- `reversed/voided → refunded`;
- `failed/declined → refunded`;
- `failed/declined → reversed`;
- partial refund without a governed partial-refund reward rule;
- internally contradictory payment lifecycle tuples.

Blocked helper transitions leave the payment row, reward ledger and integration source-change state unchanged.

The integration synchronizer now compiles payment events only from coherent `(status, refund_status, refund_amount_minor, net_amount_minor)` tuples. Contradictory/unsupported tuples produce no outbound event and remain pending rather than being falsely marked projected.

## Preserved

V6.5.9 commercial metadata/reward coherence, V6.5.8 learner evidence, V6.5.7 product activation authority, V6.5.5/6 manifest-origin and explicit-port security, canonical 300/1,500 integration scale, QA_SANDBOX_ONLY 1,500 isolation, learner UX, mastery, reviewer boundaries, Power House ingestion, payments/referrals outside the narrow terminal-state rule, and Emergency Direct Intake.

## Connected status

The exact Growth Engine v0.14.3 SHA named by Central is:
`3c378ea33e06b5421eee6f00047c92c3f7a0add9ba0c8e7e27abf5013416c284`

Those receiver bytes were not physically supplied to this ScoreMax chat. ScoreMax therefore does not claim a receiver-runtime Growth replay. Central/3-in-1 must run the final connected terminal-ordering replay against its exact frozen Growth candidate.
