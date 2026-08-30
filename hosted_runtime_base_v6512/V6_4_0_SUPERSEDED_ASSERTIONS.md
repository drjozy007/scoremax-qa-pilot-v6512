# ScoreMax V6.4.0 — Superseded Historical UX/Version Assertions

Historical test files are retained in `legacy_test_snapshots/V6_3_2/` before intentional assertion updates.
Only assertions made obsolete by an accepted descendant requirement were changed; unrelated regressions remain enforced.

Intentional supersessions include:
- login label accepts the clearer **Email or ScoreMax ID** wording;
- old public-preview labels replaced by the new landing experience;
- programme UI assertions reflect persistent FSc 1/FSc 2/MDCAT context;
- health descendant marker accepts `release_version=6.4.0` while retaining parent compatibility identity.

This file prevents a passing suite from silently rewriting history. The original V6.3.2 assertions remain available for audit.
