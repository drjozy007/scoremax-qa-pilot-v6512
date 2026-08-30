# ScoreMax V6.6.9B Hosted Qualification / Platform Consolidation

Date: 2026-08-30
Status: PRE-PRODUCTION HOSTED QUALIFICATION CONTRACT — DOES NOT CONFER RELEASE

## Exact ScoreMax candidate
- Canonical development head: `ScoreMax_V6_6_9B_Whole_Platform_Launch_Boundary_Hardened_DEPENDENT_CANDIDATE.zip`
- SHA-256: `70a181237cd028b86f34650b0fbc912174ee1516965dd62f8d4b2862bea63ffa`
- Status: LOCAL_CAPABILITY_QUALIFIED DEPENDENT CANDIDATE — NOT FROZEN
- Production release MUST remain fail-closed until the inherited hosted-production, browser/device/accessibility, Power House population/reconciliation, PSP and controlled-pilot gates are satisfied.

## Lean launch topology
Use one Render workspace/control plane. At launch retain only the minimum canonical runtime authorities:
1. ScoreMax public web/API — one instance while SQLite/WAL remains authoritative.
2. Power House canonical qualification/admin runtime.
3. Power House academic reviewer only if its external-review function is still independently required after the canonical Power House UI migration.
4. QA adapters/harnesses only as qualification evidence services; they have no release authority.
5. Growth Engine remains a bounded module/integration contract inside ScoreMax initially; do not create a separate always-on paid Growth service until traffic or isolation requires it.

## Current database boundary
Do NOT migrate ScoreMax to PostgreSQL merely for consolidation. V6.6.9B inherits the V6.6.4 production contract: one ScoreMax web instance with SQLite/WAL on a dedicated persistent disk. Horizontal scaling is blocked until a separately designed and qualified shared transactional database adapter exists.

Power House may separately evolve from SQLite to PostgreSQL under its own governed migration plan. Do not couple that migration to ScoreMax launch.

## Required hosted ScoreMax persistent layout
- `SCOREMAX_ENV=production`
- `SCOREMAX_INSTANCE_COUNT=1`
- `SCOREMAX_PERSISTENT_ROOT=/data/scoremax`
- `SCOREMAX_DB=/data/scoremax/db/scoremax.sqlite3`
- `SCOREMAX_BACKUP_DIR=/data/scoremax/backups`
- `SCOREMAX_CONTENT_INTAKE_DIR=/data/scoremax/content_intake`
- one dedicated persistent disk mounted at `/data`
- `SCOREMAX_SECRET` supplied as a Render secret; never committed to Git

## Hosted acceptance gates
Before production freeze, prove on the exact deployed V6.6.9B bytes:
- candidate source SHA / deployment identity;
- `/healthz` liveness and `/readyz` read-only readiness;
- persistent database survival across restart and redeploy;
- SQLite integrity / FK checks;
- database-native online backup;
- controlled restore with pre-restore safety backup;
- rollback evidence;
- HTTPS/TLS and security headers;
- logs, CPU, memory, storage and latency evidence;
- authenticated real-browser learner/teacher/parent/admin journeys;
- device and accessibility qualification;
- exact current Power House reconciliation/acknowledgement gates;
- real PSP provider qualification;
- controlled real-user pilot.

## Service-retirement rule
Historical Render qualification/scale services are engineering evidence, not permanent production infrastructure. Preserve their code, hashes and final evidence first, then suspend/delete them when their successor has passed the equivalent gate. Never retire the current canonical Power House service or any still-required evidence service merely to free a slot.

## Growth Engine boundary
ScoreMax may emit governed business events to Growth Engine contracts. Growth Engine receives acquisition/referral/commercial events, not arbitrary Power House question content. Power House remains content authority; ScoreMax remains learner/product authority; Growth remains acquisition/referral authority.
