# ScoreMax V6.2.7 Acceptance Checklist

## Installation safety

- [ ] Keep V6.2.6 and its valuable database unchanged.
- [ ] Install V6.2.7 in a separate folder.
- [ ] Run the V6.2.6→V6.2.7 dry-run migration against a copied database.
- [ ] Confirm SQLite integrity is `ok` and no core counts are reduced.

## Teacher of the Year

- [ ] Landing page shows a prominent Coming Soon section.
- [ ] Dedicated public page loads without login.
- [ ] No nomination form or active nomination endpoint exists.
- [ ] Teacher of the Year is not added to the primary student learning tabs.

## Student navigation

- [ ] Dashboard, Learn, My Plan, Exams, Progress and More remain visible in the sticky desktop header.
- [ ] Submenus open on hover, click and keyboard focus.
- [ ] Enter, Space and Arrow Down open a submenu.
- [ ] Arrow Up/Down move within a submenu and Escape returns focus to its trigger.
- [ ] Mobile navigation remains usable without hover.
- [ ] Page-specific actions remain on the relevant page.

## Reviewer confidentiality

- [ ] Create a named reviewer account.
- [ ] Import a 100-question JSON/CSV/XLSX batch.
- [ ] Confirm a 101-question batch is blocked.
- [ ] Create a one-time invitation and copy it before leaving the page.
- [ ] Confirm the invitation expires and cannot be reused.
- [ ] Accept confidentiality terms and set a password.
- [ ] Confirm the reviewer sees no normal ScoreMax header, dashboard or navigation.
- [ ] Attempt direct URLs for student, teacher and Admin pages; confirm redirect to `/review`.
- [ ] Attempt another reviewer’s assignment/item URL; confirm denial.
- [ ] Confirm no bulk export is available.
- [ ] Confirm reviewer-specific watermark appears.

## Quiz-style review

- [ ] Reviewer sees only chapter/topic, question, answer/options, explanation, proposed mastery level, suitability, decision and comments.
- [ ] Question navigator shows completed, current and remaining items.
- [ ] Submit several items, sign out and sign back in; confirm exact resume at the next unfinished item.
- [ ] Return to a previously completed item within the assigned batch.
- [ ] Confirm comments are mandatory for all decisions except Accept unchanged.
- [ ] Complete all items and confirm the assignment closes only at 100/100.

## Timing and quality evidence

- [ ] Confirm active time rises while the tab is visible and the reviewer is active.
- [ ] Hide the tab, leave the computer idle and close the browser; confirm those periods are not counted as active time.
- [ ] Confirm answer reveal, return visits, edits and submission time are recorded.
- [ ] Complete items unusually quickly and confirm risk flags appear without blocking submission.
- [ ] Confirm Admin sees per-item time, total time, median time, reveal gaps, decision runs and calibration results.
- [ ] Confirm no rigid minimum-time lock exists.

## Review governance

- [ ] Accept an item unchanged and confirm first-review acceptance is recorded.
- [ ] Select Correction required, Mastery level unsuitable, Reject and Unsure; confirm second review is required.
- [ ] Attempt assigning the same first reviewer as second reviewer; confirm rejection.
- [ ] Assign an independent reviewer only the flagged questions.
- [ ] Submit matching decisions and confirm second-review agreement.
- [ ] Submit a disagreement and confirm adjudication is required.
- [ ] Confirm earlier decisions become locked after independent review/adjudication begins.
- [ ] Confirm no reviewer can publish, activate or promote questions.

## Human acceptance boundary

- [ ] Test on Chrome, Edge, Safari and a mobile browser.
- [ ] Test keyboard-only and 200% zoom.
- [ ] Review legal/confidentiality wording.
- [ ] Test real SMTP invitation delivery before external reviewer use.
