# ScoreMax V6.5.9 Acceptance

## Controlled parent

Exact frozen ScoreMax V6.5.8 ZIP SHA-256:

`2a7c1b0f57ae230279c67784ad6403d0acb37a281cd3c435a759f592b3547b25`

## Scope gate

Rectified findings only:

- `SM-GE-CONN-P1-001`
- `SM-GE-CONN-P1-002`

No Growth Engine change. No Power House change. No new contract. No new reward ledger. No learner/mastery/reviewer/UX redesign.

## Platform-side acceptance target

`confirmed_total=0 · P0=0 · P1=0 · payment=PASS · referral=PASS · refund/reversal=PASS · replay=PASS · privacy=PASS · integrity=ok · FK=0`

## Required evidence

- V6.5.9 focused commercial semantics: PASS.
- Frozen `SM_GE_PRODUCT_EVENT_V1` schema SHA remains `b42ae2a0fd1965ec83e561c43e60d68e84395687de1f257948af7b87319019bb`.
- V6.5.8 learner evidence gate: PASS.
- V6.5.7 product activation gate: PASS.
- V6.5.5/6 origin and explicit-port security: PASS.
- Canonical 300/1,500 release scale: PASS.
- Dedicated 1,500 QA_SANDBOX_ONLY scale: PASS with no live questions, learner attempts or real mastery evidence.
- Inherited V6.4 baseline: 605 deterministic checks + synthetic mastery simulation + 3,000-row Emergency Direct Intake PASS.
- SQLite integrity `ok`; foreign-key violations `0`.

## Receiver-side limitation

The exact Growth Engine v0.14.3 frozen candidate SHA named by Central was not physically supplied in this ScoreMax return package. Receiver-runtime connected admission is therefore a separate Central/3-in-1 gate. This release does not substitute a local model for that missing candidate or claim Growth acceptance without its bytes.
