# ScoreMax UK 11+ — Native Email Verification Qualification
Date: 25 November 2026
Decision: Reuse the existing ScoreMax `ux_email_verification.py` workflow, with in-memory SMTP for disposable native-runtime qualification.
Status: PASSED — checksum-pinned disposable native runtime with synthetic learner and network disabled. NOT DEPLOYED / NOT LIVE VERIFIED.

## Evidence
- GitHub Actions successful full replay: https://github.com/drjozy007/scoremax-qa-pilot-v6512/actions/runs/45557050535
- Replay commit: `78b86d6673fe705269dc5f5b020a43241a10dc34`
- Native baseline pinned: `5749e8370d577044c398cdf0c3bd78344ef6a26a`
- Reconstructed base checksum: `7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9`
- Transport: existing ScoreMax `send_transactional_email` and existing email-verification token handler, with Python `smtplib.SMTP` replaced by an in-memory `CapturedSMTP` class only in the disposable test process; no external network.
- Test file: `uk11_integration/native_login_replay.py`.

## Confirmed checks
1. Native `POST /register/student` created a synthetic UK11 student with `market_id=UK`, `programme_id=UK11` and pending verification; original account protections and CSRF retained.
2. Existing mailer generated a real `EmailMessage` and a full `https://scoremax.pk/verify-email/<token>` link; one synthetic email captured.
3. Stored token field matched SHA-256 of the captured token; plaintext token absent from learner row; expiry configured.
4. Correct credentials before verification redirected to the verification-pending route without creating an authenticated session.
5. Immediate resend respected the cooldown; after moving only the synthetic `sent_at` timestamp backward, permitted resend generated a second message and rotated the token.
6. Old link after rotation did not verify the account.
7. Expired fresh link did not verify the account; restoring the previously saved expiry in the disposable synthetic record enabled genuine native token redemption.
8. Native successful redemption set `email_verified=1`, `account_status=active`, cleared token hash; subsequent attempt using the same link could not re-verify.
9. First login after actual native redemption loaded UK11 `/student` with no selected schools and Not Yet Established; previous native school changes, logout/login persistence, Pakistan-market isolation and blocked unqualified practice routes also passed.
10. No production account, network email, academic record, Pakistan database, payment or public preview deployment changed.

## Limits and next actions
- In-memory SMTP demonstrates email composition and verification, not real provider delivery, deliverability, bounce handling or a deployed mail server. These remain PENDING.
- Real parent/guardian approval, safeguarding, UK GDPR, Children's Code age-appropriate onboarding and privacy assessment remain PENDING; child public registration remains HOLD.
- Real school/provider/consortium 2028 admissions memberships, approved questions, school-scoped native learning/mocks/marking/mastery remain PENDING.
- The UK experience currently exposes only previously qualified read-only context and blocks unqualified Pakistan learning routes. Do not mistake this for full ScoreMax feature readiness.
- Next isolated gate: guardian-linked UK onboarding, parent/child authorisation, real email-provider staging configuration, then browser/mobile and accessibility qualification.
