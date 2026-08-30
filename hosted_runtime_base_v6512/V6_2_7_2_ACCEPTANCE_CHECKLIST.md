# ScoreMax V6.2.7.2 Acceptance Checklist

## Installation

- [ ] Keep the V6.2.7.1 installation and database unchanged.
- [ ] Install V6.2.7.2 in a separate folder.
- [ ] Start it using a copied database.
- [ ] Confirm the terminal identifies V6.2.7.2 and SQLite starts without integrity errors.

## Login page

- [ ] Confirm the field label reads **Email or User ID**.
- [ ] Confirm the browser accepts `admin`, `ADM-000001` and IDs such as `STU-000123`.
- [ ] Confirm the field does not enforce email-only browser validation.
- [ ] Confirm password-manager autocomplete still recognises the field as a username field.

## Account login

- [ ] Log in using a registered email address.
- [ ] Log in using the same account's formal ScoreMax User ID.
- [ ] Confirm an existing assigned username still works.
- [ ] Confirm identifiers are case-insensitive.
- [ ] Confirm Admin can use `admin` or `ADM-000001`.
- [ ] Confirm reviewer login still opens only the Reviewer Workspace.

## Security and failure behaviour

- [ ] Confirm a wrong password shows `Invalid login details.`.
- [ ] Confirm an unknown identifier shows the same message.
- [ ] Confirm a disabled account cannot log in.
- [ ] Confirm the existing login-attempt rate limit still applies.
- [ ] Confirm stale session-version invalidation still works.
- [ ] Create a controlled cross-field identity collision in a test database and confirm login is rejected rather than selecting either account.

## Regression

- [ ] Run all inherited smoke suites.
- [ ] Run `python smoke_tests_v6_2_7_2.py`.
- [ ] Complete a real Chrome/Edge login test using email and User ID.
- [ ] Complete one mobile-browser login test.
