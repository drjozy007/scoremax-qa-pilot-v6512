# ScoreMax V6.2.2 — Student Navigation & Subject Flow

## Purpose

This release fixes the subject drill-down defect reported during real browser acceptance and simplifies the student navigation before pilot use.

## Student subject journey

- `/student/subjects` is now only the all-subject selection page.
- `/student/subject/<subject>` renders a dedicated one-subject page.
- Biology can only render Biology data; Chemistry and Physics remain separate routes.
- Subject matching is case-insensitive.
- The all-subject quick strip is not redrawn on a subject-detail page.
- The selected subject page shows its own status, evidence count, test action and chapters.
- A clear `All subjects` link returns to the subject browser.

## Student navigation

Desktop top-level navigation is reduced to:

- Dashboard
- Learn
- My Plan
- Exams
- Community
- Account

Detailed practice scopes, utilities and settings are moved inside the appropriate dropdowns or destination pages. Duplicate written-practice, Access and Settings links are removed from the visible top level.

Mobile bottom navigation is reduced to:

- Home
- Learn
- Plan
- Exams
- More

## Migration

No database migration is required from V6.2.1.
