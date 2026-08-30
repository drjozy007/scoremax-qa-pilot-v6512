# Power House → ScoreMax Batch 01 (300) — Independent Central Connected Qualification

**Date:** 23 August 2026  
**Batch:** `PH-SM-CONNECTED-BATCH01-300-20260823`  
**Central disposition:** **FAILED — CONNECTED RECTIFICATION REQUIRED**

## Frozen candidates

- Power House: **CHANGE013H reissued**, SHA-256 `52bb08899ab30e9873818e0278be26d1b733059f29de80b433e38da345923b42`
- ScoreMax: **V6.5.6**, SHA-256 `64244e5d64d5df2bbeb262b0554b3c5e0b69b3f31378e8c338c71e5fb378cdb2`
- Power House executed-return outer ZIP SHA-256: `9f28052640ec0a68ee54d4d6389cb8e1a6f6443f52023783514aa29f02e1cbd8`

## Power House execution verification

The supplied executed release is genuine and internally coherent up to the ScoreMax contract boundary.

- SHA256_MANIFEST: **16/16 exact**
- immutable package SHA-256: `3ec6edf763f929ae43c277470254f0a452476ba06781132a8878f658e327b5de`
- package ZIP integrity: **PASS**
- package `manifest.json` SHA-256: `1a004d0e954f7b931240014b661588703d490239d54de682594a9525eac0123d`
- `approved_content.json` SHA-256: `2bbd0016e34cd2a9818203f01cec02f5ca39cf867d1eb1f98879db8bca2cf3b3`
- release questions: **300**
- serialized stimuli: **211**
- Power House DB: **1,600 questions**
- academically cleared / ScoreMax-ready: **1,320**
- held MINOR/MAJOR/R2: **280**
- release membership: **300**
- question versions: **300**
- Power House DB integrity: **ok**
- Power House foreign-key violations: **0**
- Power House publish replay evidence: no second release/outbox/membership
- exact event schema 1.1.0 validation at ScoreMax: **0 schema errors**
- ScoreMax transport authentication/HMAC preflight: **PASS**
- ScoreMax package URL origin: exact trusted `https://powerhouse-batch01.local`
- ScoreMax package pull constructed with bearer authentication and exact package bytes

## Exact ScoreMax V6.5.6 receiving result

The exact frozen event and package were presented to the exact V6.5.6 integration adapter.

**Result:** HTTP/business status **422 / REJECTED**.

ScoreMax correctly failed closed. No release, release membership, projected question, or learner activation was written.

- ScoreMax release rows after rejection: **0**
- ScoreMax release-membership rows: **0**
- ScoreMax quarantine rows: **0**
- ScoreMax DB integrity: **ok**
- ScoreMax foreign-key violations: **0**

### Confirmed finding INT-PHSM-B01-P1-001 — TWO_TIER_DIAGNOSTIC contract serialization mismatch

**Severity: P1**

Exactly **28** reserved questions have authoritative Power House format `TWO_TIER_DIAGNOSTIC`, eight governed option IDs (`T1A..T1D`, `T21..T24`), and a two-part answer such as `Tier 1: D; Tier 2: 4`.

Power House CHANGE013H serializes those records as:

- `content.marking.key_type = TEXT`
- text key such as `Tier 1: D; Tier 2: 4`
- while retaining the eight learner option IDs.

ScoreMax V6.5.6 correctly rejects that representation with `TEXT_OPTIONS_INCOHERENT`, because a `TEXT` marking contract may not simultaneously depend on option IDs.

The defect is in Power House `_build_question_material`: `TWO_TIER_DIAGNOSTIC` is not handled explicitly, so it falls through to the generic TEXT branch even though the question has governed options.

Affected Question IDs (28):

