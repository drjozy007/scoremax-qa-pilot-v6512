# ScoreMax V6.5.4 Changelog

Parent: exact sealed ScoreMax V6.5.3 candidate, SHA-256 `344b9e8f7246858250192bf1b9c4d8f17a0675b41f412fe3bee20f3bf8e8eceb`.

## Central admission rectifications

- Reset active `attempt_count` to zero on governed requeue while preserving immutable prior dispatch attempts.
- Added additive `retry_cycle` lineage to outbox and dispatch attempts plus prior-count/new-cycle evidence in requeue audit.
- Changed integration canonical JSON to `allow_nan=False`; recursive NaN/+Infinity/-Infinity now fail before integration persistence/hash/send.
- Added strict peer JSON parsing and standards-compliant redacted response evidence for invalid/non-JSON peer bodies.
- Added migration reconciliation that quarantines pre-V6.5.4 non-standard outbox envelopes without rewriting their original bytes.
- Completed the frozen Integration Health minimum: receive/dispatch timestamps, oldest queued work, latest durable error, credential-expiry warning, clock-skew warning and existing schema/version fields.
- Added redacted durable transport diagnostics for inbound auth/clock-skew/header/JSON failures; no credentials, learner content or raw request body is retained.
- Extended the existing Admin Integration Health card only; no new operations dashboard was created.

## Preserved boundaries

Student UX, Universal Mastery, Power House academic-review authority, Emergency Direct Intake, payment/referral authority, content admission semantics, immutable evidence pinning, marking, blueprint runtime, HTTPS/receipt binding, fair leased claims and release identity remain architecturally unchanged.
