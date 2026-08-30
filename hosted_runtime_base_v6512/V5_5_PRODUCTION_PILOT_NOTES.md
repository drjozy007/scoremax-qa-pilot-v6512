# ScoreMax V5.5 — Production Pilot Notes

V5.5 is an application-layer blueprint/calibration release. It is **not** by itself a production deployment package.

Before a real internet pilot, complete:

- PostgreSQL migration and proper foreign-key/index design;
- production WSGI hosting;
- HTTPS and secure reverse proxy;
- persistent `SCOREMAX_SECRET`;
- working SMTP configuration;
- automated backups and restore test;
- central error logging/monitoring;
- domain/DNS configuration;
- real browser/mobile acceptance;
- multi-user/concurrency test;
- removal/isolation of demo content;
- import and academic review of real Power House content;
- authoritative Power House evidence for the active blueprint.

For production blueprint transport, a shared signing secret is required by the V5.5 importer/activator:

- `SCOREMAX_POWERHOUSE_SHARED_SECRET=<strong secret>`
- `SCOREMAX_REQUIRE_POWERHOUSE_SIGNATURE=1`

The current sample MDCAT blueprint contains placeholder source evidence. Do not activate it as an official production authority merely because it passes structural validation.
