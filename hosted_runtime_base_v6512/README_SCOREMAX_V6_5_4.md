# ScoreMax V6.5.4 — Three-System Integration Central Admission Rectification Candidate

V6.5.4 is a substantive child of the exact sealed V6.5.3 candidate (`344b9e8f7246858250192bf1b9c4d8f17a0675b41f412fe3bee20f3bf8e8eceb`). It fixes exactly the three new P1 architecture classes discovered by central Integration Control and preserves the accepted ScoreMax learner platform.

## Rectified architecture

1. **Retry-cycle recovery** — governed requeue preserves message/idempotency/payload bytes and immutable prior attempt rows, increments retry-cycle lineage, and resets only the active-cycle attempt counter.
2. **Strict canonical JSON** — one shared integration serializer rejects `NaN`, `+Infinity` and `-Infinity` recursively before hash/store/send. Peer JSON is parsed strictly; invalid response bodies are represented only by redacted standards-compliant diagnostic evidence.
3. **Frozen Integration Health completion** — the existing ScoreMax operations surface now exposes the full frozen per-direction minimum from durable integration state, retaining `oldest_backlog_at` only as a compatibility alias.

V6.5.4 does not create a new dashboard, queue engine, assessment engine, reviewer workflow, mastery engine or referral ledger.

## Required status

`PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION`