`BIO12-CH13-B01-014`, `BIO12-CH13-B01-108`, `BIO12-CH13-B02-105`, `BIO12-CH13-B03-026`, `BIO12-CH13-B03-066`, `BIO12-CH13-B04-040`, `BIO12-CH13-B04-041`, `BIO12-CH13-B04-042`, `BIO12-CH13-B05-053`, `BIO12-CH13-B05-054`, `BIO12-CH13-B05-055`, `BIO12-CH13-B05-056`, `BIO12-CH13-B06-040`, `BIO12-CH13-B06-041`, `BIO12-CH13-B06-042`, `BIO12-CH13-B01-018`, `BIO12-CH13-B01-123`, `BIO12-CH13-B03-028`, `BIO12-CH13-B04-052`, `BIO12-CH13-B04-053`, `BIO12-CH13-B04-054`, `BIO12-CH13-B05-069`, `BIO12-CH13-B05-070`, `BIO12-CH13-B05-071`, `BIO12-CH13-B05-072`, `BIO12-CH13-B06-052`, `BIO12-CH13-B06-053`, `BIO12-CH13-B06-054`.

### Counterfactual diagnostic — not acceptance evidence

Central control performed an in-memory diagnostic only, without modifying either frozen candidate or declaring a pass.

For the 28 two-tier items only, the two-part governed answer was represented as the two governed option IDs, e.g.:

`Tier 1: D; Tier 2: 4` → `key_type=MULTIPLE_OPTIONS`, `key=["T1D","T24"]`

After recomputing only the diagnostic package/object checksums, the exact ScoreMax V6.5.6 adapter accepted all **300/300** questions with no further content-semantic errors. This isolates the first failure class precisely.

## Confirmed finding INT-PHSM-B01-P0-002 — ScoreMax intake bypasses inactive product staging

**Severity: P0**

The frozen integration architecture requires:

`Power House approved release → immutable package/manifest → ScoreMax authenticated intake → checksum verification → inactive ScoreMax staging → governed product activation`.

ScoreMax V6.5.6 does not preserve this boundary. In `admit_content_envelope`, after writing a release as `STAGED`, it immediately calls `_activate_release(...)` whenever Power House `effective_at` is null or due. The worker/health path also activates due releases automatically.

The real Batch-01 Power House event has `effective_at: null`.

In the isolated counterfactual diagnostic above (where the 28 marking representations were corrected only to expose downstream behaviour), ScoreMax immediately produced:

- accepted release: **1**
- membership: **300**
- projected Power House questions: **300**
- active learner questions: **300**
- release local status: **ACTIVE**

There is no separate ScoreMax-controlled product-activation authorization between academic admission and learner availability. This lets the Power House academic release timing drive learner activation, contrary to the frozen authority/activation model and the explicit Batch-01 instruction to stage inactive pending central verification.

## Non-blocking traceability observation

The exact CHANGE013H runtime event reports `producer_version = 0.11.0+CHANGE013G-3IN1-SCHEMA-CONTRACT-RECTIFICATION-CANDIDATE`. This appears to be the unchanged integration adapter BUILD_ID carried into the H reissue. Central freeze records must use the exact H artifact SHA-256 and should not infer the whole Power House platform version from this field alone. If Power House touches the integration adapter for the P1 fix above, update the producer version at the same time.

## Binary Batch-01 decision

> **POWER HOUSE → SCOREMAX 300-QUESTION CONNECTED RELEASE — FAIL**

Current connected findings:

`confirmed_total=2 · P0=1 · P1=1`

No academic reselection is required. The exact same reserved 300 must be retained.

## Required rectification scope

1. **Power House:** explicitly serialize `TWO_TIER_DIAGNOSTIC` into a ScoreMax-executable option-keyed marking contract while preserving the original question format, question identity, academic snapshot and two-tier answer semantics. Do not reselect questions.
2. **ScoreMax:** separate academic intake/staging from product activation. A valid Power House content event must end in inactive `STAGED` state until an explicit ScoreMax-controlled activation authorization occurs. Power House `effective_at` must not itself be sufficient to make content learner-live.
3. Re-run this **same Batch-01 300** from the same governed source state. Do not start the 1,500 batch.

