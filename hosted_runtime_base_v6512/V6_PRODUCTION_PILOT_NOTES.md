# ScoreMax V6.0 Production and Pilot Notes

## Default posture

Keep written answers and handwriting in controlled `PILOT`; keep the exemplar library `HIDDEN`.

## Required before external pilot

- persistent application/session secret;
- signed Power House package transport;
- encrypted private object storage and short-lived signed access URLs;
- malware/type/size validation for uploads;
- retention and deletion policy;
- provider agreements confirming student data is not used for training;
- data-location and subprocessors review;
- privacy notice and DPIA-style assessment as appropriate;
- guardian/minor consent review;
- academic gold-set validation and confidence thresholds;
- browser/mobile acceptance;
- monitoring for processing failures and cost usage.

## OCR and graders

The included local OCR simulation is not a production provider. A live adapter must preserve:

- provider/model/version;
- input page hashes;
- word/span confidence;
- original OCR output;
- student corrections;
- retries/errors;
- no-training/data-retention controls.

External grader A and B should produce independent outputs before reconciliation. A second call that simply sees or repeats the first score is not independent.

## Exemplar release

The library must remain hidden until:

- academic standards and consent wording are approved;
- perfect-score and confidence criteria are validated;
- anonymisation is tested;
- attribution/guardian rules are approved;
- access entitlement and exam-window dates are configured.

Withdrawal from live display must not erase historical consent, approval or evidence records.
