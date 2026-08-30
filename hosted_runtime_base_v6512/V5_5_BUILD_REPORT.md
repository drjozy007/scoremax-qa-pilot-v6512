# ScoreMax V5.5 — Build & Verification Report

**Release:** Assessment Blueprint Integration  
**Baseline:** ScoreMax V5.4.2 Final Pre-Pilot Application Hardening  
**Build date:** 29 July 2026  
**Status:** Implemented and packaged; browser acceptance and production infrastructure remain outstanding.

## 1. Purpose

V5.5 prevents exam structure from becoming duplicated manual data across mocks, projections, dashboards and Study Plans. It implements one versioned blueprint authority:

> Power House creates and approves the blueprint. ScoreMax imports and applies an immutable snapshot.

It also includes the agreed foundation of the Assessment Standards & Calibration Engine, kept separate from the official blueprint.

## 2. Implemented architecture

### 2.1 Authoritative blueprint layer

New governed entities include:

- assessment frameworks;
- framework versions;
- immutable assessment blueprint snapshots;
- blueprint subject/section rows;
- validation/synchronisation events;
- blueprint governance audit;
- content requirement requests.

Blueprint records retain Power House identity, framework/version identity, source status, local status, authority, source/governance notes, effective dates, approval metadata, checksum, signature status, validation report and immutable payload.

### 2.2 Import and validation

The JSON importer:

- accepts an administrative transport file rather than manual recreation;
- calculates and verifies the immutable checksum;
- verifies an HMAC signature when configured and requires signature verification in production;
- rejects duplicate subject rows;
- validates positive integer counts;
- validates subject counts against the blueprint total;
- validates percentages to 100% within rounding tolerance;
- validates eligible Power House status;
- detects same ID/version arriving with changed content;
- keeps identical re-imports idempotent;
- stores a complete validation report.

Only authorised admins can import, activate, supersede, archive or export blueprints.

### 2.3 Version and historical integrity

V5.5 pins blueprint identity and immutable composition to:

- exam papers;
- assessment sessions;
- attempts/results;
- Study Plans;
- student blueprint projections.

Activating a new blueprint affects future work only. Historical papers/results retain their original snapshot. Pre-V5.5 exam papers are marked `LEGACY_UNPINNED` unless a defensible historical snapshot exists.

### 2.4 Authentic mock assembly

Authentic full mocks:

- follow the active blueprint exactly;
- require the exact subject counts;
- use governed live questions and approved families;
- require ScoreMax-ready and defensible rights/provenance status;
- apply intended difficulty mix where metadata permits;
- prioritise family diversity, calibrated items and reduced prior exposure;
- produce subject-by-subject preflight evidence;
- block rather than silently substitute when any subject inventory is insufficient.

The sample MDCAT integration test assembled exactly 81/45/36/9/9 = 180.

### 2.5 Test-purpose separation

V5.5 keeps distinct:

- authentic full mock;
- proportional blueprint practice;
- diagnostic practice;
- adaptive practice;
- subject tests;
- chapter/topic tests;
- formal mastery assessments.

Non-authentic practice may transparently rebalance a shortage across blueprint subjects, but it records both official and adjusted allocation and is never presented as an authentic official mock.

### 2.6 Blueprint-aware Study Plan

Study priority blends:

- official subject weight;
- verified accuracy/weakness;
- unrecovered learning needs;
- syllabus coverage gap;
- exam urgency.

This prevents a crude “45% weight means nine times more study than 5%” rule. A critically weak low-weight subject can outrank a stable high-weight subject. The priority snapshot and explanatory reason are stored.

### 2.7 Blueprint-aware projections and dashboards

Subject projections show official question allocation, projected correct range, evidence confidence, coverage and mastery state. The aggregate uses the exact active blueprint. Projection snapshots retain blueprint version, and current projections can report change from the previous saved projection.

Student, parent and teacher surfaces receive blueprint-aware information without exposing Power House internal governance fields.

### 2.8 Bank sufficiency and Power House requests

For each subject, ScoreMax evaluates:

- required questions per authentic mock;
- governed usable item count;
- family count;
- safe parallel-form depth;
- difficulty coverage;
- shortage/surplus.

