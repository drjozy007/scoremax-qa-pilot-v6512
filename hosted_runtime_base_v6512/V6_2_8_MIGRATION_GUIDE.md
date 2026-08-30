# ScoreMax V6.2.7.2 → V6.2.8 Migration Guide

## Reliability rule

Do not migrate the only valuable ScoreMax database in place during acceptance.

1. Keep the V6.2.7.2 installation and database unchanged.
2. Extract V6.2.8 into a separate folder.
3. Copy the V6.2.7.2 database into the V6.2.8 test folder.
4. Back up the copied database again.
5. Run the dry-run migration.
6. Review the JSON verification report.
7. Run the live migration only against the test copy.
8. Complete browser and workflow acceptance before changing any production pointer.

## Dry run

```bash
python migrate_v6_2_7_2_to_v6_2_8.py path/to/copied_scoremax.db --dry-run
```

The script:

- creates a timestamped SQLite backup;
- migrates a separate temporary copy in dry-run mode;
- verifies SQLite integrity;
- compares core and reviewer row counts before/after;
- checks the new reviewer-import and package-entitlement tables, columns and indexes;
- confirms that no reviewer import, student entitlement, entitlement-history or checkout row is created automatically;
- confirms that the governed package catalogue is seeded.

## Live migration of the acceptance copy

```bash
python migrate_v6_2_7_2_to_v6_2_8.py path/to/copied_scoremax.db
```

## Schema additions

New tables:

- `reviewer_imports`
- `coverage_packages`
- `student_package_entitlements`
- `package_entitlement_history`
- `checkout_requests`

New reviewer columns:

- `reviewer_batches.import_id`
- `reviewer_batches.batch_number`
- `reviewer_batches.batch_count`
- `reviewer_assignments.assignment_group_code`

New subscription column:

- `subscriptions.coverage_package_id`

## Rollback

Stop ScoreMax and restore the timestamped `pre-v6_2_8` backup. Do not attempt to reverse individual DDL changes manually.
