# ScoreMax UK 11+ — Exact Native Runtime Gate Review

**23 November 2026 | Engineering qualification | HOLD — not a student release**

## Decision

Keep **Explain My Mistake** as a UK-only, default-disabled, read-only candidate. Stop iterating hand-crafted native source identities after repeated validation failures. The next acceptance fixture must follow the actual Power House-approved publish/admit/activate/session-pinning path in a disposable environment. Do **not** weaken ScoreMax's immutable source-identity validator to make a synthetic test pass.

## Verified deployed source and replay

- ScoreMax Render service `srv-daj5fbm7bikc73aq2gdg`, source commit `e5a3af5b4f601cd06eb43c4d9155135fb34b15f7`, live build command `scripts/materialize_scoremax_sqlite_nav_candidate_20261116.py`.
- The exact build reconstructed deterministically in isolated GitHub Actions: **tree SHA-256 `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`**. This identifies the pre-UK-overlay runtime only.
- Current public/accepted ScoreMax runtime does not install the optional paid-AI ownership adapter. Reused the existing source-pinned `written_ai_adapter.py` (Git blob SHA `aafcde0e572ac8967b025315f7c4b23c136f1f1f`) *only inside disposable CI*, with `SCOREMAX_PAID_AI_FEEDBACK=0`, AI budget zero and no provider key.
- Applied the UK explanation overlay only after an explicit disposable-runtime marker. Production build, persistent data and Render service were not altered.
- Native Python/Flask application booted successfully with **314 registered routes**, UK explanation route present, and all three relevant templates compiled.
- Native unauthenticated request returned **302**; authenticated nonexistent question returned **404**. These are observed rejection outcomes, not evidence that the intended eligible question renders successfully.
- **51/51 isolated UK explanation tests passed** in CI (with fake ownership/SQLite before native startup). They do not constitute independent academic or native scoring acceptance.

## Outstanding end-to-end gate

| Gate | Current result |
| --- | --- |
| Exact source materialization and tree hash | PASSED |
| Existing written-AI ownership source reuse with provider disabled | PASSED (isolated CI) |
| UK overlay application and template compilation | PASSED (isolated CI) |
| Local synthetic unit/adversarial tests | PASSED 51/51 |
| Native Flask startup + unauthorized/missing-item rejection | PASSED |
| Native eligible wrong-answer explanation HTTP 200 | **PENDING / DID NOT PASS** |
| Native scored answer and 85 Maths adversarial cases | PENDING |
| Independent academic solution clearance | PENDING |
| Provider model use, child privacy/consent, AI budgets | PENDING |
| Production, UK preview or paid-AI activation | **NOT PERFORMED** |

The native trial's synthetic records were rejected with **`PIN_SOURCE_IDENTITY_MISMATCH`**, including when using the current native `build_session_content_pins` call. An independent real-source fixture/import receipt has not been supplied, so **the cause is not established as a deployed defect**. Earlier fixture failures were traced to the existing native family-publication rule and missing/unsupported canonical question-family fields; these checks correctly failed closed. Continued ad hoc adjustments would not be defensible qualification.

**Final diagnostic run:** [GitHub Actions 45253197841](https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45253197841). Additional runs: 45250122753, 45250593298, 45250908866, 45251169269, 45251586809, 45251919795, 45252307623, 45252537728 and 45252902648. All native end-to-end runs remain **failed**, with build/local gates individually passing. No passing end-to-end receipt exists.

## Architecture review — required next action

1. Inspect the exact native `PIN_SOURCE_IDENTITY_MISMATCH` check and source-bound field requirements in the assembled `question_contract_engine.py` / `scoremax_integration_v1.py` **without changing the validator**.
2. Reuse an existing governed Power House approved-content **synthetic or licensed fixture**, and establish its exact question/version/checksum, market/programme/subject/chapter, evidence family, source review, rights and release membership.
3. Exercise the **real native content intake and product activation** in a throwaway database, not direct SQLite inserts. Keep original, staged, accepted and activated receipts distinct.
4. Use ScoreMax's normal assessment-session creation, submission and marking to produce its own immutable pinned answer and result record; do not handcraft pins, candidate scores or fake marks.
5. Only then test owned post-submission *wrong* answer, approved canonical explanation and capsule fallback, proper 403/404 denials, withdrawal and idempotence, and no marks/mastery mutation. Afterwards replay all 85 held Maths scoring scenarios.
6. Independent academic correctness and privacy validation are mandatory before any public child-facing or paid generative-AI release.

### Ownership and isolation

**Chat 3 / Engineering** owns the native source-identity contract and ScoreMax runtime qualification. **Academic** owns approved explanations/marking/source rights. **UX** owns child-friendly presentation after the backend contract qualifies. No change to Pakistan production or Power House, no paid service activation, no deployment to the UK public preview.

**Status:** Baseline reconstruction passed; candidate built and locally tested; full native result flow **HOLD**; independent audit and release **PENDING**.
