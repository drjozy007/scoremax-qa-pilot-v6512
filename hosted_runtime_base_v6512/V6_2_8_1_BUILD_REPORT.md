# ScoreMax V6.2.8.1 Build Report

## Release

**ScoreMax V6.2.8.1 — Power House V3 Reviewer Import Compatibility**

## Defect corrected

V6.2.8 opened only the active Excel worksheet. The Power House V3 workbook's active sheet is instructional, so the importer could not find `Question / Task` and `Key Answer` and returned a misleading no-valid-question error.

## Implemented correction

- workbook-wide question-sheet detection;
- automatic exclusion of non-question tabs;
- exact Power House V3 aliases;
- combined statements/options parsing;
- rubric fallback for constructed-response keys;
- source worksheet/row lineage;
- source-sheet-contained 100-question batching;
- import preview sheet summaries;
- governed dual-review routing from imported metadata.

## Governed full-scale fixture

The V6.2.8.1 suite generates the exact structural pattern of the user-supplied V3 workbook:

- Batch 1 Review: 1,199;
- Batch 2 Review: 1,168;
- Batch 3 Review: 1,199;
- total: 3,566;
- ScoreMax batches: 36;
- cross-sheet batches: 0.

The fixture includes Standard MCQ, matching-set and rubric-only constructed-response records, plus pre-governed dual-review instructions.

## Verification summary

- all inherited V5.5–V6.2.8 suites passed;
- V6.2.8.1 dedicated checks: 19;
- total regression checks: 441;
- migration dry run from an untouched V6.2.8 database: SQLite integrity `ok`, no reduced core counts, no changed reviewer row counts.

- final extracted package: 37 Python files compile, 107 templates parse, 217 routes resolve, zero broken literal template route references and zero explicit POST forms missing CSRF protection.
- final internal SHA-256 manifest: 282 release files, excluding the manifest itself.
