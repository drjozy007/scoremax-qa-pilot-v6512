# UK11 Authenticated School Preferences — Engineering Decision & Mount Gate
Date: 24 November 2026
State: BUILT AS ISOLATED CODE CANDIDATE / NOT MOUNTED / NOT NATIVE TESTED / NOT DEPLOYED

## Decision
Extend the native ScoreMax Flask login session and SQLite-backed user profile, **not** create UK login, auth tokens or a second student database.

## Evidence inspected
- Engineering branch `fix/scoremax-streamed-backup-20261022`:
  - `hosted_runtime_base_v6512/app.py`: `/login`, session `user_id`, `role`, `session_version`, CSRF and session invalidation;
  - `/student` and native user-profile workflow;
  - SQLite `users` and role-bearing parent/student accounts.
- UX preview branch: static school selector and combined routed subjects, no authenticated backend.

## Delivered — UK-only source
- `uk11_integration/uk11_account_preferences.py`: GET/POST `/uk11/api/me/schools`, student session scope, school-key allowlist, cycle/year bounds, optimistic revision conflicts, authoritative injected route resolver; rejects unknown school keys. No mastery modifications.
- `uk11_integration/uk11_preferences_migration.py`: explicit isolated database migration; no automatic schema writes in request flow.
- `uk11_integration/test_uk11_account_preferences.py`: synthetic tests for auth/roles, cross-account isolation, duplicate/unknown keys, entry years, concurrency revision, data round trip.
- Code lives **only** in the UK preview branch. It has not been imported into the engineering runtime, invoked, or run against a database.

## Required safe native mount
1. Take a verified, nonproduction working tree from accepted engineering ScoreMax baseline. Verify full SHA and deployment version. Re-run relevant native regression suite.
2. Create a UK-only disposable DB clone containing only synthetic learners. Explicitly run migration against that DB; do not touch Pakistan DB.
3. Inject native `db()`, a reconciled, country-appropriate official-identity school catalogue and Power-House-approved admission route resolver. Do not copy arbitrary static candidate IDs into the canonical contract.
4. Register blueprint on native Flask `app` only for the isolated UK runtime. Keep the existing `before_request` session validation and CSRF gate. Apply the existing synthetic learner fence.
5. Add UK dashboard binding: after authenticated login, fetch `GET /uk11/api/me/schools`, render selected-school names, unique evidenced routes, approved subject union and pending notices. On school change, POST with current revision plus native CSRF; on 409 refetch/reconcile.
6. Verify parent visibility separately via the existing parental-link authorisation; **do not** permit a parent to impersonate a student or write preferences by changing a browser-supplied ID.
7. Run native functional, adversarial, mobile/accessibility and production-like scale tests; verify unauthenticated, disabled, stale session, role-crossing, CSRF, retries, concurrent writes and entry-year changes.
8. Only after independent qualification promote approved UK scope with exact checksum and rollback. Pakistan stays frozen.

## Unverified dependency / blockers
- Exact current accepted runtime SHA and frozen authentication/migration baseline (engineering branch inspected, not accepted).
- UK official school identity coverage and school-to-route current-cycle approvals incomplete.
- The preview static site cannot authenticate real users.
- Tests are committed but **not executed**; no PASS claim.
- Real deployment cannot be treated as live until runtime and HTTP checks confirm matching SHA.

## Potential improvements after gate
Keep a revision history/audit trail of changed school selections in authenticated storage. Cache bounded evidence-qualified school/route responses; invalidate on authority revision or school-policy withdrawal. Enforce routing authorisation server-side for all question allocation, marking and mastery, not only front-end display.
