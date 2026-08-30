# Independent Review Brief — ScoreMax V6.2.5

Do not rely only on the reported smoke-suite total. Challenge the real application and database.

## Highest-risk questions

1. Can an empty or unknown programme receive an Academic Spark from FSc, Matric or another market?
2. Can a real student receive demo content through Daily Spark in local/pilot mode?
3. Can two simultaneous dashboard requests create two assignments or impressions for one student/day/stream?
4. Can double submission create both a correct and incorrect event for one Academic Spark?
5. Can Student B answer, save, dismiss or report Student A's Spark by changing `assignment_id`?
6. Does answering a Spark create an `attempt`, `attempt_answer`, mastery record, blueprint projection or Study Plan verification?
7. Does hiding a feature suppress an existing daily assignment?
8. Can Growth Engine JSON create or modify a published Sustainability claim?
9. Are future targets clearly distinguishable from current practice in the real rendered page?
10. Is Word of the Day selected without a live model/network call and without immediate repetition?
11. Does `Later` hide only the selected student's assignment during the cooldown and restore it afterward?
12. Can analytics exceed 100% because one assignment creates several event types?

## Required empirical tests

- Create two programmes and three students; leave one programme empty.
- Add approved non-demo questions to only one programme.
- Reproduce same-day refresh and concurrent-request conditions.
- Force two answer submissions with different selected answers.
- Attempt assignment-ID substitution across accounts.
- Compare counts in attempts, mastery and projections before/after Spark activity.
- Toggle each feature HIDDEN after an assignment exists.
- Import a Growth Engine sustainability draft containing `status=PUBLISHED` and confirm it remains review-only.
- Test Later/cooldown expiry and verify engagement rates remain between 0% and 100%.
- Test keyboard, 200% zoom, NVDA/VoiceOver and mobile touch.

## Deployment boundary

V6.2.5 remains a controlled pilot baseline. Public deployment still requires real accessibility acceptance, production infrastructure hardening, privacy review, verified public copy and real governed academic content.
