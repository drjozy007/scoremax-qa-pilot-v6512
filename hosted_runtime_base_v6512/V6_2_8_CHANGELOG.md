# ScoreMax V6.2.8 Changelog

## Added

- eight persistent desktop/laptop student navigation tabs;
- persistent second-row contextual navigation;
- reduced mobile/small-tablet bottom navigation;
- programme-scoped subject switcher with Included, Locked and Coming Soon states;
- server-enforced subject-package entitlements;
- coverage packages separate from Free/Level 1/Level 2/Full access depth;
- package-aware student paywall and provider-neutral checkout requests;
- Admin coverage-package and entitlement controls;
- guided reviewer import for up to 10,000 JSON/CSV/XLSX rows;
- automatic mapping suggestions and preview confirmation;
- downloadable reviewer import template and invalid-row error report;
- atomic 100/100/... automatic review batching;
- multi-batch reviewer assignment groups;
- reviewer continue-or-stop flow across assigned batches;
- safe Reviewer Demo;
- public pre-login Daily Spark preview;
- direct Available/Coming Soon programme cards;
- V6.2.7.2→V6.2.8 migration utility;
- 24 dedicated V6.2.8 regression checks.

## Changed

- Study Plans now use priority/evidence/sequence rather than prescribed study time;
- public navigation label changed from About to About Us;
- student subject discovery is persistent across core learning pages;
- Reviewer Workspace upload wording no longer presents a 100-question file ceiling;
- Account → Access now combines subject coverage with access tier.

## Preserved

- V6.2.7.1 reviewer invitation, identity, timing and concurrency hardening;
- reviewer isolation from normal ScoreMax routes;
- no Reviewer Workspace write path into live questions, attempts, mastery or Study Plans;
- V6.2.7.2 Email or User ID login;
- curriculum isolation and Coming Soon blocking;
- Daily Spark separation from formal mastery;
- Mastery Laboratory QA-only boundaries.

## Not included

- live payment-gateway processing;
- production pricing/legal terms approval;
- automatic publication of reviewed questions;
- real-browser/mobile/assistive-technology acceptance;
- production-scale external reviewer load certification.
