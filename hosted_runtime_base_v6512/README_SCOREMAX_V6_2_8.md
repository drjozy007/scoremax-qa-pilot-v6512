# ScoreMax V6.2.8 — Student Navigation, Reviewer Import & Commercial Access

V6.2.8 supersedes V6.2.7.2 as the controlled-pilot baseline.

## What changed

### Student navigation

Desktop and laptop students now receive eight persistent primary destinations:

- Dashboard
- Learn
- My Plan
- Tests
- Exams
- Progress
- Knowledge
- More

A second horizontal row directly beneath the primary navigation shows the active section's contextual destinations. Normal student navigation no longer relies on a popup, dropdown panel or separate overlay. Small tablets and mobile devices use a reduced bottom navigation plus the same compact, horizontally scrollable contextual row.

### Persistent subject access

A compact programme-scoped subject switcher appears across the core student Dashboard, Learn, My Plan, Tests, Exams and Progress areas. Every declared subject is shown as one of:

- **Included**
- **Locked — Upgrade**
- **Coming Soon**

All subject access is checked on the server. Missing content never falls back to another programme or curriculum.

### Guided reviewer import

Admin can upload JSON, CSV or XLSX files containing up to 10,000 rows. ScoreMax detects common column names and presents a mapping/preview step instead of requiring a hidden exact schema. Only Question and Correct answer are essential. Optional explanation, mastery, chapter, topic, options and IDs may be mapped or safely defaulted.

A confirmed import is validated and split atomically into separately auditable batches of up to 100. Admin may assign one, several or all batches to one named reviewer. One secure two-part invitation can activate the assigned group, while decisions, progress, timing and quality evidence remain separate for every batch. The reviewer may stop after one batch or continue through all assigned batches.

A safe **Try Reviewer Demo** route creates sample review material so Admin can inspect the reviewer experience and tracking without preparing a production file.

### Study Plans without prescribed time

Student-facing Study Plans no longer ask for or display:

- required hours;
- minutes per activity;
- weekly availability targets;
- estimated completion duration;
- time-pressure or behind-schedule messages.

Plans are organised by priority, sequence, recall/recovery, evidence required, question/test targets and verified completion. Exam dates and real deadlines remain available.

### Package-aware commercial access

Curriculum coverage and access depth are separate entitlements. Examples include:

- Biology only + Level 1 Access;
- Biology and Chemistry + Level 2 Access;
- all currently available FSc Part 1 subjects + Full Access.

Admin can manage single-subject packages, flexible bundles, full-curriculum packages, access tiers and manual/institutional entitlements. The student paywall is available through Account → Access and when a locked subject is selected.

The release is payment-provider neutral. It records checkout requests but does not process live card payments until a gateway is selected and configured.

### Public landing page

- Daily Spark appears before login as a generic, no-write preview.
- Logged-in Daily Spark appears near the top of the student Dashboard and remains personalised without directly awarding mastery.
- Available and Coming Soon programmes are shown directly, without School/College/Entrance Exam category layers.
- Public navigation and page heading use **About Us** consistently.

## Start locally

On Windows, run:

```text
start_scoremax_v6_2_8.bat
```

Or run:

```bash
python app.py
```

On first launch, the terminal displays a one-time bootstrap Admin password. Log in with either `admin` or `ADM-000001` in the **Email or User ID** field.

## Upgrade

Do not overwrite the only working installation or migrate the only valuable database. Install V6.2.8 separately and test it against a copied V6.2.7.2 database first. See `V6_2_8_MIGRATION_GUIDE.md`.
