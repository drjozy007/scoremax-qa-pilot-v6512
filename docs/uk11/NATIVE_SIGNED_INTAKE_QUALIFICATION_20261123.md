# ScoreMax UK 11+ — Native signed-intake explanation qualification

**Date:** 23 November 2026  
**Status:** PASSED — isolated synthetic software journey only; **not an academic or student-release approval**.

## Decision

Retain the UK-only `Explain My Mistake` code behind its default-OFF switch. Its first complete native ScoreMax lifecycle is now runtime-qualified **for one synthetic text-only MCQ with an approved-style explanation**. This does not qualify the broader UK 11+ content inventory, any real admissions mapping, all response types, AI-generated explanations, or child-facing production release.

## Reproducible evidence

- **Successful GitHub Actions run:** https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45261347529
- **Qualification commit:** `c62ce75e92635c8f18e8ced4ed7e45c214225e00`
- **Pre-overlay source build:** the Render-equivalent command `python -B scripts/materialize_scoremax_sqlite_nav_candidate_20261116.py`; verified baseline tree SHA-256 `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`.
- **CI local regression:** 51/51 PASSED.
- **Disposable native startup:** 314 registered Flask routes; the UK explanation route and relevant templates compiled.
- **Native payload:** reuses the repository's `integration_examples/PH_SM_APPROVED_CONTENT_V1.example.json` structure, with expressly synthetic UK Maths facts, original arithmetic question, synthetic source/academic approvals, new canonical question and envelope checksums. It carries **no authority for a real UK question**.
- **Native ingress:** signed HMAC bearer request to the existing Power House content-release route returned `202 ACCEPTED`; identical delivery replay returned `200`; item remained staged and absent from learner questions before separate ScoreMax-owned activation.
- **Activation:** ScoreMax's existing authorisation function returned `ACTIVE`; materialised question identity/version/checksum and activation scope were checked.
- **Assessment:** native assessment-session builder generated immutable UK question and release pins; normal `/test/session/<id>/submit` marked a synthetic wrong response with 0 marks.
- **Help:** `/uk11/result/<attempt>/question/<question>/explain` returned **200** with the canonical question's approved-style worked explanation. The check asserted no additional marking/AI usage records from explanation.
- **Replay:** repeated assessment submission returned **302** and persisted exactly one attempt.
- **Withdrawal:** after the isolated release was marked withdrawn, explanation endpoint returned **404**, avoiding further source-bound help disclosure.
- **Provider calls:** 0; paid AI disabled and budget 0. No persistent or production database was used. Temporary Docker runtime isolated with `--network none` and disposable `/data` tmpfs.
- **Throttle:** CI maintained the native limit of 2 student requests/second; paced synthetic retry/withdrawal requests rather than bypassing rate limiting.

## Previous failure explained

The older attempt hand-built question/release pins and failed native `PIN_SOURCE_IDENTITY_MISMATCH`. The correct native protocol now generates immutable, checksum-matching identities from the signed intake and makes session pins via ScoreMax's own assessment builder. No source checksum or validation fence was weakened.

The subsequent 429 responses during rapid CI replay were application throttling, not a marking or explanation defect. Spacing the two synthetic requests preserved the native protection and yielded successful native retry/withdrawal assertions.

## Remaining gates — PENDING

1. Replay all **85 held Maths scoring scenarios** against the exact assembled native scorer, including units, Unicode, equivalent numeric forms, rounding, mixed response types, and wrong-unit negatives; compare to independently approved expected results. Do not infer deployed bugs from earlier offline reference-scorer mismatches.
2. Test child-facing content and complex passages/diagrams, multiple schools and test/cycle routing, altered/withdrawn release pins, cross-learner attempts, and non-UK denials with actual source-derived fixtures.
3. Require academic clearance and rights/provenance review for real question solutions and misconception explanations, plus independent Whole-Bank Audit and Gold Recovery where applicable.
4. Qualify any real AI provider with safeguarding, privacy, age-appropriateness, hallucination/incorrect-explanation tests, controlled budgets, caching and deliberate feature activation. AI remains prohibited from changing official marking/mastery.
5. Separate isolated runtime-qualification evidence from independently audited, deployed, live-verified and accepted/frozen stages. Protect Pakistan production and UK demo until all release gates pass.

**Owner:** Chat 3 Engineering. Academic controls remain with Power House; Product/UX controls remain with the UK design workstream. **Student release: HOLD.**
