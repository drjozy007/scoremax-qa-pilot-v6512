# ScoreMax V6.5.8 — Batch01 Learner / Delivery Evidence Narrow Rectification Specification v1.0

## Parent

Build directly from the frozen **ScoreMax V6.5.7** candidate:

`a93edef7a4ea6cc4b8d5d8e27ef2eecdba29d0be441f974ecec5bebfcef9c118`

Do not redesign any unrelated ScoreMax subsystem. Preserve the admitted Batch01 product-activation gate and all prior integration/security behaviour.

## Mandatory findings to close

### 1. INT-PHSM-B01-LRN-P1-001 — delivery-evidence counters

`SM_PH_DELIVERY_EVIDENCE_V1` must derive recovery/reconfirmation telemetry from immutable attempt evidence instead of emitting hard-coded zeroes.

For every grouped immutable `(question_id, question_version_id, question_checksum)` item:

- `recovery_attempts` = submitted item responses belonging to `assessment_kind='recovery'`;
- `recovery_successes` = correct submitted item responses belonging to those recovery attempts;
- `reconfirmation_attempts` = submitted item responses belonging to `assessment_kind IN ('recall','reconfirmation')`;
- `reconfirmation_successes` = correct submitted item responses belonging to those reconfirmation attempts.

The counts must be derived from the pinned `attempt_answers` + owning `attempts` rows. Do not rescope from mutable current question rows.

Privacy rule: when an item is below `minimum_n` and `sample_suppressed=true`, recovery/reconfirmation counters must not leak sub-threshold information. Emit the contract-safe suppressed representation consistently with the other item metrics. When the item is unsuppressed, emit the true counts.

Permanent regression must prove both:

- a 10-learner unsuppressed recovery/reconfirmation aggregate emits the exact non-zero counts;
- a below-threshold aggregate remains privacy-safe.

### 2. INT-PHSM-B01-LRN-P1-002 — successful reconfirmation state transition

In `update_learning_intelligence_from_attempt()` preserve a recovered area when a clean targeted recall/reconfirmation succeeds.

Mandatory journey:

`10 questions at 40% → Weak Area`

`3 targeted recovery questions at 100% → Recovered`

`3 targeted recall/reconfirmation questions at 100% → remains Recovered`

The successful recall must continue to advance the recall schedule (`successful_recalls`, interval, next due date) and must not clear or regress the recovered state merely because historical cumulative accuracy remains below 75%.

Do not weaken the behaviour for a failed later recall; only fix the successful-reconfirmation transition required by this finding.

## Mandatory preservation gates

Rerun and preserve:

- exact Batch01 300-question intake and ScoreMax-owned activation gate;
- V6.5.7 focused activation tests;
- V6.5.6 / V6.5.5 origin-security gates;
- 300 and 1,500 integration scale gates;
- 3,000-question Emergency Direct Intake;
- DB `integrity=ok` and `foreign_key_violations=0`;
- immutable attempt version/release pinning;
- receiver-bound receipt/replay behaviour.

## Connected rerun gate

Use the same frozen Batch01 300-question release. Central target:

`confirmed_total=0 · P0=0 · P1=0`

Required chain:

`learner delivery → attempt pin → marking → Weak Area → Recovery → successful recall/reconfirmation → mastery → SM_PH_DELIVERY_EVIDENCE_V1 → Power House accepted advisory receipt/replay`

Return **one frozen V6.5.8 candidate**, exact SHA-256, source delta and focused evidence. Do not create any broader redesign.
