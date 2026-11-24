# ScoreMax UK 11+ — Native Student Registration Gate
Date: 24 November 2026
Decision: Reuse native ScoreMax student account registration; add UK11 market and programme atomically inside disposable UK runtime.
Status: NATIVE DISPOSABLE LOGIN/REGISTRATION/PREFERENCE REPLAY PASSED. NOT DEPLOYED. NOT LIVE VERIFIED.

## Verified evidence
- GitHub Actions: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45503165485
- Baseline exact assembled tree SHA256: `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`
- Native checkout pinned to immutable `5749e8370d577044c398cdf0c3bd78344ef6a26a`
- UK registration overlay applied AFTER exact source-tree verification and BEFORE container build, only with disposable runtime marker.
- Existing ScoreMax `/register/student` handler reused. No separate UK auth, passwords, session or registration database.
- UK-only registration page displayed; inherited Pakistan subject navigation removed from that page's final HTML through late response isolation, retaining native CSRF/session response security.
- Existing registration programme allowlist extended with `UK11` only in the disposable UK runtime source copy; Pakistan source/production unchanged.
- New synthetic student account created through native POST registration; stored `active_programme=UK11` and `academic_level=UK11`; `uk11_learner_markets` identity recorded `market_id=UK,programme_id=UK11` inside native transaction.
- Native email verification remained required: new account started `pending_email_verification` and `email_verified=0`; redirected to `/verify-email` with synthetic delivery not configured.
- **Only in the disposable synthetic test fixture**, verification state was marked active to exercise existing native sign-in; the resulting first UK `/student` GET returned 200 with no selected schools and `Not Yet Established`.
- Existing school preferences, two-school route deduplication, changed school/subject filtering, logout/login continuity, UK learning-route fail-closed checks, parent role 403 and original Pakistan homepage 200 all passed in same native replay.
- Synthetic no-network container, temporary SQLite DB, no real student data, paid AI disabled, no deployment or database mutation outside runner.

## Out-of-scope / release blockers
- Email verification **delivery** and actual token redemption **not tested**; synthetic test explicitly bypassed token processing only to exercise post-verification login. Public registration requires this gate.
- Child / parent or guardian onboarding, age-appropriate consent or parental responsibility workflow, Children's Code and UK GDPR DPIA remain pending.
- Real 2028 admissions route and school identity memberships remain pending external academic approval and Power House mapping.
- Practice, marking, exam centre, native study plans, school-scoped allocation and independent mastery qualification remain fail-closed.
- Native UK presentation is a narrowly qualified read-only candidate; full original ScoreMax learner experience must be adapted and verified, not removed.
- Scale, browser/device accessibility, security adversarial tests, rollback, live deployment and acceptance remain pending.

## Current next gate
Use the existing native verification mechanism with a mocked SMTP inbox to test genuine token issuance/expiry/redemption and prevention of unverified login; then verify guarded UK onboarding and parent/child access. Never weaken email verification or change Pakistan production to make tests pass.
