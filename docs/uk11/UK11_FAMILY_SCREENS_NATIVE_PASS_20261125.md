# ScoreMax UK 11+ — Family Onboarding Screens: Native Qualification
Date: 25 November 2026
Result: PASSED — exact assembled native ScoreMax, disposable SQLite with synthetic UK learners, CI run 45589941131.
Release: HOLD. No production or UK public deployment changed.

## Evidence
- Workflow: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45589941131
- Source branch commit tested: 0bb622dcca9d0ab36b0f29c03af1ac7f70fe259e
- Native source pinned: 5749e8370d577044c398cdf0c3bd78344ef6a26a
- Existing assembled base checksum: 7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9
- All earlier native login, token verification, school context, role isolation, Pakistan regression and linked-guardian tests passed in the same replay.
- End marker: `UK11_NATIVE_LOGIN_PREFERENCES_REPLAY_PASSED`
- New browser journey end marker: `UK11_NATIVE_GUARDIAN_BROWSER_VIEWS_PASSED`

## Newly executed native HTTP checks
1. Existing signed-in UK student opens private `/uk11/api/me/guardian-onboarding` (200) showing family access controls; response has no-store, no FSc/MDCAT content.
2. Parent opens `/uk11/api/guardian/home` (200) with no linked children; then uses existing native parent link-code endpoint to link synthetic UK learner.
3. The native `/parent` route redirects a UK-linked parent to UK-specific family home, bypassing Pakistan analytics rendering.
4. Parent home exposes only their linked UK child and the native CSRF-protected acknowledgement and withdrawal forms. The HTML contains no FSc/MDCAT/Biology/Chemistry labels.
5. Missing CSRF token is rejected (400); stale agreement version is rejected (400).
6. Parent records an acknowledgement and withdraws it using real form submissions (303); the shared guardian decision service enforces linkage and scope.
7. Another parent cannot submit a decision for that child (403), even using the exact form route.
8. Earlier synthetic suites continue to confirm child-initiated revocation, token validation, UK/Pakistan market isolation, and that guardian acknowledgement never unlocks academic pathways or claims legal guardianship.

## Implemented changes
- `uk11_integration/uk11_guardian_onboarding.py`: student access-code page, linked-parent list, dedicated parent onboarding page, scoped HTML forms, shared decision authorisation.
- `uk11_integration/uk11_native_market_boundary.py`: market-guarded route to UK parent page and late HTML response isolation while retaining existing native headers and security gates.
- `uk11_integration/native_guardian_ui_probe.py`: extra native browser form replay after account and email verification.
- `.github/workflows/uk11-native-login-replay.yml`: executes both synthetic journeys in one isolated container.
- No mutable Pakistan production files, real child records, paid AI, external email or production deployment.

## Residual qualification
- This is an onboarding acknowledgement, not independently proven legal parental responsibility or child-data legal basis.
- Full guardian identity verification, privacy notice, age-appropriate design, safeguarding, accessibility audit and parental authorisation policies are pending.
- An unlinked UK parent still uses the native general parent home before linking; full market-specific guardian onboarding and role provisioning are a separate UX gate.
- UK-school admissions authority and native question assignment, exam centre, marking, mastery and study-plan integration remain blocked until qualified.
- Desktop/mobile, assistive-technology and independent external penetration tests are pending.
- None of the above tests constitutes live Render deployment verification or release approval.

Next: extend UK parent onboarding discovery for unlinked parents using an explicit UK account market, not an inference from school or child, while preserving existing Pakistan parent access. Then qualify UK school-scoped learning content routes and privacy review before launch.
