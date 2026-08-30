# ScoreMax V6.5.0 hosted/integrated pilot — environment checklist

Do not store secret values in this file or in Git. Configure them only in the hosting provider's secret/environment settings.

## Core ScoreMax production environment

- `SCOREMAX_ENV=production`
- `SCOREMAX_SECRET=<long random secret>`
- `SCOREMAX_DB=<persistent database path>`
- `SCOREMAX_SMTP_HOST=<provider host>`
- `SCOREMAX_SMTP_FROM=<verified from address>`
- `SCOREMAX_SMTP_PORT=<usually 587 or 465>`
- `SCOREMAX_SMTP_USER=<if required>`
- `SCOREMAX_SMTP_PASSWORD=<secret>`
- `SCOREMAX_SMTP_SSL=0|1`
- `SCOREMAX_CONTENT_INTAKE_DIR=<persistent/private upload directory>`

Recommended pilot settings:
- `SCOREMAX_COOKIE_SECURE=1`
- `SCOREMAX_ENFORCE_PAYWALL=0` only while the founder/internal pilot is deliberately free-access
- `SCOREMAX_INTERNAL_FULL_ACCESS=1` only while paywall enforcement is off
- `SCOREMAX_UNIVERSAL_MASTERY=1` for shadow/pilot evaluation
- `SCOREMAX_LOG_LEVEL=INFO`

## Power House -> ScoreMax inbound service credentials

- `POWER_HOUSE_TO_SCOREMAX_TOKEN=<scoped bearer token>`
- `POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET=<HMAC secret>`
- `POWER_HOUSE_TO_SCOREMAX_PREVIOUS_TOKEN=<optional during rotation>`
- `POWER_HOUSE_TO_SCOREMAX_PREVIOUS_HMAC_SECRET=<optional during rotation>`

## Growth Engine -> ScoreMax inbound service credentials

- `GROWTH_ENGINE_TO_SCOREMAX_TOKEN=<scoped bearer token>`
- `GROWTH_ENGINE_TO_SCOREMAX_HMAC_SECRET=<HMAC secret>`
- `GROWTH_ENGINE_TO_SCOREMAX_PREVIOUS_TOKEN=<optional during rotation>`
- `GROWTH_ENGINE_TO_SCOREMAX_PREVIOUS_HMAC_SECRET=<optional during rotation>`

## ScoreMax -> Power House outbound

- `SCOREMAX_POWER_HOUSE_BASE_URL=<https://power-house-host>`
- `SCOREMAX_TO_POWER_HOUSE_TOKEN=<scoped bearer token>`
- `SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET=<HMAC secret>`

## ScoreMax -> Growth Engine outbound

- `SCOREMAX_GROWTH_ENGINE_BASE_URL=<https://growth-engine-host>`
- `SCOREMAX_TO_GROWTH_ENGINE_TOKEN=<scoped bearer token>`
- `SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET=<HMAC secret>`

## Integration policy

- `SCOREMAX_INTEGRATION_MAX_CLOCK_SKEW_SECONDS=300` (or Integration Control approved value)
- `SCOREMAX_INTEGRATION_MIN_EVIDENCE_N=10` (or Integration Control approved value)

Do not enable strict integrated-pilot preflight until both counterpart builds have their scoped service endpoints and secrets configured.

Before connecting a public domain, prove: HTTPS, `/healthz`, `/api/integration/v1/health`, build identity, persistent database/backup/restore, live email, cookie/security headers, peer authentication/rotation, outage/replay, and one-action rollback.
