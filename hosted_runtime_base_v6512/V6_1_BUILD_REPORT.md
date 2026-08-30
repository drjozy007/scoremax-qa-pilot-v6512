# ScoreMax V6.1 Build Report

## Release

**ScoreMax V6.1 — Teacher Discovery & Academic Messages**

V6.1 was built as a separate descendant of the frozen ScoreMax V6.0 Written Response Intelligence release. It does not overwrite V6.0 or the V5.5 Final rollback baseline.

## Release objective

The release adds a governed teacher-discovery and professional academic-messaging layer for Pakistan-first use without exposing personal phone numbers or turning ScoreMax into an unrestricted social messenger.

The implemented relationship is:

> moderated teacher profile and listing → structured student enquiry → teacher acceptance → number-private academic conversation → optional teacher-led group → verified interaction → moderated rating.

Knowledge Hub, the broader Social Hub, unrestricted student-to-student direct messaging, payments and live video are deliberately outside this release.

## Implemented and tested

### Teacher discovery and listings

- professional teacher profiles;
- separate identity, qualification and experience verification states;
- immutable verification-event audit;
- profile-completeness and identity-verification publication gate;
- one-to-one and group service listings;
- subject, framework, chapter scope, language, delivery mode, location, availability and indicative PKR pricing;
- Admin moderation before public discovery;
- rejection of public phone numbers, personal email, WhatsApp details, payment requests and unapproved external links.

### Structured enquiries and relationship gating

- number-private student enquiries;
- duplicate-pending-enquiry protection;
- persistent and in-process enquiry rate controls;
- teacher acceptance before a direct conversation exists;
- no teacher-initiated unsolicited random-student conversation flow;
- age, agreement and guardian-consent revalidation at relationship creation.

### Academic Messages

- text, approved meeting-link, assessment-link, Study-Plan-link and system message types;
- approved Google Meet, Zoom and Microsoft Teams meeting-link domains;
- teacher-only meeting-link creation;
- persistent and in-process message-rate controls;
- automatic safety holds for contact details, WhatsApp, payment requests, secrecy requests, abusive content and unapproved links;
- held messages hidden from recipients but preserved for audit;
- automatic safety-report creation;
- report, block, conversation lock, Admin removal and user suspension controls.

### Teacher-led group channels

- groups originate from moderated group listings;
- separate group moderation before publication;
- student membership request and teacher approval;
- capacity control;
- teacher-announcement-only or approved-member posting policy;
- no private student-to-student direct-message route.

### Safeguarding and consent

- valid date of birth required for student messaging;
- explicit linked-parent consent for known under-18 students;
- separately versioned guardian consent;
- guardian revocation suspends group and direct-conversation membership and locks one-to-one conversations without deleting evidence;
- explicit Academic Messages user agreement;
- separate Teacher Marketplace Professional Conduct agreement;
- agreement versions and acceptance/revocation history retained.

### Verified ratings

- ratings require a relationship created through ScoreMax;
- both teacher and student confirm the interaction;
- only a `VERIFIED_COMPLETED` engagement can create one rating;
- every rating remains pending until Admin moderation.

### Administration and feature controls

- `HIDDEN`, `PILOT` and `LIVE` feature states;
- named pilot-account access;
- Teacher Discovery, Academic Messages and group-channel controls;
- `student_direct_messages` permanently hard-blocked to `HIDDEN` in this release;
- production LIVE guard requiring `SCOREMAX_COMMUNITY_LIVE=1` and an operational `SCOREMAX_SAFETY_CONTACT`;
- dedicated Admin moderation view;
- parent messaging-consent view;
- explicit agreement-management view.

## Database and migration

V6.1 adds 16 governed tables:

1. `community_feature_controls`
2. `community_user_agreements`
3. `teacher_profiles`
4. `teacher_verification_events`
5. `teacher_service_listings`
6. `teacher_enquiries`
7. `academic_groups`
8. `academic_group_members`
9. `academic_conversations`
10. `academic_conversation_members`
11. `academic_messages`
12. `academic_message_reports`
13. `academic_user_blocks`
14. `academic_guardian_consents`
15. `teacher_engagements`
16. `teacher_reviews`

The controlled V6.0→V6.1 dry-run migration returned SQLite integrity `ok` and preserved all tracked V6.0 user, attempt, mastery, class, blueprint, mock and written-response table counts.

## Automated verification actually executed

The final working tree passed:

- V6.1 dedicated smoke suite: **41 checks**;
- V6.0 written-response regression suite: **34 checks**;
- V5.5 blueprint/calibration regression suite: **52 checks**;
- combined: **127 checks passed**;
- Python compilation: passed;
- Jinja template parsing: passed through the smoke suites;
- route duplicate and literal template-route checks: passed;
- explicit POST-form CSRF check: passed;
- SQLite migration integrity: `ok`;
- tracked pre-existing data counts: preserved.

The release ZIP was also extracted to a clean directory and the same automated suites and compilation checks were rerun before release.

## Implemented but awaiting browser/operational acceptance

- responsive desktop/mobile presentation;
- complete teacher, student, parent and Admin journeys in a real Flask browser runtime;
- production HTTPS, encrypted storage and operational backups;
- notification delivery and unread-message behaviour;
- moderation workflow usability at realistic volumes;
- parent/guardian consent usability;
- accessibility and screen-reader review.

The build environment did not contain a real Flask/Werkzeug browser runtime. The automated suites used the disclosed compatibility harness for business logic, SQLite operations, templates, routes and CSRF checks. No claim is made that browser acceptance has been completed.

## Deliberately deferred

- unrestricted student-to-student private messaging;
- wider Social Hub feed and community network;
- Knowledge Hub/blog CMS;
- voice notes and file attachments;
- real-time WebSocket or push chat;
- on-platform video, whiteboard or lesson recording;
- on-platform tuition payments, refunds or commissions;
- external KYC/qualification-verification provider;
- production-grade behavioural trust-and-safety classifier;
- automated retention/deletion and legal-hold operations;
- institution-wide messaging administration.

## Pilot limitations and challenge points

- The current safety text-pattern pre-filter is transparent and testable, but it is not a replacement for trained human moderation or a production trust-and-safety classifier.
- Identity verification demonstrates that an identity check was recorded; it does not constitute academic endorsement by ScoreMax.
- Indicative pricing and teacher ratings remain separate from mastery, academic approval and assessment results.
- Lessons and payments remain off-platform, so off-platform leakage and disputes require clear marketplace terms and reporting routes.
- Before minors use the pilot, the safeguarding model, guardian-consent wording, privacy notices, retention rules and moderator escalation procedures require independent review.

## Release conclusion

V6.1 provides a controlled, number-private academic communication and teacher-discovery foundation while preserving V5.5 assessment-governance and V6.0 written-response integrity. It is suitable for independent technical review and controlled browser acceptance, not unrestricted public launch.
