# Independent Review Brief — ScoreMax V6.2.7

## Review objective

Attempt to disprove that the Academic Reviewer Workspace is confidential, resumable, traceable and isolated from the wider ScoreMax platform.

## Required adversarial challenges

1. Import 100 valid questions, 101 valid questions, duplicate IDs, missing answers and malformed XLSX/JSON.
2. Force a database failure during import and confirm whole-batch rollback and clean retry.
3. Forward, reuse, expire and tamper with invitation tokens.
4. Log in as a reviewer and attempt every known student, teacher, parent and Admin route.
5. Change assignment and item IDs in URLs to access another reviewer’s work.
6. Leave a question open while idle, hide the tab and sleep the device; compare wall-clock and active time.
7. Click rapidly through many questions and inspect risk evidence.
8. Submit non-acceptance without comments.
9. Create a second review using the same person, overlapping questions and conflicting decisions.
10. Attempt to alter a first decision after second review begins.
11. Search HTML, API responses and database snapshots for student data, source lineage, LO/concept ledgers, family architecture and mastery-engine rules.
12. Attempt direct publication, live-bank promotion, assessment creation or mastery write-back from reviewer routes.
13. Test keyboard submenu behaviour and mobile no-hover navigation.
14. Confirm Teacher of the Year is public Coming Soon only, with no nomination endpoint.

## Evidence expected

- exact reproduction steps;
- HTTP status/redirect chain;
- database counts before and after;
- timing-event evidence;
- assignment/outcome state;
- screenshots from real browser testing;
- classification as Verified Safe, Weakly Tested, Pilot Restricted or Release Blocker.

## Honest boundary

The automated suite cannot prove real email deliverability, screenshot prevention, human review quality, accessibility with assistive technology or whether the interface feels appropriately minimal. Those require human acceptance.
