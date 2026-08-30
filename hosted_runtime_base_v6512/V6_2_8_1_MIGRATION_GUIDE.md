# ScoreMax V6.2.8 → V6.2.8.1 Migration Guide

1. Close ScoreMax and retain the complete V6.2.8 installation unchanged.
2. Back up the V6.2.8 SQLite database.
3. Extract V6.2.8.1 into a separate folder.
4. Copy the V6.2.8 database into the V6.2.8.1 test folder.
5. Run a dry migration rehearsal:

```bash
python migrate_v6_2_8_to_v6_2_8_1.py path/to/scoremax.db --dry-run
```

6. Confirm:
   - SQLite integrity is `ok`;
   - no core-table count is reduced;
   - reviewer imports, batches, questions, assignments, decisions and timing counts are unchanged;
   - the new reviewer-question and source-sheet columns exist.
7. Only after acceptance, run the same command without `--dry-run` against a copied deployment database.
8. Retain the generated pre-migration backup until the release has completed human acceptance.

V6.2.8.1 does not automatically import a workbook, create reviewer assignments or publish any questions.
