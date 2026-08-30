# ScoreMax V6.2.7.2 Build Report

## Release

**ScoreMax V6.2.7.2 — Email or User ID Login**

## Purpose

Replace the email-only browser control with one safe login identity field supporting registered email and ScoreMax User ID, while retaining existing username compatibility and all established authentication protections.

## Delivered

- one `Email or User ID` text input;
- email, formal system User ID and assigned username lookup;
- case-insensitive matching;
- cross-field ambiguity rejection;
- neutral login-failure wording;
- backward compatibility with the legacy `email` POST key;
- case-insensitive unique-index protection where existing data permits;
- 13 dedicated V6.2.7.2 regression checks.

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
- V6.2.7.2: 13;
- **Total: 397 checks.**

## Database impact

No account rows, passwords or identifiers are rewritten. Startup adds case-insensitive identity indexes only when existing data is compatible. Ambiguous matches are rejected at login.

## Remaining acceptance boundary

A real-browser check remains required to confirm password-manager behaviour and visual/mobile presentation. All broader external-reviewer acceptance boundaries from V6.2.7.1 remain unchanged.

## Packaged-artifact verification

The clean release ZIP was extracted into a separate directory. Its internal SHA-256 manifest verified **257/257** entries in both directions with no missing, extra or mismatched files. The extracted package then passed:

- 31/31 Python-file compilation;
- 107/107 Jinja-template parsing;
- 214 discovered Flask route functions with zero broken template route references;
- zero POST forms missing CSRF protection;
- all **397/397** regression checks across V5.5 through V6.2.7.2.

The release package contains no generated SQLite database, private upload, content-intake upload, pilot backup or Python bytecode artifact.
