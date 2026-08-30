# ScoreMax V6.5.10 — Integration Control Handoff

## Decision
Return one frozen V6.5.10 candidate to 3-in-1 for independent connected requalification.

## Exact lineage
Parent: ScoreMax V6.5.9

Parent SHA-256:
`fae57ad5adb0be5373ff9943c263f0bce350c9b25dc936303ada956a5fd167d0`

## ScoreMax finding closed
`SM-GE-CONN-P1-003`

ScoreMax now rejects unsupported terminal-state transitions before any authoritative mutation, and its synchronizer will not infer PAYMENT_REFUNDED merely from a positive refund amount. Only coherent payment lifecycle tuples can generate outbound payment events; contradictory tuples remain pending.

## Preserved authority
- ScoreMax remains authoritative for payment/referral reward facts.
- Growth Engine remains projection/CRM only.
- Existing direct + one-upstream reward lineage remains unchanged.
- Frozen `SM_GE_PRODUCT_EVENT_V1` contract remains unchanged.
- Power House is untouched.

## Central connected rerun
Use exact Growth Engine v0.14.3 SHA-256:
`3c378ea33e06b5421eee6f00047c92c3f7a0add9ba0c8e7e27abf5013416c284`

Re-run:
Teacher A → Teacher B → Student → programme selection → successful payment → direct/upstream reward → replay → full refund;
plus a separate successful payment → reversal;
then terminal-ordering attacks:
- refund → reversal;
- reversal → refund;
- failed → refund;
- failed → reversal;
- partial refund;
- raw contradictory lifecycle tuples.

Target:
`confirmed_total=0 · P0=0 · P1=0 · payment=PASS · referral=PASS · terminal_ordering=PASS · replay=PASS · privacy=PASS · integrity=ok · FK=0`
