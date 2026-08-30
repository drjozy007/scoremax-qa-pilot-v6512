# V6.2.2 → V6.2.3 Migration Guide

## Before migration

1. Stop ScoreMax.
2. Copy the application folder.
3. Back up the SQLite database separately.
4. Verify the V6.2.2 baseline before changing the pilot copy.

## Dry run

```bash
python migrate_v6_2_2_to_v6_2_3.py path/to/scoremax.db --dry-run
```

The report must show:

- SQLite integrity `ok`;
- no reduced core-table counts;
- all three V6.2.3 tables present;
- `coach_enabled` and `future_pathway_code` present on users.

## Live migration

```bash
python migrate_v6_2_2_to_v6_2_3.py path/to/scoremax.db
```

The script creates an integrity-checked pre-migration backup before calling the idempotent application migration.

## New data

- `student_pathway_preferences`
- `coach_nudge_events`
- `platform_social_links`
- `users.coach_enabled`
- `users.future_pathway_code`
- pilot-feedback context/page columns

Existing evidence, questions, attempts, mastery, blueprints, classes, written responses and Academic Messages are not rewritten.

## Rollback

Stop the application and restore the timestamped `pre-v6_2_3` database backup. V6.2.2 code does not understand the new UX tables, but the migration makes no destructive changes to existing records.
