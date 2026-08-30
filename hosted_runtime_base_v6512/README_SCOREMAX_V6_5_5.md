# ScoreMax V6.5.5 — Power House Manifest Origin Security Rectification

V6.5.5 is a narrow security child of the exact frozen V6.5.4 candidate whose ZIP SHA-256 is:

`5c86d0fc9c703c5fd4c50b01442311a5f9e0897d0fbc45983b0a2794dbbcb7ee`

It closes only **INT-SM654-P0-001**. No mastery, learner UX, reviewer architecture, payments, referrals, Emergency Intake, or other cleared ScoreMax subsystem is redesigned.

## Security boundary

For Power House `MANIFEST_PULL`, ScoreMax now derives the trusted origin from deployment-controlled `SCOREMAX_POWER_HOUSE_BASE_URL`. Before reading `SCOREMAX_TO_POWER_HOUSE_TOKEN` or creating any network request, the package URL must have the same canonical HTTPS origin. Exact scheme/host/port comparison rejects cross-origin hosts, suffix-host confusion, URL userinfo tricks, unexpected ports, and non-HTTPS URLs. Redirects are permitted only within the same trusted Power House origin; cross-origin redirects are blocked before a redirected request can be constructed or sent.

Legitimate same-origin package pulls retain bearer authentication, governed ZIP/manifest/content checksum verification, and normal staging.

Windows qualification remains a separate infrastructure/CI gate and is not represented as passed by this package.
