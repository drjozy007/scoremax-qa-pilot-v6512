# ScoreMax V6.4.0 Changelog

## Added
- Persistent FSc 1 / FSc 2 / MDCAT student programme selector.
- Programme-aware public landing experience and cinematic intelligence hero asset.
- Context-aware student mastery hero and new-student Starting Point state.
- Teacher direct-referral and one-level teacher-recruitment override reward model.
- Versioned teacher referral rates/holds and paid-conversion preservation when rates are not configured.
- Three-sheet monthly teacher referral Excel export.
- Growth Engine payment/referral outbox events.
- Admin-only 3,000-row Emergency Direct Intake with governed release attestation.
- Source worksheet/row lineage preservation for emergency intake.
- Production WSGI entry point, Procfile, environment checklist and V6.4 Windows one-click launcher.

## Changed
- Registration/login language now clearly uses email or ScoreMax ID.
- Subject chips no longer expose operational “Open” wording.
- Home prioritises mastery identity, Today’s Focus and momentum rather than empty/technical metrics.
- Health endpoint exposes V6.4 release identity while retaining the V6.2.8.1 compatibility marker.
- Referral admin settings now include teacher-direct and teacher-override rules.

## Hardened
- Emergency release opens eligible question + family gates together.
- Reviewer-2-required rows are explicitly release-blocked.
- 3,000-row emergency release is chunked for SQLite safety.
- Referral spreadsheet export neutralises formula-leading cells.
- Restore of a corrupt SQLite backup fails safely with a clean operator message.
- Paid teacher referral attribution is retained even while commission rates remain deliberately unconfigured.
