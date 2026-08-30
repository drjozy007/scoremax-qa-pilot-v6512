# Integration Control Contract Rectification Decision — PH_SM_APPROVED_CONTENT_V1 schema 1.1.0

**Decision status:** `VERSIONED_PATCH_ISSUED — V1.0 BYTES PRESERVED`

## Decision

Do not edit or replace the frozen schema 1.0.0 bytes. Add schema 1.1.0 under the same business contract name and contract version:

- `contract_name`: `PH_SM_APPROVED_CONTENT_V1`
- `contract_version`: `1`
- original `schema_version`: `1.0.0` — preserved for backward-compatible INLINE messages only
- rectified `schema_version`: `1.1.0` — defines INLINE, MANIFEST_PULL and governed withdrawal semantics

ScoreMax and Power House must support schema negotiation explicitly. No receiver may reinterpret a 1.0.0 message as 1.1.0.

## Why the patch is required

Schema 1.0.0 permits `delivery_mode=MANIFEST_PULL` but unconditionally requires at least one inline question. That contradicts the frozen transport decision that 300/1,500 releases use an immutable manifest and authenticated package pull. Schema 1.0.0 also lacks a contract-valid full-release withdrawal operation, although the acceptance brief requires withdrawal to affect future delivery without changing active sessions or historical evidence.

## Schema 1.1.0 semantics

### PUBLISH_SNAPSHOT + INLINE

- `package_download_url` is `null`.
- At least one question is supplied inline.
- `release_status=ACADEMICALLY_READY`.
- `question_count` and `stimulus_count` must equal the supplied arrays.

### PUBLISH_SNAPSHOT + MANIFEST_PULL

- `package_download_url` must be HTTPS.
- Envelope `questions` and `stimuli` are empty.
- `question_count` and `stimulus_count` describe the immutable pulled package.
- Receiver downloads the archive using service authentication, verifies the archive SHA-256, verifies the exact manifest bytes, verifies every manifest file hash, validates the package manifest and package content schemas, then stages the release inactive before governed activation.

### WITHDRAW_RELEASE

- `delivery_mode=INLINE`, `package_download_url=null`, and both arrays are empty.
- `release_status=WITHDRAWN`.
- `question_count=0`, `stimulus_count=0`.
- `withdrawn_at` and `withdrawal_reason` are mandatory.
- Existing learner sessions and historical attempts retain their pinned snapshots; withdrawal affects future inventory only.

## Effective-time rule

For both publish and withdrawal operations:

- `effective_at=null` means apply immediately after durable, valid admission.
- a future RFC 3339 UTC timestamp means stage until due.
- a past/current RFC 3339 UTC timestamp means apply immediately.

No platform may silently invent a separate activation meaning for `null`.

## Governed eligibility interpretation

The receiver must enforce the exact schema and must not add narrower local requirements that contradict it:

- `source_check_status=CLEAR` and `source_check_status=NOT_REQUIRED` are both eligible.
- `generated_clearance_status` is optional/nullable in schema 1.1.0; its absence must not override Power House `ACADEMICALLY_READY` and question-level governed readiness.
- rights status must be one of the schema-approved commercial/ownership states.
- required Knowledge Node, Claim Family and Reasoning Seed identities must be present exactly as opaque strings.
- dependent, recovery, reconfirmation and shared-stimulus-dependent records must retain zero independent mastery weight.

## Identity and persistence rule

A full release snapshot may reuse unchanged question versions. Therefore ScoreMax must separate:

1. immutable question-version identity, unique by `question_id + question_version_id`; and
2. release membership, unique by `release_id + release_version + question_id + question_version_id`.

A Power House external ID must never update a legacy ScoreMax row merely because its text equals `questions.question_id`. Power House projections require a dedicated namespace/flag and lookup through `ph_question_id`.

## Checksum rule

- Envelope `payload_checksum_sha256`: SHA-256 of canonical UTF-8 JSON payload using sorted keys and compact separators.
- Question checksum: SHA-256 of canonical UTF-8 JSON of the complete question object excluding `question_checksum_sha256` itself.
- Stimulus checksum: SHA-256 of canonical UTF-8 JSON of the complete stimulus object excluding `stimulus_checksum_sha256` itself.
- Manifest checksum: SHA-256 of the exact `manifest.json` bytes.
- Package checksum: SHA-256 of the exact immutable archive bytes.

Receiver must verify all applicable levels before learner activation.

## Compatibility rule

- Continue to accept valid schema 1.0.0 INLINE messages during transition.
- Continue to reject schema 1.0.0 MANIFEST_PULL with the explicit frozen-conflict reason.
- Implement schema 1.1.0 for new Power House exports and all 300/1,500 machine releases.
- Never replace changed schema bytes under the old schema version.
