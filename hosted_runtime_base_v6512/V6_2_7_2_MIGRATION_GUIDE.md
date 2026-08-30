# ScoreMax V6.2.7.1 → V6.2.7.2 Migration Guide

## Safety rule

Do not replace the accepted V6.2.7.1 installation or its only database. Extract V6.2.7.2 into a separate folder and test it with a copied database first.

## Database impact

No table or data migration is required. During normal `app.init()` startup, V6.2.7.2 attempts to add case-insensitive unique indexes for:

- `users.email`;
- `users.username`;
- `users.system_user_id`.

If historical case-insensitive duplicates exist within one column, ScoreMax leaves that index unenforced and prints a terminal warning. Login remains safe because an identifier matching more than one account is rejected rather than resolved arbitrarily.

## Controlled upgrade steps

1. Keep the V6.2.7.1 folder and database unchanged.
2. Extract V6.2.7.2 separately.
3. Copy the V6.2.7.1 SQLite database into the V6.2.7.2 folder or point `SCOREMAX_DB` to a copied database.
4. Start V6.2.7.2 and confirm SQLite opens normally.
5. Test Admin login with `admin` and `ADM-000001`.
6. Test one student/teacher/parent/reviewer with both email and formal User ID where available.
7. Confirm unknown and wrong-password attempts show the same neutral response.
8. Keep V6.2.7.1 available for rollback until acceptance is complete.

## Rollback

Stop V6.2.7.2 and return to the untouched V6.2.7.1 installation and database. V6.2.7.2 does not rewrite account identifiers or passwords.
