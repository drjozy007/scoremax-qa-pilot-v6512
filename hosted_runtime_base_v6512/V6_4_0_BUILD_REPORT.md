# ScoreMax V6.4.0 — Build Report

## Decision

Consolidate the founder-agreed student UX changes and the minimum live-pilot operational requirements into one controlled descendant of V6.3.2. Do not reopen the accepted mastery engine or duplicate Power House/Growth Engine responsibilities.

## Parent / rollback

- Parent: ScoreMax V6.3.2 Governed Chapter Identity Candidate
- Parent SHA-256: `ca1fef5913d67b411405b1a8c41a58bfbfbd9ec74b62641de0dd1b6fc30acc93`
- Parent retained as external rollback artifact.
- V6.4 local runtime uses a fresh database: `internal_live_data/scoremax_v6_4_0_internal_live.db`.

## Build scope delivered

1. Persistent FSc 1 / FSc 2 / MDCAT programme context across the learner shell.
2. Modern public landing experience with programme strip, learning-intelligence hero and motivational energy layer.
3. Context-aware Home mastery hero with honest Starting Point state for learners without evidence.
4. Student-facing language/login/header cleanup while retaining existing chapter Existing/Potential Mastery.
5. Teacher referral expansion on the existing referral ledger: direct paid-student commission + one-level recruited-teacher override, configurable/versioned rates, refund/reversal lineage and monthly Excel reporting.
6. Asynchronous ScoreMax → Growth Engine payment/referral event boundary.
7. Emergency Direct Intake fallback, capped at 3,000 rows, reusing the existing source-preserving/adaptive importer with Draft/inactive first and strict academic-release fencing.
8. V6.4 local one-click launcher, fresh DB, backup/restore hardening, health/build identity and hosted WSGI/env preparation.

## Acceptance evidence before sealing

- 605/605 deterministic checks PASS.
- 1,000 learner / 10,000 randomized quick mastery replay PASS.
- 10,000 learner / 200,000 randomized large mastery attack PASS; 0 QA→LIVE leakage.
- 3,000-row Power House-style XLSX end-to-end intake scale PASS; preview ~1.01s, Draft import ~0.36s, governed release ~0.15s in the build environment; SQLite integrity `ok`.
- All confirmed self-audit findings listed in `V6_4_0_SELF_AUDIT_FINDINGS.md` were rectified before sealing.

## Not claimed

- The domain is not connected yet.
- This package has not yet passed real hosted HTTPS/SMTP/browser/accessibility acceptance.
- No claim is made that every legacy question has Universal Mastery mappings.
- No raw emergency spreadsheet can self-publish; academic approval is not inferred.

## Immediate next action after sealing

Deploy the exact sealed bytes unchanged to the private/pilot host once the domain/hosting account is available, then run the outstanding Production Reality Audit gates before any broad live use.
