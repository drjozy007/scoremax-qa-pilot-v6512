# ScoreMax V6.2.5 Build Report

## Release

**ScoreMax V6.2.5 — Sustainability, Public Trust & Daily Spark**

Built from the verified V6.2.4 Curriculum Isolation & Accessibility Foundations baseline.

## Delivered scope

### Sustainability and Public Trust

- Public Sustainability page under About/More/footer rather than the core student navigation.
- Four public sections: Sustainability Statement, Current Policies and Commitments, What We Are Doing Now, and Future Sustainability Plan.
- Explicit claim stages: `CURRENT_PRACTICE`, `IN_PROGRESS`, `FUTURE_COMMITMENT`.
- Versioned policy register, commitment register, progress-report structure and feature controls.
- Commitment records include baseline, target, target date, owner, evidence boundary, operating status and public status.
- Growth Engine sustainability JSON is stored as `DRAFT_REVIEW_REQUIRED` and cannot publish or alter public claims automatically.
- Seed copy deliberately avoids quantified environmental claims where no measured baseline exists.

### Daily Spark MVP

- One compact student-dashboard module with two streams only:
  - Academic Spark.
  - English Word of the Day.
- Academic Spark is assembled inside ScoreMax from existing governed question content and student evidence; no duplicate Power House Spark bank is created.
- Selection order: recent missed question, next Study Plan area, then deterministic current-programme recall.
- Real students are protected from demo content and cross-programme fallback.
- Supported compact response formats are limited to single-choice/MCQ, True/False, fill-in-the-blank and numerical items.
- Word of the Day uses a controlled 36-word vocabulary library, age-aware deterministic selection and 120-day repeat avoidance where inventory allows.
- No live AI or network call is required to load or select a word.
- Same-day assignments are immutable and duplicate-resistant.
- Actions: answer/reveal, save, later, dismiss and report.
- `Later` applies a two-hour cooling-off period.
- Reports preserve hidden assignment/source context without exposing technical IDs to students.
- Daily Spark activity is engagement/diagnostic evidence only; it does not create attempts, mastery, recovery, exam-readiness or blueprint-compliance evidence.

### Analytics and administration

- Admin feature controls for Academic Spark and Word of the Day.
- Vocabulary management and stream-level engagement snapshot.
- Deduplicated impressions, engaged assignments and completed assignments.
- Open and completion rates are calculated from distinct assignments and remain bounded from 0% to 100%.
- Sustainability administration for public blocks, policies, commitments, reports and Growth Engine draft intake.

## Additional defects prevented during the build

- Unknown programmes cannot receive Academic Sparks from another curriculum.
- Real students cannot receive demo Spark questions.
- Same-day refresh cannot create a second assignment or inflate impressions.
- Concurrent/double answer submission cannot record both correct and incorrect outcomes.
- Another student cannot act on an assignment by substituting its ID.
- Hidden feature controls suppress already-created assignments as well as new ones.
- Fill-in-the-blank and numerical Sparks no longer render misleading empty option controls.
- Snoozed content is hidden during the cooldown and becomes available afterward.
- Analytics no longer risk percentages over 100% from multiple event types on one assignment.

## Migration verification

The V6.2.4→V6.2.5 migration was dry-run against a real copied V6.2.4 SQLite database.

Verified:

- pre-migration checksum-recorded backup created;
- SQLite integrity: `ok`;
- no reduced core-table counts;
- all ten V6.2.5 tables created;
- 36 vocabulary entries seeded;
- four published Sustainability blocks seeded;
- existing users, questions, attempts, mastery, plans, blueprints, written responses, messages, pilot issues and Knowledge Hub records preserved.

No destructive migration is required.

## Automated verification

The complete inherited and new regression stack passed:

| Suite | Checks |
|---|---:|
| V5.5 Blueprint and Calibration | 52 |
| V6.0 Written Response Intelligence | 34 |
| V6.1 Teacher Discovery and Messages | 41 |
| V6.2 Pilot Readiness and Content Intake | 30 |
| V6.2.1 Session Integrity | 10 |
| V6.2.2 Navigation and Subject Flow | 19 |
| V6.2.3 Student Command Centre | 33 |
| V6.2.4 Curriculum Isolation and Accessibility | 14 |
| V6.2.5 Sustainability and Daily Spark | 34 |
| **Total** | **267** |

The inherited V5.5 suite also verifies global template parsing, literal route references, duplicate routes and explicit POST-form CSRF coverage.

## Honest environment boundary

The build environment does not provide Flask/Werkzeug for a genuine live browser-server session. Automated tests therefore use the existing transparent compatibility harness while exercising the real application functions and temporary SQLite databases.

Still required before public release:

- genuine browser and mobile acceptance;
- keyboard-only and screen-reader testing;
- 200% zoom and responsive-layout inspection;
- visual review of Sustainability copy and claim presentation;
- pilot review of Academic Spark relevance and vocabulary difficulty;
- privacy/legal approval of final public policies and statements;
- production hosting, secrets and infrastructure hardening.

V6.2.5 is a controlled pilot baseline, not approval for unrestricted public deployment.
