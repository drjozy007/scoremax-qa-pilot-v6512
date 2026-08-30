# ScoreMax V6.2.7.1 Build Report

## Release

**ScoreMax V6.2.7.1 — Reviewer Assurance Hardening**

## Purpose

Narrowly close the four Medium findings and packaging-hygiene observation from the independent V6.2.7 Claude audit, while preserving all previously verified ScoreMax behaviour.

## Delivered

- shared-engine enforcement of second-review parent and reviewer independence;
- transaction-scoped duplicate and overlap checks;
- three database uniqueness backstops;
- server-authoritative active-time reconciliation;
- current-item, incomplete-item and active-assignment timing restrictions;
- route-level timer flood ceiling;
- two-part reviewer invitations with separately delivered verification code;
- hashed verification storage, attempt counting, lock and reissue;
- safe migration of legacy unused invitations to reissue-required;
- stronger meaningful-comment validation;
- clean packaging without generated upload/test artifacts;
- 18 new hardening checks with genuine threaded concurrency tests.

## Automated verification

- V5.5: 52;
- V6.0: 34;
- V6.1: 41;
- V6.2: 30;
- V6.2.1: 10;
- V6.2.2: 19;
- V6.2.3: 33;
- V6.2.4: 14;
- V6.2.5: 34;
- V6.2.6: 66;
- V6.2.7: 33;
- V6.2.7.1: 18;
- **Total: 384 checks.**

## Migration rehearsal

A database created by the untouched V6.2.7 package was seeded with 95 live questions, two users, one reviewer batch, one reviewer question, one unused legacy reviewer assignment and one assignment item. The V6.2.7→V6.2.7.1 dry run returned SQLite integrity `ok`, preserved every tested live and reviewer row count, installed all required columns/indexes, cleared the legacy token and moved the unused invitation to `INVITATION_REISSUE_REQUIRED`.

## Remaining acceptance boundary

Real browser/mobile/assistive-technology testing, actual separate-channel invitation delivery, legal/confidentiality wording review and an external academic-review usability session remain required before wider external rollout.

## Packaged-artifact verification

The clean release ZIP was extracted into a separate folder. Its internal SHA-256 manifest was verified in both directions with no missing, extra or mismatched files. The extracted package then passed all 384 regression checks and the genuine V6.2.7→V6.2.7.1 migration dry run. The package contains no generated `private_uploads`, `content_intake_uploads`, `pilot_backups`, SQLite databases or Python bytecode.
