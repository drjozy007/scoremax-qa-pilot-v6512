# ScoreMax V6.5.1 Rollback Evidence

## Immutable parent
Retained Integration Control parent:
- ScoreMax V6.5.0 Three-System Integration Platform Candidate
- SHA-256: `8a32da65da5d389e69b5771f495b81047dee347cbc7705ee5951536aa111f0e2`

Earlier V6.4 rollback parent remains separately retained by project governance.

## Database strategy
V6.5.1 migrations are additive. Promotion must take a pre-upgrade database backup. Rollback procedure:
1. Stop V6.5.1 application/worker processes.
2. Back up the current V6.5.1 database for forensic/forward recovery; do not delete it.
3. Restore the retained pre-upgrade V6.5.0 database backup.
4. Launch the exact retained V6.5.0 package identified above.
5. Run `PRAGMA integrity_check` and the V6.5.0 health/acceptance smoke.

This avoids trying to destructively reverse child integration tables and guarantees learner evidence is not rewritten during rollback.

## Upgrade evidence
An exact V6.5.0 disposable DB was initialized using the exact parent bytes, then upgraded using V6.5.1. Final integrity was `ok`; corrected integration tables and release columns were present. See `V6_5_1_MIGRATION_EVIDENCE_2026_08_21.txt`.

## Backup/restore evidence
V6.5.1 local backup utility was run against a disposable child DB, then the DB was mutated, then restored from the backup. The probe returned to its pre-mutation value and `PRAGMA integrity_check` returned `ok`. See `V6_5_1_BACKUP_RESTORE_EVIDENCE_2026_08_21.txt`.
