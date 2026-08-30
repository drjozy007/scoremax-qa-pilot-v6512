# ScoreMax V6.2 Browser Acceptance Checklist

## Baseline

- [ ] Launch from a copied V6.1 database.
- [ ] Existing student, teacher, parent and Admin accounts work.
- [ ] V5.5 Exam Structure/blueprint views remain correct.
- [ ] V6 written-response pages remain correct.
- [ ] V6.1 teacher discovery and messaging remain correct.

## Pilot Readiness

- [ ] Admin can open Pilot Readiness.
- [ ] Manual backup downloads and opens with integrity `ok`.
- [ ] Demo quarantine requires the exact confirmation phrase.
- [ ] Demo content disappears from pilot evidence but configuration remains.

## Prompt Bridge

- [ ] Valid sample prompt pack imports.
- [ ] Tampered checksum is rejected.
- [ ] Production-mode unsigned or invalidly signed prompt pack is rejected.
- [ ] Complete prompt copies correctly.
- [ ] Provider/model can be recorded.
- [ ] Valid output is stored as candidate only.
- [ ] Exported return opens as valid JSON for Power House.

## Content Intake

- [ ] CSV and XLSX previews persist after logout/login.
- [ ] Original source file downloads and matches its checksum.
- [ ] Duplicate IDs block the entire batch.
- [ ] One invalid row blocks all rows.
- [ ] Confirmation automatically creates a backup.
- [ ] All questions import as Draft + inactive.
- [ ] Spreadsheet Approved values do not publish.
- [ ] Candidate summary is clearly not production inventory.
- [ ] Unused batch rolls back safely.
- [ ] Used or academically reviewed batch cannot be deleted by rollback.

## Pilot Issues and Analytics

- [ ] Student can report a question issue from phone and desktop.
- [ ] Academic issue routes to Power House.
- [ ] Technical issue routes to ScoreMax.
- [ ] Admin can triage, resolve and preserve history.
- [ ] Pilot analytics loads without demo inflation.
- [ ] Failed processing job can be re-queued.

## Knowledge Hub

- [ ] Hidden state shows no public articles.
- [ ] Admin can create a sourced manual draft.
- [ ] Growth Engine JSON becomes Draft only.
- [ ] Publishing requires a human action.
- [ ] Public article renders on mobile.

## Sign-off

- [ ] Academic owner
- [ ] Product owner
- [ ] Technical reviewer
- [ ] Safeguarding/privacy reviewer where applicable