Admins can generate structured Content Requirement Request JSON for Power House. ScoreMax does not generate or approve Power House content through this path.

## 3. Assessment Standards & Calibration foundation

### 3.1 Separate versioned policy

The assembly/rigor policy is separate from the official blueprint. It supports global, framework-version, blueprint, programme, subject, chapter and assessment-type scope.

A policy stores:

- rigor score (0–100);
- mastery standard score (0–100);
- selection configuration;
- evidence configuration;
- reason;
- preview;
- status/version/approval/audit.

### 3.2 What the controls change

For future assessments only, policy can influence:

- intended Easy/Moderate/Difficult mix;
- calibrated-item preference;
- cognitive-demand bias metadata;
- question volume;
- mastery cut score;
- minimum independent forms;
- target-level item ratio;
- unseen-family ratio;
- verification interval.

It does not relabel questions, rewrite the official blueprint or recalculate historical results.

### 3.3 Historical preview

Policy drafts include a conservative historical form simulation:

- current observed form pass rate;
- estimated pass rate under proposed thresholds;
- observed form count;
- evidence-confidence warning.

It explicitly does **not** claim external percentile prediction. External exam-outcome calibration remains a later evidence phase.

### 3.4 Existing mastery under tightened policy

A materially stricter activated policy moves affected currently verified mastery to `Verification Due`. It does not automatically downgrade earned mastery. Fresh evidence then governs retention/downgrade under the existing reconfirmation architecture.

## 4. Question-bank integration changes

V5.5 import requires and preserves separate:

- mastery Level;
- Difficulty;
- Difficulty Source;
- Family ID;
- Family Construct;
- Family Invariants;
- Rights Status;
- ScoreMax Ready;
- Assessment Purpose.

Spreadsheet Status/Review Status remain non-authoritative: all imported questions/families enter Draft + inactive.

## 5. Migration verification

A controlled V5.4.2 sentinel dry-run preserved:

- 3 users;
- 95 questions;
- 1 attempt;
- 1 mastery record;
- 1 classroom and membership;
- 1 legacy exam paper.

SQLite `PRAGMA integrity_check` returned `ok`. The old exam paper became `LEGACY_UNPINNED` rather than being falsely linked to the new MDCAT sample blueprint.

## 6. Executed automated checks

`smoke_tests_v5_5.py` completed **49 checks**, including:

- fresh schema and idempotent migration;
- V5.4.2 demo bank preservation;
- valid/invalid blueprint validation cases;
- checksum/signature verification;
- duplicate/tampered version handling;
- activation/supersession;
- exact 180-question authentic mock assembly;
- missing-English blocking;
- Access-ceiling enforcement;
- paper/session/result pinning;
- learner-need-over-weight Study Plan case;
- projection aggregation/confidence;
- bank sufficiency/content need;
- question/family Draft publication isolation;
- difficulty independent from mastery level;
- historical paper/result integrity after version change;
- policy scope/version/audit;
- Verification Due on material tightening;
- rigor-aware mastery form pinning/breadth;
- proportional and diagnostic practice;
- ordinary practice policy/blueprint pinning;
- 64 Jinja templates parsing;
- 113 routes with no duplicate paths;
- literal template route-reference resolution;
- explicit POST-form CSRF coverage.

## 7. Implemented but awaiting browser acceptance

- all new Admin blueprint pages and forms;
- JSON upload/download UX;
- exact mock publication/start/result flow in a real Flask browser;
- student/parent/teacher visual layouts;
- slider behaviour and readable simulation display;
- timed assessment behaviour under full browser runtime;
- SMTP and production environment behaviour.

## 8. Explicitly deferred

- live Power House two-way API;
- PostgreSQL conversion;
- production hosting;
- advanced exposure control;
- IRT, DIF and Angoff standard setting;
- automatic external percentile calibration;
- automatic content generation/publishing;
- large-scale queues/background workers;
- major unrelated UX or architecture refactor.

## 9. Honest limitation

Flask/Werkzeug were unavailable in the build container. The business/schema layer was executed against real SQLite databases using a lightweight compatibility stub. No claim is made that a real browser test was executed. The manual checklist must be completed before pilot acceptance.
