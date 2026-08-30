# ScoreMax V6.5.11 — Power House Synthetic Learner Qualification Pilot

Narrow child of the exact frozen **ScoreMax V6.5.10** candidate.

Parent ZIP SHA-256:
`b028f7b7250a06310f92c25e3b562eb05d2c7998c8668d81fb08e1bbfadc5142`

Parent ZIP members: **551**.

## Decision

Add the smallest governed qualification capability needed for the first Power House→ScoreMax synthetic-learner pilot:

- one deterministic QA learner identity;
- one visual/semantic QA learner identity;
- normal ScoreMax authentication;
- hard isolation from real learner attempts/mastery/evidence/analytics/Growth events;
- reuse of the existing Mastery Laboratory `QA_SANDBOX_ONLY` question store;
- reuse of the production learner question renderer and live marking function;
- question selection pinned to opaque external Question ID **and external version**.

This is a **locally contract-tested candidate**, not a production-accepted release.

## Identities

Provisioned only when explicitly requested:

- deterministic: `PH_QA_DETERMINISTIC_001` / role `qa_student`;
- visual/semantic: `PH_QA_VISUAL_001` / role `qa_student`.

The provisioning script refuses to run unless:

`SCOREMAX_QA_SYNTHETIC_PROVISION_CONFIRM=YES`

It should always be pointed at a disposable/pilot database through `SCOREMAX_DB` during qualification.

A guarded runtime fixture stager is also supplied for the one-question pilot. It calls the **existing** `mastery_lab_engine.import_candidate_batch()`; it does not create a second ingestion path. It requires `SCOREMAX_QA_SYNTHETIC_STAGE_CONFIRM=YES` and an explicit `SCOREMAX_DB`.

## Isolation

`qa_student` is a dedicated non-real-learner role. A request fence permits only the synthetic-QA routes, logout and static assets. Login for this role does not emit a Growth login event.

Synthetic attempts are stored only in Mastery Laboratory QA evidence tables. They do not write to the live learner attempt/mastery paths.

Required question partition remains:

- `content_environment = QA_SANDBOX_ONLY`
- `student_release_status = NOT_STUDENT_RELEASED`
- `bank_approval_status = NOT_BANK_APPROVED`
- `mastery_validity = NOT_VALID_FOR_REAL_MASTERY`

## Deterministic learner

The deterministic learner submits a governed response through the real rendered answer control. ScoreMax evaluates that response with its live marker and the existing Mastery Laboratory scorer. The QA result passes only when the two scorers agree and the observed correctness matches the expected mode (`CORRECT` or `INCORRECT`).

The pilot deliberately fails closed for question families where current learner-renderer/live-marker parity is not established. Supported in this pilot are currently live-markable forms of single choice, true/false, multiple select, single-blank cloze/fill blank, numerical without relative-tolerance semantics, and supported response modes of the existing diagram/misconception/adaptive wrappers.

Matching, ordering, constructed response, multi-blank cloze, relative-tolerance numerical cases, negative marking and unknown/inactive renderers are **not** claimed as deterministic-passable by this pilot.

## Visual/semantic learner

The visual learner opens the same production `take_test_v4.html` question card used for learners, captures the rendered page and records screenshot evidence in QA-only tables.

Semantic judgement is flag-only. Allowed outcomes:

- `PASS`
- `FLAG_TECHNICAL`
- `FLAG_ACADEMIC_R2`
- `UNABLE_TO_JUDGE`

A semantic judge may not rewrite governed question content or confer curriculum/academic approval.

No external AI call is made unless the Power House tool explicitly enables it. This ScoreMax package contains no external-AI client.

## Acceptance completed locally

- ScoreMax dependency-light contract tests: **5/5 PASS**.
- Real production-derived Biology G12 Chapter 18 R2-held MCQ imported into Mastery Laboratory with identity/version preserved and QA-only flags intact.
- Governed correct response scored correct; governed incorrect response scored incorrect.
- Actual live ScoreMax marker vs Mastery Laboratory scorer: **20 correct/incorrect parity cases PASS** across currently eligible live-markable families.
- Sentinel live tables for attempts/mastery/Growth remained unchanged in the deterministic contract test.
- Visual evidence ownership is bound to the exact visual identity/session.
- Production learner template rendered the real R2 MCQ successfully in Chromium using the actual ScoreMax stylesheet; no clipping or internal R2/QA/key leakage was observed in the captured learner view.
- Source compile/static fences passed.

## Gates still pending

- Full Flask/Werkzeug runtime login/session acceptance in a disposable ScoreMax runtime: **PENDING** (those runtime dependencies were unavailable in the build sandbox).
- Automated external semantic-vision provider call: **PENDING** and opt-in only; no paid API call was made.
- Windows acceptance: **PENDING**.
- Render/live deployment: **PENDING**; no ScoreMax Render service was available in the connected workspace.
- Multiple synthetic learners / parallel execution / 300 and 1,500 scale: **PENDING** by design; this is the one-learner-per-mode pilot.

## Rollback

Rollback is the exact supplied frozen ScoreMax V6.5.10 ZIP identified by SHA-256 above. V6.5.10 bytes were not overwritten.
