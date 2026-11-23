# ScoreMax UK 11+ — Engineering Gate Register (23 November 2026)

**Scope:** isolated read-only qualification baseline for Power House -> ScoreMax content, UK school/test/cycle routing, native rendering/marking, mastery and performance.
**This document is not an acceptance certificate.**
**Do not modify Pakistan production, persistent databases, frozen schemas, credentials or paid infrastructure based on this document.**

## Deployment identities observed (Render, 23 November 2026)

- ScoreMax service `srv-daj5fbm7bikc73aq2gdg`, branch `fix/scoremax-streamed-backup-20261022`, latest live deployment `dep-dc25ft40916s738b1hog`, source commit `e5a3af5b4f601cd06eb43c4d9155135fb34b15f7`. The actual production runtime is assembled from committed baseline, patches and overlays; this commit by itself is NOT an inspected fully assembled runtime.
- Power House reviewer service `srv-da08cfdbedkc73a5qdr0`, branch `main`, latest live deploy `dep-dc25ulmk1f9s73blsb60`, source commit `acc62714e04e231d294fee8bd9f24cab18454773`. Native publisher output at this deployed assembly is not yet replayed.
- UK static design preview `srv-dc26mgmi0phs73bt500g`, separate branch `preview/uk11-static-site-20261123`, commit `448b26ee7d40f8a09f0de9dd219d1fe7e612d5ec`. Pure HTML prototype; no native grading or learner persistence.

## Current proven source findings (not native runtime qualification)

1. The ScoreMax *base* `hosted_runtime_base_v6512/integration_contracts/v1_1_0/PH_SM_APPROVED_CONTENT_V1.schema.json` specifies envelope schema 1.1.0; release identity is market/programme/subject/chapter. The question contains immutable ID/version/checksum, curriculum, content/marking, architecture, governance and provenance. Neither the base release object nor the base curriculum object contains explicit school/provider/admissions-cycle membership fields. Do **not** infer that the final assembled runtime lacks them: inspect its final compiled schemas first.
2. The *base* receiver `hosted_runtime_base_v6512/scoremax_integration_v1.py` defines LIVE key types SINGLE_OPTION, MULTIPLE_OPTIONS, TEXT, NUMERIC and BOOLEAN; the base schema additionally allows RUBRIC_ONLY. Actual assembled native receiver/marking support requires testing before treating this as either a deployed defect or an accepted capability.
3. Power House `native8_qualification_candidate/fsc2200_native_mdcat_membership_20261009.py` contains a source-preserving multiple-destination pattern and requires native approved-content schema 1.2.0. This is evidence of reusable architecture, NOT proof the current PH sender and SM receiver are schema-compatible.
4. ScoreMax `tests/test_programme_practice_routing.py` defines disposable SQLite regression cases for one canonical question appearing in multiple approved programme destinations, wrong-destination exclusion, activated-release checks, withdrawal exclusion, hash mismatch and guided-practice separation. Its test logic has not been executed here against the exact assembled UK runtime.
5. `v6611d_bridge/scoremax_ph_bridge_v6611d.py` contains outbox-only receipt/incident/withdrawal logic; the actual deployed assembly must prove it is installed, version-compatible and operational.
6. The existing UK readiness register (23 Oct 2026) is DESIGN BASELINE / NOT FROZEN: Maths CANDIDATE/HOLD, other three subjects NOT YET EVIDENCED. The UK 20Q Maths pilot still has BANK_APPROVED=NO, STUDENT_RELEASED=NO and VALID_FOR_REAL_MASTERY=NO. Offline scoring: 85 cases, 13 reference mismatches, 9 unresolved policy cases, 0 native executions. No inference of live ScoreMax defects from that offline scorer.

## Required UK release gates — all PENDING unless stated

