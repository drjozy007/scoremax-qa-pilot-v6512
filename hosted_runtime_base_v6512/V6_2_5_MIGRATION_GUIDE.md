# V6.2.4 → V6.2.5 Migration Guide

## Safe sequence

1. Stop ScoreMax.
2. Copy the existing V6.2.4 database and application folder.
3. Run a dry migration:

```bash
python migrate_v6_2_4_to_v6_2_5.py path/to/scoremax.db --dry-run
```

4. Confirm:
   - SQLite integrity is `ok`;
   - no core table count is reduced;
   - all ten V6.2.5 tables exist;
   - at least 30 vocabulary words are seeded;
   - four public Sustainability blocks exist.
5. Run the live migration:

```bash
python migrate_v6_2_4_to_v6_2_5.py path/to/scoremax.db
```

6. Start V6.2.5 and complete the browser checklist.

## Migration behaviour

- Creates a checksum-recorded pre-migration backup.
- Uses the idempotent application migration.
- Adds new tables only; no core table is dropped or rewritten.
- Seeds controlled public-trust content and the Word of the Day library using `INSERT OR IGNORE`.
- Preserves all V6.2.4 users, questions, attempts, mastery, plans, blueprints, written responses, messages, pilot issues and Knowledge Hub records.

## Rollback

Stop the application and restore the generated `pre-v6_2_5` database backup. V6.2.4 code will ignore the additional V6.2.5 tables, but restoring the backup is the clean rollback method.
