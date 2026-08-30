# ScoreMax V6.1 Production/Pilot Notes

## Do not make the module public immediately

Keep Teacher Discovery, Academic Messages and teacher-led groups in `PILOT`. Enable only named test accounts.

## Required before any real-student pilot

- documented teacher identity-verification process;
- privacy notice and data-protection review;
- safeguarding policy, named lead and escalation rota;
- clear community standards and teacher professional-conduct rules;
- encrypted production database/storage and HTTPS;
- backup, restore and moderator-audit procedures;
- retention/deletion and safety-case legal-hold policy;
- operational response targets for reports;
- testing with adult and under-18 accounts;
- parent/guardian consent wording review;
- browser/mobile accessibility acceptance;
- independent penetration and authorization testing.

## Production environment gates

```text
SCOREMAX_ENV=production
SCOREMAX_SECRET=<strong persistent secret>
SCOREMAX_SMTP_HOST=<configured>
SCOREMAX_SMTP_FROM=<configured>
SCOREMAX_COMMUNITY_LIVE=1          # set only after approval
SCOREMAX_SAFETY_CONTACT=<monitored operational contact>
```

Do not set the final two variables merely to bypass the control.

## Known pilot boundaries

- message delivery is request/response, not real-time WebSocket chat;
- no voice notes or general attachments;
- meeting links are limited to approved domains and teacher senders;
- safety filtering is transparent pattern-based pre-screening;
- Admin verification is a recorded workflow, not external KYC;
- tuition and payments occur outside ScoreMax;
- no commission, refund or dispute-payment system;
- no automatic tutor recommendation from sensitive personal data;
- no student-to-student DMs;
- no public Social Hub feed;
- no Knowledge Hub in this release.
