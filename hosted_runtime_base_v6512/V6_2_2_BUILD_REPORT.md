# ScoreMax V6.2.2 Build Report

## Release

**ScoreMax V6.2.2 — Student Navigation & Subject Flow**

## Baseline

Built from the verified V6.2.1 Session Integrity Hotfix. No database schema was changed.

## Defect corrected

The prior `subject_detail()` route loaded `_subject_map()` and rendered `subject_browser.html` again with both `subjects` and `selected`. This meant that after choosing Biology the student was shown the full Biology/Chemistry/Physics browser again, creating a confusing and error-prone journey.

V6.2.2 separates the routes and templates:

- all-subject browser: `subject_browser.html`
- one-subject detail: `subject_detail.html`

The one-subject template receives only the selected subject object.

## UX simplification

The student desktop header now exposes only Dashboard, Learn, My Plan, Exams, Community and Account. Detailed routes remain available inside the correct dropdown or destination page. The mobile bottom bar is Home, Learn, Plan, Exams and More.

## Automated verification

- V5.5 blueprint/calibration: 52 passed
- V6.0 written response: 34 passed
- V6.1 teacher discovery/messages: 41 passed
- V6.2 pilot readiness/content intake: 30 passed
- V6.2.1 session integrity: 10 passed
- V6.2.2 navigation/subject flow: 19 passed
- **Total: 186 passed**

Python compilation passed. Existing template parsing, route-reference and CSRF checks remained green through the inherited suites.

## Browser boundary

A genuine Flask browser could not be launched in this build container because Flask/Werkzeug are unavailable. The acceptance checklist therefore requires a real browser check of Biology, Chemistry, Physics, desktop menus and mobile navigation before pilot adoption.
