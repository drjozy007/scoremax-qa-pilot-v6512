# ScoreMax UK 11+ Maths B01 — 40Q native response characterisation

**Date:** 24 November 2026  
**Classification:** AUTHORING CANDIDATE / HOLD — not approved academic content, not a bank release.

## Exact upload and identity

The user-uploaded `ScoreMax_UK11_Maths_B01_40Q_ORIGINAL_GOVERNED_CANDIDATE_HOLD_v0_1(2).xlsx` was compared byte-for-byte with the Project Library copy `ScoreMax_UK11_Maths_B01_40Q_ORIGINAL_GOVERNED_CANDIDATE_HOLD_v0_1.xlsx`. Both SHA-256: `6221c6085ff0bd4368754759c109d017344a734aef13201d9531ead0ff8d52b8`.

The workbook contains **40 original draft questions**: 16 single-select, 10 numeric, 12 unit-bearing, 2 fractions. It specifies **244 proposed native response cases**: 59 expected correct, 178 expected incorrect, 6 author policy holds, 1 explicit scoring block. Academic route statuses are 35 index-READY (not frozen or verified for actual exam), 1 SUPPORT, and 4 HOLD_SOURCE_RECORD. The source workbook remains unchanged.

## Native test executed

- GitHub Actions PASS: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45338854086
- Branch: `qualification/uk11-native-integration-20261123`
- Verified exact assembled ScoreMax via the accepted Render materializer and its expected tree checksum before applying disposable UK-only test overlays.
- Normal ScoreMax direct marker `mark_question_response` used for 16 single-select / 10 numeric items, and exercised under **provisional numerical fallback** for the 12 unit and 2 fraction families, without classifying those fallback outcomes as production acceptance.
- The separate synthetic signed Power House intake → staging → activation → native wrong-answer marking → explanation → retry → withdrawal regression passed again in the same CI job.
- No real source approval, Power House bank ingestion, school/provider/cycle membership, production DB, learner mastery or paid AI provider call.

## Case-level result aggregation

| Outcome | Cases | Decision |
| --- | ---: | --- |
| NATIVE_MC_MATCH | **96** | Expected marks matched for all 16 MCQ items under provisional four-option native contracts; UI/render and academic approval still pending |
| NATIVE_NUMERIC_MATCH | **39** | Direct native numeric matched provisional expected marks |
| NATIVE_NUMERIC_MISMATCH | **2** | **UKM-B01-004-CORRECT_EXACT** `8,365` and **UKM-B01-006-CORRECT_EXACT** `2,450` incorrectly returned zero in direct decimal parsing against numeric targets 8365 and 2450; native format / UI policy needs an approved thousands-separator rule |
| UNIT_CONTRACT_HOLD | **88** | Unit-bearing answer test responses were probed using plain number fallback; no unit-aware production contract proven |
| FRACTION_CONTRACT_HOLD | **12** | Direct decimal fallback does not establish an approved fractional input and equivalence policy |
| POLICY_HOLD | **6** | Source expectations explicitly unresolved |
| BLOCK_SCORING | **1** | Source explicitly prohibits a score pending resolution |
| **Total** | **244** | **No question released or counted towards mastery** |

**Important:** a separate fail-unsafe mapping probe showed that **all 12 unit-value questions would award 1 mark to a bare matching number if incorrectly represented as plain numerical entry**, despite a required unit in the author's contract. This is an integration P0 **risk** if that mapping is chosen; it is **not** evidence the existing ScoreMax unit-aware or written scorer awarded wrong marks on a real published question. Do not normalize or discard units to make tests pass. Currency and square-unit strings require explicit representation rules.

The two numeric mismatches occur in questions UKM-B01-004 and UKM-B01-006. They are not wrong mathematical keys: ScoreMax's direct numeric parser uses `float(response)`, which rejects comma-grouped `8,365` and `2,450` strings as submitted. Resolve whether the learner UI strips approved grouping separators or the existing native bounded normalization accepts them; preserve the authored expected mark pending academic approval.

## Actionable response-contract map

| B01 author format | Count | Existing native path | Required safe gate |
| --- | ---: | --- | --- |
| single_select | 16 | Existing single-choice radio/option scoring | Pin option IDs and correct key; test real renderer and version/cycle routing |
| numeric | 10 | Existing numerical scorer | Approve numeric input grammar: thousands commas, decimal notation, sign, rounding, tolerance and permitted units |
| unit_value | 12 | No approved unit-aware B01 contract demonstrated | Require value **and correct dimension/currency**, reject wrong/missing units where asked; verify actual native renderer and scorer |
| fraction | 2 | No approved B01 fraction contract demonstrated | Approve slash, Unicode fraction, mixed/improper equivalence, precision and layout constraints; test native delivery |
| Source held items | 4 | Not eligible for release | Bind exact source opportunities and rights independently |
| Author policy holds | 6 + 1 block | Not scorable | Academic Power House decision required before marking or mastery |

## P0 engineering prevention, not batch-by-batch patches

1. **Before scaling content**, freeze a machine-validated PH->SM response-format profile per archetype containing format ID, learner widget, response grammar, answer-normalization bounds, unit dimension/value, accepted-equivalence rules, mark demand, marking engine version, and source/academic authority. Do not invent IDs/approvals.
2. Extend **the existing native scorer and renderer** once through contract-aware format profiles, rather than writing a second ad-hoc UK Maths scorer.
3. Run all 244 fixtures again using the **exact signed approved content bytes and assembled ScoreMax UI/marking path** after Academic finalizes rules, including wrong-unit and wrong-currency negative tests.
4. Treat this as a **candidate-only trial**. Four source-opportunity holds, independent WCA/Gold, production handoff, 300-/1,500-question scale and official school/provider/cycle memberships remain open.
5. Put the same contract gate before each later batch to avoid reproducing FSc/MDCAT handoff delays. A transport ACCEPTED receipt is not proof of a usable or safely marked question.

**Status:** CI direct-scoring characterisation PASSED; **academic and student release HOLD**.
