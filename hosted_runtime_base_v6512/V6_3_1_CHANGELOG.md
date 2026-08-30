# ScoreMax V6.3.1 — Student UX V2 Changelog

**Parent:** ScoreMax V6.3.0 Internal Live RC2 — Post-Claude Rectified  
**Parent SHA-256:** `b7850f5ba0e703b755d05de50e51a5fb8c3fee32bcf5fbee47f2e5475f0db8fa`

## Student UX

- Simplified desktop student navigation to **Home · Learn · My Plan · Practice · Exams · Progress**.
- Removed the rendered contextual third navigation row; the subject switcher is now the only study-context second row.
- Moved Knowledge Hub, Pathways, teacher discovery, Messages, Access, Settings, Help and Logout into a supporting account/profile menu.
- Simplified mobile navigation and corrected mobile Learn to open subjects rather than the test builder.
- Rebuilt Home around **Today's Focus**, compact progress, subjects, coming-up work and quick actions.
- Kept Daily Spark as a lower-priority optional module and preserved its no-formal-mastery boundary.
- Simplified Practice, Progress and Results wording; technical assessment metadata remains available under details rather than leading the result.

## Chapter mastery opportunity

Every live chapter card now shows:

- **Existing Mastery** — formal governed chapter mastery only.
- **Potential Mastery** — highest chapter mastery level supported by the current eligible production question bank and active mastery/assembly requirements.
- A two-layer visual graph showing achieved versus available mastery opportunity.
- Practice accuracy separately, so practice activity is not misrepresented as mastery.
- Access limitation separately, so commercial access does not redefine academic capability.

Chapter mastery remains capped at **Distinction**. Expert and Elite are not awarded from one chapter.

### Governance protections

- Demo questions cannot increase Potential Mastery.
- Blocked/review-negative calibration questions cannot increase Potential Mastery.
- Existing earned mastery is not visually erased because later inventory or access changes.
- Verification Due preserves the earned mastery level while clearly marking evidence freshness.
- No invented Node/Family/Seed identity is created by this UX update.

## Architecture boundaries preserved

- Universal Mastery logic from V6.3.0 RC2 is unchanged except release/simulation labels.
- Academic Reviewer Workspace remains disabled from the forward ScoreMax student/admin shell; Power House remains the reviewer system of record.
- Growth Engine remains an event/outbox boundary only; it receives no mastery authority.
- No database migration is required for V6.3.1.
- V6.3.1 uses a new local internal-live database filename to avoid accidentally reusing the V6.3.0 test database.
