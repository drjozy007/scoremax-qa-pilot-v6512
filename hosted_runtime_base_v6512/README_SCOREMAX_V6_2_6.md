# ScoreMax V6.2.6 — Pre-Pilot Assurance & Mastery Laboratory

V6.2.6 extends the verified V6.2.5 Sustainability and Daily Spark baseline with a sealed technical environment for testing the Chapter 1 candidate corpus before any question is admitted to the live bank or shown to a real student.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Or use `start_scoremax_v6_2_6.bat` on Windows.

## Open the laboratory

Log in as an Admin and open:

> Pilot Readiness → Mastery Laboratory

The laboratory accepts JSON, CSV and XLSX candidate files. A technical sample covering the supported question families can be downloaded or imported from the page.

## Hard evidence boundary

Every imported candidate is forced to remain:

- `QA_SANDBOX_ONLY`
- `NOT_STUDENT_RELEASED`
- `NOT_BANK_APPROVED`
- `NOT_VALID_FOR_REAL_MASTERY`

The laboratory uses dedicated `mastery_lab_*` tables. It does not write to:

- the live `questions` table;
- student `assessment_sessions` or `attempts`;
- live `mastery_records`;
- real Study Plans.

## Supported question families

- standard MCQ;
- four-statement selection;
- True/False;
- cloze;
- diagram/data stimulus;
- matching;
- ordering;
- multiple response;
- numerical interpretation;
- constructed response;
- misconception probe;
- adaptive recovery item/pathway.

The data model retains family-specific answer and marking configuration. It does not convert every family into an ordinary MCQ.

## Evidence identity

The laboratory distinguishes:

- independent seed;
- true variant;
- scaffold;
- shared-stimulus pair;
- integrated question;
- recovery item;
- reconfirmation item.

Seed variants, scaffolds and shared-stimulus items are identity-capped so closely related responses cannot manufacture independent breadth.

## Synthetic learner histories

Seven deterministic profiles are included:

1. high recall but weak application;
2. strong-looking performance from repeated variants only;
3. broad performance with one missing concept;
4. scaffold success followed by failed independent retest;
5. apparent mastery followed by delayed forgetting;
6. genuine Distinction evidence;
7. inconsistent or guessed answers.

Every phase records scoring, concept/LO evidence, state transition, rationale, recovery need and next action.

## Internal mastery states

`UNASSESSED`, `PROVISIONAL_FOUNDATION`, `VERIFIED_FOUNDATION`, `PROVISIONAL_EXAM_READY`, `VERIFIED_EXAM_READY`, `PROVISIONAL_ADVANCED`, `VERIFIED_ADVANCED`, `PROVISIONAL_DISTINCTION`, `VERIFIED_DISTINCTION`, `VERIFICATION_DUE`, `RECOVERY_REQUIRED`, `RECOVERY_IN_PROGRESS`, `RECONFIRMED`.

These are laboratory states only. They do not alter the student-facing mastery record.

## Assurance gates

1. Content Admission
2. Assessment Execution
3. Mastery and Study Plan
4. Security, Privacy and Isolation
5. Release Acceptance

Gate 5 means only that the QA-sandbox milestone is technically accepted. It does **not** approve candidates for students or real mastery.

See `V6_2_6_BUILD_REPORT.md`, `V6_2_6_ACCEPTANCE_CHECKLIST.md`, `V6_2_6_MASTERY_LAB_CONTRACT.md` and `V6_2_6_MIGRATION_GUIDE.md`.
