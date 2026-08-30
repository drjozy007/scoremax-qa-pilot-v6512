# ScoreMax V6.2.7.1 — Reviewer Assurance Hardening

V6.2.7.1 is a narrow assurance patch over V6.2.7. It closes the four Medium findings from the independent Claude audit without adding new product features.

## Hardening delivered

- second-reviewer independence is enforced inside the shared reviewer engine;
- every second review requires a valid first-review parent assignment;
- duplicate batch, first-assignment and second-review overlap checks run inside `BEGIN IMMEDIATE` transactions;
- database-level unique indexes backstop all three governance rules;
- active review time is reconciled against server elapsed time;
- rapid, replayed and multiple-tab timer requests cannot multiply credited time;
- only the currently open, incomplete item in an active assignment can receive time;
- reviewer invitation activation requires both the invitation link and a separate verification code;
- failed verification attempts are counted and locked after eight failures;
- old unused V6.2.7 invitations are invalidated and must be reissued;
- Admin can reissue unused or locked invitations;
- non-acceptance comments must contain meaningful descriptive text;
- release packaging excludes test uploads, synthetic import fixtures and backup folders.

## Current boundary

This remains a controlled-pilot build. Real browser/mobile/assistive-technology testing, live SMTP or separate-channel delivery testing, legal/confidentiality wording review and external reviewer usability testing remain required before external rollout.

## Start locally

```bash
python app.py
```

Or use `start_scoremax_v6_2_7_1.bat` on Windows.

## Upgrade

Use `migrate_v6_2_7_to_v6_2_7_1.py` against a copied V6.2.7 database first. See `V6_2_7_1_MIGRATION_GUIDE.md`.
