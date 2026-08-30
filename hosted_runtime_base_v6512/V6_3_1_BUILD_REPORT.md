# ScoreMax V6.3.1 — Student UX V2 Build Report

## Decision

Extend the rectified V6.3.0 RC2 rather than rebuild ScoreMax. Make the student surface materially simpler while preserving the existing mastery, assessment, Study Plan, exam, recovery, security and data-integrity engines.

## What already existed and remains untouched

- V6.3 Universal Mastery foundation and false-mastery protections.
- Atomic assessment submission / concurrency protection.
- Study Plan, weak areas, recovery, reconfirmation, exams/mocks, Progress and access architecture.
- Power House as academic authority; ScoreMax reviewer workflow not part of forward design.
- Growth Engine event/outbox boundary.

## What changed

1. Student shell simplified to six core journeys plus one subject-context row.
2. Home rebuilt around next action rather than system capability panels.
3. Subject and chapter screens rebuilt around Existing Mastery versus Potential Mastery.
4. Potential Mastery is computed from eligible current production inventory and active mastery requirements rather than raw accuracy or decorative percentages.
5. Practice, Progress and Results use simpler learner language and defer technical metadata.
6. Local internal-live database renamed for V6.3.1 so testing starts from a fresh descendant database.

## Principal risks attacked

- Demo inventory inflating potential mastery — blocked and tested.
- Practice accuracy being confused with formal mastery — visually and logically separated.
- Commercial access redefining academic potential — separated.
- Stale mastery level disappearing when Verification Due — prevented.
- Historical UX regression tests being silently rewritten — originals preserved and supersession documented.
- Runtime artifacts leaking into the release package — packaging exclusions enforced.

## Acceptance evidence

- 550/550 deterministic checks.
- 107/107 Jinja templates parse.
- 10,000-learner / 200,000-invariant synthetic mastery attack passes.
- Backup/restore integrity passes.

## Pending

- Real Windows installation replay.
- Real Edge/Chrome visual and interaction walkthrough with the product owner.
- Mobile/keyboard/200% zoom acceptance.
- Any UX refinements emerging from that walkthrough.

## Rollback

Rollback parent remains the immutable V6.3.0 RC2 package with SHA-256:
`b7850f5ba0e703b755d05de50e51a5fb8c3fee32bcf5fbee47f2e5475f0db8fa`.
