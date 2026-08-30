# Power House → ScoreMax Assessment Blueprint Contract (V5.5)

## Ownership

Power House is authoritative. ScoreMax stores a consumed immutable snapshot and never edits authoritative values in place.

## Transport

V5.5 supports administrative JSON transport. A secure API can later carry the same logical contract.

## Required top-level concepts

- `schema_version`
- `blueprint_id`
- `framework.id` / `framework.name`
- `framework_version.id` / `framework_version.name`
- `blueprint_version`
- `status` eligible for use (`APPROVED` / `APPROVED_ACTIVE`)
- `authority`
- `total_questions`
- `sections[]`
- approval metadata
- `checksum`

## Section requirements

Each section contains:

- stable subject name;
- positive integer `question_count`;
- `weight_percent`;
- optional order/duration/difficulty composition.

Counts must equal the total. Weights must equal 100% within a small rounding tolerance. Duplicate subjects are rejected.

## Integrity

`checksum` is calculated over the canonical payload excluding transport integrity fields. In production, `signature` is required and is an HMAC over the same canonical payload using `SCOREMAX_POWERHOUSE_SHARED_SECRET`.

Same Blueprint ID + version + same checksum is idempotent. Same identity with changed checksum is rejected and logged. Power House must issue a new version.

## Lifecycle

Power House source status and ScoreMax local status are separate.

Typical local flow:

`IMPORTED / VALIDATED → ACTIVE → SUPERSEDED → ARCHIVED`

Invalid payloads become `REJECTED`/`SYNC_ERROR` and cannot be activated.

## Immutability

Every active snapshot retains:

- original canonical payload;
- calculated checksum;
- source approver/time/policy;
- ScoreMax importer/time;
- validation report;
- activation/supersession audit.

Correction requires a new Power House version or explicitly governed emergency activation of an older version. Existing mocks/results remain pinned.

## Blueprint versus assembly policy

The contract carries official structure. ScoreMax’s separate assembly policy may govern future selection rigor, but cannot change counts/weights in the imported blueprint.

## Example

See `sample_powerhouse_mdcat_2026_blueprint.json`. Its source reference is intentionally a placeholder requiring real Power House evidence before production use.
