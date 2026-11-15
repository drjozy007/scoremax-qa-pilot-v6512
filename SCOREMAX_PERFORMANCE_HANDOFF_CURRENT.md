# SCOREMAX PERFORMANCE — CANONICAL LIVE PROJECT HANDOFF

**Status:** P0 CAPACITY BLOCKER · EXISTING PR #55 DRAFT · NOT DEPLOYED  
**Updated:** 15 November 2026, UTC — durable shadow stage passed; full capacity qualification pending  
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
| **PR #55** | **OPEN / DRAFT / NOT MERGED**; candidate head **1f461ac02b64f51cea5043a409828b7352b3be56** (verify) |
| PR base | **18c8c70640362aebb531651422c606bb7cf0dfaa** at time of this handoff |
| Most recent CI | [Run 43700240005](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/43700240005), job 132769574659; **FAILED intentionally at P0 performance gate**, after functional/governance rehearsal stages passed |
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
