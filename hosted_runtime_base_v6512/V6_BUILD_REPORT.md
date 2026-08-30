# ScoreMax V6.0 Build Report

## Release identity

**Name:** Written Response Intelligence  
**Baseline:** ScoreMax V5.5 Final  
**Pilot scope:** FSc Biology Part I, chapter-by-chapter  
**Status:** Core typed workflow and governed architecture implemented and deterministic smoke-tested. Browser acceptance, provider integration and academic validation remain required.

## System boundary

Power House owns academic content and standards. ScoreMax imports an immutable approved package and separately stores student submissions, OCR/transcription evidence, marking runs, feedback, recovery, reconfirmation and mastery evidence.

ScoreMax does not independently author or silently alter official questions, mark schemes, approved scaffolds or academic standards.

## Implemented

### Package governance

- immutable package payload snapshot;
- checksum verification;
- optional HMAC signature verification, required by production configuration;
- package/version conflict protection;
- imported and active states;
- exact package, question, rubric and policy pinning.

### Typed written-answer journey

- Practice and Mock modes;
- original independent response;
- point-level marking output;
- contradiction, misconception and command-verb analysis;
- independent local grader A/B records and reconciliation;
- confirmed/provisional/more-evidence states;
- feedback-led improvement as a new version;
- unseen reconfirmation linked to the original attempt;
- recovery tasks and Study Plan action creation;
- structured evidence for the existing Mastery Engine.

### Handwriting architecture

- private original page storage;
- multiple-page sequence and file hashing;
- image dimension/brightness/contrast/edge quality evidence;
- retryable processing jobs;
- transcript confirmation and correction audit;
- production fence requiring secure object-storage configuration;
- explicit local OCR simulation for workflow testing only.

### Approved Student Exemplar Library

- eligibility limited to perfect, confirmed, independent submissions;
- separate academic review and student opt-in consent;
- consent and approval can occur in either order without premature publication;
- anonymised by default, with controlled first-name attribution option;
- hidden pre-release exemplar state;
- LIVE release and withdrawal controls that preserve evidence;
- exact package/rubric/policy/approver/consent linkage;
- first-attempt versus improved-answer distinction.

## Tests actually executed

### V6 suite

`python smoke_tests_v6.py`

**34 checks passed.**

### Full V5.5 regression suite on V6 baseline

`python smoke_tests_v5_5.py`

**52 checks passed.**

The V6 build therefore passed 34 dedicated written-response checks while preserving all 52 V5.5 blueprint, mock, calibration, access and historical-integrity checks.

## Honest limitations

- No real browser acceptance pass was executed in the build container.
- No production OCR or external AI grader was invoked.
- The local marker is deliberately deterministic and inspectable for workflow testing; it must not be represented as validated high-stakes marking.
- Academic gold-set validation, privacy review, minor/guardian consent review and provider contracts are required before controlled live use.
- The exemplar library is built but HIDDEN by default.
