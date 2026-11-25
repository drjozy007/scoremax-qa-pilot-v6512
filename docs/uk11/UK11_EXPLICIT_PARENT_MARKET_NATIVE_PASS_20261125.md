# UK11 — Explicit UK Parent Market and Unlinked Onboarding Qualification
Date: 25 November 2026
Status: PASSED in synthetic disposable native ScoreMax runtime only. NO deployment or live release.

## Decision
Reuse ScoreMax native parent registration, login, session, CSRF, password checks, parent-child link and guardian acknowledgement. Persist a separate explicit UK11 parent identity rather than infer the market from the presence of a linked student. Keep Pakistan data, login and dashboards unchanged.

## Changes
- `uk11_integration/uk11_preferences_migration.py`: new, UK-only `uk11_parent_markets` table, keyed to existing `users` with `parent_user_id`, `market_id=UK`, `programme_id=UK11`. Applied only in disposable UK DB.
- `uk11_integration/apply_registration_overlay.py`: UK parent signup GET template and UK market record inserted in the **existing native registration transaction**; neither new authentication nor self-asserted assignment by school selection.
- `uk11_integration/uk11_native_market_boundary.py`: UK parent's native `/dashboard` and `/parent` routes redirect to UK family onboarding **with or without a linked child**. Original native parent linking remains available. Pakistan/legacy parents remain on their native homepage, denied UK guardian routes.
- `uk11_integration/native_login_replay.py`: explicit parent market fixture, UK unlinked first-home, legacy parent regression and UK API denial.
- `uk11_integration/native_guardian_ui_probe.py`: native parent signup, database market mapping, authentication, first UK parent homepage and empty family page; plus previously proven guardian linking, forms, access isolation and CSRF tests.

## Evidence
- Final successful native run: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45591031164
- Run commit: `b8e665e0f9e6517e20566d12032543bc8c33c765`
- Pinned accepted native source snapshot: `5749e8370d577044c398cdf0c3bd78344ef6a26a`
- Existing assembled base checksum: `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`
- Logs: `unlinked_uk_parent_home` 302; `pakistan_parent_home_untouched` 200; `new_unlinked_uk_parent_first_login` 200; and passing markers `UK11_NATIVE_LOGIN_PREFERENCES_REPLAY_PASSED`, `UK11_NATIVE_GUARDIAN_BROWSER_VIEWS_PASSED`, `UK11_NATIVE_PARENT_MARKET_REGISTRATION_PASSED`.
- In-memory SQLite/temporary container with synthetic accounts only, network disabled, no paid API or production data.

## Boundary and outstanding gates
1. Native ScoreMax parent registration is reused; independent parent email-address verification, parental responsibility identity assurance, UK GDPR legal basis, Children's Code and safeguarding assessment are **not** qualified here.
2. `uk11_guardian_onboarding` remains a versioned, scoped acknowledgement only; the tests do not establish legal guardianship or authorise all child-data processing.
3. Parent and student interfaces remain candidacy-only. The public UK preview and Render deployment were not modified by this qualification.
4. Existing authenticated UK parent endpoints remain narrowly allowlisted; school-specific question access, mocks, marking, study plans and mastery are still not released. All six mastery levels remain displayed without fabricated awards.
5. External desktop/mobile accessibility, synthetic concurrent families, verification-provider delivery, account-recovery paths, official exam-route memberships, academic QA and rollback remain PENDING.

## Next action
Qualify parent contact verification and child-privacy/legal assurance separately, then route Power House-approved UK school memberships into the existing ScoreMax learning services server-side before widening parental reports or academic functionality. Do not change Pakistan production or claim deployment success without exact version/rollback and live verification.
