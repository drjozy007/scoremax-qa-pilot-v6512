# ScoreMax V6.4.0 — Self-Audit Findings

The build was self-audited as a distinct stage before sealing. Confirmed defects were rectified in the working candidate; they are recorded here rather than hidden.

| Finding | Severity | Status | Rectification |
|---|---|---|---|
| Emergency release initially activated eligible questions but not their family gate, so a released question could remain invisible to learner selection. | P0 academic/delivery integrity | **FIXED / TESTED** | Eligible release now opens question and family gates atomically enough for learner inventory rules; focused regression added. |
| `Reviewer 2 Required` could have been missed by a narrower readiness fence. | P0 academic-integrity | **FIXED / TESTED** | Explicit R2/dual-review blockers added; R2 fixture remains inactive after release attempt. |
| Source worksheet/row lineage was not guaranteed in the canonical imported row payload. | P1 governance | **FIXED / TESTED** | Source sheet/row retained in batch rows and question lineage metadata. |
| 3,000-row release using one giant SQL `IN` set could hit SQLite variable limits. | P1 scale/data integrity | **FIXED / TESTED** | Release updates chunked in blocks of 500; 3,000-row end-to-end qualification passes. |
| Paid teacher referral with a deliberately unconfigured commission rate could lose the commercial reward-ledger record. | P1 commercial auditability | **FIXED / TESTED** | Paid teacher conversion is retained as `rate_not_configured`, preserving payment/referrer/rule-version evidence. |
| Teacher referral export could later expose formula-leading text to spreadsheet execution. | P1/P2 export hardening | **FIXED / TESTED** | Formula-leading text is apostrophe-neutralised; deterministic export test added. |
| Corrupt restore source surfaced raw `sqlite3.DatabaseError` even though live DB remained safe. | P2 operations | **FIXED / TESTED** | Integrity wrapper converts corruption to a clean failed-integrity result before replacement. |
| Monthly teacher summary did not clearly separate direct and downstream commercial contribution. | P2 reporting clarity | **FIXED / TESTED** | Summary now separates direct/downstream students, direct/network eligible sales and direct/override rewards. |
| Growth Engine commercial boundary did not yet receive explicit payment/referral conversion events. | P1 integration foundation | **FIXED / TESTED** | Asynchronous outbox events added; no synchronous Growth control path. |

## Deliberately unresolved / external gates

- Real domain/DNS/HTTPS/hosting identity: **PENDING**.
- Real SMTP/password-reset delivery: **PENDING**.
- Founder browser/mobile/keyboard/200% zoom walk: **PENDING**.
- One real academically approved Power House chapter through canonical release → learner attempt → mastery: **PENDING**.
- Universal Mastery mappings for legacy inventory: **N/A until governed mappings arrive; no mappings are fabricated**.
- Claude N1 legacy duplicate-laden assessment DB cleanup: **N/A for the fresh V6.4 internal-live DB**; required only if an old contaminated DB is migrated.
