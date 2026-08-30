# V6.2 Production/Pilot Notes

## Required before live hosting

- PostgreSQL or an approved managed database plan.
- HTTPS and persistent secret management.
- Protected `SCOREMAX_CONTENT_INTAKE_DIR`.
- Protected `SCOREMAX_BACKUP_DIR` with off-host copies.
- Protected `SCOREMAX_PILOT_UPLOAD_DIR`.
- Production SMTP configuration.
- `SCOREMAX_POWERHOUSE_PROMPT_SECRET` for signed prompt-pack transport.
- Logging, monitoring and recovery ownership.
- Privacy, retention and safeguarding review.

## Pilot content rule

Imported does not mean approved. Only a question and family that both pass governance and activation may enter student delivery. Candidate and demo content must not influence genuine mastery, projections or authentic mocks.

## Knowledge Hub

The CMS exists but is `HIDDEN` by default. Do not make it live until sources, rights, author/reviewer responsibility and stale-content review are operational.

## Browser acceptance

Automated business/database tests were executed. A real browser/mobile test was not available in the build environment and remains mandatory before pilot use.
