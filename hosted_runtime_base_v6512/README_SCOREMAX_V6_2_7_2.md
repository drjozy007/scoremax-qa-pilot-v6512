# ScoreMax V6.2.7.2 — Email or User ID Login

V6.2.7.2 is a narrow login compatibility patch over V6.2.7.1. It does not add a new account type or change the Reviewer Workspace boundary.

## Login delivered

The shared login page now provides one field labelled:

> **Email or User ID**

It accepts:

- a registered email address;
- a formal ScoreMax system User ID, such as `STU-000123`, `TCH-000123`, `PAR-000123`, `REV-...` or `ADM-000001`;
- an existing assigned username, including the local bootstrap Admin username `admin`.

Matching is case-insensitive. Email, username and system User ID are checked together. If one identifier could refer to more than one account because of a cross-field collision, ScoreMax rejects the login rather than choosing an arbitrary account.

## Security preserved

- one neutral `Invalid login details.` response is used for unknown, ambiguous and wrong-password attempts;
- the existing login rate limit remains unchanged;
- password hashing and verification remain unchanged;
- disabled-account and session-version protections remain unchanged;
- reviewer accounts still redirect only to the isolated Reviewer Workspace;
- older local clients that still submit the legacy `email` form key remain compatible.

## Start locally

On Windows, run:

```text
start_scoremax_v6_2_7_2.bat
```

Or run:

```bash
python app.py
```

On first launch, use the one-time bootstrap Admin password printed in the terminal. The Admin can enter either `admin` or `ADM-000001` in the **Email or User ID** field.

## Upgrade

There is no destructive data migration. Install V6.2.7.2 separately and test it against a copied V6.2.7.1 database. See `V6_2_7_2_MIGRATION_GUIDE.md`.
