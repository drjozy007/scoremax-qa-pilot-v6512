# ScoreMax V6.3.0 — Claude Blind Audit Remediation (RC2)

Date: 17 August 2026
Parent: verified ScoreMax V6.2.8.1
Candidate: V6.3.0 Internal Live RC2 (post-Claude rectification)

## Audit disposition

Claude's first blind audit reproduced 506 deterministic checks and reported no surviving security breach. It identified two material defects, one intentional integration limitation, and several hygiene/operational findings.

### P4-01 — duplicate submission / double scoring — CONFIRMED AND RECTIFIED

Observed defect: repeated POSTs of one assessment session could create multiple scored attempts.

Rectification:

- assessment submission now takes an SQLite `BEGIN IMMEDIATE` writer claim before scoring;
- the session is atomically moved from `in_progress` to `submitting` before attempt creation;
- each scored attempt stores `assessment_session_id`;
- a partial unique index enforces at database level that one session can create at most one attempt;
- the session stores `submitted_attempt_id` and repeated submissions redirect to the existing result;
- failures before the first commit roll the writer transaction back.

New regression evidence:

- three sequential submissions → exactly one scored attempt;
- eight concurrent route-function submissions → exactly one scored attempt and no exception;
- inherited assessment/mastery regressions remain green.

External re-attack still requested against the real Flask stack using simultaneous HTTP clients.

### P2-01 — stale-positive re-verification — CONFIRMED AND RECTIFIED

Observed defect: after a family reopened, a single new correct response could combine with a positive route earned before the reopen and jump back to `VERIFIED_MASTERED`.

Rectification:

- reopening/AT_RISK/MAINTENANCE_DUE now establishes a prospective re-verification boundary;
- evidence before the active boundary remains historical but carries no closure credit for re-verification;
- the boundary remains active through intermediate provisional states until a later `VERIFIED_MASTERED` transition;
- maintenance boundaries are pinned to the last evidence event ID, avoiding second-granularity timestamp ambiguity;
- indexed history lookups preserve simulation/replay performance.

New regression evidence explicitly proves:

- one fresh route after REOPENED cannot recycle a stale second route;
- repeated fresh answers on the same route still cannot re-verify;
- a second fresh independent route can legitimately re-verify;
- AT_RISK follows the same prospective evidence rule;
- MAINTENANCE_DUE remains due until fresh policy evidence is sufficient;
- mandatory misconception-gate recovery no longer reuses stale route credit.

### P1-02 — internal-live access gating — CONFIRMED AND RECTIFIED WITHOUT WEAKENING COMMERCIAL TESTS

A broad "paywall off means full mastery ceiling" change would break inherited commercial-access guarantees, so it was rejected.

Instead V6.3 introduces the explicit local/internal flag:

`SCOREMAX_INTERNAL_FULL_ACCESS=1`

The internal-live launcher sets this flag while `SCOREMAX_ENFORCE_PAYWALL=0`. Normal/free/commercial semantics remain unchanged when the flag is absent. The inherited Free Access authentic-mock regression still passes.

### P1-03 — runtime artifacts shipped — CONFIRMED AND RECTIFIED

The first candidate contained test-time handwriting images, intake CSVs and database backups. RC2 packaging excludes all runtime-data directories and database/cache artifacts. A release-builder script enforces the exclusion set.

### P1-04 — bootstrap admin has no reset email — MITIGATED FOR INTERNAL LIVE

No email address is invented. RC2 instead bundles a local Admin Password Reset utility that creates a backup, resets only the Admin account, invalidates prior sessions where supported and integrity-checks the database. Production account recovery remains a later deployment concern.

### P1-01 — Universal Mastery not driven by real governed content — ACCEPTED CURRENT LIMITATION, NOT SILENTLY 'FIXED'

This remains intentional. Legacy ScoreMax mastery is still authoritative for real learner content. Universal Mastery remains PILOT/SHADOW and only accepts questions with governed Node/Family/Seed architecture mappings. Unmapped legacy questions are skipped rather than assigned fabricated academic identities.

The limitation is removed only when Power House supplies a governed approved machine package containing those mappings. Synthetic/QA fixtures are explicitly partitioned from LIVE learner evidence.

### P2-GOV — authoring dependence on route identity — GOVERNANCE NOTE

No destructive automatic parent-seed inference has been added. Power House must supply governed seed/dependency identity; ScoreMax continues to prevent known dependent/variant/recovery records from carrying independent mastery weight. A future import lint should reject contradictory/missing identity metadata before a package is admitted.

## Current verification after rectification

- 441 / 441 inherited deterministic checks PASS.
- 82 / 82 V6.3 deterministic checks PASS.
- 523 total deterministic checks PASS.
- 1,000 learner / 10,000 randomized-invariant acceptance simulation: 0 failures, 0 QA→LIVE leakage.
- 10,000 learner / 200,000 randomized-invariant stress simulation: 0 detailed failures, 0 fuzz failures, 0 QA→LIVE leakage.
- 30,019 QA response events and 92,274 decision-log rows generated in the large stress run.

Status: `POST_CLAUDE_RECTIFIED_RC2_PENDING_EXTERNAL_ATTACK_2_AND_BROWSER_UX_ACCEPTANCE`
