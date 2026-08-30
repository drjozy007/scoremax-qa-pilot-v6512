# ScoreMax V6.3.1 — Superseded Historical UX Assertions

**Date:** 17 August 2026  
**Reason:** Student UX V2 is an explicit product decision, not an accidental regression.

ScoreMax V6.3.1 intentionally replaces the V6.2.x student shell that used eight persistent primary tabs plus a contextual secondary row. The V6.3.0 RC2 parent remains immutable and retains those original historical tests exactly as accepted.

For V6.3.1, the original affected test files are preserved under `frozen_legacy_ux_assertions/` before updating only the assertions that described the superseded presentation. Non-UX capability assertions remain unchanged.

## Explicitly superseded UI contracts

- **V6.2.2:** eight desktop student journeys → six core learning journeys plus account/support menu.
- **V6.2.3:** Dashboard/More shell and four dashboard workspace tabs → Home centred on Today's Focus, with support outside the core daily-action surface; Practice tab wording updated.
- **V6.2.5:** exact labels `Academic Spark` / `Word of the Day` → compact learner labels `Academic` / `Word of the day`; Sustainability remains outside core learner navigation.
- **V6.2.7:** secondary-navigation accessibility contract → simplified two-row contract: primary navigation + subject strip, with mobile bottom navigation.
- **V6.2.8:** eight persistent primary tabs + contextual row → six primary journeys + subject strip + supporting account menu.
- **V6.3.0 application wiring:** release marker `6.3.0` → descendant release marker `6.3.1`; compatibility parent remains `6.2.8.1`.

## Current accepted learner shell contract

**Desktop core:** Home · Learn · My Plan · Practice · Exams · Progress  
**Second row:** subject switcher only  
**Supporting destinations:** profile/account menu  
**Mobile bottom bar:** Home · Learn · Plan · Practice · More

The old tests were not hidden, deleted, or made to pass using invisible legacy labels. They are frozen for audit and the current tests now assert the accepted V6.3.1 experience directly.
