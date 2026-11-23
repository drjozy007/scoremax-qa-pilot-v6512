# Current Work B SQLite navigation candidate — 23 November 2026 UTC

This is the continuation of existing PR #56, composed after current ScoreMax PR #59
`bcd9834c4e956f70561b41f786e0c3a2e568aacf`, not the historical18c8c runtime.
Accepted live baseline is `8d5c0fd44ede20c56d62a42f0515207bb4b94bda`.
The current exact generated source tree is
`d02a710a307788e68ee5b7be19f01b39e6be7ec4c8e7bc84d09e352e327810f2`.
The existing materializer now composes the accepted+scored+pending receiver and
an exact12-file code delta. Build opens no DB and creates no index. Preserve the
existing API-OFF, original-source-marks/positive-weight pending-answer contract.

The selected code batches native programme/chapter display reads, uses bounded
commit/restore-invalidated display aggregates, pure immutable context/normalizer
transforms and clean connection leases within one GET only. Every formal PH
answer read still checks current exact authority; assessment admission, marking,
withdrawal and mastery awards remain native. No PostgreSQL or shadow is enabled.

Local100800-question/1001-learner/102300-FINAL-answer HTTP evidence,200 scheduled
requests per route with50 distinct learners, one CPU/one worker/ONE thread:
Learn p951004.826ms, Subject1217.720ms, Chapter1396.234ms, Catalogue1084.975ms.
All800 requests succeeded, no timeout censoring;16 protected tables unchanged.
These are local derived-fixture results, not Render or mixed-writer acceptance.
Four-thread trials still FAILED (Subject1542.612ms,Chapter1598.731ms). ONE thread
is a tested candidate configuration, NOT a production configuration change.
All1/10/50 hosted gates, repeat trials, actual mixed writer load, resource limits,
real bank and low-bandwidth/mobile checks remain independently required.

Self-audit:30 exact-build, drift, pure-context, commit/fork/restore/concurrency,
lease-lifecycle and writer-reservation controls PASS. Native signed parity across
28 programme/subject pairs,42 opaque/Unicode/whitespace chapter inputs, five
version/revocation/family/withdrawal states PASS, including native presentation
fallbacks. Current pending, scored and signed-recovery regression results are
recorded separately; no real academic approval is conferred by software fixtures.

The failed per-label global-cache experiment is rejected. It displaced aggregate
entries under the existing64-query bound. Its replacement reads chapter catalogue
labels in bounded page-local SQL batches and adds zero global label entries.
Do not increase cache bounds or treat a failed trial as passed evidence.

Seven additive optional expression indexes are still a SEPARATE explicit guarded
migration with verified backup, write fence, disk budget, plan/write/rollback
qualification. The synthetic load fixture explicitly applies them; default build
and startup do not. Production rollout requires coordinated code, build command,
index migration and any worker-setting decision with pre/post checks and rollback.
No merge, deployment, secret rotation, public activation or production DDL occurred.
The current real source/DB fixture is unavailable through the existing secure
transfer route; this is independent of future AI API activation.

Existing PR #55 remains the programme handoff and contains the optional PostgreSQL
prototype. Preserve its intentionally failing full-schema cutover veto. PostgreSQL
cutover is not part of this SQLite candidate; no migration completeness is claimed.

Historical evidence below retains its original versions and limits.

---

# ScoreMax SQLite-only speed release — acceptance and rollback

**Status:** Draft, production deployment **NOT authorised or performed**  
**Scope:** Existing Render service `srv-daj5fbm7bikc73aq2gdg`, production ref `18c8c70640362aebb531651422c606bb7cf0dfaa`, independent draft PR #56.  
**Excluded:** PostgreSQL, shadow/epoch projections, SQLite index creation, schema/data migration, Power House production changes.

## Change inventory

The candidate uses the **accepted hash-verified Biology runtime materialiser** and an eleven-step source-locked SQLite-only navigation overlay. It may change only `app.py`, `ux_student_batch.py`, `ux_catalogue_browser.py`; build CI fails if any other runtime file changes.

Improvements are same-request grouping of frozen validated evidence, grouped/fused programme subject discovery, bounded source-subject pushdown, slimmer display-only mastery-card rows, reusable request-local active blueprint/policy/access, and skipping work for widgets already hidden by native flags. Native grading, mastery award, source admission, PH ACK/withdrawal, student entitlement and persistent data are unchanged. No live SQLite migration or index DDL.

## Academic and security hazards to preflight

| Risk | Required acceptance |
| --- | --- |
| False formal mastery from practice-only or dependent PH items | Native formal mastery unit and programme/regression suites PASS; unchanged marking/credit functions |
| Wrong programme/chapter/question availability, withdrawn question leakage | Governed PH/FSc/MDCAT and withdrawal tests PASS, including 29 current native PH compatibility cases |
| Historical evidence or changed field projection silently disappearing | Frozen answer context/response parity and immutable source evidence; no new student history writes |
| One learner's cache visible to another | Confirm Flask `g` request-scoped only, keys include student/programme, no Redis/global/persistent cache |
| Stale same-request authorization during active PH release | Use native admission at question START and SUBMIT; no cached decision grants release authority |
| HTML/access/UX drift | Same status, HTML SHA-256 and bytes for four student routes; check hidden routes, all supported formats and mobile |
| Slower 100k-question loads despite small-fixture gain | Paired identical native vs candidate 100,800-question, 1,000-student 1/10/50 distinct-user HTTP; no >10% p95 regression on any tested route |
| Startup/Render configuration regressions | Keep one Gunicorn worker/four threads, persistent secret, /data mount, existing PH dispatcher and health path |
| Rollback causes data loss | No schema migration; preserve existing DB and WAL, rotate no secrets, revert build command and code together |

