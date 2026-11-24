# UK11 — Native ScoreMax Student Homepage Integration Replay
Date: 24 November 2026
Verdict: PASSED — disposable synthetic HTTP rendering and native session qualification ONLY.
Release: HOLD — not deployed; official school memberships and server-scoped practice remain unqualified.

## Exact evidence
- GitHub Actions run: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45380660949
- Pinned engineering source: `5749e8370d577044c398cdf0c3bd78344ef6a26a` (immutable commit, not changing branch head).
- Verified assembled base tree SHA-256: `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`.
- UK-only source: `uk11_integration/uk11_native_student_home.py` and original authenticated preferences adapter.
- Tested native `/student` HTTP 200, existing login/logout session and CSRF unchanged.
- Synthetic Alpha + Beta schools (shared Maths route) resulted in one route and Maths-only homepage panel.
- After logout/login, saved selection persisted.
- Synthetic Gamma (English) and Unmapped (no approved route) resulted in English-only subject/test, visible pending message and no stale Maths route.
- All six levels visible: Foundation → Exam Ready → Advanced → Distinction → Expert → Elite; no unsupported mastery award.
- Native Pakistan student (without UK selection) rendered the existing home with MY SUBJECTS and COMING UP sections and **no** UK school panel.
- Cross-student preferences isolated; parent-only account denied preference access HTTP 403.
- Production rate limiter respected through pacing. Existing tests were re-run in isolated CI.
- Earlier reproducibility failures prompted immutable commit pinning and exact assembled template-structure inspection, rather than altering production policy.

## Architectural limits and remaining risk
- The new panel is implemented as a guarded Jinja extension of the **existing** native student homepage, only on disposable UK runtime. It is not mounted in production.
- Underlying `/student` view may still execute Pakistan-oriented analytics, personalization and Daily Spark data-access routines before template filtering; user-facing sections can be hidden in the UK candidate, but **this does not enforce market isolation** for server queries, allocation, tracking or billing. This is a P0/P1 integration risk depending on observed cross-market behavior.
- The test uses synthetic route resolver and school keys; neither 2028 membership nor exam rights/scoring are qualified.
- An initial UK learner with **no** saved selections cannot yet be distinguished from a Pakistan learner purely by this candidate panel; a proper authenticated UK market/profile attribute is required before production integration.
- Country-specific parent/student dashboards, mock/practice route entitlement, question allocation, marking, mastery, independent accessibility/mobile review and real admission cycle source qualification remain pending.
- No Power House/ScoreMax production changes, API calls to paid AI providers or new real child data.

## Next necessary gate
1. Extend existing authenticated learner profile with explicit **UK market/programme** identity (not inferred from presence of school keys).
2. Use that stable account identity and Power House-backed cycle/membership resolver to populate verified learner context **before** native student dashboard queries; never execute unrelated Pakistan learner analytics for UK.
3. Gate native subject browser, practice, exam centre, question allocation, study plans and mastery server-side, not only Jinja display.
4. Validate no Pakistan regression with both account markets and learner roles on disposable DB, then human/browser/mobile and scalability QA.
5. Keep independent academic mapping/audit and real-source transfer as separate release blockers.
