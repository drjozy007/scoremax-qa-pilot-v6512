# ScoreMax V6.5.9 → Growth Engine v0.14.3
## Independent Central Connected Requalification Report v1.0

**Date:** 23 August 2026  
**Workstream:** SCOREMAX × POWER HOUSE × GROWTH ENGINE — 3-in-1 Integration Control

## Decision

> **SCOREMAX V6.5.9 — CONNECTED RECTIFICATION REQUIRED**
>
> `confirmed_total=1 · P0=0 · P1=1`

The two findings that caused V6.5.9 to be requested are closed. A wider terminal-payment ordering attack found one new ScoreMax-side P1. Growth Engine v0.14.3 requires no change.

## Exact candidates

### ScoreMax V6.5.9

- Frozen candidate SHA-256: `fae57ad5adb0be5373ff9943c263f0bce350c9b25dc936303ada956a5fd167d0`
- Exact parent: ScoreMax V6.5.8
- Parent SHA-256: `2a7c1b0f57ae230279c67784ad6403d0acb37a281cd3c435a759f592b3547b25`
- Frozen `SM_GE_PRODUCT_EVENT_V1` schema SHA-256: `b42ae2a0fd1965ec83e561c43e60d68e84395687de1f257948af7b87319019bb`
- Release manifest: **532/532 payload entries exact**
- ZIP CRC: **PASS**
- No runtime cache/backups/private-upload artifacts present in the frozen ZIP.

### Growth Engine v0.14.3

- Exact sealed candidate SHA-256: `3c378ea33e06b5421eee6f00047c92c3f7a0add9ba0c8e7e27abf5013416c284`
- Contract schema bytes match ScoreMax exactly.

## V6.5.9 source delta

The child is genuine and narrow. Production behaviour changes are confined to:

1. `app.py`
   - governed full-refund helper;
   - governed reversal helper;
   - reward reversal can participate in the same transaction.
2. `scoremax_integration_v1.py`
   - governed `payment_provider` metadata key;
   - fail-closed producer checks for contradictory payment/reward combinations;
   - V6.5.9 release identity.

No Power House or Growth Engine source was changed.

## Preservation evidence independently rerun

- V6.5.9 commercial semantics: **30/30 PASS**
- V6.5.8 learner evidence: **PASS**
- V6.5.7 product activation: **25/25 + wrapper assertion PASS**
- V6.5.6 explicit-port security: **44/44 PASS**
- V6.5.5 manifest-origin security: **23/23 PASS**
- V6.5.4 central rectification: **31/31 PASS**
- V6.5 integration: **48/48 PASS**
- canonical Power House 300/1,500 scale: **PASS**
- QA_SANDBOX_ONLY 1,500 scale: **PASS** with live questions=0, attempts=0, mastery evidence=0
- inherited V6.4 baseline completed: **605 deterministic checks + synthetic mastery simulation + 3,000-row Emergency Direct Intake PASS**

## Same real connected chain — PASS

Central rebuilt the commercial chain using ScoreMax's existing business/referral/event logic:

Teacher A → Teacher B → Student → programme selection → successful payment → direct reward → one-upstream reward → governed full refund; plus a separate governed reversal payment.

ScoreMax produced **14 exact contract events**. Every envelope validated against the frozen ScoreMax schema. ScoreMax-produced HMAC headers were then verified by the exact Growth Engine v0.14.3 verifier.

Growth Engine results:

- first pass: **14/14 ACCEPTED**;
- identical replay: **14/14 returned the same durable receipts**;
- integration inbox count unchanged on replay;
- integration product-event count unchanged on replay;
- payment projection count unchanged on replay;
- reward projection count unchanged on replay;
- primary payment ended `REFUNDED`, refund amount `100000`;
- separate reversal payment ended `REVERSED`;
- four direct/upstream reward projections ended `REVERSED` and retained exact ScoreMax IDs/teacher lineage/amounts;
- **10** non-system product events linked to CRM audience projection;
- open integration quarantines: **0**;
- exact test emails, provider references and payment-method text were absent from the Growth database;
- ScoreMax SQLite integrity: `ok`, FK violations `0`;
- Growth SQLite integrity: `ok`, FK violations `0`.

