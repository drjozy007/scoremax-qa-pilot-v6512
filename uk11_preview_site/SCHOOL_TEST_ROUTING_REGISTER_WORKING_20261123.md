# SCOREMAX UK 11+ — School-to-Test Routing Register (Working Preview)

Date: 23 November 2026
Status: **WORKING / PARTIAL AUTHORITY COVERAGE / NO PRODUCTION RELEASE**
Branch: `preview/uk11-static-site-20261123`
Entry cohort shown: September 2028 (tests typically sat in 2027).

## Product requirement

A learner can search and select **one or many schools**. ScoreMax derives a distinct list of applicable examination routes (deduplicated across schools), plus a union of evidenced subject requirements. School selection alone does **not** establish admissions eligibility. If a school has no confirmed or historical routed exam, show **mapping pending**, not an invented test. Retain separate school, route, provider and cycle keys.

This is a static demonstration of the school selector and evidence statuses, not a complete validated national admissions database.

## Catalogue coverage in this version

- **231 selectable candidate entries**: 168 England (163 state grammar directory candidates, three CSSE additional schools, two partially selective) and 63 Northern Ireland candidate schools.
- **No independent-school catalogue** yet. ISEB appears only as an independent assessment route and is not automatically assigned to unverified schools.
- Scotland/Wales independent-school route assessment not yet undertaken. There is no assertion that all UK selective/independent schools are covered.
- All school identities need final reconciliation against official UK school registers, including Get Information About Schools (GIAS), Northern Ireland official school directories, academy renamings, mergers, and possible school-specific year-of-entry changes.

| Mapping state | Candidate school count | How preview behaves |
|---|---:|---|
| CURRENT_CYCLE_OFFICIAL | 11 | 2028 route populated from school/consortium publication |
| PRIOR_CYCLE_OFFICIAL | 64 | Historical shared route populated with explicit 2028 confirmation warning |
| REGIONAL_CANDIDATE | 27 | Regional route suggested with individual-school confirmation required |
| MULTI_OR_ALTERNATIVE_TEST_REVIEW | 7 | No forced one-test mapping |
| SCHOOL_ROUTE_UNVERIFIED | 59 | No automatic exam assignment |
| SEAG_MEMBERSHIP_UNVERIFIED | 63 | School searchable, but SEAG membership not inferred |
| **Total** | **231** | Not all authoritative or complete |

These values are generated from the static catalogue and route logic, not official totals for the UK market. They do not represent final admissions coverage.

## Confirmed or historical relationships surfaced

1. **Slough Consortium (2028 entry) — 4 schools — Quest Assessments.** Herschel, Langley, St Bernard's Catholic, Upton Court. **Official 2028 source:** https://www.herschel.slough.sch.uk/year-7-admissions-2028/ . 2028 testing described as two papers combining Maths, English, Verbal Reasoning and Non-Verbal Reasoning.
2. **Buckinghamshire grammar schools (2027 entry reference) — 13 schools — GL Assessment.** 2028 requirements pending. **Official source:** https://www.buckinghamshire.gov.uk/schools-libraries-and-parks/school-admissions-and-appeals/guides-and-policies/guide-to-grammar-schools-and-the-secondary-school-transfer-test-11-plus/
3. **CSSE (2027 entry reference) — 10 member schools — CSSE test.** 2028 re-verification pending. **Official source:** https://csse.org.uk/storage/2026/03/CSSE-Information-Guide-2027-Entry.pdf
4. **Sutton SET (2027 entry reference) — six schools — first-stage shared selective test.** The five grammar schools have additional school-specific second-stage requirements; Greenshaw is a partially selective school. **Official source:** https://www.sutton.gov.uk/schools-and-learning/school-admissions/apply-start-secondary-school/secondary-school-tests-assessments-and-supplementary-forms
5. **West Midlands Grammar Schools (2027 entry reference) — 19 candidate school matches in the preview.** Exact memberships, all pathways and 2028 provider/format require current-policy review. **Official source:** https://www.birmingham.gov.uk/info/20119/school_admissions/584/grammar_schools_in_birmingham/
6. **Kent Test — 27 regional school-route candidates, not school-level verified 2028 memberships.** Five flagged for possible alternatives including Dover/Folkestone/Cranbrook. **Official source:** https://www.kent.gov.uk/education-and-children/schools/school-places/kent-test
7. **SEAG Northern Ireland — 63 candidate school names.** Individual SEAG 2028 participation was not verified; no automatic assignment. **Official directory start:** https://seagni.co.uk/

