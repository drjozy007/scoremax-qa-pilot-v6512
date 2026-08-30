# ScoreMax V6.5.12 — Synthetic Learner Isolation Rectification Candidate

## Parent

Exact parent is the sealed **ScoreMax V6.5.11 Power House Synthetic Learner Qualification Pilot Candidate**.
V6.5.11 is preserved as rollback and is not overwritten.

## Why this child exists

The one+one Pilot01 qualification exposed two adjacent release risks before full runtime acceptance:

1. An authenticated `qa_student` request to an allowed QA route could continue into the global integration-housekeeping hook. That hook may activate due integration releases. It does not write learner mastery, but qualification traffic must not mutate unrelated production/integration state.
2. The package repeated a historical acceptance-regression class: inherited smoke tests enumerated allowed descendant version strings and therefore would reject a new otherwise-compatible ScoreMax release. This class had already been recorded historically as an acceptance-regression P1, so V6.5.12 fixes the acceptance architecture rather than appending another version to every list.

## Rectification

- `qa_student` now exits `_integration_housekeeping_tick()` before time, database, outbox, activation, or commit work.
- Added dependency-free `release_compatibility.py` with a strict same-major semantic descendant comparison.
- Historical release-marker smoke assertions now use the central comparison instead of manually enumerating future patch versions.
- V6.5.10 integration protocol identity remains unchanged at `6.5.10`; this child changes no integration contract.
- The existing V6.5.11 deterministic and visual synthetic learner machinery is retained.

## Scope / non-scope

- Exactly one deterministic learner and one visual-semantic learner remain the Pilot01 scope.
- No Growth Engine change.
- No real learner mastery/evidence changes.
- No question receives academic R2 clearance through this software qualification.
- Multiple learners and 300/1,500-scale execution remain pending by design.

## Current gates

- Dependency-light V6.5.11 synthetic learner tests: required.
- Dependency-light V6.5.12 rectification tests: required.
- Python compile and Jinja parse: required.
- Full Flask/Werkzeug inherited acceptance: **pending in this ChatGPT execution sandbox** because the pinned runtime dependencies are unavailable here.
- Normal authenticated `qa_student` browser traversal: **pending** until run in a normal Flask runtime.

Do not promote this candidate merely because dependency-light tests pass. Full runtime acceptance remains mandatory.
