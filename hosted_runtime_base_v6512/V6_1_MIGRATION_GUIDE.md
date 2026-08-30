# ScoreMax V6.0 → V6.1 Migration Guide

V6.1 is additive. It creates Teacher Discovery, Academic Messages, teacher-group, guardian-consent, moderation and verified-rating tables without rewriting existing V5.5/V6 academic records.

## Dry run

```bash
python migrate_v6_to_v6_1.py path/to/scoremax_v4.db --dry-run
```

Review `V6_1_MIGRATION_RESULT.json`. The SQLite integrity result must be `ok`, and all preserved table counts must remain unchanged.

## Real migration

Stop ScoreMax, take an external backup, then run:

```bash
python migrate_v6_to_v6_1.py path/to/scoremax_v4.db
```

The utility also creates a timestamped `.pre_v6_1_*.bak` backup unless `--no-backup` is deliberately supplied.

## Rollback

Stop ScoreMax, restore the `.pre_v6_1_*.bak` database, and run the frozen V6.0 source package.

## Post-migration checks

- run `python smoke_tests_v6_1.py`, `python smoke_tests_v6.py`, and `python smoke_tests_v5_5.py`;
- confirm Teacher Discovery, Academic Messages and teacher-led groups remain `PILOT`;
- confirm student direct messages remain `HIDDEN`;
- enable pilot flags only for named test accounts;
- verify a teacher profile and approve it before publishing a listing;
- test parent/guardian approval and revocation for an under-18 account;
- test contact-detail holds, report resolution, block controls and verified-review moderation.
