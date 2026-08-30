# ScoreMax V6.3.2 — Governed Chapter Identity

V6.3.2 is a narrow descendant of the accepted V6.3.1 Student UX V2 candidate.
It does not redesign the learner shell or mastery engine. It makes chapter presentation
consistent and source-governed before the founder browser walkthrough.

## What changed
- Added a `chapter_catalogue` presentation layer separate from the raw `questions.chapter` key.
- Supports explicit `Chapter Number` and `Chapter Name` metadata from governed imports.
- Deterministically parses only chapter identity already present in a source label.
- Never invents a missing chapter name or chapter number.
- Chapter cards show chapter number + name when both are governed/available.
- Chapter detail, Practice, Study Plan and mastery selection reuse the same display label.
- Raw chapter keys remain unchanged for URLs, question selection, mastery scope and historic evidence.
- Practice's dynamic chapter renderer now HTML-escapes imported labels before using `innerHTML`.

## Acceptance
- 441 inherited checks PASS.
- 82 V6.3 mastery/application checks PASS.
- 27 V6.3.1 Student UX V2 checks PASS.
- 14 V6.3.2 chapter identity checks PASS.
- 564 deterministic checks total PASS.
- 10,000 synthetic learners / 200,000 randomized invariant attacks PASS with 0 detailed failures, 0 fuzz failures and 0 QA→LIVE leakage.

## Gate
`CHAPTER_IDENTITY_CANDIDATE_PENDING_WINDOWS_BROWSER_ACCEPTANCE`

The next activity is a real Windows login and page-by-page founder walkthrough. Browser/visual acceptance is not claimed by automated tests.
