# ScoreMax V6.5.8 — Batch01 Learner Evidence Narrow Rectification

Exact parent: frozen ScoreMax V6.5.7 ZIP SHA-256 `a93edef7a4ea6cc4b8d5d8e27ef2eecdba29d0be441f974ecec5bebfcef9c118`.

Scope is limited to two ScoreMax-owned P1 findings from the Batch01 learner-chain central qualification:

- `INT-PHSM-B01-LRN-P1-001`: derive recovery/reconfirmation counters from immutable `attempt_answers` pins joined to owning `attempts.assessment_kind`, with minimum-N suppression preserved.
- `INT-PHSM-B01-LRN-P1-002`: preserve `Recovered` after a successful targeted recall/reconfirmation while retaining normal failed-recall behaviour.

No learner UX, mastery architecture, product activation authority, reviewer architecture, payment/referral, Power House authority, or Growth Engine behaviour was redesigned.
