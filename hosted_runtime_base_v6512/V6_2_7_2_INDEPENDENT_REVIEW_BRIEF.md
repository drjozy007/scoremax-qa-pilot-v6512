# Independent Review Brief — ScoreMax V6.2.7.2

Review this as a narrow login compatibility patch over the independently reviewed V6.2.7.1 baseline.

Verify independently that:

1. the visible login field is labelled **Email or User ID** and uses a text input;
2. registered email, formal `system_user_id` and existing username each authenticate the same intended account;
3. matching is case-insensitive but exact after normalisation;
4. a cross-field collision cannot cause ScoreMax to choose the wrong user;
5. unknown, ambiguous and wrong-password attempts do not enumerate accounts;
6. password hashing, account-status checks, rate limiting, session-version handling and role redirects remain unchanged;
7. reviewer accounts still enter only the isolated Reviewer Workspace;
8. older clients posting the legacy `email` form field remain compatible;
9. case-insensitive identity indexes are created safely and do not corrupt an existing database;
10. all inherited suites and the new V6.2.7.2 suite reproduce the claimed total.

Do not modify source code during the first review. Report exact files, lines, commands, reproduced results and any regression or ambiguity risk.
