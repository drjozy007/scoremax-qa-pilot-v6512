# ScoreMax → Growth Engine — Independent Central Connected Qualification Report v1.0

**Date:** 23 August 2026  
**Central workstream:** SCOREMAX × POWER HOUSE × GROWTH ENGINE — 3-in-1 Integration Control

## Decision

> **SCOREMAX → GROWTH ENGINE THIN CONNECTED SLICE — RECTIFICATION REQUIRED**
>
> `confirmed_total=2 · P0=0 · P1=2`

This qualification used the actual frozen platform candidates:

- **ScoreMax V6.5.8** — SHA-256 `2a7c1b0f57ae230279c67784ad6403d0acb37a281cd3c435a759f592b3547b25`
- **Growth Engine v0.14.3 sealed candidate** — SHA-256 `3c378ea33e06b5421eee6f00047c92c3f7a0add9ba0c8e7e27abf5013416c284`

The frozen `SM_GE_PRODUCT_EVENT_V1` schema is byte-identical on both platforms:

`b42ae2a0fd1965ec83e561c43e60d68e84395687de1f257948af7b87319019bb`

No platform source was edited for the acceptance result.

## Connected scenario executed

A fresh ScoreMax database was used to create authoritative ScoreMax facts through the existing ScoreMax business logic:

1. Teacher A registered.
2. Teacher B registered and was attributed to Teacher A.
3. A student registered and was attributed to Teacher B.
4. A programme-selection product event was committed.
5. A successful PKR payment of 100,000 minor units was committed.
6. ScoreMax created the direct teacher referral reward of 10,000 and one upstream override reward of 2,000.
7. ScoreMax projected committed source changes into its governed `SM_GE_PRODUCT_EVENT_V1` integration outbox.
8. The exact ScoreMax HMAC signing algorithm was used against Growth Engine's real service verifier.
9. Growth Engine's exact v0.14.3 validator and durable inbound processor were used.
10. A refund transition was then attacked as required by the final integration plan.

ScoreMax produced nine schema-valid contract events:

- `TEACHER_REGISTERED` ×2
- `TEACHER_REFERRAL_RECORDED`
- `LEARNER_REGISTERED`
- `STUDENT_REFERRAL_RECORDED`
- `PROGRAMME_SELECTED`
- `PAYMENT_CLEARED`
- `REFERRAL_REWARD_ELIGIBILITY_CHANGED`
- `PAYMENT_REFUNDED`

ScoreMax database integrity ended `ok` with zero foreign-key violations.

## What passed before the defects

The following real cross-platform boundaries are compatible:

- frozen schema identity;
- ScoreMax business idempotency/outbox generation;
- pseudonymous learner identities;
- opaque teacher/referral identities;
- HMAC signature construction and Growth Engine verification;
- teacher registration intake;
- teacher-referral intake;
- learner registration intake;
- student-referral intake;
- programme/product event intake;
- Growth Engine CRM audience projection for those accepted events;
- Growth Engine privacy controls (no raw test names/emails persisted in governed integration state);
- SQLite integrity and FK enforcement.

## Confirmed finding SM-GE-CONN-P1-001 — payment metadata semantic mismatch

**Severity:** P1  
**Owner:** ScoreMax

ScoreMax's production `sync_growth_outbox()` emits payment metadata as:

```json
"metadata": {"provider": "..."}
```

Growth Engine v0.14.3 deliberately fail-closes the frozen contract's open metadata object through a semantic allowlist. The governed key is:

```text
payment_provider
```

not `provider`.

Therefore the exact ScoreMax `PAYMENT_CLEARED` event is rejected by Growth Engine before persistence with:

- HTTP-equivalent status: `422`
- error code: `METADATA_FIELD_NOT_ALLOWLISTED`
- path: `/payload/event_data/metadata/provider`

This prevents the authoritative payment event from reaching Growth Engine and causes the subsequent reward event to lack its required payment projection.

### Diagnostic only

Central changed **only** `provider` → `payment_provider` in memory, recomputed the checksum and resigned the message. With that one diagnostic substitution, Growth Engine accepted the same real ScoreMax payment event, projected the payment, direct reward and upstream reward, and reused the existing learner CRM audience correctly.

The diagnostic was not used as acceptance evidence.

## Confirmed finding SM-GE-CONN-P1-002 — refund/reward transition can become contract-incoherent

**Severity:** P1  
**Owner:** ScoreMax

The current ScoreMax integration synchronizer reads the current referral-reward row while constructing every payment-state event. If a payment obtains `refund_amount_minor > 0` while its referral reward is still non-negative/pending, ScoreMax emits `PAYMENT_REFUNDED` containing the same positive reward IDs/amounts and:

```text
reward_status = pending
```

After the metadata-key diagnostic above, Growth Engine correctly rejects this state with:

- HTTP-equivalent status: `409`
- receipt status: `QUARANTINED`
- error code: `REWARD_PAYMENT_STATE_INVALID`

Growth Engine's v0.14.3 payment/reward guard is behaving as designed: a refunded/reversed payment cannot simultaneously introduce an eligible/pending/paid reward transition.

This is a valid connected integration defect because the frozen ScoreMax database currently permits the refund fact and reward fact to coexist, and the final 3-in-1 qualification explicitly requires refund/reversal ordering to work.

### Diagnostic only

Central separately proved that when ScoreMax's existing `reverse_referral_reward()` is applied before projection, so the authoritative reward state is `reversed`, and the metadata key is corrected, Growth Engine accepts:

- `PAYMENT_REFUNDED`;
- the direct reward reversal;
- the upstream reward reversal;
- the separate `REFERRAL_REWARD_ELIGIBILITY_CHANGED` reversal event.

Growth then ends with payment state `REFUNDED` and both reward projections `REVERSED`.

Again, this was diagnostic proof only and did not modify either frozen candidate.

## Idempotency/replay diagnostic

With the two defects neutralised in memory only, all nine real ScoreMax events were accepted. Replaying the identical nine messages produced no duplicate state:

- integration inbox: unchanged;
- integration product events: unchanged;
- legacy ScoreMax product events: unchanged;
- payment projection count: unchanged;
- reward projection count: unchanged.

This demonstrates that the receiving idempotency architecture is sound once producer semantics match the governed contract.

## Growth Engine disposition

**No Growth Engine rectification is requested.**

Growth Engine v0.14.3 is correctly enforcing:

- the governed privacy metadata allowlist;
- payment/referral authority boundaries;
- reward/payment coherence;
- idempotent projection.

Do not weaken those gates to accept the current ScoreMax payloads.

## Required ScoreMax rectification

Produce **ScoreMax V6.5.9** as a narrow connected-commercial-event rectification only.

1. Change the payment metadata projection key from `provider` to the already-governed `payment_provider` key.
2. Make refund/reversal event projection compatible with ScoreMax's authoritative reward state. A `PAYMENT_REFUNDED` / `PAYMENT_REVERSED` event must never carry a non-negative reward transition that Growth Engine is required to reject.
3. Reuse the existing ScoreMax referral-reward reversal/governance logic rather than building a second reward ledger.
4. Preserve V6.5.8 learner/mastery/evidence behaviour and all previously admitted integration gates.

Target central gate:

`confirmed_total=0 · P0=0 · P1=0 · payment=PASS · referral=PASS · refund/reversal=PASS · replay=PASS · privacy=PASS · integrity=ok · FK=0`

## Final disposition

The ScoreMax → Growth Engine connection is **mostly working**. Registration, referral and ordinary product events already cross correctly. The remaining work is a narrow ScoreMax producer-side commercial-event compatibility fix.

Do not alter Growth Engine and do not reopen Power House.
