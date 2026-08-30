# ScoreMax V6.3.0 — Functionality Self-Audit Findings

**Audit date:** 17 August 2026  
**Scope:** new universal mastery runtime + V6.2.8.1 integration  
**Method:** direct unit/integration attacks, synthetic learner profiles, randomized invariant checks, inherited regression replay.

## Confirmed findings rectified during the build

1. **SOURCE_ONLY family-weight leakage — HIGH.** Initial draft correctly zeroed source-only Knowledge Node evidence but a derived Claim Family mapping could still receive independent weight. Rectified by making source-only/ineligible question evidence zero-weight at qualification and by collapsing derived family mappings with source eligibility preserved. Claim Family independent weight is now capped too.

2. **Response-event ID collision — HIGH operational reliability.** Two identical rapid evidence events could hash to the same ID because timestamps were second-resolution. Rectified with cryptographic nonce material while retaining immutable payload checksums.

3. **Decision/history ID collision — MEDIUM/HIGH operational reliability.** Rapid deterministic replay could generate the same decision/history primary key inside one second. Rectified with unique nonce material; decision input checksums remain deterministic for replay comparison.

4. **Verified mastery could become effectively immortal — CRITICAL mastery logic.** Historical positive qualifying weight continued to satisfy closure thresholds, so later repeated wrong evidence did not necessarily make the preliminary aggregate state fall. Reopen logic therefore might never execute. Rectified by evaluating contradictory evidence against already-verified/maintenance states even when old positive evidence still meets aggregate thresholds.

5. **Reopened mastery could silently reverify on another wrong answer — CRITICAL mastery logic.** Once a state reopened, the next recalculation could again see the historical positive aggregate and return VERIFIED despite the newest evidence still being wrong. Rectified by preserving REOPENED/AT_RISK on non-qualifying or wrong follow-up evidence until fresh qualifying evidence supports recovery.

6. **Misconception gate could become unrecoverable for too long — HIGH.** The first draft treated any high-confidence wrong in the latest evidence window as a continuing gate failure, even after a later governed correction. Rectified so the latest decisive qualifying gate evidence controls the current gate state. A later unassisted correction can therefore repair a prior gate failure, while a newer high-confidence misconception can still reopen it.

## Post-rectification replay

After those fixes:

- 441/441 inherited regression checks passed.
- 55/55 V6.3 Universal Mastery foundation checks passed.
- 10/10 V6.3 application-wiring checks passed.
- 10,000 synthetic learner journeys passed with zero invariant failures.
- 200,000 randomized invariant checks passed with zero failures.
- 0 synthetic QA evidence events entered the LIVE partition.

## Remaining validation posture

These results demonstrate software behaviour under the covered invariants. They do not substitute for real learner calibration, browser UX acceptance, public deployment hardening or academic approval of content mappings.
