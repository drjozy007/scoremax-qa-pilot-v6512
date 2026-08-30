# V6.1 → V6.2 Migration Guide

## 1. Preserve V6.1

Keep the V6.1 ZIP and database unchanged as the rollback baseline.

## 2. Dry run

From the V6.2 folder:

```text
python migrate_v6_1_to_v6_2.py C:\path\to\scoremax.db --dry-run
```

The script:

- creates an integrity-checked `pre-v6_2` backup;
- migrates a disposable copy;
- compares core table counts;
- verifies all V6.2 tables;
- runs `PRAGMA integrity_check`.

## 3. Live migration

```text
python migrate_v6_1_to_v6_2.py C:\path\to\scoremax.db
```

Do not interrupt the process.

## 4. Verification

Confirm:

- integrity is `ok`;
- no core table count decreased;
- all 13 V6.2 tables exist;
- Admin → Pilot Readiness opens;
- existing users, attempts, mastery, blueprints, written answers and messages remain visible.

## Rollback

Stop ScoreMax, rename the migrated database, and restore the automatically created `pre-v6_2` backup. Do not merge rows manually after a failed migration.
