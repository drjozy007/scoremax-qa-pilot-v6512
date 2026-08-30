# Independent Review Brief — ScoreMax V6.2.3

Review the extracted ZIP, not the build folder.

## Highest-risk questions

1. Does the compact dashboard genuinely reduce cognitive load, or merely hide an equally confusing structure inside tabs?
2. Can keyboard and screen-reader users operate every tab and Coach action?
3. Does any Matric student see unrelated live-bank subjects from other programmes or markets?
4. Can a Coming Soon subject reach a test-start route?
5. Can a manipulated issue-report URL attach another student's attempt?
6. Does a 60-question custom test remain within subject, access and approval constraints?
7. Can Growth Engine or social-link payloads expose an unapproved or non-HTTPS external link?
8. Do any dashboard/progress paths still emit Stretch or Peak as a mastery/performance level?
9. Does the weekly workload recommendation distinguish missing coverage evidence from actual 0% coverage?
10. Are teacher discovery and messages secondary without becoming undiscoverable when genuinely needed?

## Required live-browser sequence

- Log in with session version 0 and navigate Dashboard → Subjects → Biology → Plan → Exams → Progress → More.
- Repeat at desktop, tablet and narrow mobile widths.
- Use browser back/forward with dashboard, Study Plan and Exam tabs.
- Save a Matric pathway, snooze a Coach suggestion, build a 60-question/60-minute test, and report a question.
- Increment `session_version` in the database and confirm immediate invalidation.

## Regression suites

Expected total: **219** passing checks.

Do not accept the release solely because automated tests pass. Challenge scroll length, hierarchy, empty states, focus states, touch targets, contrast, wording and route integrity using real browser sessions.
