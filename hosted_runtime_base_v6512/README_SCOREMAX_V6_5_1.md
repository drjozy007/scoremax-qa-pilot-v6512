# ScoreMax V6.5.1 — Three-System Integration Rectification Candidate

**Status:** `PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION`

V6.5.1 is an additive rectification child of the exact Integration Control-supplied ScoreMax V6.5.0 parent. It does not redesign ScoreMax, Power House, Growth Engine, the student UX, or the frozen v1.0 integration contracts. It closes the ScoreMax-side contract/identity/delivery defects independently reproduced by Integration Control and adds the approved PH→ScoreMax contract schema v1.1.0 alongside frozen v1.0.

## Key rectifications
- Draft 2020-12 JSON Schema + format checking at inbound/outbound/receipt gateways.
- Strict semantic question/stimulus/archive/manifest checksum verification.
- Collision-safe Power House projection namespace; opaque PH IDs never overwrite legacy/emergency ScoreMax rows.
- Immutable question-version store separated from release membership.
- Full release membership safely supports 0/50/90/100% unchanged question versions.
- v1.1.0 `INLINE`, `MANIFEST_PULL`, and `WITHDRAW_RELEASE` support; frozen v1.0 MANIFEST_PULL contradiction remains explicitly rejected.
- Receipt-aware dispatch: HTTP success alone never marks delivery.
- Stable referral attribution across referral/payment/refund/reward events.
- Skipped/unanswered telemetry separated from incorrect.
- Minimum-N privacy retained; no learner IDs/raw answers in Power House aggregate evidence.
- Incremental source-change queue removes unbounded Growth/content-requirement scans from learner requests.
- Strict production preflight rejects non-HTTPS peers and weak/placeholder secrets.
- Additive V6.5.0→V6.5.1 DB migration corrected and tested on the exact parent.

## Acceptance evidence
- 605/605 inherited V6.4 deterministic checks PASS.
- 48/48 V6.5 focused integration checks PASS.
- 22/22 V6.5.1 focused rectification checks PASS.
- 24/24 V6.5.1 deep receipt/version-membership checks PASS.
- Total deterministic checks: **699/699 PASS**.
- Integration Control supplied adversarial harness: **18/18 NOT_CONFIRMED; 0 surviving defects**.
- Canonical 300-question and 1,500-question contract scale gates PASS.
- Emergency 3,000-question XLSX fallback remains PASS.
- 10,000 synthetic learners + 200,000 randomized mastery/invariant attacks: 0 detailed failures, 0 fuzz failures, 0 QA→LIVE leakage.
- Exact V6.5.0 database upgrade to V6.5.1 PASS.
- V6.5.1 backup→mutate→restore PASS with integrity `ok`.

## Launch locally
Run `INSTALL_AND_START_SCOREMAX_V6_5_1.bat` once on Windows, or `start_scoremax_v6_5_1_internal_live.bat` after requirements are installed.

## Boundaries
Academic review stays in Power House. Universal Mastery remains governed/pilot for mapped content only. Growth Engine remains advisory/commercial and cannot mutate learner mastery or academic truth. Cross-system acceptance still belongs to Integration Control using the actual Power House and Growth Engine counterpart candidates.
