# UK11 School-Aware Dashboard — Native Replay Evidence
Date: 24 November 2026
STATUS: NATIVE HTTP TEST PASS (DISPOSABLE SYNTHETIC ROUTES). NOT DEPLOYED / NOT ACADEMICALLY QUALIFIED.

## Exact evidence
- GitHub Actions: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45376693096
- Verified assembled base SHA-256: `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`
- Existing ScoreMax native authentication and CSRF gate remained in place; UK blueprint explicitly mounted on disposable image.
- Observed 315 runtime Flask rules after mount, including `GET /uk11/my-learning`.
- Existing student login succeeded with native credentials; unauthenticated request redirected; native logout cleared access; re-login recovered the saved schools.
- Saved synthetic schools Alpha and Beta; route aggregation returned exactly one shared Maths test.
- `GET /uk11/my-learning` returned HTTP 200, contained Alpha, Beta, Maths; did not contain English subject/test; shared Maths route rendered exactly once.
- After logout/login, dashboard still displayed saved schools.
- Changed selection to synthetic Gamma (English) and Unmapped (pending): returned HTTP 200; English subject/test visible, Maths subject/test absent, pending admissions warning visible; six mastery levels and Not Yet Established displayed.
- Other student had no inherited school selection; parent role refused with HTTP 403.
- Separate original and expanded isolated school-preference tests passed in GitHub Actions.
- No Power House content, actual school eligibility, marks, mastery, or paid AI were used.

## Accurate scope
The learner-specific route is currently a **read-only UK view** mounted on a disposable runtime. It is not a fully branded production student home, and the actual existing native `/student` homepage has not yet been switched to this context. Native practice, mocks, search, study plans, question allocation, marking and mastery have **not** been proven school-scoped.
The route fixture is synthetic only, not the 2028 approved UK admissions crosswalk. Neither the public UK preview nor any production service was deployed or modified.

## Remaining decisions / next gates
1. Safely integrate UK-specific context into the existing ScoreMax student navigation without losing full features, introducing a second UX, or changing Pakistan.
2. Replace synthetic route resolver with approved Power House-owned school/provider/test/cycle membership and official identity reconciliation; fail closed on uncertain routes.
3. Verify server-side route gating throughout practice/mocks/allocation; a presentation filter cannot enforce actual school entitlement.
4. Test 300/1500 mixed school/subject rows, concurrency, availability, accessibility, mobile and logout/session invalidation.
5. Only after product, academic, security and runtime qualification should UK staging be deployed, followed by verified live URL and rollback.

GO for next isolated engineering changes. NO-GO for UK student release.
