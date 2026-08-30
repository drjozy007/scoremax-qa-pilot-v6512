# Daily Spark MVP Contract

## Streams

- `ACADEMIC`: source type `QUESTION`; approved, active, programme-scoped ScoreMax content only.
- `WORD`: source type `VOCABULARY`; controlled stored library, selected by age and repeat history.

## Selection order for Academic Spark

1. Approved question previously answered incorrectly, excluding recent Spark repetition.
2. Approved question aligned to the next Study Plan subject/chapter/topic.
3. Deterministic approved question from the learner's programme.

Academic delivery is limited to compact supported response types: single-choice/MCQ, True/False, fill-in-the-blank and numerical.

## Evidence boundary

Daily Spark can inform engagement and future recommendation logic. It does not create an assessment attempt and cannot award formal mastery, recovery, blueprint compliance or exam readiness.

## Assignment integrity

One immutable assignment per `student_id + spark_date + stream`. Payload and content version are snapshotted. Feature controls can suppress display without deleting evidence.

## Analytics events

`IMPRESSION`, `OPEN`, `ANSWER_CORRECT`, `ANSWER_INCORRECT`, `REVEAL`, `SAVE`, `SNOOZE`, `DISMISS`, `REPORT`.

`SNOOZE` applies a two-hour cooling-off period. Open and completion rates use distinct assignments rather than raw event totals.
