# ScoreMax UK 11+ — Guardian-Linked Onboarding Native Replay
Date: 25 November 2026
Status: **NATIVE DISPOSABLE TEST PASSED**. Not publicly deployed, not legal guardian verification, no UK learning release.

## Decision
Extend existing `users`, `parent_student_links`, native CSRF, roles, student-controlled link revocation and email-verified login. Store a distinct scoped and versioned `UK11_ONBOARDING` acknowledgement. Existing guardian messaging consent remains independent.

## Exact evidence
- Passing native run: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45587318388
- Passing source revision: `5c5700ba129fd63071fd94275e40dcc974e9b65e`
- Pinned exact accepted engine source revision: `5749e8370d577044c398cdf0c3bd78344ef6a26a`
- Exact assembled base SHA256: `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`
- Isolated UK adapter: `uk11_integration/uk11_guardian_onboarding.py`
- Explicit disposable-only migration: `uk11_integration/uk11_preferences_migration.py` (`GUARDIAN_DDL`)
- No production database, Pakistan registration, academic content, paid API, email delivery or live deployment modified.

## Passed native scenarios
1. Newly registered/UK-bound student sees guardian status `PENDING_GUARDIAN` and a pending notice on existing UK student home.
2. Unauthenticated and wrong-role API boundaries enforce existing native session/CSRF controls.
3. A parent with **no active link** cannot approve a synthetic UK child (403).
4. Parent uses existing ScoreMax `POST /parent/link-student` with child email and parent access code; linked child becomes visible to that parent only.
5. Invalid acknowledgement version is rejected (400), valid current version is accepted.
6. Acknowledgement changes status to `ACKNOWLEDGED`, **without** legal guardianship verification, academic/messaging consent, learning unlock or mastery credit.
7. Parent explicit `REVOKED` returns the student to pending, and a subsequent new acknowledgement works.
8. Second unrelated parent sees no linked children and cannot approve first parent's student (403).
9. Existing student-controlled `POST /student/parent-link/<link_id>/revoke` invalidates effective onboarding acknowledgement, returns UK student dashboard to pending and removes parent access.
10. Native UK student home correctly updates pending → acknowledged → pending.
11. Previously verified native registration, email verification, school selection, multi-school subject filtering, market isolation, logout/login and Pakistan regression checks remained green in the same replay.

## Important boundaries
- **No verified parental responsibility**: a parent who possesses a child-provided link code is a linked account, not independently verified legal guardian.
- **No UK GDPR or Children's Code clearance**. Required privacy notices, child-appropriate legal basis, verified guardian workflow if necessary, DPIA and parental controls remain pending.
- **Not an approved launch consent**: text version `UK11-ONBOARDING-CANDIDATE-20261125` is intentionally candidacy-only.
- UK parent dashboard still needs market-scoped integration to avoid running unrelated Pakistan learner analytics for UK children.
- UK learner-facing distribution of the existing parent access code and a visible parent decision screen are still pending. APIs are native-tested, not complete user journeys.
- No release of school-specific questions, practice, mocks, marking, study plans or mastery; these require separate Power House academic authority and native end-to-end qualification.
- Password verification, guardian identity assurance, email-provider delivery and mobile/browser accessibility need independent runtime staging checks.

## Next technical gate
Safely extend the existing parent navigation and student profile with UK-only access-code sharing, parent linking and explicit acknowledgement/revocation, while preventing market-irrelevant parent analytics from executing. Run visual accessibility and adversarial account-ownership tests on disposable UK runtime. Do not override identity, privacy or academic release gates to satisfy the launch schedule.
