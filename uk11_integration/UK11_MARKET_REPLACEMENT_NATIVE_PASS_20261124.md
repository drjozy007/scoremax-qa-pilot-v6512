# UK 11+ market replacement and Pakistan isolation — native test evidence
Date: 24 November 2026
Decision: UK-only account context and school-specific interface. Do not delete FSc/MDCAT from Pakistan production.
Outcome: PASSED in disposable native ScoreMax runtime; NOT deployed or accepted for UK public release.

## What was checked
- UK static preview `uk11_preview_site/index.html`, `uk11_context_dashboard.js` and `uk11_school_catalogue.js`: no literal FSc, MDCAT or Pakistan labels found in those files.
- Native ScoreMax assembled baseline: SHA-256 `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`, pinned Git revision `5749e8370d577044c398cdf0c3bd78344ef6a26a`.
- UK account identity is stored separately from school selections in `uk11_learner_markets`, `market_id=UK`, `programme_id=UK11`, created by explicit **disposable-only** migration.
- UK account without any schools renders UK 11+ onboarding rather than falling into Pakistan.
- Native security gates remain active. UK account requires explicit market record, with no implicit upgrade from school selection.
- Exact UK homepage HTML yielded none of the forbidden literal terms `FSc`, `MDCAT`, `Pakistan`, `Biology`, `Chemistry` after restoring its UK-only response after the existing native presentation injectors.
- Two synthetic schools sharing Maths => single deduplicated route.
- Changing to English-route + unmapped school => English-only learner context, pending verification visible, Maths removed.
- Saved schools survive logout/login. Separate student cannot access UK school API (403) without UK market identity.
- Native unqualified practice/subject/exam/study-plan request probes returned 403 for UK account instead of routing to Pakistan.
- Pakistan/legacy synthetic student still loads native homepage (200) with original Pakistan content; no UK panel.
- Parent-only user cannot access the student preferences API (403).
- No external paid service, real child data, production DB or deployment changed.

## Evidence and boundaries
- GitHub Actions native success: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45445211829
- Synthetic API suite success: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45445211664
- Test sources: `uk11_integration/native_login_replay.py`, `uk11_native_market_boundary.py`, `uk11_preferences_migration.py`.
- Only UK native view + access protection is qualified here; full existing ScoreMax practice/mocks/analytics, UK 11+ original academic content, provider/cycle routing, independent academic acceptance and UK onboarding provisioning are NOT qualified.
- This is not deletion of the inherited Pakistan backend, only UK-market separation on a synthetic runtime. Native production remains unchanged.
- The final UK child-facing experience should reuse ScoreMax's full product UX and six mastery stages, while UK academic admission/marking gates remain fail closed.

## Next
Replace manual synthetic UK market record with controlled account-registration/profile flow in an isolated UK instance. Integrate true Power House-approved school/provider/cycle mappings, native question allocation and examination functionality. Verify whole-platform UK navigation, accessibility, performance, independent academic tests, runtime marking and rollback before any UK release.
