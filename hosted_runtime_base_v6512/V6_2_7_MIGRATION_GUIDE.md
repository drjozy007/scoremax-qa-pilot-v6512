# ScoreMax V6.2.6 → V6.2.7 Migration Guide

## Safety rule

Do not migrate the only valuable ScoreMax database first.

1. Preserve the stable V6.2.6 folder and database unchanged.
2. Copy the database into a separate V6.2.7 installation.
3. Run the migration in dry-run mode.
4. Review SQLite integrity and core-table count preservation.
5. Test the Admin and reviewer journeys in a real browser.
6. Migrate a controlled pilot copy only after acceptance.

## Commands

```bash
python migrate_v6_2_6_to_v6_2_7.py path/to/scoremax.db --dry-run
```

After successful acceptance:

```bash
python migrate_v6_2_6_to_v6_2_7.py path/to/scoremax.db
```

## Migration behaviour

- creates a verified pre-migration backup;
- creates eight isolated `reviewer_*` tables;
- seeds the Reviewer Workspace control in `QA_ONLY` state;
- creates no reviewer accounts automatically;
- imports no review questions automatically;
- creates no assignments or invitations automatically;
- preserves all tested ScoreMax core data;
- verifies SQLite integrity.

## Rollback

Stop ScoreMax and restore the verified `pre-v6_2_7` backup. Do not manually delete reviewer tables from the only valuable database.