This closes both original connected findings.

## Original finding closure

### SM-GE-CONN-P1-001 — CLOSED

ScoreMax now emits payment metadata as:

`metadata.payment_provider`

The ungoverned `metadata.provider` key is absent. The exact Growth v0.14.3 privacy/semantic validator accepts the real payment events. Provider references/payment methods/credentials remain inside ScoreMax.

### SM-GE-CONN-P1-002 — CLOSED for the intended successful-payment → terminal transition paths

For a normal successful payment followed by either the governed full-refund helper or governed reversal helper:

- ScoreMax commits terminal payment state and reward reversal coherently;
- the payment event is accepted by Growth;
- the distinct reward reversal event is accepted by Growth;
- direct and one-upstream reward identities/amounts remain authoritative and unchanged;
- replay remains idempotent.

## New confirmed finding SM-GE-CONN-P1-003 — terminal payment state transitions are not fail-closed

**Severity:** P1  
**Owner:** ScoreMax

V6.5.9 added terminal payment helpers, but they do not enforce a coherent terminal state machine.

### Dynamic reproduction A — refund → reversal creates cross-system truth divergence

Central executed:

1. successful payment;
2. governed full refund;
3. successful ScoreMax → Growth projection;
4. `reverse_payment_transaction()` on that already-refunded payment;
5. another ScoreMax integration synchronization.

ScoreMax accepted step 4 and changed its authoritative payment row to:

- `status = reversed`
- `refund_amount_minor = 100000`
- `refund_status = reversed`

However no new `PAYMENT_REVERSED` event was emitted.

The synchronizer currently gives `refund_amount_minor > 0` precedence over the authoritative status. It therefore resolves the row to the already-existing `PAYMENT_REFUNDED` identity. The source change is then treated as projected, even though Growth has not received the new ScoreMax terminal state.

The exact Growth v0.14.3 candidate therefore remains:

- `current_state = REFUNDED`
- `last_event_type = PAYMENT_REFUNDED`

while ScoreMax authoritative state is `reversed`.

This breaches the frozen authority model: Growth is permitted to project/report ScoreMax financial truth, but the producer must not silently leave Growth on a different terminal payment state.

### Dynamic reproduction B — reversal → refund is also permitted

V6.5.9 allows a fully reversed payment to be changed to fully refunded. ScoreMax emits `PAYMENT_REFUNDED` after `PAYMENT_REVERSED` rather than failing closed for an unsupported cross-terminal transition.

No governed transition policy was identified that authorizes switching between these two terminal states.

### Dynamic reproduction C — failed payment → refund is permitted

A payment recorded as `failed` can be passed to `refund_payment_transaction()` and becomes `refunded`, producing `PAYMENT_FAILED` followed by `PAYMENT_REFUNDED`.

There is no governed failed-payment refund rule in the supplied V6.5.9 rectification scope. This should fail closed rather than create a new financial lifecycle implicitly.

## Why this blocks connected admission

The final 3-in-1 adversarial plan explicitly requires payment/refund/reversal ordering. The exact V6.5.9 happy paths are now correct, but the terminal transition API can still create an authoritative ScoreMax state that either:

- is not projected at all; or
- changes one terminal state into another without a governed transition rule.

This is a connected P1, not a Growth Engine defect.

## Required next action

Produce a **narrow ScoreMax V6.5.10** from the exact V6.5.9 candidate. Do not alter Growth Engine, Power House, the integration contract, learner/mastery logic, or referral architecture.

Required closure is specified in `ScoreMax_V6_5_10_SM_GE_Terminal_Payment_State_Machine_Rectification_Spec_v1_0.md`.

Target:

`confirmed_total=0 · P0=0 · P1=0 · payment=PASS · referral=PASS · terminal_ordering=PASS · replay=PASS · privacy=PASS · integrity=ok · FK=0`

## Growth Engine disposition

> **NO GROWTH ENGINE RECTIFICATION REQUIRED**

Growth Engine v0.14.3 accepted the coherent V6.5.9 chain, rejected no valid event, preserved exact ScoreMax payment/reward lineage, and remained idempotent/private.
