# ScoreMax V6.3.2 — Windows Login / Founder Walkthrough

1. Extract the ZIP into a **new folder**. Do not overwrite V6.3.1.
2. Open Command Prompt in that folder.
3. Run: `python -m pip install -r requirements.txt`
4. Double-click: `start_scoremax_v6_3_2_internal_live.bat`
5. Open: `http://127.0.0.1:5000`
6. Use the normal student registration flow for the walkthrough. This intentionally tests registration as part of the real journey.

The launcher uses a new `internal_live_data/scoremax_v6_3_2_internal_live.db`, so the V6.3.1 internal-test database is not upgraded in place.

For the walkthrough, stop after logging in and start at **Home**. We will then inspect each page in order rather than making untracked changes across several screens at once.
