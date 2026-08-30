# ScoreMax V5.5 Final → V6.0 Migration Guide

## Principle

V6 uses additive, idempotent tables/columns. Existing users, access entitlements, questions, attempts, mastery, Study Plans, classrooms, blueprints, policies, mocks and reports must remain unchanged.

## Dry run

```bash
python migrate_v5_5_to_v6.py path/to/scoremax_v4.db --dry-run
```

Review the JSON report and SQLite integrity result.

## Real migration

Stop the application, take an external backup, then run:

```bash
python migrate_v5_5_to_v6.py path/to/scoremax_v4.db
```

The utility creates a timestamped backup unless `--no-backup` is explicitly supplied.

## Rollback

Stop the application and replace the migrated database with the timestamped `.pre_v6_0_*.bak` file. Use the frozen V5.5 Final source package.

## Post-migration checks

- run both smoke suites;
- confirm existing user/attempt/mastery/class/mock counts;
- confirm written feature controls default to PILOT/HIDDEN;
- import only approved test packages in local/pilot mode;
- do not enable public written-answer or exemplar access until acceptance is complete.
