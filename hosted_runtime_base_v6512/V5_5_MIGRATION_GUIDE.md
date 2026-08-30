# ScoreMax V5.4.2 → V5.5 Migration Guide

## Safe approach

1. Keep the working V5.4.2 folder and ZIP untouched.
2. Copy the V5.4.2 database before any migration.
3. Extract V5.5 into a separate folder.
4. Run the provided migration utility in dry-run mode.
5. Review the JSON report and confirm `integrity_check: ok` and preserved counts.
6. Run the real migration with automatic backup.
7. Start V5.5 and complete the browser checklist.

## Dry run

`py migrate_v5_4_2_to_v5_5.py C:\path\to\scoremax_v4.db --dry-run`

This migrates a temporary copy only.

## Real migration

`py migrate_v5_4_2_to_v5_5.py C:\path\to\scoremax_v4.db`

Unless `--no-backup` is deliberately supplied, the script creates:

`scoremax_v4.db.pre_v5_5_YYYYMMDD_HHMMSS.bak`

It also writes `V5_5_MIGRATION_RESULT.json`.

## What is preserved

The migration is additive/idempotent and is designed to preserve users, roles, questions, attempts, answers, mastery, plans, classes, parent links, reports and existing exam papers.

Existing papers without defensible blueprint evidence are marked `LEGACY_UNPINNED`. They are not fabricated as MDCAT 2026 mocks.

## Rollback

1. Stop ScoreMax.
2. Move the migrated database aside.
3. Copy the `.pre_v5_5_*.bak` file back to the original database filename.
4. Start the untouched V5.4.2 application folder.

Do not attempt to downgrade the V5.5 schema in place.

## Startup migration

V5.5 still performs its idempotent migration at startup for convenience. The utility is recommended because it adds explicit backup, dry-run and impact evidence.
