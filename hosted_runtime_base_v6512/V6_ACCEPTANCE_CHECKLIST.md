# ScoreMax V6.0 Browser and Academic Acceptance Checklist

## Baseline and migration

- [ ] Preserve the frozen V5.5 Final database and package.
- [ ] Run `migrate_v5_5_to_v6.py <database> --dry-run`.
- [ ] Confirm users, access, attempts, mastery, classes, blueprints, policies and historical mocks are unchanged.
- [ ] Run a real migration only after reviewing the backup and report.

## Power House package governance

- [ ] Import an approved signed written-assessment package.
- [ ] Confirm unsigned or invalidly signed packages are blocked in production mode.
- [ ] Confirm checksum tampering is blocked.
- [ ] Confirm imported academic values cannot be edited in ScoreMax.
- [ ] Activate the reviewed package through an authorised Admin action.

## Typed answer pilot

- [ ] Enable one pilot student.
- [ ] Submit an independent typed answer in Practice Mode.
- [ ] Confirm package, question, rubric and policy versions are pinned.
- [ ] Confirm point-level evidence, contradictions and command-verb findings are understandable.
- [ ] Confirm isolated keywords do not receive full explanation marks.
- [ ] Confirm uncertain evidence does not create high-confidence mastery.
- [ ] Improve the answer and verify the original remains immutable.
- [ ] Complete an unseen reconfirmation and verify it is explicitly linked.
- [ ] Confirm writing evidence reaches the Mastery Engine without directly overwriting mastery records.

## Mock Mode

- [ ] Confirm final submission freezes substantive editing.
- [ ] Confirm feedback release follows the active policy.
- [ ] Confirm the exact assessment/marking policy versions remain auditable.

## Handwriting workflow

- [ ] Upload one and multiple notebook pages.
- [ ] Confirm files are private and unavailable without authorisation.
- [ ] Confirm poor-image warnings appear for controlled test images.
- [ ] Confirm production refuses insecure local storage configuration.
- [ ] Run the labelled local OCR simulation in pilot only.
- [ ] Correct an uncertain transcription and verify original OCR, correction and page image remain preserved.
- [ ] Confirm substantive answer amendment is not disguised as OCR correction.

## Exemplar governance

- [ ] Confirm a non-perfect answer never becomes a candidate.
- [ ] Confirm a perfect but provisional answer never becomes a candidate.
- [ ] Confirm a perfect confirmed independent answer becomes review-eligible only.
- [ ] Approve academically without consent and verify nothing is published.
- [ ] Record separate opt-in consent without academic approval and verify nothing is published.
- [ ] Complete both approvals and verify the exemplar remains hidden before release.
- [ ] Set the library LIVE and verify only eligible exemplars appear.
- [ ] Return it to HIDDEN and verify publication is withdrawn without deleting evidence.
- [ ] Confirm anonymisation/default attribution and guardian-consent workflow with legal review.

## Academic validation

- [ ] Build a fixed chapter gold set covering full, partial, vague, contradictory, misconception-heavy, unusual-valid, weak-grammar and blank responses.
- [ ] Record false-positive, false-negative and point-level agreement rates.
- [ ] Test command verbs and paraphrases.
- [ ] Establish confidence thresholds before wider pilot.
- [ ] Do not release high-stakes claims until validation criteria are approved.
