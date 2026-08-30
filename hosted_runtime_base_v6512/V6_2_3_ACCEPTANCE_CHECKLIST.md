# V6.2.3 Browser and Mobile Acceptance Checklist

Use a copied pilot database and at least these accounts:

- new Matric student with no attempts;
- Matric student with attempts and an active Study Plan;
- student with an in-progress test;
- student with teacher relationship/messages;
- admin.

## Dashboard

- [ ] At 1366×768, the command centre, quick actions and tab header are visible without passing multiple full-page sections.
- [ ] Only one dashboard workspace panel is visible at a time.
- [ ] Do This Now prioritises an in-progress test over all other actions.
- [ ] Teacher discovery and messages do not appear ahead of Practice, Plan, Exams or Progress.
- [ ] Mobile dashboard remains readable without horizontal overflow.

## ScoreMax Coach

- [ ] New Matric student receives pathway guidance before generic commercial/support prompts.
- [ ] Student with active test receives Continue test.
- [ ] Later suppresses the same suggestion temporarily.
- [ ] Dismiss suppresses it for the configured period.
- [ ] The non-dashboard Coach is collapsed by default and does not block the page.

## Subjects and pathways

- [ ] Matric student sees the current Matric catalogue, not only Biology/Chemistry/Physics.
- [ ] Subjects without approved bank depth show Coming Soon and cannot start a test.
- [ ] Selecting Biology opens Biology only.
- [ ] Pathway Explorer saves and changes a direction without altering the student's current academic level.
- [ ] Future assessment labels do not imply that an unavailable test is live.

## Study Plan

- [ ] Core, Stretch and Peak show weekly ranges rather than fixed minutes/day.
- [ ] Weekly availability accepts a realistic range and displays fit feedback.
- [ ] Today, This week, Roadmap and Settings panels switch correctly.
- [ ] Rebuilding preserves historical evidence and changes future activities only.

## Practice and tests

- [ ] Quick Start, Choose Scope and Design My Own tabs work on desktop/mobile.
- [ ] Custom count supports 60.
- [ ] Timing supports untimed, 15, 30, 45 and 60 minutes.
- [ ] A 60-question request is limited by approved inventory rather than filled from another subject.
- [ ] Authentic mock timing remains blueprint-controlled.

## Exams and Progress

- [ ] Exam Centre tabs open from direct hashes such as `#past-papers` and `#mocks`.
- [ ] Only one Exam Centre panel is visible.
- [ ] Progress tabs switch without losing evidence.
- [ ] Mastery levels display in the official order and never show Stretch or Peak.

## Help, Knowledge and social links

- [ ] FAQ search filters questions and reveals matches.
- [ ] Report this question auto-populates context without showing database IDs.
- [ ] General Report an Issue works without question context.
- [ ] Knowledge Hub link is visible and honours its feature state.
- [ ] Only admin-enabled HTTPS social links appear on Connect/footer.

## Regression

- [ ] Four protected pages remain accessible after a real login with `session_version=0`.
- [ ] A session-version bump logs the user out on the next request.
- [ ] Content import, rollback, messaging, written responses and blueprint mocks still work.
