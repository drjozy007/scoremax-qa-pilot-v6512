# ScoreMax V6.2.5 → V6.2.6 Migration Guide

## Safety rule

Do not migrate the only valuable working database first.

1. Keep the stable V6.2.5 installation unchanged.
2. Copy its database.
3. Install V6.2.6 in a separate folder.
4. Run the dry-run migration against the copy.
5. Review integrity and count preservation.
6. Run browser acceptance before migrating a controlled pilot database.

## Command

```bash
python migrate_v6_2_5_to_v6_2_6.py path/to/scoremax.db --dry-run
```

After successful review:

```bash
python migrate_v6_2_5_to_v6_2_6.py path/to/scoremax.db
```

## Migration behaviour

- creates a verified pre-migration backup;
- creates 14 `mastery_lab_*` tables;
- seeds four configurable laboratory policies;
- seeds seven synthetic profiles;
- imports no candidate questions automatically;
- preserves core data counts;
- verifies SQLite integrity;
- verifies there are no Mastery Laboratory rows in live attempts or mastery.

## Rollback

Stop ScoreMax, retain the failed database for diagnosis and restore the verified `pre-v6_2_6` backup. Do not attempt manual partial deletion of laboratory tables on the only valuable database.
