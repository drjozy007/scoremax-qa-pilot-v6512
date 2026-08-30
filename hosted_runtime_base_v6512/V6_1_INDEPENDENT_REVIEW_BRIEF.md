# Independent Review Brief — ScoreMax V6.1

Review the actual V6.1 source package, not only this brief.

## Review priority

1. Confirm V6.0/V5.5 regressions remain intact.
2. Attempt to bypass accepted-enquiry requirements and create unsolicited teacher contact.
3. Attempt to enable student-to-student direct messaging.
4. Test under-18 DOB, parent-link, consent, re-check and revocation pathways.
5. Attempt to publish incomplete/unverified teacher profiles and listings.
6. Test contact-detail, WhatsApp, payment, secrecy and external-link holds.
7. Verify held messages are hidden from recipients but auditable by Admin.
8. Test report/block/suspension and session invalidation.
9. Attempt fake ratings without a dual-confirmed engagement.
10. Inspect SQL authorization for cross-teacher, cross-student and cross-conversation access.
11. Check all POST actions for CSRF and all private routes for authentication.
12. Review data-minimisation, retention and safeguarding gaps before production.

## Explicitly challenge

- whether profile verification is strong enough for a live marketplace;
- whether transparent regex safety checks are too weak for production;
- whether group posting permissions can be bypassed;
- whether parent consent can become stale or be spoofed;
- whether rate limits remain reliable under multiple application workers;
- whether direct SQLite message storage needs encryption/partitioning before pilot;
- whether moderator access is sufficiently least-privilege;
- whether off-platform lesson/payment disclaimers are clear;
- whether teacher ratings can be manipulated through collusive completion confirmations.

## Expected build assertions

- 41 V6.1 checks pass;
- 34 V6.0 checks pass;
- 52 V5.5 checks pass;
- V6.0→V6.1 migration integrity is `ok`;
- 16 additive V6.1 tables exist;
- Student Direct Messages remain `HIDDEN`;
- Teacher Discovery, Academic Messages and teacher-led groups remain `PILOT`.

Do not accept automated checks as a substitute for browser, mobile, privacy, safeguarding or adversarial review.
