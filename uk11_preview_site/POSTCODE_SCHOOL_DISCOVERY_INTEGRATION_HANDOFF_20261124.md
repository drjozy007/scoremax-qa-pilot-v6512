# UK 11+ School Discovery and Selection — Integration Handoff
Date: 24 November 2026
Status: PREVIEW CODE COMMITTED; RUNTIME / AUTHENTICATED INTEGRATION PENDING

## Existing features (reuse)
- Multi-school choice and deduplicated assessment routes in the UK preview
- School-aware student, practice, mocks, parent and mastery displays
- Candidate England / Northern Ireland catalogue with cycle-specific route uncertainty
- Outward postcode district lookup (Postcodes.io); approximate proximity from locality centres
- Four initial GIAS-identified school records with official website and register links
- Preview-only sessionStorage of selected school IDs in one browser tab

## Critical contract boundaries
- This is **not real account persistence**. Do not use the preview session storage as production profile storage.
- Do not infer or grant admission eligibility, test membership, subjects, mastery, or access permissions from a display-selected school alone.
- Persist selections **server-side** against the authenticated student/profile with parent permissions where applicable; do not store full postcode, street location or child identity in browser storage.
- On login: read saved selection -> resolve canonical school identity and academic-cycle route -> compute union of evidenced subjects and deduplicated tests -> render existing ScoreMax dashboard.
- Unknown/outdated school route: display pending evidence, never silently add expected subjects.
- Reusing same question across several examinations requires independently approved membership evidence in Power House.
- Source authority and provenance remain Power House-owned; routing UI is a consumer.

## Suggested interoperable data shape (DESIGN, NOT APPROVED CONTRACT)
- School record: internally stable school key, nation, authoritative establishment ID (URN for England, relevant official ID elsewhere), canonical name, website with verification source/date, geographic precision and location source
- Admission route: route key, provider, entry cycle, official specification source, verified school membership, optional additional stage, subjects with evidence and verification status
- Preference: authenticated learner ID, selected canonical school keys, entry cycle, version, updated timestamp, audit metadata
- Learner context response: selected school summaries, unique eligible test routes, approved subjects, pending mappings, next verified revision

## Acceptance suite (PENDING execution, not a pass report)
1. Search ST4, HP20, W1A and invalid/full postcode; no complete postcode enters API or storage.
2. Compare approximate ordering with known locality-centre reference samples; no displayed distance described as journey or catchment.
3. Verify each GIAS URN against school identity and official website; reject non-unique name-based automatic matches.
4. Choose two schools using same test: one test, one subject union; then add a school with new evidenced subjects.
5. Unknown, historic and alternative exam mappings: leave uncertainty visible and block unsupported claims.
6. Toggle schools, refresh same tab, verify preview-only IDs are restored. New browser/session must not pretend authenticated persistence.
7. In real ScoreMax test environment: logout/login and parent/student permissions, concurrent changes, invalid ID, withdrawn school, changed entry cycle, record migration and rollback.
8. Screen-reader keyboard navigation, narrow mobile layout, safe outbound links, input errors, and API failures.
9. Native practice, mocks, marking, plans and mastery must use server-scoped authorized routes, not client-only filters.
10. Check Render deployment commit exactly against intended GitHub SHA; never label live before HTTP/runtime verification.

## Unchanged and deliberately excluded
Pakistan production, immutable academic question records, login service and master contract are untouched.
No independent UK subject achievements, scores or entrance probabilities have been created.

## Launch verdict
Preview functionality: BUILT / code committed, not runtime-qualified.
School directory: PARTIAL verification; broader national identity and current-cycle admissions checks pending.
Real login and persistent school-scoped entitlements: PENDING.