| Gate | Required concrete acceptance evidence | Status |
| --- | --- | --- |
| UK-E00 Current deployment identity | Reproducibly reconstruct exact deployed runtime, pin tree checksums and migrations, verify readiness | PENDING (service deploy identities observed only) |
| UK-E01 Canonical contract | PH publisher -> exact assembled SM receiver JSON parity, immutable IDs/checksums, no silent field drops | PENDING |
| UK-E02 School/test/cycle memberships | Evidence-bound route records, no eligibility inference, one source question many routes, correct destination filtering | PENDING |
| UK-E03 Renderer/learner firewall | Full learner view across MCQ, numerical, stimulus, diagrams, multipart, matching, written; no keys/rubrics/QA leakage | PENDING |
| UK-E04 Native marking | Run 85 Maths scoring cases plus representative English/VR/NVR and negative/adversarial responses in real renderer/scorer | PENDING |
| UK-E05 Mastery independence | Shared-question exposure counts once; assistance/cosmetic variants do not verify mastery; no QA->LIVE spill | PENDING |
| UK-E06 Transport lifecycle | Approved versioned ingest, receipt, activation, retry, duplicate replay, withdrawal, incident and rollback | PENDING |
| UK-E07 Scale and operations | Indexed bounded searches, safe cache invalidation, 300/1,500-item mixed populations, P50/P95/P99 latency, disk headroom | PENDING |
| UK-E08 Academic/release authority | Exact source rights, frozen taxonomy, subject QC, independent audit/Gold, separate product activation | PENDING |

## Sequence of engineering work

1. **Discover and pin** the exact assembled PH publisher, ScoreMax receiver, native scorer and renderer for the deployed snapshots. Read-only inspection first; no assumptions from the older base package.
2. Produce a **strict field-level PH->SM crosswalk** and separate school/test/provider/cycle membership proposal using existing membership tables/engines where possible. Preserve frozen canonical schema bytes unless separately approved.
3. Build a disposable **UK-only synthetic-learner qualification** with actual heterogeneous content, renderer and marker. Preserve correct/wrong/adversarial variants, units, Unicode, aliases, diagram/passage references and unsupported-type abstention.
4. Prove the full lifecycle: PH approved item -> signed transport -> SM staging -> search/allocation -> learner render -> response -> native marking -> mastery -> reverse evidence/withdrawal. Accepted receipt alone is insufficient.
5. Measure correctness, storage, memory and indexed route-query performance; identify any systemic failure before scaling.
6. Share only qualified interface contracts and implementation-ready details with Product/UX and Academic chats. Never treat the public demo questions as a released bank.

## Quality policy and risk boundaries

- **P0 launch blockers:** unsupported response type silently credited, wrong units credited, incomplete stimulus/diagrams, incorrect school-cycle membership, canonical key/version corruption, unapproved academic release or child-data/hidden-answer leakage.
- Previous OFFLINE grader failures establish **test risks**, not proven deployed bugs.
- Production PH and ScoreMax services untouched. Preview/UX changes belong only to the isolated UK preview branch.
- Gate statuses: DESIGNED/BUILT/LOCALLY TESTED/RUNTIME QUALIFIED/INDEPENDENTLY AUDITED/DEPLOYED/LIVE VERIFIED/ACCEPTED require distinct evidence; never collapse them.

## Source links

- ScoreMax repo: https://github.com/drjozy007/scoremax-qa-pilot-v6512/tree/fix/scoremax-streamed-backup-20261022
- PH repo: https://github.com/drjozy007/power-house-reviewer-service
- ScoreMax base 1.1.0 schema: `hosted_runtime_base_v6512/integration_contracts/v1_1_0/PH_SM_APPROVED_CONTENT_V1.schema.json`
- ScoreMax routing regression: `tests/test_programme_practice_routing.py`
- PH multi-exam membership: `native8_qualification_candidate/fsc2200_native_mdcat_membership_20261009.py`
- UK readiness: `ScoreMax_11Plus_Universal_Readiness_Register_v0_1.xlsx` (23 Oct)
- Pilot: `ScoreMax_11Plus_Maths_20Q_Native_Scoring_and_WCA_PreAdmission_v0_4.xlsx` (22 Oct)

**No release authority conferred. No live changes authorised by this register.**
