# ScoreMax V6.5.4 — Central Admission Rectification Specification

## Parent

Exact immutable parent: `ScoreMax_V6_5_3_Three_System_Integration_Admission_Rectification_Candidate.zip`

SHA-256: `344b9e8f7246858250192bf1b9c4d8f17a0675b41f412fe3bee20f3bf8e8eceb`

## Scope

Fix exactly the three confirmed P1 architecture classes and cheap adjacent regression risks. Reuse V6.5.3. Do not redesign ScoreMax, the student UX, mastery, Power House review, Emergency Direct Intake, payment/referral authority, or the frozen three-system contracts.

### R1 — Retry-cycle recovery

- Preserve message_id, idempotency_key, payload checksum and immutable envelope bytes on operator requeue.
- Preserve all historical `integration_dispatch_attempts` and requeue audit evidence.
- Start a new bounded active retry cycle after a governed requeue from `DEAD_LETTER` or `QUARANTINED`.
- Do not let an exhausted prior cycle cause immediate re-dead-letter on the first new transient failure.
- Prefer resetting only the active-cycle attempt counter; add cycle lineage only if needed for unambiguous audit.

Required attack: exhaust all configured retries → dead-letter → operator requeue → one 503/transport failure → row must be RETRY with a future due time, not DEAD_LETTER; old attempt rows remain unchanged and a new attempt row is appended.

### R2 — Strict canonical JSON

- One canonical integration serializer must reject non-finite numbers (`NaN`, `+Infinity`, `-Infinity`) with no persistence side effect.
- Apply recursively to payload, envelope, open nested metadata/supporting objects, receipts, quarantine/error evidence and dispatch bodies.
- Hash exactly the standards-compliant canonical bytes that are persisted/sent.
- Do not silently coerce non-finite values to strings or null.

Required attack: place each non-finite value in schema-open product-event metadata and other open integration objects; every case must fail closed before outbox/inbox/quarantine/log persistence attributable to the invalid payload.

### R3 — Frozen Integration Health completion

Every direction must expose at least:

`direction, contract, connection_state, last_success_at, last_received_at, last_dispatched_at, queued_count, retrying_count, dead_letter_count, quarantined_count, oldest_queued_at, last_error_code, last_error_at, local_schema_version, peer_schema_version, peer_version, credential_expiry_warning, clock_skew_warning`

- Reuse existing Admin/operations health; no new dashboard.
- Values must come from durable integration state, not hard-coded zero/healthy placeholders.
- Error/diagnostic values must be redacted and contain no credentials or learner data.
- If credential-expiry semantics are not configured for a direction, return a truthful null/unknown state rather than false reassurance.

Required attack: exercise receive, dispatch, retry, quarantine/dead-letter, requeue and auth/skew-warning states and reconcile health values with underlying rows.

## Protected positive V6.5.3 behaviour

Must remain green:
- semantic content admission and zero-side-effect rejection;
- numeric, multiple-select, text/boolean and negative/partial marking;
- learner-safe stimulus projection;
- immutable session/attempt question/release/scope pins;
- release and blueprint semantic checksum conflict quarantine;
- original durable receipt replay;
- HTTPS-before-credential access and receiver binding;
- 200/202/409/422/429/503 receipt state matrix;
- atomic claims, fairness and worker heartbeat;
- released blueprint runtime control;
- 300/1,500 Power House-style scale and 3,000-row emergency intake;
- migration/backup/restore/rollback and database integrity;
- clean package, no caches/runtime DB/secrets.
