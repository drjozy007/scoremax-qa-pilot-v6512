# ScoreMax V6.2.6 Build Report

## Release

**ScoreMax V6.2.6 — Pre-Pilot Assurance & Mastery Laboratory**

Built from the verified V6.2.5 baseline.

## Delivered milestone

```text
Import governed question candidates
→ preserve question family and mastery metadata
→ record seed / variant / scaffold relationships
→ score different question families
→ write evidence to concepts and LOs
→ calculate provisional laboratory mastery
→ identify recovery needs
→ replay synthetic student histories
→ explain every mastery decision
```

## Architecture

The laboratory is a separate admin-only subsystem using dedicated `mastery_lab_*` tables. There is no promotion route and no write path into live questions, attempts or mastery.

## Candidate import

- JSON, CSV and XLSX.
- Maximum 10,000 rows per batch.
- Whole-batch structural validation.
- Atomic `BEGIN IMMEDIATE` transaction.
- Exact-payload duplicate protection.
- Source checksum and external question/version identity.
- Unresolved warnings preserved.
- Technical test proved a 322-row Chapter 1 import.

## Question families

Twelve distinct family identities are supported, including four-statement selection, cloze, matching, ordering, multiple response, numerical, constructed response, misconception and stimulus-based items.

## Evidence independence

Closely related items are grouped by seed or stimulus identity and capped before mastery metrics are calculated. Scaffold and recovery evidence cannot independently verify a level.

## Mastery Laboratory

- Four configurable technical policy levels: Foundation, Exam Ready, Advanced and Distinction.
- Thirteen explicit internal states.
- Concept and learning-outcome ledgers.
- Mastery-ceiling eligibility.
- Recovery-need register.
- Explainable state history and next actions.
- Seven deterministic synthetic profiles.

These policies are QA defaults, not final academic standards and not real mastery policy.

## Assurance gates

- Gate 1: Content Admission.
- Gate 2: Assessment Execution.
- Gate 3: Mastery and Study Plan.
- Gate 4: Security, Privacy and Isolation.
- Gate 5: Release Acceptance for the QA milestone only.

## Testing

| Suite | Checks |
|---|---:|
| V5.5 Blueprint and Calibration | 52 |
| V6.0 Written Response | 34 |
| V6.1 Teacher Discovery and Messages | 41 |
| V6.2 Pilot Readiness and Intake | 30 |
| V6.2.1 Session Integrity | 10 |
| V6.2.2 Navigation and Subjects | 19 |
| V6.2.3 Student Command Centre | 33 |
| V6.2.4 Curriculum Isolation and Accessibility | 14 |
| V6.2.5 Sustainability and Daily Spark | 34 |
| V6.2.6 Mastery Laboratory | 66 |
| **Total** | **333** |

V6.2.6-specific challenges include:

- 322-candidate import;
- structural rejection;
- forced mid-import failure and rollback;
- clean retry;
- duplicate import rejection;
- correct/incorrect scoring across every family;
- partial scoring challenges;
- identity caps;
- explicit state transitions;
- seven synthetic histories;
- live-ID collision blocking;
- warning preservation;
- admin-only route checks;
- no live attempt/mastery writes.

## Migration rehearsal

A genuine V6.2.5 database with sentinel user and attempt records was copied and migrated in dry-run mode.

- SQLite integrity: `ok`.
- No reduced core counts.
- 14 laboratory tables created.
- 4 laboratory policies seeded.
- 7 synthetic profiles seeded.
- 0 candidate questions imported by migration.
- 0 live attempt leaks.
- 0 live mastery leaks.

## Honest boundaries

- The actual 322 Chapter 1 candidate corpus was not supplied in this build session; a structurally equivalent 322-row corpus proved scale and transaction behaviour.
- Laboratory thresholds are configurable technical defaults and require academic calibration.
- Constructed-response production marking remains dependent on governed rubrics/manual or future external marking.
- No real browser, assistive-technology or realistic load test was available in this restricted environment.
- V6.2.6 does not approve, publish or promote candidates.
- The Growth Engine was deliberately not expanded in this release.

## Packaged release verification

The clean release ZIP was extracted into a separate directory and verified independently of the working source.

- Internal SHA-256 manifest: 222 packaged source/data/document files verified.
- Python compilation: passed.
- Extracted-package regression: all 333 checks passed.
- Fresh V6.2.5-to-V6.2.6 migration dry-run: passed.
- SQLite integrity after rehearsal: `ok`.
- Core data counts: preserved.
- Laboratory after migration: 0 candidates, 4 policies and 7 synthetic profiles.
- Live attempt leakage: 0.
- Live mastery leakage: 0.
