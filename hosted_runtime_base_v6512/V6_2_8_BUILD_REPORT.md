# ScoreMax V6.2.8 Build Report

## Release

**ScoreMax V6.2.8 — Student Navigation, Reviewer Import & Commercial Access**

## Purpose

Deliver the agreed low-click student navigation and subject access model, remove prescribed Study Plan timing, make programmes and Daily Spark prominent, and replace the Reviewer Workspace's hidden 100-row schema requirement with a guided large-import and automatic batching workflow.

## Delivered

### Student experience

- eight persistent desktop/laptop primary tabs;
- persistent contextual second row;
- reduced mobile/small-tablet bottom navigation;
- programme-scoped subject switcher across core learning pages;
- Included, Locked and Coming Soon subject states;
- public and logged-in Daily Spark placement;
- direct Available/Coming Soon programme cards;
- About Us wording;
- Study Plans based on priority/evidence rather than prescribed time.

### Reviewer operations

- guided JSON/CSV/XLSX import up to 10,000 rows;
- common column detection and Admin mapping preview;
- Question and Correct answer as the only essential semantic fields;
- optional-field defaults and downloadable excluded-row report;
- atomic automatic batching at 100 questions;
- one/many/all batch assignment groups;
- stop-or-continue reviewer flow;
- safe Reviewer Demo;
- existing invitation, confidentiality, active-time and governance hardening retained.

### Commercial access

- coverage packages separated from access tiers;
- single-subject, flexible bundle, science bundle and full available FSc Part 1 packages;
- Coming Soon Grade 9, Grade 10, FSc Part 2 and MDCAT package definitions;
- auditable entitlement replacement/history;
- server-side subject gates;
- provider-neutral checkout requests and explicit no-live-gateway status.

## Automated verification

- V5.5: 52;
- V6.0: 34;
- V6.1: 41;
- V6.2: 30;
- V6.2.1: 10;
- V6.2.2: 20;
- V6.2.3: 33;
- V6.2.4: 14;
- V6.2.5: 34;
- V6.2.6: 66;
- V6.2.7: 33;
- V6.2.7.1: 18;
- V6.2.7.2: 13;
- V6.2.8: 24;
- **Total: 422 checks.**

## Migration rehearsal

A database created by the untouched V6.2.7.2 package was seeded with live users, 96 live questions and an in-progress reviewer assignment with timing/outcome evidence. The V6.2.7.2→V6.2.8 dry-run migration:

- created and migrated a separate copy;
- retained every tested core and reviewer row count exactly;
- returned SQLite integrity `ok`;
- created the new tables, columns and indexes;
- seeded the package catalogue;
- created zero reviewer imports, student entitlements, entitlement-history events or checkout requests automatically.

## Static verification

The working release passed:

- 35/35 Python-file compilation;
- 107/107 Jinja-template parsing;
- 217 discovered application routes;
- zero broken literal template route references;
- zero explicit POST forms missing CSRF protection.

## Remaining acceptance boundary

The build is ready for controlled acceptance, not commercial launch certification. Still required:

- real desktop/mobile/tablet and assistive-technology testing;
- realistic 3,000-question corpus import and reviewer usability exercise;
- external academic-reviewer end-to-end session;
- live separate-channel invitation delivery;
- legal/confidentiality and commercial terms review;
- payment-gateway selection, integration and financial compliance testing;
- realistic concurrent-load testing.

## Packaged-artifact verification

The clean ZIP was extracted into a separate verification directory. Its internal manifest verified **271/271** entries with no missing or mismatched file. The extracted package then passed:

- 35/35 Python-file compilation;
- 107/107 Jinja-template parsing;
- 217 discovered application routes;
- zero broken literal template route references;
- zero explicit POST forms missing CSRF protection;
- all **422/422** regression checks across V5.5 through V6.2.8.

The release ZIP contains no generated SQLite database, private upload, content-intake upload, pilot backup or Python bytecode artifact.
