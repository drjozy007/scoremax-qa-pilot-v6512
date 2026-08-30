# ScoreMax V6.2.7.2 Changelog

## Added

- one shared login field labelled **Email or User ID**;
- login by registered email;
- login by formal `system_user_id`;
- continued login by existing assigned username;
- case-insensitive lookup and uniqueness indexes for email, username and system User ID;
- explicit ambiguity rejection when one supplied identifier matches more than one account;
- 13 login compatibility and security regression checks.

## Changed

- the login input is now `type="text"` with `autocomplete="username"`, so browsers no longer reject values such as `admin` or `STU-000123`;
- login failures now use the neutral message `Invalid login details.`;
- release health marker and startup messages now identify V6.2.7.2.

## Preserved

- password verification;
- login rate limiting;
- account-status checks;
- session-version invalidation;
- role-based redirects;
- reviewer route isolation;
- backward compatibility for older clients posting the previous `email` form key.
