# ScoreMax V6.2.7.1 Changelog

## Reviewer governance hardening

- Moved duplicate and assignment checks inside write transactions.
- Added unique index on `reviewer_batches.source_checksum`.
- Added partial unique index allowing only one first-review assignment per batch.
- Added `round_no` to reviewer assignment items and a partial unique index allowing only one second-review assignment per question.
- Enforced a valid first-review parent and independent reviewer inside `create_assignment()` itself.

## Active-time integrity

- Server elapsed time is now authoritative for credited active seconds.
- Rapid/replayed requests are recorded as discarded ticks with zero credit.
- Multiple tabs share one server-side timing baseline.
- Only the current, incomplete item in an `IN_PROGRESS` assignment receives time.
- Added a route-level 20-per-minute timer request ceiling as secondary abuse protection.

## Invitation identity assurance

- Added separately delivered reviewer verification codes.
- Stored invitation links and verification codes only as SHA-256 hashes.
- Added eight-attempt verification lock.
- Prevented another logged-in ScoreMax identity from accepting a named reviewer invitation.
- Added `no-referrer` protection to the invitation page.
- Added Admin reissue for unused or locked invitations.
- Invalidated unused one-part V6.2.7 invitations during migration.

## Review evidence and packaging

- Strengthened meaningful-comment validation for non-acceptance decisions.
- Removed generated private-upload, content-intake and pilot-backup artifacts from the release package.
- Added 16 hardening regression checks, including genuine threaded concurrency tests.
