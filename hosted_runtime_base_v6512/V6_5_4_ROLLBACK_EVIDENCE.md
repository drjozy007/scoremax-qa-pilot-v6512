# ScoreMax V6.5.4 Rollback Control

Rollback authority remains the exact sealed V6.5.3 parent. V6.5.4 schema changes are additive. Qualification uses disposable databases; production rollback must restore a V6.5.3 backup together with the exact V6.5.3 application bytes rather than attempting to reinterpret a modified live database silently.

Independent migration evidence proves: V6.5.3 database opens cleanly; V6.5.4 additive migration completes with SQLite integrity `ok` and FK `0`; unsafe V6.5.3 permissive-JSON outbox rows are quarantined without byte rewriting; restoring the untouched V6.5.3 database backup reopens cleanly under V6.5.3.
