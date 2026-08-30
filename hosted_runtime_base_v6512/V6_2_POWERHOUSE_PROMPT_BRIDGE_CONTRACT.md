# Power House → ScoreMax Prompt Bridge Contract

## Purpose

Allow the owner to use an approved Power House prompt with an existing ChatGPT, Claude or other AI subscription, then return candidate output for Power House validation.

## Authority

A ScoreMax import does not make a prompt or output academically approved. Power House remains authoritative.

## Prompt-pack minimum fields

```json
{
  "schema_version": "1.0",
  "prompt_pack_id": "PH-PP-...",
  "prompt_pack_version": "1",
  "status": "APPROVED_FOR_MANUAL_GENERATION",
  "framework": "FSc",
  "framework_version": "2026",
  "subject": "Biology",
  "chapter": "...",
  "learning_outcome_ids": ["..."],
  "source_evidence_ids": ["..."],
  "prompt_text": "...",
  "expected_output_schema": {},
  "checksum": "sha256"
}
```

## ScoreMax workflow

1. Validate status and checksum.
2. Verify checksum and, in production, the Power House HMAC signature.
3. Store immutable prompt snapshot.
4. Display complete provider-neutral prompt for copying.
5. Record provider/model where known.
6. Store raw candidate output separately.
7. Validate only structural linkage and JSON shape.
8. Export a `MANUAL_AI_GENERATION_RETURN` wrapper to Power House.
9. Power House performs deterministic validation, independent review, academic approval and later ScoreMax export.

## Prohibited behaviour

- ScoreMax cannot silently alter the prompt.
- Candidate output cannot enter the live question bank directly.
- Provider output cannot self-declare academic approval.
- Missing evidence IDs must not be invented by ScoreMax.

## Production signature

Production requires `SCOREMAX_POWERHOUSE_PROMPT_SECRET` and a valid HMAC-SHA256 `signature`. Local testing can use checksum-only prompt packs unless `SCOREMAX_REQUIRE_SIGNED_PROMPT_PACKS=1`.
