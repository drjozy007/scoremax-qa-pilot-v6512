# ScoreMax V6.2.7 → V6.2.7.1 Migration Guide

## Safety rule

Do not migrate the only valuable database directly.

1. Keep the V6.2.7 installation and database unchanged.
2. Install V6.2.7.1 in a separate folder.
3. Copy the V6.2.7 database.
4. Run the dry run against the copy.
5. Review integrity, counts, indexes and invitation reissue results.

## Dry run

```bash
python migrate_v6_2_7_to_v6_2_7_1.py path/to/copied-scoremax.db --dry-run
```

The script creates a timestamped backup before working. A successful report must show:

- SQLite integrity `ok`;
- no reduced live/core table counts;
- no changed reviewer batch/question/assignment/item/outcome/time-event counts;
- all three hardening indexes present;
- all verification and round columns present;
- no legacy token retained on an invitation requiring reissue.

## Unused invitation handling

Unused V6.2.7 invitations are moved to:

```text
INVITATION_REISSUE_REQUIRED
```

The old token is cleared. Open Admin → Reviewer Workspace and choose **Reissue**. Send the new link and verification code through separate channels.

## Live migration

Only after a successful copied-database dry run:

```bash
python migrate_v6_2_7_to_v6_2_7_1.py path/to/working-copy.db
```

Retain the generated pre-migration backup until controlled acceptance is complete.
