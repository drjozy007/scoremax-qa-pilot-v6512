# ScoreMax V6.2.2 Changelog

## Fixed

- Selecting Biology no longer reuses the all-subject template.
- A subject detail route cannot display another subject's chapter section.
- Subject matching now handles URL case safely.
- The global subject strip no longer redraws all subjects on the subject-detail page.
- Duplicate and competing student navigation links were removed.

## Changed

- Added a dedicated `subject_detail.html` template.
- Reduced desktop student navigation to six principal journeys.
- Simplified mobile bottom navigation to Home, Learn, Plan, Exams and More.
- Limited the quick subject strip to relevant learning pages.
- Updated health/version marker to 6.2.2.

## Database

No schema changes and no migration required.
