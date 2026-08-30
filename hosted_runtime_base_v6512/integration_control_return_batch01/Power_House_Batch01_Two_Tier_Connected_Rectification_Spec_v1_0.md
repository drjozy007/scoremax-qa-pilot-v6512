# Power House — Batch 01 Connected Rectification Spec

## Scope

Fix only the confirmed connected defect `INT-PHSM-B01-P1-001`. Do not reselect the 300 questions, alter academic decisions, alter reviewed learner-facing text, or redesign Power House.

## Required behaviour

For authoritative Power House `question_format = TWO_TIER_DIAGNOSTIC`:

- preserve `content.exam_question_type = TWO_TIER_DIAGNOSTIC`;
- preserve all governed tier option IDs/text;
- parse the already-governed answer `Tier 1: <A-D>; Tier 2: <1-4>` without changing its academic meaning;
- serialize the executable ScoreMax marking contract as `key_type = MULTIPLE_OPTIONS` with exactly two option IDs, e.g. `Tier 1: D; Tier 2: 4` → `["T1D","T24"]`;
- `accepted_answers` must not be used as a substitute for option-key marking;
- the two selected key IDs must exist in the option set;
- recompute immutable question versions/checksums and package/manifest/event checksums through the normal compiler;
- preserve the same 300 public Question IDs and release scope;
- update `producer_version` to the actual connected-rectification runtime identity if the integration adapter code changes.

## Permanent regression gate

Add tests covering all 16 Tier1×Tier2 key combinations, malformed two-tier answers, missing tier options, duplicate tier keys, and the actual Batch-01 pattern with eight option IDs.

The exact returned Batch-01 package must contain 300 members and must pass the unchanged ScoreMax V6.5.6 semantic content compiler except for the separate ScoreMax activation-gate finding owned by ScoreMax.

Do not start the 1,500 batch.
