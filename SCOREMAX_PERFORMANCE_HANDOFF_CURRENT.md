# SCOREMAX PERFORMANCE — CANONICAL LIVE PROJECT HANDOFF

**Status:** P0 CAPACITY BLOCKER · EXISTING PR #55 DRAFT · NOT DEPLOYED  
**Updated:** 15 November 2026, UTC — chapter mastery read bundle qualified on synthetic fixtures; 50-user P0 still FAILED  
**Living document:** Edit this file in place after each meaningful completed work checkpoint. Do not create replacement handoffs, parallel issue trackers or separate systems.

## 0. Resume here — what the next session MUST do

1. Read this complete handoff first, then inspect the live GitHub PR #55 and its latest workflow runs. Do not infer that the SHA below is still latest.
2. Inspect the current **live** ScoreMax Render deployment separately. Do not equate a CI-generated runtime, branch head, successful test or PR merge with deployment or live verification.
3. Continue the existing workstream: [PR #55](https://github.com/drjozy007/scoremax-qa-pilot-v6512/pull/55), branch **perf/student-navigation-batch-20261114**, base branch **fix/scoremax-streamed-backup-20261022**. Do not open a new PR or engineering project to repeat it.
4. **Do not alter production database, workers, learner accounts, Power House dispatchers, question releases, or live platform** without completing the explicit release gates. All new tests run against disposable databases.
5. After every substantive action with verified evidence, update **this very file**: latest state/SHA, result, decision, unresolved risks, rollback and next action. Keep the present-state sections current, preserve a short dated decision log, and update PR #55's brief handoff pointer. This is a within-session working discipline, **not** a promise of automatic updates when no session or monitoring job is running.
6. For ChatGPT Project continuity: the GitHub file is the durable, exact project handoff. If the ChatGPT Project files do not automatically expose it, open the link in a new chat or add a copy to Project files once; do not rely on inferred/automatic ChatGPT memory as the version authority.

## 1. Last physically verified baselines (verify again on resumption)

| System / stage | Accepted or observed state |
|---|---|
| **ScoreMax LIVE** | Render service **srv-daj5fbm7bikc73aq2gdg**; last verified live deployment commit **18c8c70640362aebb531651422c606bb7cf0dfaa**, deployed 9 Nov 2026 |
| Render workspace | **tea-da0721bl550s73cpo260** (owner-confirmed correct workspace) |
| Hosting architecture | Frankfurt, Render Standard, **1 vCPU / 2 GiB**, single instance, 1 Gunicorn worker / 4 threads, SQLite on persistent disk (reported 5 GB). Verify actual disk and free capacity before any migration |
| Database scaling constraint | Render service with attached persistent disk is not currently horizontally scalable by simply adding web instances. Multiple Gunicorn processes on the same SQLite disk alone have **failed** the target |
| Shared storage | Last checked workspace had **no managed PostgreSQL** and **no Key Value** instance to reuse. Do not provision a new one without measured, qualified migration/rollback design |
| **PR #55** | **OPEN / DRAFT / NOT MERGED**; latest qualified code+CI candidate **0545346c5f9a540b44d7d08585fe780581a8538d** (15 Nov); verify new head in GitHub before mutation |
| PR base | **18c8c70640362aebb531651422c606bb7cf0dfaa** at time of this handoff |
| Most recent CI | [Run 43716120025](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43716120025), job 132817917450; read-bundle/idempotence/HTML parity PASSED, **FAILED intentionally at P0 performance gate** |
| **Power House** | Separate live production operation. Service **srv-da08cfdbedkc73a5qdr0**, governed DB **/data/power_house_review.db**. **Not inspected or modified in this performance workstream.** Verify its own latest accepted state independently if integration evidence is needed |
| Student status | Do not assume zero pilot users or no new releases solely from older checkpoints. Current live users, released inventory and ACK counts require live, read-only reconciliation |

**Protected baseline:** Keep ScoreMax commit **18c8c706...** and current production DB/WAL/backup lineage intact. No PR #55 migration or runtime code has been deployed to the live service.

## 1A. Latest checkpoint — 15 November 2026: real writer-surface inventory

- **Source-locked implementation:** `scripts/scoremax_visibility_writer_surface_audit_20261115.py` added to **existing PR #55**, latest implementation commit **acfbd6ab47e4d9303c120661b0888fa06b73ff5d**. Production untouched.
- **CI:** [Run 43702523991](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43702523991), job 132776539228. Focused source writer audit **PASSED**; overall CI **FAILED at intentionally enforced P0 p95 capacity gate** (not a production regression).
- The generated accepted runtime contains direct SQL mutation sites in all seven governed authority tables: **questions (26 function/module locations), question_families (10), PH question version store (6), PH release membership (4), PH release table (5), product activation authorisations (3), staged withdrawal exclusions (2)**. These are *lexical function/module locations*, not audited unique transactional writers.
- **15 flagged dynamic/indirect-write candidates** across app.py, integration, bridge and auxiliary engines still need manual inspection. Some may be false positives; none is certified safe or ignored merely because it is dynamic. Source audit reports `all_writers_certified=false`.
- Explicit native writers include `_activate_release`, `_stage_question_version`, `_withdraw_release`, `authorize_product_activation`, `_withdraw_one`, family edits, admin question edits, import and rollback. This confirms a shared invalidation boundary is viable but not yet proven exhaustive.
- Observed Gunicorn test in that run (synthetic CI only): 50-user p95 **22.885 s** with one worker and **22.480 s** with two. **P0 remains FAILED**. No student writes exercised, real PH fixture still PENDING.
- **Decision:** Do **not** activate a materialised eligibility cache until every dynamic source mutation and transactional boundary is reviewed. Next: implement a **disposable-only, feature-OFF-derived visibility projection** with indexed reads, transactional stale fallback and rollback; independently test 300/1,500/100k scale, write amplification and native parity before runtime integration.

## 1B. Latest checkpoint — 15 November 2026: durable shadow projection qualification

- **Candidate built only on disposable data:** `scripts/scoremax_persistent_shadow_visibility_candidate_20261115.py`, commit **1f17e0b3f7d585ea0e919759c5a0ad301de456e2**; [CI run 43703778124](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43703778124), job 132780356402.
- Focused durable-shadow stage **PASSED**. The test reconstructs ScoreMax's effective native publication function as the original family-approval gate **plus** the guided/self-marking exclusion wrapper. It verifies additive derived tables and indexed membership, transactional invalidation, native question-ID equivalence, fallback on stale state, 1,500-row bulk mutation coalescing, and restart/rollback recovery in a temporary SQLite database.
- **100,000-question synthetic ABBA query measurement** added. At this checkpoint the focused script has passed, but detailed timing and the full CI capacity gate are to be reconciled from completed run logs before accepting any performance claim.
- **Design is OFF by default and NOT installed in ScoreMax runtime.** The script is a disposable offline research/qualification candidate. Real PH membership diversity, all production writer coverage, full transactional installer safety and concurrency/submission capacity still **PENDING**.
- **Risks:** 15 dynamic/indirect authority-writer candidates remain unresolved; triggers impose per-row overhead even when their single epoch update is coalesced. Measure 300/1,500 and 100k import/write overhead before deployment.
- **Decision:** Do not merge or deploy. Keep p95 under 1.5 s with 50 concurrent users as P0 acceptance; pursue only demonstrably faster indexed reads with exact native parity and bounded rollback.

## 1C. Verified checkpoint — 15 November 2026: 100k indexed shadow read qualification

- **Implementation:** existing PR #55 file `scripts/scoremax_persistent_shadow_visibility_candidate_20261115.py`, commit `1f17e0b3f7d585ea0e919759c5a0ad301de456e2`, qualification [run 43703778124](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43703778124), job **132780356402**. Full run **FAILED intentionally at existing P0 concurrency gate**, while durable-shadow tests **PASSED**.
- **ABBA benchmark on 100,000 synthetic questions (1,500 actual-structure synthetic PH links, 97,000 additional synthetic legacy rows):** FSc Part 1 inventory aggregation native **136.187 ms**, indexed shadow **12.729 ms**, **90.7% faster**; MDCAT native **136.303 ms**, shadow **12.382 ms**, **90.9% faster**. Exact grouped counts matched native. These are single SQLite query timings, NOT HTTP page p95 or live data qualification.
- **Tested derived state:** 21 source-table INSERT/UPDATE/DELETE triggers across 7 governed tables, durable SQLite table with (programme, internal question id, subject, chapter), source epoch/dirty flag, atomic BEGIN IMMEDIATE rebuild, live-reader parity assertion, transaction-pinned read, stale native fallback, crash/restart recovery. **97,000-row synthetic bulk insert ~500.637 ms; 100k rebuild ~936.216 ms in isolated runner**. 1,500-row update increments epoch once, source rollback does not invalidate clean snapshot.
- **P0 concurrency still FAILED** because the projection has **not** been connected to student navigation. 50 students, actual local Gunicorn: one worker **20.502 s p95**, two workers **17.354 s p95**. CI red is correct, and production is unchanged.
- **Risks / next gates:** 15 dynamic/indirect writer candidates not certified; current prototype's DDL installer is disposable and must be hardened into a backup/manifest/rollback-safe migration; need real PH mixed-format/multi-programme corpus and simultaneous writer-reader replay; need opt-in real navigation integration and full HTML/academic/QA gates before any deploy.
- **Decision:** Proceed to a **feature-OFF, shadow-only ScoreMax integration candidate**, reusing native SQL/identity and with authoritative fallback on dirty/missing/uncertain state. Do not claim 90% whole-page improvement, do not provision PostgreSQL or change Render instances, and do not weaken release p95 thresholds.

## 1D. Verified checkpoint — 15 November 2026: opt-in navigation integration, default OFF

- **Build:** `scripts/scoremax_shadow_navigation_v1.py` and source-bound installer `scripts/scoremax_nav_shadow_integration_delta_20261115.py`. Existing ScoreMax `_subject_map` fused inventory query now has an opt-in indexed alternative **only when `SCOREMAX_NAV_SHADOW_ENABLED=1`**, with native full-governance fallback on disabled, missing, stale, invalid or empty scope. Default feature **OFF**. No active production schema, app release or Power House modification.
- **CI evidence:** [Run 43704992024](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43704992024), job 132784043163. Source-bound install/idempotence, formal mastery checks, four-route HTML equivalence and snapshot freshness **PASSED**; overall CI **FAILED AS DESIGNED at existing P0 50-user gate** because that gate still exercised default native (shadow OFF).
- 100,800 **synthetic legacy** question bank, single-process Flask serial A→B route medians: Learning native **674.10ms** vs shadow **536.09ms** (20.5% directional); Subject 1042.37→911.00ms (12.6%); Chapter 1133.71→1007.06ms (11.2%); Catalogue 1025.09→893.85ms (12.8%). **All four HTML SHA-256 payload hashes identical**, all four shadow epochs remained clean and matched, on-disk projection rebuild after app startup **724.809ms**, 21 triggers present. A→B cache warming remains a confounder; do not promote these to live acceptance.
- Existing default native Gunicorn 50-student p95 from same run **14.334s (one worker) / 11.818s (two workers)** — still FAIL, **not** a measurement with the shadow enabled. Next test must exercise shadow on via actual Gunicorn and assert persistent freshness throughout.
- **Principal risk:** only `_subject_map` inventory benefits so far; repeated chapter mastery, availability and publication reads remain. 15 indirect/dynamic governance writers not certified; real Power House 300/1500 heterogeneous memberships and concurrent student submissions not yet tested. Do not deploy this candidate or claim thousands-of-learners capacity.

## 1E. Verified checkpoint — 15 November 2026: shadow Gunicorn HTTP concurrency

- Build commit **964594be0929369cd5186561cf4a4949ff81d547**, [CI run 43709920671](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43709920671), job 132799041118. Overall run FAILED at **intentionally enforced P0 1.5s gate** after shadow-enabled HTTP and freshness steps PASSED.
- Worker startup performs governed UPDATE questions and correctly dirties the source-epoch snapshot. The **disposable test harness only** now explicitly rebuilds after Gunicorn startup and before student load. Rebuild duration ~972ms (one worker) and ~998ms (two workers); no production startup/rebuild or worker setting changed.
- 50 synthetic distinct concurrent learners on /student/learn-vnext, 100,800 synthetic legacy questions, 1,000 synthetic accounts: native p95 **18.197s (one worker)**, **16.164s (two workers)**; opt-in shadow p95 **12.280s (one worker)**, **11.890s (two workers)**. At 10: native **3.857s / 3.828s**, shadow **2.902s / 2.635s**. Sequential nonrandomised CI measurements only; not verified on actual governed PH memberships or live Render.
- Shadow source and snapshot epochs stayed clean across load; protected user/question/attempt/mastery/release row-count census unchanged. **Candidate improvement 26–33% at 50 students remains provisional; P0 capacity still FAILED by large margin.** No answer submissions or signed Power House ACK/withdrawal traffic were exercised.
- Live ScoreMax remains commit **18c8c70640362aebb531651422c606bb7cf0dfaa**; PR #55 draft/undeployed, opt-in feature default OFF. Power House and production database untouched.
- Immediate next engineering target: profile and reduce remaining synchronous learner navigation computation (chapter mastery/availability, shared Jinja context, evidence and coach), using governed subject/programme partitioning. Audit all 15 unresolved dynamic writers before any live cache installation; qualify real PH 300/1,500, concurrent submissions and signed bridge. Keep p95 <1.5s at 50 concurrent and strict rollback gates.

## 1F. Verified checkpoint — 15 November 2026: hidden shared-template guard and real load

- **Candidate:** `scripts/scoremax_hidden_template_work_guard_20261115.py`, implementation commit `65b44c3645ed1c44a99fba17bb32178504a7508e`, corrected marker formatting in `9399fd500c7c47c98c7cb13355f895cae95d91cd`, and extra hidden-route HTML parity test code+workflow at `fefe7f0c1cfc3bebde547a13e1ad168f3510a3f0`. These are *draft build-time changes*, not accepted production.
- **CI:** [run 43712653072](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43712653072), job `132807380380`: build/idempotence and formal-mastery gates PASSED; baseline-vs-candidate exact HTML body checks PASSED for four learner navigation routes plus `science_genius_home` (HTTP 200). `community_home` had an HTTP 302 redirect; status/body equality PASSED but did not test its protected page after authorisation.
- **Scale provenance:** synthetic 100,800 legacy questions, 1,000 distinct accounts, 102,300 finalised answers, not actual heterogeneous PH memberships. Shadow-enabled Gunicorn /student/learn-vnext 50 concurrent p95 **16.626s with one worker**, **16.502s with two**. Native/default-off p95 **22.406s / 21.562s** in the same run. These are sequential single-run synthetic measurements and do **not** establish production speedup.
- **Result:** Functional equivalence PASSED within measured coverage; **P0 concurrency acceptance FAILED** (target p95 <1.5s). Do not declare the hidden-work guard a systemic fix; the code is not integrated into production and any improvement of pages with hidden navigation is unquantified. Keep owner-facing UX untouched.
- **Priority decision:** no more speculative micro-patches just to change a percent. Evidence shows the remaining dominant cost is eager whole-chapter mastery/availability and shared context/coach computation: 203 SQLite executes on the Learning page, ~441 on Subject, and dynamic question-type processing on Chapter. Inspect multi-chapter query aggregation and native visibility projection under genuine PH contracts first. Any new cache must preserve atomic writer invalidation; 15 dynamic/indirect writer candidates are still unresolved.
- **Next actions:** (1) profile the full request path with exact real PH 300/1,500 diverse fixtures; (2) reduce chapter/mastery-query explosion using source-locked batching or safely derived aggregate; (3) mixed 50-user GET+submit+mark+Power House ACK/withdrawal under proper transactional storage and Render-equivalent CPU; (4) verify live compression/asset payload and mobile throttling; (5) backup/rollback + owner acceptance. Do not merge, redeploy or alter live account/database/dispatcher states.

## 1G. Verified checkpoint — 15 November 2026: chapter mastery shared read bundle (PR #55 only)

- **Source-bound feature built:** `scripts/scoremax_chapter_mastery_local_bundle_20261115.py`, creation commit `f6f7d546b5181712ce569a6b3ea5e6aeaa1f8f7e`; final candidate workflow commit `0545346c5f9a540b44d7d08585fe780581a8538d`. Reuses the same native assessment blueprint, mastery policies and student access within one `_chapter_snapshots` invocation, with a local bundle passed to `chapter_mastery_opportunity`. Chapter-specific coverage, approval, formal mastery eligibility, PH scope, previous families and direct callers remain unchanged.
- **Systemic installer correction:** Two initial CI failures exposed fragile whitespace insertion; replaced it with original-statement-indentation-derived block substitution and added `tests/navigation_perf_20261114/test_mastery_bundle_source_indentation.py` (nested/function-body/duplicate-anchor checks). Subsequent CI revealed older installer replay could not accept a later modification to `_chapter_snapshots`; changed build order to validate all original installer replay checks **before** installing the new bounded overlay, preserving the original fail-closed checks. This corrects the build composition rather than weakening drift detection.
- **Latest CI:** [run 43716120025](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43716120025), job `132817917450`: source/idempotence, formal mastery, four learner HTML equivalence, hidden-page parity, 100,800-question synthetic characterisation, shadow-enabled Gunicorn freshness stages PASSED; overall run **FAILED AS DESIGNED** at P0 p95<1.5s load gate.
- **Scale:** 100,800 synthetic questions, 1,000 synthetic accounts, 102,300 FINAL saved answers. Latest isolated navigation medians: Learning **0.856s**, Subject **1.304s**, Chapter **1.431s**, Catalogue **1.291s**. They are runner-specific, not stable comparative gains or live p95. Shadow-enabled Gunicorn 50 distinct concurrent GETs p95 **12.335s (1 worker)** / **11.876s (2 workers)**; native default-off p95 **16.826s / 15.154s**; still **FAILED** the 1.5-second P0 threshold. These are isolated sequential nonrandomized synthetic runs, no real PH shared-release fixture or concurrent submissions.
- **Decision:** retain bounded code in DRAFT pending richer test evidence, but **do not treat it as a capacity resolution**. The remaining architectural blocker is high per-request CPU/SQL cost plus a single persistent SQLite service/1-vCPU instance. Another modest reduction will not achieve 50-user p95. Prioritise a governed chapter availability/mastery aggregate or indexed read-model backed by release-state mutation coverage and a qualified shared transactional database path; do not silently relax academic eligibility or add cross-user caches.
- **Unchanged:** LIVE ScoreMax Render at `18c8c70640362aebb531651422c606bb7cf0dfaa`; Power House delivery, learner accounts and both live databases untouched; PR #55 still DRAFT and unmerged. **Next:** verify real FSc/MDCAT 300/1,500 heterogeneous release fixtures, 15 indirect writers and startup invalidation; prove multi-client read+submission+mark/ACK safety, Render-equivalent performance, migration/rollback and low-bandwidth behavior before any deploy.

## 2. Why this is P0: observed evidence vs inference

**Observed live 14 Nov 2026:** Student chapter pages ~18–20 seconds; subject up to **38.467 seconds**; ordinary homepage ~**0.013 seconds**. At the sampled interval, peak five-minute CPU average about 0.296 of 1 vCPU and memory about 408 MB of 2 GiB. These averages do not rule out CPU spikes; they do argue against assuming that buying more RAM/CPU solves the root problem.

**Confirmed hot paths:** repeated governed publication and programme-membership SQL, chapter-card mastery/availability queries, context-processor subject navigation, repeated learner evidence reads and multiple complete inventory scans. Native publication is a family-status AND per-question approval gate; PH projections require exact version/checksum match, ACTIVE release, product activation authority and absence of question-level withdrawal. **Never drop those predicates to improve speed.**

**Transport:** sampled student HTML ~65–76 KB raw, estimated ~18 KB gzip. Isolated responses lacked Content-Encoding; LIVE CDN/proxy compression, CSS/JS/images, and Pakistan low-bandwidth interactive rendering are **NOT VERIFIED**. Transfer tuning cannot explain the observed multi-second server work on its own.

**Scale test fixture:** **100,800 synthetic legacy questions**, **1,000 synthetic user accounts**, **102,300 finalised saved answers**. Validated frozen evidence was added after an earlier unrealistic seed was caught. These are NOT 100,800 genuine PH memberships and do NOT qualify cross-market release diversity.

## 3. Work already implemented in the existing PR (DRAFT build-time candidate)

- Bounded navigation/query changes: group programme inventory; prevent repeated per-subject full scans; batch chapter evidence; narrow mastery-card question projection; request-only subject map caching keyed by student and programme; request-only frozen answer evidence reuse; use scalar copies where safe with nested deep-copy fallback.
- Catalogue count path: push requested subject filter into the existing governed placement SQL; avoid invoking the expensive question-type interpreter for a count-only result. Real question type/marking checks remain unchanged.
- Fused native subject-discovery plus grouped chapter-inventory query preserving exact learner subject spellings and chapter keys. It passed tested HTML equality and showed **directional** 9–15% improvement in a same-run A-then-B synthetic comparison; ordering could favour warm cache. Do not claim stable production gains without ABBA/reversed order.
- Explicit, guarded **five additive SQLite navigation indexes**, including expression lower(COALESCE(subject,'')), chapter, id. Not invoked at boot; migration requires backup, integrity check, write lock, disk capacity and rollback.
- Source-anchored fail-closed installers; idempotence checks; byte-equivalent HTML for four tested student pages and formal-mastery regression tests.
- Real local Gunicorn HTTP harness for 1 and 2 workers at 1/10/50 distinct synthetic users, read-only; protected table row-count check.
- **Enforced P0 CI failure gate**: measured student HTTP p95 must be **strictly below 1.5 s** in every specified concurrency scenario; green functional checks do not override this gate.

All of these are PR-candidate changes. **None is accepted as production deployed or Windows/live verified.**

## 4. Most recent acceptance results

### Functional/security and academic safeguards

- **PASSED (disposable):** native-vs-release-driven governed visibility **10 adversarial scenarios**; same canonical PH question may be visible in FSc and MDCAT, but staged ECAT stays hidden, withdrawal/revocation isolates scope, mismatched checksum/version/internal link or partial projection cannot leak.
- **REJECTED as an optimisation:** release-driven SQL UNION/CTE query. It was equivalent but slower under ABBA: **FSc Part 1 native 47.779 ms vs candidate 76.165 ms; MDCAT native 75.264 ms vs candidate 76.489 ms** in the 3,000-row fixture. It is *only* a diagnostic script, **not wired into ScoreMax**.
- **PASSED (disposable):** transactional eligibility invalidation rehearsal, **18 scenarios**, **seven authority tables**, **40 snapshot reads**, **32 authoritative fallback reads**. Same-transaction source-epoch and snapshot-epoch equality; atomic rebuild; source rollback and interrupted rebuild preserve correctness. This is an **in-memory prototype**, not a deployed materialised view, not production writer coverage.
- Other tested synthetic HTML and mastery safeguards passed in preceding CI. Some source-conditioned tests were skipped when optional accepted-source fixtures were absent; do not count skipped tests as passed.

### Performance (hard blocker)

Latest [run 43700240005](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43700240005) had the P0 capacity gate **FAILED AS DESIGNED**:

| Concurrent distinct synthetic students | One worker p95 | Two workers p95 |
|---|---:|---:|
| 1 | **0.979 s** | **2.707 s** (cold/order effect possible) |
| 10 | **4.885 s** | **5.872 s** |
| 50 | **23.092 s** | **20.714 s** |

- This test used local CI runner + Gunicorn HTTP, not Render production. No student submissions were exercised. DO NOT extrapolate to 1,000 truly simultaneous learners from this small synthetic set.
- **Acceptance:** p95 student navigation **<1.5s under 50 concurrent users**; stretch <1s, and then test 100/300/1,000-user realistic mixes with evidence and no data loss. Current **FAILED**.
- Individual 100k navigation medians have frequently been ~0.9–1.5s in isolated Flask tests, but vary across CI runners and do not prove live or concurrency readiness.
- No hardware, DB migration, global cache, or worker count increase has been validated as a solution.

## 5. Next execution sequence — minimum duplication, maximum proof

**A. Governed mutation-surface audit (P0).** Inventory every production write path that can change question eligibility—source version/checksum links, question family approval, live question status, membership admission/release, activation/revocation, withdrawal, correction, direct recovery, return/ACK reconciliations and rollback. Trace real write transaction boundaries, triggers, bulk performance and out-of-band SQL. The in-memory rehearsal watches seven tables, but **does not prove coverage of every writer**. Do not install a cache before this.

**B. Extend the existing native read system with shadow-mode derived visibility (P0).** If justified by query plans, design one **derived** eligibility projection, not a separate source of academic authority. Ensure atomic epoch/invalidation on governed mutations, matching snapshot version within a read transaction, on-mismatch fail-closed native fallback, version/checksum and programme/withdrawal lineage, deterministic rebuild, reconciliation ledger, and safe rollback. Avoid per-row trigger amplification during 300/1,500 intake and 100k rebuilds; measure write amplification, locks and disk. Never silently materialise unauthorised or staged releases.

**C. Real heterogeneous production-equivalent fixtures (P0).** Replay **actual approved, privacy-safe PH records** in disposable ScoreMax test DB: FSc Y11/Y12 + MDCAT, shared FSc/MDCAT items, 300/1,500 batches, MCQ, T/F, Cloze, SAQ/constructed response, opaque IDs, missing/unfamiliar metadata, activation, revocation, withdrawals, amendments, R2 holds, practice-only zero-weight and incomplete contracts. Assert exact learner-visible question-ID sets vs native reader, no cross-programme leakage, correct marking/official mock/mastery protection. If real source cannot be accessed, mark PENDING, never silently substitute synthetic evidence.

**D. Mixed read/write load and persistence (P0).** Evaluate 1/10/50/100/300 and representative thousands of registered learners (not all simultaneously unless explicitly specified), with concurrent navigation, assessment creation, saves, submit/grade, feedback, PH signed delivery, ACK and withdrawals. Record p50/p95/p99, error rate, CPU throttling, SQLite lock waits, disk/WAL, tail latency, integrity, lost-update/double-credit defects and crash recovery. At 50 concurrent: p95 <1.5s with no safety regressions. Test 100k+ question population and realistic answer-history distributions.

**E. Storage/horizontal-scaling decision (P0/P1).** Existing persistent SQLite disk precludes simple multi-instance Render scaling. Qualify shared transactional database (e.g., PostgreSQL) only once necessity is evidenced and migration strategy covers identifiers, exact question/version membership, historical answers, rollback/replay, signed Power House interfaces and cutover dual-read proof. **No database provisioned, no migration authorised or completed.** Do not deploy a second ungoverned system.

**F. Low-bandwidth real browser (P1).** Verify live proxy gzip/Brotli first, then assets and caching policy, navigation/web-vitals on representative mobile devices and Pakistan network throttling. Never cache student-private HTML publicly. Preserve frozen learner UX.

**G. Release (P0).** Explicit gates: correctness, identity, source authority, release/withdrawal parity, mastery and mock exclusions, write safety, concurrency SLA, Windows/Linux/Render compatibility, DB backup+rollback, package/manifest integrity, controlled live before/after test, and Power House ACK end-to-end. Only then update/merge/deploy. Keep Power House releases independent unless the tests reveal a verified integration risk.

## 6. Acceptance register (NOT a launch sign-off)

| Gate | State |
|---|---|
| ScoreMax live baseline and PR #55 identity | PASSED — last verified 15 Nov 2026 |
| Code safety on synthetic native routes | PASSED (scope-limited) |
| Exact HTML parity on four synthetic routes | PASSED (scope-limited) |
| Governed native/alternate relation 10 synthetic scenarios | PASSED (candidate rejected for speed) |
| Transactional invalidation 18 synthetic scenarios | PASSED (rehearsal only) |
| P0 p95 <1.5s with 10/50 Gunicorn concurrent users | **FAILED** |
| Production-equivalent real PH shared release fixtures | **PENDING** |
| Live-safe derived projection + every-writer invalidation coverage | **PENDING** |
| 300/1,500/100k mixed formats & real governed load | **PENDING** |
| Concurrent submissions, marking, PH delivery/ACK/withdrawal | **PENDING** |
| Shared database migration/backout qualification | **PENDING** |
| Real low-bandwidth/browser and CDN compression | **PENDING** |
| Windows/Render acceptance and live before/after | **PENDING** |
| Merge, deployment, activation of candidate | **NOT STARTED** |

## 7. Rollback and protected boundaries

- Never modify original question/source identity or infer numeric meaning from opaque PH IDs. Preserve original/amended version lineage, curricula and academic authority in Power House.
- Never relax statuses to satisfy latency: family approval, PH active authorised membership, exact checksum and version, withdrawn exclusion, programme access, independent mastery and mock eligibility.
- No Power House database, reviewer QA/R2 or production dispatcher changes are part of ScoreMax PR #55; resolve ScoreMax-specific performance in its own repository.
- Preserve the live ScoreMax commit, DB/WAL and full verified recoverable backup before any index, trigger, projection or schema deployment. Use disposable databases for all prerelease tests.
- If the same failure recurs twice, review query architecture and system-of-record design rather than stacking local patches or caches.
- Distinguish **designed → built → locally tested → Windows accepted → deployed → live verified → frozen**. Only assert stages for which physical evidence is present.

## 8. Short decision trail (current; detailed audit in PR #55)

| Date | Decision / verified evidence |
|---|---|
| 14 Nov | Live student pages observed 18–38s; ScoreMax PR #55 isolated improvements; production unchanged |
| 14 Nov | 100,800 questions + 1,000 accounts synthetic showed 1.0–3.6s medians; 50-student concurrency failed; work restricted to draft PR |
| 14 Nov | Subject/chapter index, catalogue SQL pushdown and fused discovery qualified in isolated tests; source-locked safeguards retained |
| 14 Nov | True Gunicorn 1/2 worker HTTP at 10/50 users still failed; simply adding workers rejected as systemic solution |
| 15 Nov | Request-local scalar evidence copy qualified; hard P0 GitHub gate introduced and failed correctly |
| 15 Nov | Native vs release-driven PH visibility parity in 10 scenarios PASSED; alternate query slower by ABBA and **rejected** |
| 15 Nov | 18-scenario transactional eligibility epoch/rollback rehearsal PASSED; **no live derived projection exists** |
| 15 Nov | Current living handoff established. Future substantive work must update these current facts and PR #55's link |
| 15 Nov | Post-startup shadow Gunicorn parity PASSED; 50-user p95 12.280s / 11.890s, P0 still FAILED, run 43709920671 |
| 15 Nov | Hidden-template guard built and tested; 4 navigation + 2 hidden-route output checks passed, but shadow 50-user p95 16.626s / 16.502s, P0 FAILED, run 43712653072 |
| 15 Nov | Source-derived, install-order-safe chapter mastery local read bundle tested; 50 concurrent shadow p95 12.335s / 11.876s, P0 FAILED; run 43716120025 |

## 9. Update contract for every future progress checkpoint

Update **this same file** in one guarded GitHub commit (not a new document); verify the PR head and Render live SHA first. Reconcile and replace stale status, don't append full chat transcripts. Record: exact UTC date, implementation commit, focused tests and CI run/job URLs, PASS/FAIL/PENDING gates, real vs synthetic provenance, stage (built/tested/live), new risks, rollback and the immediate next action. If the outcome is a defect, retain it as unresolved; if repeated, re-evaluate architecture. Update PR #55 summary to point here and state the latest blocker. **Only claim the update is written after GitHub confirms its commit.**

**New-chat continuation prompt:**  
"Resume the existing ScoreMax P0 performance workstream. Read SCOREMAX_PERFORMANCE_HANDOFF_CURRENT.md on branch perf/student-navigation-batch-20261114 in drjozy007/scoremax-qa-pilot-v6512, then inspect PR #55, latest GitHub CI and the live Render deployment. Continue from the latest verified checkpoint. Keep the P0 p95<1.5s gate and academic/Power House release controls intact; update the same handoff after each substantive checkpoint. Do not create new systems or deploy without acceptance."

---
**Current source references:**
- [PR #55 — existing performance recovery workstream](https://github.com/drjozy007/scoremax-qa-pilot-v6512/pull/55)
- [GitHub CI — 43700240005 (P0 red)](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43700240005)
- [Render ScoreMax service](https://dashboard.render.com/web/srv-daj5fbm7bikc73aq2gdg)
- [Power House Render service](https://dashboard.render.com/web/srv-da08cfdbedkc73a5qdr0)
