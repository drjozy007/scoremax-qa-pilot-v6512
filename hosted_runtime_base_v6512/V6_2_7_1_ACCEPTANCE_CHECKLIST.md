# ScoreMax V6.2.7.1 Acceptance Checklist

## Installation and migration

- [ ] Keep V6.2.7 and its database unchanged.
- [ ] Install V6.2.7.1 separately.
- [ ] Run the V6.2.7→V6.2.7.1 dry-run migration on a copied database.
- [ ] Confirm integrity `ok`, counts preserved and all three unique indexes present.
- [ ] Confirm unused old invitations become `INVITATION_REISSUE_REQUIRED` with no retained token.

## Two-part invitation

- [ ] Create an assignment and copy both the link and verification code.
- [ ] Send them through separate channels.
- [ ] Confirm the link alone cannot activate the account or change its password.
- [ ] Confirm a wrong code increments the attempt count.
- [ ] Confirm eight wrong codes lock the invitation.
- [ ] Reissue the invitation and confirm the old link/code no longer work.
- [ ] Confirm the correct link/code combination activates exactly once.
- [ ] Confirm a different logged-in ScoreMax identity cannot accept the invitation.

## Active-time integrity

- [ ] Confirm normal five-second heartbeats add approximately five server-reconciled seconds.
- [ ] Fire rapid repeated heartbeats and confirm they add zero extra time.
- [ ] Open the same question in two tabs and confirm time is not doubled.
- [ ] Open a different question and confirm the old tab no longer receives time.
- [ ] Submit a decision and confirm that item receives no further time.
- [ ] Complete/revoke an assignment and confirm timing stops.
- [ ] Confirm discarded requests are visible in time-event evidence.

## Governance and concurrency

- [ ] Call the shared assignment engine without a parent for round two; confirm rejection.
- [ ] Attempt self-assignment as second reviewer; confirm rejection.
- [ ] Confirm only `SECOND_REVIEW_REQUIRED` questions can enter round two.
- [ ] Submit concurrent duplicate imports; confirm exactly one batch commits.
- [ ] Submit concurrent first-review assignments; confirm exactly one commits.
- [ ] Submit concurrent second-review claims for one question; confirm exactly one commits.

## Comment quality and packaging

- [ ] Confirm punctuation-only and repeated-character comments are rejected.
- [ ] Confirm concise, meaningful academic comments are accepted.
- [ ] Confirm the release ZIP contains no `private_uploads`, `content_intake_uploads` or `pilot_backups` artifacts.

## Remaining human acceptance

- [ ] Test Chrome, Edge, Safari and mobile browsers.
- [ ] Test keyboard-only, screen reader and 200% zoom.
- [ ] Test the real invitation-delivery workflow using genuinely separate channels.
- [ ] Review legal and confidentiality wording.
- [ ] Run a controlled session with an external academic reviewer.