The former 2026-10-07 `qualify_ph_multi_programme_projection` script uses an obsolete AST-only helper/tuple contract and is **not** a reliable release gate for the accepted Biology receiver. Current native PH compatibility/marking suites cover the governed interface; never weaken the actual academic tests merely to remove a red status.

## Predeployment checks

1. Reconcile latest live Render SHA, enabled worker count, startup/build command and disk free space. Confirm production ScoreMax is healthy; do not restart or interrupt Power House releases.
2. Verify PR #56's exact generated candidate digest and runtime changed-file allowlist, academic/PH tests and full synthetic route/50-user HTTP evidence. Treat a capacity shortfall as launch P0, **not** necessarily an incremental-code regression; reject the incremental candidate for any non-equivalence, learner leakage, failed academic gate, >10% p95 regression or unresolved critical error.
3. Inspect traffic status and in-flight assessment sessions/acknowledgements. Stage a read-only WAL-consistent SQLite backup through SQLite Backup API and verify integrity before any production rollout. **Do not copy the live WAL database as a bare .db file.** Snapshot and verify the exact baseline Render settings and previous rollback deploy.
4. Verify that the candidate's **new build command** is the only required Render change. The existing live build command is:

   `python -B scripts/materialize_scoremax_biology_receiver_20261027.py && pip install -r scoremax_runtime_v669b/requirements.txt`

   The candidate command would be:

   `python -B scripts/materialize_scoremax_sqlite_nav_candidate_20261116.py && pip install -r scoremax_runtime_v669b/requirements.txt`

   Keep the entire existing start command unchanged (including pinned `SCOREMAX_SECRET`, persistent paths, Gunicorn 1-worker/4-thread mode and dispatcher). Simply merging PR #56 **without updating this Render build command would not activate any optimisation**.

5. **Separate owner deployment authorisation after all acceptance evidence.** AutoDeploy remains OFF. Do not merge, manually deploy or change the build command while the release remains draft.

## Narrow post-deploy checks (only after approval)

Verify authenticated read routes for FSc/MDCAT and Foundation/Exam Ready access; current PH ACTIVE/withdrawal counts; frozen practice answer retrieval; one disposable current-version submit (where safe); exact assessment/mocked mastery rules; signed outbox + backlog; 4xx/5xx rates, CPU and memory. Compare live p50/p95 Learning, Subject, Chapter and Catalogue latency to the predeploy baseline, with 1/10/50 test traffic only if safe on the actual service. Examine mobile throughput/HTML payload without caching personalised pages. Do not enable the unqualified PostgreSQL path or shadow feature.

Rollback trigger: any unexpected change to formal mastery, question eligibility, signed release/ACK identity, learner isolation, assessment submission, security, persistent database state; any significant 5xx increase or latency regression. **Rollback both Render build command and exact git SHA**, restoring the verified predeployment command and `18c8c70640362aebb531651422c606bb7cf0dfaa`. Keep the original /data disk and stable secret untouched; do not restore the entire DB for a read-only code regression without forensic proof because it would erase later student/PH writes. Reconcile all acknowledgements and submissions before reopening any halted traffic.

## Future speed improvements deliberately NOT bundled

- **Additive SQLite indexes:** separate migration only after exact query-plan proof, WAL backup, disk/free-space and exclusive write tests; no automatic DDL on boot or ordinary deployment.
- **Multiple Gunicorn workers:** possible CPU parallelism but requires startup, memory, SQLite lock, PH ACK and idempotency qualification; not a default configuration change.
- **Compression/CDN/static assets:** inspect HTML/payload, Pakistan/mobile bandwidth, privacy and BREACH/CSRF reflection risk before applying gzip to authenticated HTML. Avoid public caching of student pages.
- **Permanent PostgreSQL shared store:** continues under original PR #55's full 302-table/schema/index/trigger/application parity and zero-loss cutover gate; cannot delay safe SQLite-only improvements.

**Required evidence:** precise per-route p50/p95 baseline/candidate, 50-user regression, unchanged academic/mastery/PH acceptance, rollback rehearsal, and independent release decision. The goal is one comprehensively qualified SQLite performance release rather than an endless series of unmeasured hotfixes.

## 16 Nov 2026 — synthetic learner journey matrix (new gate, awaiting CI)

The draft now includes `scripts/scoremax_synthetic_persona_journeys_20261116.py`, running against **two separate disposable copies** of one seed: accepted production-matched generated runtime and the SQLite-only PR #56 generated runtime. It is a *real Flask client* test, not a live hosted preview. The matrix includes four scenarios over three distinct synthetic learner accounts: FSc Part 1 Foundation, FSc Part 1 Exam Ready, MDCAT Foundation, and FSc Part 2 Foundation. It compares six learner page/assessment setup paths per scenario with exact status, body digest, redirect and Cache-Control; tests practice-session creation, saved answer, attempted other-student session access, final grading, idempotent repeat submission, frozen attempt-answer identity and no practice-generated formal mastery. It enforces exact native-versus-candidate parity.

The tests are stricter than the previous navigation timing harness, but **passing on synthetic learners does not establish real Power House data, teacher/guardian/child commercial entitlements, actual R2 corrections or real student device/browser performance**. No live ScoreMax data or learner accounts may be touched for this test. Do not deploy while CI for this new matrix is pending or failed. Record any source-contract drift and correct the *test* only if accepted native behavior supports that correction; never weaken the learner authorization or mastery contract for a green badge.
