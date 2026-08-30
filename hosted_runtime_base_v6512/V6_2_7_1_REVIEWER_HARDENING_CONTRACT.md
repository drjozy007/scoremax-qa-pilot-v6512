# ScoreMax V6.2.7.1 Reviewer Hardening Contract

## Non-negotiable reviewer boundary

The reviewer portal remains a minimal QA-only environment. It has no direct publication, live-bank, student-attempt, mastery or Study Plan write path.

## Two-part invitation

An invitation is usable only when the reviewer possesses:

1. the one-time invitation link; and
2. the separate verification code supplied through a different communication channel.

Only hashes are stored. Eight failed code attempts lock the invitation. Admin must reissue a locked or legacy invitation.

## Timing evidence

Client heartbeats are claims, not authority. ScoreMax credits no more time than has elapsed on the server since the last accepted heartbeat or item opening. Rapid, duplicated or concurrent heartbeats cannot create additional time.

Time is accepted only when:

- the assignment is `IN_PROGRESS`;
- the item is incomplete;
- the item is the assignment's current open question;
- at least four seconds of server time have elapsed.

## Review independence

A round-two assignment must:

- reference a valid round-one assignment for the same batch;
- use a different reviewer;
- contain only questions currently in `SECOND_REVIEW_REQUIRED`;
- not overlap another round-two assignment.

These rules are enforced by transactional application checks and database uniqueness constraints.

## Migration rule

Unused V6.2.7 invitations have no separately recoverable verification code. Migration therefore clears their old token and moves them to `INVITATION_REISSUE_REQUIRED`. Existing completed or in-progress reviewer work is preserved.
