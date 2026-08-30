# ScoreMax V6.1 — Teacher Discovery & Academic Messages

## Release purpose

V6.1 adds a controlled teacher-discovery and professional academic-messaging layer to the frozen V6.0 Written Response Intelligence baseline.

It is not a general social network and it is not a WhatsApp clone. The release is designed around a governed relationship:

> moderated teacher profile and service listing → structured student enquiry → teacher acceptance → number-private academic conversation → optional verified session confirmation → moderated verified rating.

The release preserves all V5.5 blueprint/calibration and V6.0 written-response behaviour.

## Permanent product boundaries

- Power House remains the academic-content and assessment-package authority.
- ScoreMax assessment evidence and mastery remain separate from marketplace popularity, chat activity and teacher ratings.
- Teacher identity or qualification verification is not the same as ScoreMax academic endorsement.
- Teachers cannot initiate unsolicited direct conversations with random students.
- Unrestricted student-to-student direct messaging remains hard-blocked.
- Teaching, payment and live video remain off-platform during this pilot.
- Knowledge Hub and the wider Social Hub remain separate future modules.

## Implemented capabilities

### Teacher Discovery

Teachers can create a professional profile containing subjects, assessment frameworks, qualifications, experience, languages, city/district, teaching platforms, availability, response expectation and 1-to-1/group availability.

Profiles are not discoverable until:

1. the teacher accepts the current Academic Messages rules;
2. the teacher accepts the Teacher Marketplace Professional Conduct agreement;
3. the profile is at least 60% complete;
4. identity verification is recorded by an authorised admin;
5. the admin publishes the profile.

Separate verification states are retained for identity, qualifications and experience. All verification changes create audit events.

### Service listings

Teachers can create separate:

- one-to-one listings;
- group listings.

Listings include subject, assessment/framework, chapter scope, online/local/hybrid delivery, approved platform names, availability, capacity and indicative PKR pricing. A listing cannot be published before its moderated teacher profile is published.

Public profile and listing content is rejected when it contains phone numbers, private email addresses, WhatsApp details, payment requests or unapproved external links.

### Structured student enquiries

A student selects a published service and explains the academic support required. The enquiry does not reveal a personal phone number.

The system prevents:

- duplicate pending enquiries for the same listing;
- more than five enquiries per student per day;
- personal contact details and unsafe content;
- use by a student with missing/invalid date of birth;
- under-18 use without active linked-parent consent;
- use without the current Academic Messages agreement.

The teacher must accept before a conversation is created. Age and guardian consent are checked again at acceptance time.

### Academic Messages

Accepted relationships create governed one-to-one conversations. Messages support:

- text;
- approved teacher meeting links for Google Meet, Zoom and Microsoft Teams domains;
- assessment links;
- Study Plan links;
- system messages.

Pilot safety controls include:

- maximum 40 user messages per hour, checked against persistent database history and an in-process limiter;
- automatic holds for phone numbers, private email addresses, WhatsApp references, payment requests, off-platform secrecy, abusive content and unapproved links;
- held messages hidden from the recipient while retained for audit;
- automatic safety report creation for held messages;
- Report and Block controls;
- one-to-one conversation locking after a block;
- controlled Admin moderation and user suspension;
- message evidence preserved for safety review.

The current text-pattern pre-filter is a transparent pilot safeguard, not a production-grade trust-and-safety classifier.

### Teacher-led group channels

A teacher can create a group only from a group service listing. The group is separately moderated before publication.

Students request membership; teachers approve or reject. Age, agreement and guardian requirements are checked at request and approval.

Groups support:

- teacher-announcement-only posting; or
- posting by all approved members.

The teacher owns and moderates the group relationship. The release does not create private student-to-student direct messaging.

### Under-18 and parent controls

For a known student under 18:

- a linked parent/guardian must explicitly approve Teacher Discovery and Academic Messages;
- the consent version and timestamps are stored separately;
- the parent can revoke consent;
- revocation suspends group membership and conversation membership;
- existing one-to-one conversations are locked rather than silently deleted;
- old evidence remains auditable.

A new enquiry/relationship is required after later re-approval; old conversations are not silently reopened.

### Verified teacher ratings

A rating cannot be submitted merely after viewing a profile or sending an enquiry.

The teacher and student must separately confirm that the interaction occurred. Only a `VERIFIED_COMPLETED` engagement can create one review, and that review remains pending until Admin moderation.

Public teacher ratings therefore derive only from moderated, verified interactions.

### Admin governance

The Admin area includes:

- feature controls: `HIDDEN`, `PILOT`, `LIVE`;
- named pilot-account access;
- profile moderation;
- identity/qualification/experience verification audit;
- listing moderation;
- teacher-group moderation;
- held-message and user-report review;
- message removal and user suspension;
- verified-review moderation.

`student_direct_messages` cannot be changed from `HIDDEN` through the Admin route.

In production, moving community capabilities to `LIVE` additionally requires:

```text
SCOREMAX_COMMUNITY_LIVE=1
SCOREMAX_SAFETY_CONTACT=<operational safety contact>
```

## Default release state

| Capability | Default |
|---|---|
| Teacher Discovery | PILOT |
| Academic Messages | PILOT |
| Teacher-led Group Channels | PILOT |
| Student Direct Messages | HIDDEN and code-blocked |

Every student and teacher pilot account must be explicitly enabled by Admin.

## Local start

```bash
pip install -r requirements.txt
python app.py
```

On Windows, use:

```text
start_scoremax_v6_1.bat
```

## Migration

Run a dry migration first:

```bash
python migrate_v6_to_v6_1.py path/to/scoremax_v4.db --dry-run
```

See `V6_1_MIGRATION_GUIDE.md`.

## Automated verification completed

- V6.1 dedicated suite: **41 checks passed**
- V6.0 written-response suite: **34 checks passed**
- V5.5 blueprint/calibration suite: **52 checks passed**
- combined automated checks: **127 passed**
- Python compilation: passed
- SQLite migration integrity: `ok`
- tracked V6.0 table counts: preserved
- new V6.1 tables: 16

## Still requiring browser/operational acceptance

- real browser and responsive mobile review;
- production HTTPS and encrypted database/storage operations;
- independent privacy and safeguarding review;
- teacher-verification operating procedure;
- moderator training and escalation rota;
- data-retention/deletion policy and legal-hold process;
- production trust-and-safety classification beyond the transparent pilot pre-filter;
- notification delivery;
- voice notes and file attachments;
- real-time WebSocket/push chat;
- payment/refund/commission handling;
- live video or whiteboard;
- full Social Hub and student-to-student community features.
