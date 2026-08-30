# ScoreMax V6.2.8.1 Acceptance Checklist

## Automated acceptance

- [x] All inherited V5.5–V6.2.8 regression suites pass.
- [x] Power House V3 workbook structure detects only the three review sheets.
- [x] 1,199 / 1,168 / 1,199 source counts are preserved.
- [x] 3,566 records import with zero structural exclusions in the governed fixture.
- [x] 36 batches are created: 12 per source sheet.
- [x] No ScoreMax batch mixes source worksheets.
- [x] Standard MCQ options are parsed from `Statements / Options`.
- [x] Matching/statement content is preserved.
- [x] Rubric-only constructed responses import safely.
- [x] Stimulus/context is preserved in the minimal reviewer snapshot.
- [x] Source sheet and row lineage are retained.
- [x] Pre-governed dual-review items route to second review after unchanged acceptance.
- [x] Migration rehearsal preserves existing records and SQLite integrity.

## Human acceptance still required

- [ ] Upload the actual `PH_CH1_Final_Academic_Review_Workbook_Post_AI_Assurance_v3_0.xlsx` through the Admin UI.
- [ ] Confirm the preview displays the three review sheets and 3,566 detected records.
- [ ] Confirm the actual workbook produces 36 batches and no unexpected exclusions.
- [ ] Open representative Standard MCQ, matching, four-statement, two-tier, short constructed and extended response items as a reviewer.
- [ ] Confirm answer/rubric presentation is academically usable.
- [ ] Review mobile/browser/accessibility behaviour.
- [ ] Conduct an external academic reviewer usability session before wider rollout.
