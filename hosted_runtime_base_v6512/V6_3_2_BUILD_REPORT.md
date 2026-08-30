# ScoreMax V6.3.2 Build Report

Parent: ScoreMax V6.3.1 Student UX V2 Candidate
Parent SHA-256: `a0f7a03b712671330b4f7e560192acb3d772a39eea413bf5eef70091abb85312`

Decision: extend V6.3.1 rather than redesign. The user-visible issue was inconsistent chapter identity, not a mastery-engine defect.

Implementation:
1. Added a governed chapter display catalogue without changing raw academic/question identity.
2. Added deterministic source-label parsing with no academic guessing.
3. Added governed `Chapter Number` / `Chapter Name` import support.
4. Reused the display identity across the main student journey.
5. Preserved Existing Mastery / Potential Mastery calculations and URLs/filter keys.
6. Added adjacent XSS hardening to Practice's dynamic chapter controls.
7. Created a fresh V6.3.2 local DB path to avoid upgrading V6.3.1 internal-test data in place.

Acceptance evidence: see `V6_3_2_ACCEPTANCE.md`, `V6_3_2_ACCEPTANCE_RUN_2026_08_17.txt` and `V6_3_2_SIMULATION_RESULTS.json`.
