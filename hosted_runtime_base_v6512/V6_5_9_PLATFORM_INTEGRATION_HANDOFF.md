# ScoreMax V6.5.9 — Integration Control Handoff

## Decision

Return one frozen V6.5.9 candidate to 3-in-1 for independent connected admission.

## Exact lineage

Parent: ScoreMax V6.5.8

Parent SHA-256:
`2a7c1b0f57ae230279c67784ad6403d0acb37a281cd3c435a759f592b3547b25`

## Central findings closed on ScoreMax side

### SM-GE-CONN-P1-001
Payment metadata projection now uses:

`metadata.payment_provider`

The ungoverned `metadata.provider` key is no longer emitted.

### SM-GE-CONN-P1-002
ScoreMax now provides governed terminal payment transitions through the existing payment/reward authority. Refund/reversal state and direct/one-upstream reward reversal are committed coherently. The integration producer independently fails closed if raw database state is contradictory, and partial refund is blocked until a governed partial-refund reward rule exists.

## Preserved authority boundaries

- ScoreMax remains authoritative for payment and referral reward facts.
- Growth Engine remains a commercial projection/CRM consumer and cannot mutate ScoreMax financial truth.
- One upstream teacher level remains the maximum.
- Power House is untouched.

## Independent central action

Use the exact frozen Growth Engine v0.14.3 candidate already controlled by 3-in-1 to rerun the same real chain:

Teacher A → Teacher B → Student → programme event → cleared payment → direct/upstream rewards → replay → governed refund/reversal → terminal payment/reward projections.

Target:

`confirmed_total=0 · P0=0 · P1=0 · payment=PASS · referral=PASS · refund/reversal=PASS · replay=PASS · privacy=PASS · integrity=ok · FK=0`
