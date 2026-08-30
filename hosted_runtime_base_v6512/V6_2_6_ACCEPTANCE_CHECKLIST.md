# ScoreMax V6.2.6 Acceptance Checklist

## Installation and migration

- [ ] Install V6.2.6 separately from V6.2.5.
- [ ] Preserve the stable V6.2.5 database.
- [ ] Run migration dry-run on a copied database.
- [ ] Confirm SQLite integrity is `ok`.
- [ ] Confirm no core table count is reduced.
- [ ] Confirm all 14 `mastery_lab_*` tables exist.
- [ ] Confirm the sandbox begins with zero candidates.

## Access and isolation

- [ ] Student cannot navigate to or open Mastery Laboratory routes.
- [ ] Teacher and parent cannot open Mastery Laboratory routes.
- [ ] Admin can open the laboratory.
- [ ] Candidate imports never appear in Subjects, Practice, Exams, Daily Spark or Mastery.
- [ ] No lab run creates a live assessment session, attempt or mastery record.
- [ ] All candidates show all four non-release flags.

## Chapter 1 import

- [ ] Import the 322-candidate corpus into a fresh QA database.
- [ ] Confirm row count and payload checksum.
- [ ] Confirm question-family counts.
- [ ] Confirm seed, variant, scaffold, stimulus, integrated, recovery and reconfirmation relationships.
- [ ] Confirm concept and LO identities.
- [ ] Review every unresolved warning.
- [ ] Retry the same payload and confirm it is rejected as a duplicate.
- [ ] Force an import failure and confirm the whole transaction rolls back.

## Scoring

- [ ] Challenge each family with correct, incorrect and malformed responses.
- [ ] Check multiple-response partial credit.
- [ ] Check cloze blank-level scoring.
- [ ] Check matching and ordering.
- [ ] Check numerical tolerance and units policy if supplied.
- [ ] Check constructed-response rubric/manual-review boundaries.
- [ ] Confirm misconception tags are retained.

## Evidence and mastery

- [ ] Confirm variants and scaffolds cannot inflate independent breadth.
- [ ] Confirm shared-stimulus pairs are group-capped.
- [ ] Confirm evidence writes to concepts and LOs.
- [ ] Confirm question mastery ceilings affect eligibility.
- [ ] Replay all seven synthetic profiles.
- [ ] Confirm repeated variants do not produce verified mastery.
- [ ] Confirm scaffold success requires an independent retest.
- [ ] Confirm delayed forgetting produces recovery need.
- [ ] Confirm genuine Distinction evidence can be verified and reconfirmed synthetically.
- [ ] Confirm every decision has rationale and next action.

## Assurance decision

- [ ] Review Gates 1–5.
- [ ] Review every open blocker.
- [ ] Export at least one synthetic run and independently inspect the evidence.
- [ ] Record one of: Ready for QA sandbox / Ready with restrictions / Not ready.

## Browser and accessibility

- [ ] Keyboard-only operation.
- [ ] 200% zoom.
- [ ] NVDA or VoiceOver review.
- [ ] Mobile/tablet layout.
- [ ] Large batch tables remain usable without horizontal-page breakage.
