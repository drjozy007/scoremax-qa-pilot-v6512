# ScoreMax V6.2.8.1 Changelog

## Fixed

- Excel imports no longer read only the active first worksheet.
- Question-bearing worksheets are detected by header evidence across the workbook.
- Instructional/reference sheets are ignored automatically.
- Added exact Power House V3 mappings for `Question / Task`, `Key Answer`, `Explanation / Marking Rubric`, `Statements / Options`, `Stimulus / Context`, mastery and review-governance fields.
- Rubric-based constructed responses import when no separate key cell is provided.
- Combined option/statement fields are preserved and lettered options are parsed where available.
- Source worksheet and row lineage are preserved.
- Automatic 100-question batching never crosses source-sheet boundaries.
- Pre-governed dual-review items remain second-review-required after an unchanged first review.
- Import previews now report detected question sheets and row counts.
- Error reports identify the source worksheet and row.

## Added

- V6.2.8→V6.2.8.1 migration utility.
- Full-scale 3,566-record Power House V3 structural regression fixture.
- 19 dedicated V6.2.8.1 compatibility/governance checks.
