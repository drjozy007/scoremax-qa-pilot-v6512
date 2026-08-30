# ScoreMax V6.2.8 Acceptance Checklist

## Installation and migration

- [ ] Install in a separate folder.
- [ ] Use a copied V6.2.7.2 database only.
- [ ] Dry-run migration reports SQLite integrity `ok`.
- [ ] Core and reviewer record counts are preserved.
- [ ] No entitlement or checkout is created automatically.

## Student navigation

- [ ] Eight primary tabs are visible on desktop/laptop.
- [ ] Clicking a primary tab updates the second row without opening a popup/overlay.
- [ ] Active primary and secondary destinations are clear.
- [ ] Mobile/small tablet uses reduced bottom navigation.
- [ ] Keyboard, focus, 200% zoom and screen-reader checks pass.

## Subject switcher and isolation

- [ ] Subject switcher appears on every agreed core student page.
- [ ] Included, Locked and Coming Soon states are understandable.
- [ ] Locked subjects are denied server-side by direct URL and form submission.
- [ ] Coming Soon subjects cannot start assessments.
- [ ] Empty programme inventory never falls back to another programme.

## Study Plans

- [ ] No hours, minutes, weekly availability or estimated duration appears.
- [ ] Plan creation does not ask for study hours.
- [ ] Priority, sequence, recall/recovery and evidence status remain clear.
- [ ] Exam dates/deadlines still function without generating prescribed hours.

## Reviewer import

- [ ] Upload a genuine non-template Excel/CSV/JSON file.
- [ ] Mapping suggestions are understandable.
- [ ] Question and Correct answer are the only essential mappings.
- [ ] Optional missing fields do not produce a raw “first row missing” failure.
- [ ] Preview and excluded-row report are accurate.
- [ ] A 3,000-question realistic file imports and splits into 30 batches of 100.
- [ ] A forced import failure rolls back every generated batch.
- [ ] Demo route allows inspection without a production file.

## Reviewer assignment and tracking

- [ ] Admin can select one, several or all generated batches.
- [ ] One invitation activates the assigned group only.
- [ ] Reviewer can stop after 100 or continue.
- [ ] Resume behaviour is exact across sessions and batches.
- [ ] Per-question time, decisions, comments, reveals and flags remain visible.
- [ ] Reviewer sees no normal ScoreMax route or confidential architecture.

## Commercial access

- [ ] Biology-only package unlocks Biology and locks other released subjects.
- [ ] Bundle/full package changes subject states immediately.
- [ ] Access tier remains separate from subject coverage.
- [ ] Upgrade preserves historic learning evidence.
- [ ] Account → Access clearly states that live checkout is not yet connected.
- [ ] Legal pricing, renewal, cancellation and refund wording is approved before launch.

## Public landing page

- [ ] Generic Daily Spark is visible without login and creates no visitor/mastery record.
- [ ] Logged-in Daily Spark appears near the top of the Dashboard.
- [ ] Available/Coming Soon programme cards are direct and prominent.
- [ ] About Us wording is consistent.

## Release decision

- [ ] No Critical/High defect remains.
- [ ] External independent review is reconciled.
- [ ] Controlled-pilot owner records the acceptance decision and restrictions.