8. **Gloucestershire Grammar Schools (2028 entry) — 7 schools — FSCE.** County council confirms the provider change for 2028; includes cross-curricular Compass content outside the four currently supported ScoreMax subjects. **Official source:** https://www.gloucestershire.gov.uk/schooladmissions/grammar-schools/
9. **Bexley Selection Test (2027 entry) — 4 schools — Quest Assessments.** Distinct from Kent/Medway. **Official source:** https://www.bexley.gov.uk/services/schools-and-education/selection-tests/about-test
10. **Medway Test (2027 entry) — 6 schools — GL Assessment.** Chatham Grammar also accepts the **Kent Test OR Medway Test**. The alternate is not a requirement to sit both. **Official source:** https://www.medway.gov.uk/medwaytest
11. **Wirral non-Catholic grammar assessment (2027 entry) — 4 schools — Quest Assessments.** St Anselm's College and Upton Hall School FCJ use separate assessments and are not assigned this route. **Official source:** https://www.wirral.gov.uk/schools-and-learning/school-admissions/secondary-education-information-parents
12. **Redbridge 11+ (2027 entry) — 2 schools — GL Assessment.** Ilford County High and Woodford County High; check catchment. **Official source:** https://www.redbridge.gov.uk/11plus

## Architectural test

Three selected schools:
- Aylesbury Grammar School (Bucks Secondary Transfer Test)
- Aylesbury High School (same Bucks route)
- Herschel Grammar School (Slough Consortium)

**Expected:** 3 school selections → 2 distinct tests → deduplicated union of relevant subjects (Maths, English, verbal and non-verbal reasoning). The current preview logic satisfies this synthetic evaluation. It does not represent qualified admissions or production API behaviour.

**Alternative test example:** Dover Grammar School for Boys is explicitly flagged *alternative/school-specific route review*, not force-populated with Kent Test.

**Unknown test example:** Antrim Grammar School is searchable, but SEAG membership and current entry route remain pending until official proof.

## Known limitations / source integrity

- Directory names initially assembled from public historical lists and must be checked against official school identifiers and admissions policies. Exact national coverage is **not** established.
- The 2028 Slough and Gloucestershire routes have official evidence. Most other mapped schools use 2027-entry references or regional candidate associations; they are **not certified 2028 mappings**.
- Some schools require more than one exam or allow alternatives. The eventual canonical model must represent **AND, OR, sequential and conditional** route dependencies, not just an array of exam IDs.
- School year-of-entry and test year differ. The UI must distinguish September **2028 entry** from testing in **2027**.
- The static interface stores no selections between page loads, has no child account or live learning data, and does not submit exam registrations.
- Northern Ireland / Scotland / Wales independent and special admissions pathways, independent schools (including ISEB Common Pre-Tests users), and partial-selective schools outside the small sample must still be researched.

## Backend ownership for Chat 3

Reuse the existing ScoreMax school routing and study-plan engines. Do **not** copy the static preview as a new production backend.

Conceptual relationships, not approved field names:

- School (official identity / location / phase / status)
- Admissions route (authority, provider, cycle, route version)
- School route membership (evidence URL, effective dates, mandatory/alternative/conditional, verification status)
- Test specification (subjects, skills, format, timing/scoring only with official evidence)
- Learner target schools (multi-select, role permissions and privacy)
- Deduplicated preparation plan (canonical eligible question versions, evidenced route memberships)

Key rule: a school with no accepted current-cycle route cannot produce an authoritative exam assignment. Historical route can only appear as a **provisional reference**.

## QA gates

- **PASSED (local code simulation):** JavaScript syntax; full catalogue parse; distinct school same-name resolution (e.g. Queen Elizabeth's Grammar Schools in different towns, King Edward VI in different areas); 3-school → 2-test union; pending NI school does not create an exam.
- **PENDING:** live browser/mobile/keyboard accessibility test, fully authoritative school identity matching, 2028 membership verification of all entries, full multi-exam AND/OR logic, production ScoreMax routing integration.
- **N/A:** academic question approval or native marking (not part of this UX workstream).

**Release gate:** Do not market the directory as complete or ready to determine school admissions routes until the authority register is fully verified.
