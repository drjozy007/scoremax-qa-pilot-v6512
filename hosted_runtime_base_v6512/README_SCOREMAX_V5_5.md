# ScoreMax V5.5 — Assessment Blueprint Integration

ScoreMax V5.5 connects the learner-delivery platform to immutable, versioned Assessment Blueprints created and approved in Power House.

## Architectural boundary

- **Power House** creates, evidences, reviews, approves and versions the authoritative blueprint.
- **ScoreMax** imports the approved blueprint snapshot, validates it, activates it through authorised governance and applies it consistently.
- **Assessment Blueprint** defines the official structure: framework, version, subjects/sections, counts, weights, duration and any approved official difficulty composition.
- **Assembly / Rigor Policy** is a separate ScoreMax version controlling future item mix and mastery evidence. It cannot alter the official blueprint or rewrite history.

Every authentic mock, assessment session and result can retain both:

- the exact Blueprint ID/version and immutable composition snapshot;
- the exact assembly/rigor policy ID/version used.

## Main V5.5 capabilities

1. Governed JSON blueprint import with checksum validation and optional HMAC signature verification.
2. Explicit validation, activation, supersession, archive, audit and immutable export.
3. Blueprint-driven authentic full-mock assembly with exact subject counts and no silent substitution.
4. Separate proportional practice, diagnostic and adaptive practice journeys that are clearly non-authentic.
5. Bank-sufficiency analysis and structured Power House Content Requirement Requests.
6. Blueprint-aware Study Plan priority, combining official weight with verified learner need.
7. Blueprint-aware score projections with evidence confidence and historical version pinning.
8. Student, parent and teacher blueprint views.
9. Versioned Assessment Rigor and Mastery Standard policies with preview, audit and future-form pinning.
10. Policy tightening moves affected mastery to **Verification Due**; it never performs a retroactive automatic downgrade.
11. V5.4.2 data-preserving migration with legacy mocks marked `LEGACY_UNPINNED` rather than falsely attributed.
12. Strengthened Power House question import template with Level and Difficulty kept separate.

## Initial sample blueprint

`sample_powerhouse_mdcat_2026_blueprint.json` demonstrates:

- Biology: 81 questions / 45%
- Chemistry: 45 / 25%
- Physics: 36 / 20%
- English: 9 / 5%
- Logical Reasoning: 9 / 5%
- Total: 180 / 100%

**Important:** the sample contains an explicit placeholder source reference. It is an integration/test artifact, not proof that the figures are an officially approved production blueprint. Power House must attach authoritative evidence and final approval before production activation.

## Start locally

1. Extract V5.5 into a new folder. Keep V5.4.2 untouched.
2. Install requirements:

   `py -m pip install -r requirements.txt`

3. Start:

   `start_scoremax_v5_5.bat`

4. Open:

   `http://127.0.0.1:5000`

## Migration

Run a dry-run first:

`py migrate_v5_4_2_to_v5_5.py path/to/scoremax_v4.db --dry-run`

Then perform the real migration with automatic backup:

`py migrate_v5_4_2_to_v5_5.py path/to/scoremax_v4.db`

See `V5_5_MIGRATION_GUIDE.md`.

## Security / transport settings

Power House transport settings (signature is mandatory in `SCOREMAX_ENV=production`):

- `SCOREMAX_POWERHOUSE_SHARED_SECRET`
- `SCOREMAX_REQUIRE_POWERHOUSE_SIGNATURE=1`

Production still requires the deployment hardening described in `V5_5_PRODUCTION_PILOT_NOTES.md`.

## Test boundary

`smoke_tests_v5_5.py` executed 49 deterministic schema/business/regression checks against real temporary SQLite databases using a lightweight Flask/Werkzeug compatibility stub. Real browser, SMTP, multi-user concurrency and production-host testing remain manual acceptance tasks.


## Final stakeholder-facing layer
- Student Exam Structure pages for every active blueprint.
- Honest assessment relationship labels.
- Pre-mock blueprint summaries.
- Blueprint-based result breakdowns.
- Teacher/institution structure visibility.
- Detailed mock Blueprint Compliance Reports.
