# ScoreMax V6.2.1 — Session Integrity Hotfix

## Purpose

V6.2.1 is a narrowly scoped release-blocking hotfix built from the frozen V6.2 Pilot Readiness & Content Intake package.

It corrects the authenticated-session comparison that converted a valid numeric zero into the missing-version sentinel. A user whose database and signed browser session both contained `session_version = 0` was therefore logged out on the next protected request.

## Correct behaviour

- `0` and `"0"` are valid session versions.
- A missing or malformed session version is rejected.
- Matching non-zero versions remain authenticated.
- Password reset or security-version increments invalidate old sessions.
- Disabled or archived accounts cannot retain access even with a matching version.

## Schema and migration

No schema migration is required from V6.2. Replace the application package while retaining a verified copy of the database and uploads.

## Scope

All V6.2 content-intake, prompt-bridge, pilot-control, Knowledge Hub foundation, V6.1 messaging, V6.0 written response, and V5.5 blueprint capabilities are preserved.
