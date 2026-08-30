# ScoreMax V6.3.0 Internal Live RC2 — Acceptance Snapshot

Date: 17 August 2026

## Deterministic regression

- Inherited V5.5 → V6.2.8.1: **441 / 441 PASS**
- V6.3 Universal Mastery + application wiring: **82 / 82 PASS**
- Combined deterministic checks: **523 / 523 PASS**

## Large synthetic stress run

- Synthetic learners: **10,000**
- Randomized invariant/fuzz checks: **200,000**
- QA response events: **30,019**
- Decision log rows: **92,274**
- Recovery rows: **4,170**
- Detailed failures: **0**
- Fuzz failures: **0**
- LIVE response events created by simulation: **0**

## Material first-audit defects now protected by regression tests

1. Duplicate assessment submission / double scoring.
2. Stale pre-reopen evidence being recycled to re-verify mastery.
3. AT_RISK fresh-evidence recovery.
4. MAINTENANCE_DUE fresh-evidence reconfirmation.
5. Internal-live full journey access without weakening default commercial gates.
6. Runtime/private artifact exclusion from release packaging.

## Known intentional limitation

Universal Mastery remains PILOT/SHADOW for governed mappings only. Existing real learner content continues to use the established ScoreMax mastery engine until Power House provides approved Node / Claim Family / Reasoning Seed / Question architecture mappings. Synthetic QA evidence cannot enter LIVE mastery.

## Remaining gates before INTERNAL-LIVE ACCEPTED

- Claude Attack 2 against this exact RC2 package, especially real HTTP concurrency and cross-role BOLA/IDOR.
- Windows real-framework replay.
- Student browser/UX acceptance (desktop/mobile/keyboard/zoom).
- Final package/restart/backup/restore replay after UX rectification.

Current status: **strong internal-live release candidate, not public-live freeze.**
