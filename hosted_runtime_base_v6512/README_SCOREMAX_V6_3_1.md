# ScoreMax V6.3.1 — Student UX V2 Candidate

This is the student-experience descendant of the rectified V6.3.0 RC2.

## Start on Windows

1. Extract this ZIP into a **new folder**. Do not overwrite V6.3.0 RC2.
2. Open Command Prompt in that folder.
3. Install declared dependencies once: `python -m pip install -r requirements.txt`
4. Run `RUN_SCOREMAX_V6_3_1_ACCEPTANCE.bat`.
5. Run `start_scoremax_v6_3_1_internal_live.bat`.
6. Open the localhost URL printed in the window.

The launcher creates a V6.3.1-specific fresh local database under `internal_live_data/` and enables internal full access for our own testing. Do not use this launcher as a public Internet deployment method.

## What to inspect first

- Home / Today's Focus
- Learn → Subject → chapter cards
- Existing Mastery vs Potential Mastery graph
- Chapter detail
- My Plan
- Practice
- Results / weak areas / recovery
- Progress
- Exams
- Mobile navigation

## Current status

`STUDENT_UX_V2_CANDIDATE_PENDING_WINDOWS_BROWSER_ACCEPTANCE`

See `V6_3_1_ACCEPTANCE.md` and `V6_3_1_BUILD_REPORT.md`.
