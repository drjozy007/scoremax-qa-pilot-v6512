# ScoreMax V6.1 Browser and Pilot Acceptance Checklist

## Setup

- [ ] Extract V6.1 separately from V6.0.
- [ ] Copy a test database and run `migrate_v6_to_v6_1.py --dry-run`.
- [ ] Confirm integrity `ok` and all preserved counts `true`.
- [ ] Run all three smoke suites.
- [ ] Create named Admin, adult student, under-18 student, linked parent and teacher accounts.
- [ ] Enable Teacher Discovery and Academic Messages only for those pilot accounts.

## Community agreements

- [ ] Student cannot send an enquiry before accepting current Academic Messages rules.
- [ ] Teacher cannot create a profile before accepting both required agreements.
- [ ] Agreement version and timestamp are recorded.
- [ ] Revoking the messaging agreement suspends conversation membership.

## Teacher profile and verification

- [ ] Teacher saves a draft profile.
- [ ] JSON-backed list fields render as readable comma-separated values.
- [ ] Profile with phone/email/WhatsApp details is rejected.
- [ ] Admin cannot publish before identity verification.
- [ ] Admin cannot publish an incomplete profile.
- [ ] Identity, qualification and experience are displayed as separate badges.
- [ ] Verification audit history is preserved.
- [ ] No badge says or implies ScoreMax academic endorsement.

## Service listings and discovery

- [ ] 1-to-1 listing can be submitted and moderated.
- [ ] Group listing requires capacity of at least two.
- [ ] Listing cannot publish before profile publication.
- [ ] Student can filter by subject, framework, service and delivery mode.
- [ ] Personal contact details and unsafe public links are rejected.
- [ ] Indicative PKR pricing is displayed clearly.

## Adult student enquiry

- [ ] Student explains the academic support needed.
- [ ] Phone/email/WhatsApp details are rejected.
- [ ] Duplicate pending enquiry is prevented.
- [ ] Daily enquiry limit is enforced.
- [ ] Teacher cannot message before acceptance.
- [ ] Teacher acceptance creates exactly one governed conversation.

## Under-18 controls

- [ ] Missing date of birth blocks messaging.
- [ ] Under-18 student without linked-parent approval is blocked.
- [ ] Linked parent can approve current consent version.
- [ ] Teacher acceptance re-checks current consent.
- [ ] Group approval re-checks current consent.
- [ ] Parent revocation suspends memberships and locks direct conversations.
- [ ] Revocation does not delete historical evidence.

## Academic Messages

- [ ] Ordinary academic text is visible to both participants.
- [ ] Phone, email, WhatsApp, payment and secrecy phrases are held.
- [ ] Held content is not shown to the recipient.
- [ ] Held content creates an Admin safety case.
- [ ] Student meeting-link message is held.
- [ ] Teacher can send an approved Meet/Zoom/Teams link.
- [ ] Unknown external links are held.
- [ ] 40-message-per-hour limit works.
- [ ] Report creates an Admin case.
- [ ] Block locks one-to-one chat.
- [ ] Disabled user sessions invalidate correctly.

## Teacher-led groups

- [ ] Group requires a group listing.
- [ ] Group requires separate Admin moderation.
- [ ] Student requests membership.
- [ ] Teacher approves or rejects.
- [ ] Capacity is enforced.
- [ ] Teacher-only group blocks student posting.
- [ ] All-members group allows only approved members.
- [ ] No private student-to-student DM route is exposed.

## Verified ratings

- [ ] Review is unavailable before both sides confirm a session.
- [ ] Both confirmations produce `VERIFIED_COMPLETED`.
- [ ] Student can submit only one review for that engagement.
- [ ] Review is not public before moderation.
- [ ] Published aggregate uses only published verified reviews.

## Admin governance

- [ ] Student Direct Messages cannot be moved from `HIDDEN`.
- [ ] Production `LIVE` activation fails without master switch and safety contact.
- [ ] Admin can remove a reported message.
- [ ] Admin can suspend a reported account.
- [ ] Audit evidence remains after moderation.

## Regression

- [ ] V5.5 authentic mock and blueprint compliance still work.
- [ ] V5.5 Study Plan/projection/calibration still work.
- [ ] V6.0 typed written answers and exemplar controls still work.
- [ ] No existing users, attempts, mastery, classes, blueprints or written-answer records are changed.
