# ScoreMax UK 11+ — Explain My Mistake (candidate qualification)

**23 November 2026 | Isolated engineering branch only | NO student release**

## Decision and scope

Extend ScoreMax's existing submitted-result review, its verified `written_ai_adapter.owned_material` authorization, its immutable Power House version store, approved question explanations, and approved Learning Capsules. Do not build a new tutor, marking engine, database, AI transport, or learner activity pipeline.

**Prototype is a read-only, feature-flagged, zero-provider-call explanation route.** The old written-response DeepSeek feedback adapter remains untouched and disabled by default. The result-page query must include UK market and auto-markability fields before its link can be safely shown; this was detected and rectified in the overlay. Independent academic acceptance is not implied.

## Target integration

- Existing ScoreMax base files inspected at deployed source commit `e5a3af5b4f601cd06eb43c4d9155135fb34b15f7`:
  - `hosted_runtime_base_v6512/scoremax_production.py` (one WSGI installation anchor)
  - `hosted_runtime_base_v6512/templates/result.html` (one result review question-report anchor)
  - `hosted_runtime_base_v6512/app.py` (existing results query, extended only in a disposable runtime to select `q.ph_market_id` and `q.ph_is_auto_markable`)
  - `hosted_runtime_base_v6512/scoremax_integration_v1.py` (immutable version store, PH governance gate, membership and pinned-question support)
  - `ux_vnext_overlay/ux_paid_ai_marking_20261026.py` and `ux_vnext_overlay/paid_ai_marking_20261026/written_ai_adapter.py` (existing AI ownership/feature/receipt policy)
- New isolated files: `uk11_result_explanation.py`, `ux_uk11_explain_overlay.py`, `uk11_explain_mistake.html`, `test_uk11_result_integration.py`.
- Existing candidate `ai_explanation_candidate.py` remains a provider-free reviewer prototype; strengthened phone-number firewall and test.

## Native sequence (proposed, not live)

1. Existing owned submitted answer via native `scoremax_written_ai_owned_material`.
2. Recheck incorrect response, nonempty saved answer and non-provisional native mark.
3. Verify six pinned immutable fields against the submitted answer.
4. Confirm UK market, release membership and question version in canonical Power House store.
5. Reuse native `_governance_ready` for approved review, holds, rights, source-check and R2.
6. Exclude unqualified response types and unresolved stimuli/diagrams; require `ph_is_auto_markable=1`.
7. Use the canonical approved marking key, never the potentially stale local projection; prefer approved canonical explanation; otherwise use an explicitly question-bound, reviewed Learning Capsule. Never infer a capsule from a fuzzy topic match.
8. Return learner-readable explanation **after submission only**. Display no internal IDs, keys, rubrics or AI candidates. Do not write to database or update score/mastery.
9. Future generative AI may reword an approved solution only after independent academic/child-privacy review and through the existing paid-AI budget/consent gate; the current code makes **no AI calls**.

## Protection

- New feature flag `SCOREMAX_UK11_EXPLAIN_ENABLED_TEST_ONLY`, defaults to 0.
- Overlay `apply(root)` requires `.uk11_disposable_qualification_runtime` inside a disposable runtime, and verifies native startup/HTML anchors before writing. Conflicting targets fail closed; rollback restores modified files on write failure.
- In disabled mode, the existing results-page global guard remains defined and returns false (prevents template failure when feature off).
- Student access, assessment ownership, question pin, release state/withdrawal, membership, rights and academic review all fail closed.
- Public UK preview, Power House production, ScoreMax Pakistan production, child data, credentials and Render settings were **not** changed.

## Local test evidence

`python -m unittest discover -s qualification/uk11 -p 'test_*.py' -q`

**51/51 synthetic/local tests passed**: 17 provider-free approved-content tests and 34 synthetic result/route/overlay tests. Tests include cross-student denial, unsubmitted/blank/correct answers, unscored attempts, modified pins, release withdrawal, wrong country, missing membership, disallowed rights, held/R2 content, unqualified response types, unresolved visual assets, missing approved explanations, HTML escaping, feature-off rendering, and safe overlay application.

**Not qualified:** These tests use a synthetic SQLite database and a stubbed Flask route adapter (Flask not available in this qualification worker). They are not native tests of the exact final assembled ScoreMax receiver/scorer or authenticated Render runtime. No real paid AI transport, quota or latency tests were run. Academic correctness of the explanations has not been independently audited.

## Remaining gates

| Gate | Status | Acceptance evidence required |
|---|---|---|
| Candidate syntax + test validation | PASSED | 50 local tests and source hashes |
| Existing native source/anchor inspection | PASSED (source only) | Pin exact source paths and hashes |
| Actual assembled-runtime install/Flask results flow | PENDING | Disposable assembled runtime with written AI adapter installed; browser/HTTP replay |
| Exact native marking + 85 Maths adversarial cases | PENDING | Real native scoring receipts; no wrong-unit credit |
| English/VR/NVR passages/diagram and marking | PENDING | Format-specific assets/academic qualification |
| Child-data privacy/accessibility/mobile | PENDING | Runtime and browser evidence |
| Academic source/solution correctness | PENDING | Independent Power House-backed explanation review |
| Provider AI feedback, costs and consent | PENDING | Separate approved AI budget, privacy and semantic benchmark |
| Public student activation | PENDING | Academic, marking, privacy and engineering gates |

## Next engineering work

1. Reconstruct exact deployed ScoreMax assembly in an **isolated disposable runtime**; verify that native written AI ownership extension is installed even when the provider is off.
2. Apply this UK-only overlay and replay HTTP/session/marks checks, then run the held Maths scoring suite.
3. Supply UX workstream the result-link and explanation-page design contract. Supply Academic workstream the approved-explanation/learning-capsule requirements for each question.
4. Only after evidence-based acceptance, plan UK-staging enablement; do not enable paid AI or public production by default.

**Status:** Built + locally tested candidate; not runtime qualified, independently audited, deployed or learner released.
