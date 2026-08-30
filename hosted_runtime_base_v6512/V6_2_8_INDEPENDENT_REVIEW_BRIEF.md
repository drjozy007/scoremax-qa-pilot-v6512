# Independent Review Brief — ScoreMax V6.2.8

Conduct an independent, adversarial review of the complete V6.2.8 package. Treat documentation and test totals as unverified until reproduced. Do not modify source during the first audit pass.

## Priority questions

1. Can a student bypass a Locked or Coming Soon subject through direct URLs, form posts, test-start routes, mastery routes or Study Plan activities?
2. Can subject/package logic borrow inventory from another programme or curriculum?
3. Does one coverage package remain separate from the Free/Level 1/Level 2/Full access tier?
4. Can a large reviewer import write to or publish the live question bank?
5. Can malformed/duplicate/concurrent imports leave partial batches?
6. Does guided mapping avoid the old hidden-schema/first-row failure while still rejecting rows without a defensible question and answer?
7. Can one invitation expose batches not explicitly assigned to that reviewer?
8. Does multi-batch continuation preserve per-batch timing, progress, decisions and governance?
9. Does the Reviewer Workspace retain V6.2.7.1 identity, timing, concurrency and route-isolation protections?
10. Are prescribed Study Plan hours/minutes absent from generation, settings, cards and reports?
11. Does public Daily Spark create no visitor, attempt or mastery evidence?
12. Does the paywall clearly avoid implying that live card processing is operational?
13. Are the two-row desktop and reduced mobile navigation accessible and stable?

## Required adversarial tests

- 0, 1, 99, 100, 101, 3,000 and 10,001-row reviewer imports;
- alternative spreadsheet headings and missing optional fields;
- failed confirmation midway through batch creation;
- duplicate IDs, duplicate payloads and concurrent confirmations;
- one, multiple and all-batch assignments;
- invitation replay/cross-reviewer IDOR;
- stop/resume at arbitrary points across multiple batches;
- direct locked-subject requests with paywall on and off;
- entitlement replacement/expiry while a student session is active;
- empty-programme and Coming Soon content;
- public Spark repeated requests and database-write checks;
- keyboard-only, 200% zoom, screen-reader and mobile navigation.

## Required output

Create `CLAUDE_INDEPENDENT_AUDIT_SCOREMAX_V6_2_8.md` containing:

- executive verdict: Verified safe / Ready with restrictions / Not ready;
- exact environment and commands;
- independently reproduced test totals;
- Critical/High/Medium/Low/Informational findings;
- file/line, reproduction, expected/actual, impact, correction and confidence for every finding;
- confidentiality and live-write boundary verdicts;
- package-entitlement and curriculum-isolation verdicts;
- migration/rollback verdict;
- release-blocker register;
- controlled-pilot recommendation;
- confirmation that source was not modified.
