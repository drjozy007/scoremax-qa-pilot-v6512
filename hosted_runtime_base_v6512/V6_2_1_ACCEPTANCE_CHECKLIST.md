# ScoreMax V6.2.1 Browser Acceptance Checklist

Use a copied pilot database and a stable `SCOREMAX_SECRET`.

## Critical session sequence

1. Create or select an active user whose `session_version` is `0`.
2. Sign in through the real browser form.
3. Open Dashboard, Practice, Study Plan and Exam Centre on successive requests.
4. Confirm the user remains authenticated and is not redirected to Login.
5. Refresh the page and open a second protected route.
6. Sign out and sign in again.

## Non-zero session

1. Set the user session version to a non-zero value through the normal application flow.
2. Sign in and confirm repeated navigation remains authenticated.

## Invalidation security

1. Sign in in Browser A.
2. Complete a password reset for the same account in Browser B or through the approved reset route.
3. Return to Browser A and open a protected page.
4. Confirm Browser A is logged out.
5. Disable the account and confirm an existing session is rejected.

## Regression acceptance

- Run the V6.2 content import preview and cancel safely.
- Confirm Admin Pilot Readiness loads.
- Confirm Teacher Discovery and Academic Messages load for enabled pilot users.
- Confirm Written Response pilot pages load.
- Confirm Blueprint and Exam Structure pages load.

Do not begin the real-user pilot until the critical session sequence passes in Chrome/Edge and on a mobile browser.
