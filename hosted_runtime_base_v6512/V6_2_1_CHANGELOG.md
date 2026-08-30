# ScoreMax V6.2.1 Changelog

## Fixed

- Corrected `_v54_security_gate()` so valid `session_version = 0` is not converted to `-1`.
- Added explicit `_session_version()` parsing that preserves numeric zero and safely rejects missing or malformed values.
- Added a dedicated sign-in-to-next-private-request regression sequence.
- Added regression checks for non-zero session versions, password-reset invalidation, missing/malformed versions and disabled accounts.

## Unchanged

- No database schema changes.
- No changes to Power House content authority or import governance.
- No changes to blueprint, mastery, written-response or teacher-messaging rules.
