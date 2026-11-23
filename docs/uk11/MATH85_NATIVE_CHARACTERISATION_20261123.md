# UK 11+ Maths — 85-case exact-native scoring characterisation

**Date:** 23 November 2026  
**Release disposition:** **HOLD — not academically or student-release qualified**.

## Source and method

- Source: `ScoreMax_11Plus_Maths_20Q_Native_Scoring_and_WCA_PreAdmission_v0_4.xlsx`, tab `SCORING_FIXTURES`, exactly **85** distinct case IDs: **55 BASE_V0_3 + 30 ADVERSARIAL_V0_4**. Original provisional expected marks and policy-blank cases are retained unchanged.
- Immutable text extraction saved in `qualification/uk11/fixtures/math20_v04_scoring_cases.csv` for traceability. The source workbook remains the authoritative offline register; extraction is not a new approval.
- Successful CI: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45263917072
- Qualification CI commit: `ad20723f5162fa5aa48085bcc02d4364a3d45147`.
- Actual assembled ScoreMax verified pre-overlay by materializer's existing tree checksum; UK-only overlays installed in disposable Docker under `--network none`; no live data, real learner accounts or paid AI.
- Calls **the actual assembled native `mark_question_response`** for supported direct-response cases. The question/answer configurations are **provisional software representations** derived from the held workbook, not original signed Power House question contracts. Boolean Yes/No display aliases are explicitly labelled provisional.
- Full source-signed synthetic PH intake, activation, native wrong-answer marking, post-answer explanation, retry and withdrawal also independently passed in this run. That 1-question synthetic path does not academically clear the 85 cases.

## Evidence-backed population

| Status | Cases | Interpretation |
| --- | ---: | --- |
| NATIVE_REFERENCE_MATCH | **41** | Native direct scoring agrees with provisional expected mark under the documented synthetic response configuration; **not academic clearance** |
| NATIVE_REFERENCE_MISMATCH | **11** | Native direct scoring differs from the provisional expectation; investigate UK input rules and response UI, do not rewrite official marks |
| UNSUPPORTED_SOURCE_FORMAT | **24** | Determinate two-part constructed-answer cases (Q011/Q014) were **not** passed into a single-response scorer |
| POLICY_HOLD | **9** | Workbook has no approved expected mark; remains unresolved rather than assumed correct/incorrect |
| INPUT_DATA_ERROR / NATIVE_EXCEPTION | **0** | No test-register decode failures or scorer exceptions in final run |
| **Total** | **85** | **52 actually compared**; **33 held outside direct scorer execution** |

## Per-question status

| Question | Match | Mismatch | Unsupported | Policy hold |
| --- | ---: | ---: | ---: | ---: |
| Q004 fractional sharing | 11 | **8** | 0 | 2 |
| Q008 Village A/B comparison | 7 | **1** | 0 | 1 |
| Q011 mass of counters, two parts | 0 | 0 | **12** | 2 |
| Q014 fencing and cost, two parts | 0 | 0 | **12** | 3 |
| Q016 distributive law yes/no | 9 | 0 | 0 | 1 |
| Q018 bar chart/Art club label | 7 | **1** | 0 | 0 |
| Q020 fraction strip/label | 7 | **1** | 0 | 0 |

The nine Boolean comparison matches depend on a **provisional native-valid single correct ID** and a test-only `false -> No`, `true -> Yes` response mapping. This is not a qualified student UI contract.

## Mechanisms to resolve

1. **Q004, eight provisional mismatches:** native numeric entry calls `float(response)`, so correct value strings expressed as `13/4`, `3 1/4`, Unicode fraction, or typed with a **correct** flatbread unit are not accepted by the direct numeric scorer. A correct-number/wrong-dimension string is rejected in these cases, but this alone does **not** prove all unit-handling safety or a qualified fraction-entry policy. Separate exact input widget contracts, acceptable notation, units and normalization policy are necessary. Do not silently permit inappropriate units.
2. **Q008, Q018, Q020, one provisional mismatch each:** `Village B.`, `The art club`, and `Strip A.` require bounded, academically approved alias/punctuation handling or controls that do not emit these strings. Current text scorer uses direct accepted string membership after trim/casefold.
3. **Q011/Q014, 24 determinate unsupported cases:** native single-answer `mark_question_response` is **not** a substitute for two-part scoring. Must inspect exact native multipart/written scorer and the source-part rubric before any execution or part-credit statement. Wrong units in either part must not gain a mark.
4. **Nine policy holds:** follow-through/ECF, answer prose, decimal locale, Boolean free-text, alternative representations and unit conversions remain governed decisions. Never infer policy from an offline scorer's observed mark.
5. **Renderer/assets:** diagram-related questions (e.g. Q018/Q020) still need the original assets and full assembled learner input UI verified before graduating any response-alias result beyond direct-scorer characterisation.

## Risk, ownership, and next actions

**P0: no full production or student release.** The 20Q Maths bank remains held; the workbook flags BANK_APPROVED=NO, STUDENT_RELEASED=NO and VALID_FOR_REAL_MASTERY=NO. Independent Whole-Bank Audit/Gold, rights, mappings and release controls are not supplied by this test.

**Engineering:** Produce a **per-response-type UK marking capability contract** based on the exact native renderer/scorer; extend existing bounded normalization/unit policies only after Academic approval. Build source-valid 2-part rubrics through existing native constructed-response engines, never parallel ad-hoc marking. Replay 85 cases with exact signed question/format/marking bytes, asserting receipt, search/allocation, UI response, marks and mastery exclusion. Add cross-exam membership/route checks and scale/replay receipts.

**Academic / Power House:** Explicitly settle nine policy holds; approve allowed numeric/fraction/unit forms, written labels/aliases, multipart marks/follow-through, and diagram asset rights. No test fixture confers source approval.

**Product:** Ensure input controls enforce the approved response contract; show helpful mistake explanations only after native submission, without modifying marking or mastery.

**Transport anti-repeat gate:** **Question production may not scale beyond governed pilot until a fully heterogeneous production-style sample passes PH→SM schema/version/identity checks, signed transfer, staging, authorised activation, school routing, native rendering/marking, idempotency, withdrawal and rollback.** A `202 ACCEPTED` receipt is not proof of learner usability. Use bounded indexed queries and measurable 300-/1,500-question bulk replay before broad launch.

**Status:** Native direct scorer **characterised**, NOT **qualified** for the held 85 cases. Real bank, paid AI and all live production untouched.
