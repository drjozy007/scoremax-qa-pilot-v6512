# V6.2 Changelog

## Added

- Pilot Readiness Control Centre.
- Persistent governed import batches and row-level validation records.
- Original import-file preservation with SHA-256 verification.
- Whole-batch atomic import; no valid-row-only partial import.
- Automatic integrity-checked backup before import and rollback.
- Whole-batch rollback while content remains unused, inactive and unreviewed.
- Import lineage on questions and newly created question families.
- Candidate inventory and active-blueprint compatibility snapshots.
- Power House provider-neutral prompt-pack import and copy workflow.
- Manual ChatGPT/Claude/other-provider output return and Power House export wrapper.
- Pilot issue reporting with academic/technical authority routing.
- Basic pilot operational analytics.
- Failed written-processing job re-queue.
- Demo-data quarantine with automatic backup.
- Knowledge Hub CMS foundation, manual entries, source governance and Growth Engine draft intake.
- V6.1 → V6.2 migration utility and dry-run mode.

## Changed

- Question imports are no longer stored in browser sessions.
- Imported questions receive scoped answer/marking configuration without a full migration pass.
- Imported questions remain `Draft`, inactive and `CANDIDATE` regardless of spreadsheet approval fields.
- Existing demo questions are explicitly labelled `DEMO`.
- Production screenshot/content storage now requires configured protected directories.

## Deferred

- Real Power House API synchronisation.
- Full Social Hub and student-to-student messaging.
- Production OCR and external written-answer graders.
- PostgreSQL conversion and hosted deployment.
- External examination-outcome calibration.
- Automated social-media publishing.
