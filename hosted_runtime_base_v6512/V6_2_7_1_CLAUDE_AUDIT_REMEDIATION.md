# ScoreMax V6.2.7.1 — Claude Audit Remediation Record

This document maps the independent V6.2.7 audit findings to the V6.2.7.1 changes and regression evidence.

## Medium 1 — Shared-engine reviewer independence

**Audit finding:** `create_assignment()` could create a round-two self-review when `parent_assignment_id` was omitted by a direct caller.

**V6.2.7.1 correction:**

- round two now requires a parent assignment;
- the parent must be round one for the same batch;
- the reviewer must differ from the first reviewer;
- the checks execute inside `BEGIN IMMEDIATE`;
- direct-call regression tests cover missing parent and same reviewer.

## Medium 2 — Active-time request flooding

**Audit finding:** rapid timer requests could credit 600 seconds in under one second.

**V6.2.7.1 correction:**

- server elapsed time is authoritative;
- each request can receive no more than actual elapsed time;
- rapid/replayed ticks receive zero credit;
- the shared database timestamp prevents multiple tabs from multiplying time;
- only the current, incomplete item in an `IN_PROGRESS` assignment receives credit;
- a secondary route-level request ceiling is applied;
- regression tests reproduce the original 20-request flood and confirm zero added time.

## Medium 3 — Invitation link possession

**Audit finding:** the first holder of a valid link could set the reviewer password and claim the identity.

**V6.2.7.1 correction:**

- activation now requires a separate eight-character verification code;
- the link and code are stored only as hashes;
- Admin is instructed to deliver them through separate channels;
- eight failed attempts lock the invitation;
- reissue invalidates all previous credentials;
- another currently logged-in ScoreMax identity cannot accept the named invitation;
- unused V6.2.7 one-part invitations are invalidated during migration.

## Medium 4 — Check-then-act concurrency races

**Audit finding:** duplicate checksum and assignment checks occurred before acquiring the write lock.

**V6.2.7.1 correction:**

- all affected checks now execute after `BEGIN IMMEDIATE`;
- unique index on batch checksum;
- partial unique index for one first-review assignment per batch;
- `round_no` persisted on assignment items;
- partial unique index for one round-two claim per question;
- genuine threaded tests confirm exactly one commit for concurrent batch imports, first-review assignments and second-review claims.

## Low — Packaged test artifacts

**Audit finding:** synthetic uploads, intake CSVs and backup folders were included in V6.2.7.

**V6.2.7.1 correction:**

- `private_uploads/`, `content_intake_uploads/` and `pilot_backups/` are excluded;
- the clean extracted package is explicitly checked for their absence.

## Informational — Comment padding

**Audit observation:** repeated punctuation could satisfy the eight-character comment check.

**V6.2.7.1 correction:**

- non-acceptance comments require at least 12 characters, two alphanumeric words, six letters and meaningful character variation;
- punctuation-only regression case is rejected.

## Deferred maintainability observation

The large `app.py` remains a future modularisation task. It was not changed in this narrow assurance patch because the audit did not identify it as a functional or controlled-pilot blocker.
