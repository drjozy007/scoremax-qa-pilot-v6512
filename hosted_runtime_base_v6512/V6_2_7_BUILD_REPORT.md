# ScoreMax V6.2.7 Build Report

## Release

**ScoreMax V6.2.7 — Reviewer Assurance & Navigation**

## Delivered

### Academic Reviewer Workspace

- eight isolated `reviewer_*` tables;
- minimal question snapshots only;
- JSON/CSV/XLSX import, 1–100 questions;
- named reviewer accounts;
- one-time hashed invitations with seven-day expiry;
- confidentiality acceptance and reviewer watermark;
- normal ScoreMax-route fence for reviewer sessions;
- one-question-at-a-time review;
- answer reveal, mastery suitability, explicit decision and comments;
- autosave and exact resume;
- per-question and total active-time evidence;
- hidden-tab/inactivity-aware client timer;
- fast review, answer-reveal, decision-run and calibration risk evidence;
- independent second-review and adjudication routing;
- decision locking after independent review/adjudication starts;
- no direct publishing, live-bank promotion, attempts or mastery writes.

### Navigation

- sticky key student tabs;
- accessible click/focus/hover submenus;
- keyboard opening, movement and Escape handling;
- grouped mega menus for high-density areas;
- page-specific actions remain contextual.

### Teacher recognition

- Teacher of the Year Coming Soon landing-page section;
- dedicated public information page;
- no nomination workflow enabled.

## Verification

- V5.5: 52 checks;
- V6.0: 34 checks;
- V6.1: 41 checks;
- V6.2: 30 checks;
- V6.2.1: 10 checks;
- V6.2.2: 19 checks;
- V6.2.3: 33 checks;
- V6.2.4: 14 checks;
- V6.2.5: 34 checks;
- V6.2.6: 66 checks;
- V6.2.7: 33 checks;
- **Total: 366 checks.**

Additional checks completed:

- all Python modules compile;
- 107 Jinja templates parse;
- all literal template route references resolve;
- all POST forms contain CSRF fields;
- genuine V6.2.6 database dry-run migration;
- SQLite integrity `ok`;
- all tested core counts preserved;
- eight reviewer tables created empty;
- QA-only control seeded;
- no reviewer account, batch or assignment created automatically.

## Remaining acceptance boundary

Real browser/mobile/assistive-technology testing, SMTP delivery, confidentiality/legal review, realistic concurrent reviewer load and external academic-review usability remain required before external deployment.

## Packaged-artifact verification

The clean release ZIP was extracted into a separate folder. Its 241-entry internal SHA-256 manifest was verified, the complete inherited regression stack through V6.2.6 passed again, the V6.2.7 suite passed all 33 checks, and packaged template/route checks passed.
