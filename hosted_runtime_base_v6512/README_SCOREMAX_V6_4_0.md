# ScoreMax V6.4.0 — Live Pilot UX & Operations

## Decision

Build one consolidated live-pilot candidate rather than a sequence of small UX patches. Preserve the accepted
V6.3.2 mastery, assessment, chapter-identity and data-integrity foundations; change only the agreed student UX,
commercial-referral and live-operations surfaces.

## Immutable parent

- Parent: `ScoreMax V6.3.2 — Governed Chapter Identity Candidate`
- Parent SHA-256: `ca1fef5913d67b411405b1a8c41a58bfbfbd9ec74b62641de0dd1b6fc30acc93`
- Rollback: retain the sealed V6.3.2 ZIP separately. V6.4.0 uses a fresh internal-live database path.

## Principal changes

### Student experience
- Persistent programme context: **FSc 1 | FSc 2 | MDCAT** across the student shell.
- Programme switching is stateful, not decorative; subject/chapter context cannot bleed across programmes.
- Public landing page gains the same programme context plus a modern, cinematic learning-intelligence hero.
- Motivational progression: **Discipline → Consistency → Progress → Mastery → Results**.
- Home hero now answers: where am I, what is next, and am I progressing?
- A new student is shown **Starting point / Not established**, never fabricated Foundation mastery.
- Formal mastery ladder remains Foundation → Exam Ready → Advanced → Distinction at chapter level.
- Chapter Existing Mastery vs Potential Mastery remains governed by formal evidence + eligible bank capacity.
- Learner-facing production jargon is reduced; subject chips no longer say “Open”.
- Registration/login explicitly tells learners to use their exact email or ScoreMax ID.

### Teacher referral programme foundation
- Permanent teacher referral codes/links reuse the existing ScoreMax referral architecture.
- Teacher → paying student creates a direct reward ledger entry tied to the exact cleared payment.
- Teacher A → Teacher B → paying student supports **one upstream teacher override only**; no multi-level chain.
- Rates/holds are configurable and version-pinned. No founder commission percentage is hard-coded.
- Paid teacher conversions remain recorded even when commission rates are still unconfigured.
- Refund/reversal lineage is preserved.
- Monthly admin Excel export contains:
  1. Teacher Monthly Summary
  2. Student Referral Detail with package/payment/reward evidence
  3. Teacher-to-Teacher Rewards
- Formula-leading spreadsheet text is neutralised on export.
- ScoreMax emits asynchronous `PAYMENT_RECORDED` and `TEACHER_REFERRAL_CONVERSION` Growth Engine outbox events;
  Growth Engine receives no authority over mastery, academic truth or payments.

### Emergency Direct Intake
- Explicit admin-only **Emergency Direct Intake** fallback when Power House transport is temporarily unavailable.
- Maximum 3,000 rows for the emergency path (standard existing importer remains capable of 10,000).
- Reuses the existing adaptive multi-sheet XLSX/CSV parser; preserves source bytes, SHA-256, worksheet and row lineage.
- Recognises Power House-style learner question/answer/rubric/mastery headers without manual column renaming.
- Imports valid records as **Draft + inactive** first.
- Never fabricates opaque external IDs, mastery identities or approval.
- Release requires an exact founder/admin attestation and only explicitly ready, rights-cleared, non-held, non-R2 records can enter learner inventory.
- Held, unresolved, rejected, R2-required or otherwise not-ready records remain excluded.
- Question and family release gates are opened together only for eligible rows.
- 3,000-row release updates are chunked to avoid SQLite parameter-limit failure.

### Live-pilot operations
- Current health identity exposes immutable compatibility marker plus `release_version=6.4.0` and build name.
- New one-click Windows installer/launcher and fresh V6.4 internal-live database path.
- Backup/restore utility converts corrupt-database integrity errors to clean operator failures and never replaces a good DB with a failed restore.
- WSGI entry point + `Procfile` + production environment checklist included. Public deployment still requires real hosting/domain/secrets/SMTP/persistent DB acceptance.

## What stays untouched

- Power House remains the academic-review authority.
- Historical ScoreMax Reviewer Workspace is not restored to the forward workflow.
- Universal Mastery does not invent mappings for legacy questions; legacy mastery remains authoritative until governed mappings arrive.
- Existing V6.3 duplicate-submit, stale-reverification and QA/LIVE isolation fixes remain intact.
- Expert/Elite remain broader subject/full-exam achievements, not chapter labels.

## Current gate

`LIVE_PILOT_CANDIDATE_PENDING_DOMAIN_AND_FOUNDER_BROWSER_ACCEPTANCE`

Local deterministic/simulation/scale acceptance is required before packaging. Domain/HTTPS, real browser/mobile/accessibility,
SMTP, real approved Power House bridge and founder live acceptance remain separate gates.
