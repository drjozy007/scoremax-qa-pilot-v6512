# Power House → ScoreMax Written Assessment Package Contract

## Authority

Power House is authoritative for curriculum mapping, questions, question families/variants, mark schemes, propositions, causal links, acceptable alternatives/paraphrases, contradictions, misconceptions, command verbs, model answers, scaffolds, unseen reconfirmation assets, source evidence, approval and versioning.

ScoreMax stores the approved payload immutably and stores student evidence separately.

## Required package concepts

The validator expects package identity and governance fields, including:

- `schema_version`
- `assessment_package_id`
- `assessment_package_version`
- `framework_id`
- `framework_version_id`
- `blueprint_snapshot_id`
- `subject_id`
- `chapter_id`
- `academic_approval_status`
- `approved_at`
- `approved_by`
- `rubric_version`
- `marking_policy_version`
- `questions`
- `export_checksum`

Each question carries its identity, family/variant, type, text, command verb, maximum marks, difficulty, cognitive demand, mastery level, purpose, required mark points, accepted evidence, contradictions/misconceptions and relevant recovery/scaffold/unseen links.

## Integrity

`export_checksum` is the SHA-256 digest of the canonical payload excluding transport signature fields.

Production can require:

- `signature_algorithm: HMAC-SHA256`
- `signature_key_id`
- `signature`

The HMAC covers the canonical package identity/checksum contract. Secrets are configured in ScoreMax and are never embedded in the export.

## Version rules

- The same package ID/version with the same checksum is idempotent.
- The same package ID/version with a different checksum is rejected.
- Corrections arrive as a new Power House version.
- Student attempts remain linked to the exact imported package and policy versions.
- ScoreMax does not edit approved academic fields.

## Separation of policies

Pin separately where applicable:

- blueprint version;
- assessment package version;
- rubric version;
- marking policy version;
- mastery policy version;
- rigor/assembly policy version;
- OCR provider/model version;
- grader A/B model/prompt versions;
- factual-integrity rules version;
- reconciliation policy version;
- feedback policy version.
