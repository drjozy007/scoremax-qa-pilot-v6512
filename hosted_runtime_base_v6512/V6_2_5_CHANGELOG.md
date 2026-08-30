# ScoreMax V6.2.5 Changelog

## Added

- Public `Sustainability` section under About/More and the public footer.
- Sustainability governance tables for public blocks, policies, commitments, progress reports and Growth Engine draft intake.
- Explicit claim stages: Current Practice, In Progress and Future Commitment.
- Admin Sustainability editor with version, owner, evidence, baseline, target, target date and publication controls.
- Daily Spark MVP on the student dashboard.
- Academic Spark created from governed ScoreMax questions and personalised using programme, prior mistakes and Study Plan context.
- Word of the Day from a seeded 36-word controlled vocabulary library.
- Age-aware, deterministic and repeat-limited word selection.
- Spark actions: answer/reveal, save, Later, dismiss and report.
- Spark impression, answer, reveal, save, snooze, dismiss and report analytics.
- Admin Daily Spark controls, vocabulary editor and engagement snapshot.
- V6.2.4→V6.2.5 migration script and dry-run verification.

## Hardened

- Academic Spark is programme-scoped and excludes demo content for real students.
- Same student/day/stream assignment is immutable and concurrency-safe.
- Impression and answer events are duplicate-resistant; engagement rates use distinct assignments and are bounded to 100%.
- Students cannot act on another learner's Spark assignment.
- Double answer submission records one result only.
- Academic Spark is limited to compact supported response formats.
- `Later` hides a Spark for a two-hour cooling-off period and safely restores it afterward.
- Daily Spark never creates an assessment attempt or mastery record.
- Hidden feature controls suppress previously assigned Sparks as well as new ones.
- Growth Engine sustainability drafts cannot change the public register automatically.

## Deferred

- Additional Discovery Sparks such as history facts, science facts and logic puzzles.
- Live AI generation of daily content.
- Punitive streaks or formal mastery from Daily Spark.
- Public environmental-impact claims before measurable baselines exist.
