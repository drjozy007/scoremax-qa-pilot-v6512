# ScoreMax V6.2 — Pilot Readiness & Content Intake

## Permanent boundary

- **Power House** creates and governs assessment blueprints, prompt packs, question families, questions, evidence, review and academic approval.
- **ScoreMax** receives immutable governed transports, validates delivery readiness, delivers learning and preserves student evidence.
- **Growth Engine** may provide Knowledge Hub drafts, but it cannot publish without human review.

## Main Admin areas

- Pilot Readiness
- Power House Prompt Bridge
- Governed Excel/CSV Import
- Pilot Issues
- Pilot Operations Analytics
- Knowledge Hub Administration

## Default release state

- Content intake: `PILOT`
- Pilot issue reporting: `PILOT`
- Pilot analytics: `PILOT`
- Knowledge Hub: `HIDDEN`
- Existing V6 written-response controls: unchanged
- Existing V6.1 teacher/messaging controls: unchanged

## Start

Install the versions in `requirements.txt`, set a persistent `SCOREMAX_SECRET`, and run:

```text
python app.py
```

For production content intake, configure protected storage:

```text
SCOREMAX_CONTENT_INTAKE_DIR=<protected directory>
SCOREMAX_BACKUP_DIR=<protected backup directory>
SCOREMAX_PILOT_UPLOAD_DIR=<protected screenshot directory>
```
