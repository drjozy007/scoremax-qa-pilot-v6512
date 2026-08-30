# ScoreMax V6.3.0 RC2 — External Adversarial Attack 2

You are performing the second independent adversarial audit of ScoreMax V6.3.0 Internal Live RC2.

The first audit found two confirmed defects (duplicate scoring and stale-positive re-verification), one deliberate Universal-Mastery integration limitation, and several hygiene findings. The source has now been rectified. **Do not trust the remediation claims or the new tests. Reproduce everything against the actual source and real framework. Do not modify the supplied source during the audit; use a working copy.**

Read `V6_3_0_CLAUDE_BLIND_AUDIT_REMEDIATION.md` only to understand what is claimed to have changed. Treat every claim as an attack target.

## Mandatory re-attacks

### A. Duplicate submission / concurrency — highest priority

1. Fresh database and real Flask stack.
2. Create one student assessment session and complete it.
3. POST the exact submit endpoint sequentially at least 5 times.
4. Then create a fresh session and POST it with **20 truly simultaneous HTTP clients/threads/processes**.
5. Verify exactly one `attempts` row, one logical result, one set of `attempt_answers`, and no duplicated downstream learning/mastery/plan effects.
6. Repeat using a challenge-linked assessment and verify leaderboard/rank/history cannot be inflated.
7. Force a retry while the first submit is blocked/slow if practical.
8. Attack migration compatibility: initialise an older-style DB and ensure the idempotency columns/index are added safely.

Any path that creates two attempts from one assessment session is **BLOCK** for internal scored testing.

### B. Stale-positive mastery re-verification

Reproduce the original P2-01 attack and variants:

1. Verify a family using two independent routes A+B.
2. Produce later contradictory evidence that causes REOPENED.
3. Submit one fresh correct on route A only.
4. Confirm route B's old positive cannot be recycled to reach VERIFIED.
5. Repeat route A multiple times; still no re-verification if the policy requires two routes.
6. Supply a fresh route B; only then may the policy re-verify.
7. Repeat the same logic for `AT_RISK`.
8. Repeat for `MAINTENANCE_DUE` / reconfirmation.
9. Attack mandatory gates: old pre-reopen gate/route evidence must not silently close the family after one unrelated correct.
10. Check timestamp-collision cases where maintenance/reopen and new evidence occur in the same second.
11. Run deterministic replay after each sequence; replay must equal live calculation.

Any path that re-verifies from stale pre-boundary closure credit is **HIGH**, and **BLOCK** if it affects learner-facing Universal Mastery.

## Previously untested / partially tested attacks

### C. Cross-role BOLA / IDOR

Exhaustively create at least two of each relevant role where supported: student, teacher, parent/guardian, institution/admin context. Attack IDs in URLs/forms/API payloads for:

- attempts/results;
- recovery;
- study plans;
- classroom membership and assignments;
- parent/student links and reports;
- academic messages;
- teacher discovery/contact state;
- institution/classroom data;
- challenge entries;
- profile/account data.

Prove ownership/tenant scoping empirically, not only by reading code.

### D. Session/authentication controls

- session fixation / session identifier behavior across login;
- `HttpOnly`, `SameSite`, and production `Secure` cookie configuration;
- logout and `session_version` invalidation;
- password-reset token single use and expiration;
- admin recovery utility: backup first, only Admin password changes, existing sessions invalidated, DB integrity remains OK.

### E. Untrusted import / upload attack

Attack xlsx/csv/json and other supported intake paths with:

- formula cells / CSV formula injection;
- malicious strings in IDs/headers;
- duplicate identities;
- path traversal filenames;
- oversized/zip-bomb-like shapes within practical limits;
- malformed JSON;
- type confusion;
- wrong sheet/header mappings;
- invalid question dependency/seed metadata.

No import may silently invent academic identity or publish itself.

### F. Backup / restore integrity

- make a valid backup;
- mutate live data;
- restore and verify deterministic recovery;
- attempt restore of a deliberately tampered/corrupt DB;
- ensure the tool fails safely rather than replacing a good DB with corruption;
- check backup/runtime artifacts are excluded from the supplied release ZIP.

### G. Architecture separation attacks

- prerequisite failure must route to the prerequisite and must not automatically destroy the parent concept's verified state;
- `mastery_rank` ordering must not invert Elite/Expert/etc.;
- full-exam pacing/entry/fatigue losses must not contaminate content mastery;
- MDCAT/NEET/JEE exam rules must remain market/exam-specific;
- Growth Engine boundary must be outbox/advisory only and must never write mastery;
- Reviewer Workspace must not be required for the forward workflow;
- QA/SYNTHETIC evidence must never create LIVE mastery.

### H. Internal-live access flag

Run once with no `SCOREMAX_INTERNAL_FULL_ACCESS` flag and prove inherited Free Access restrictions remain intact. Run again with `SCOREMAX_INTERNAL_FULL_ACCESS=1` and paywall enforcement off and prove the full internal student journey is testable. Ensure the flag does not alter earned mastery labels or become active in a normal production configuration accidentally.

### I. Universal Mastery mapping reality check

The product currently claims Universal Mastery is PILOT/SHADOW and governed-mapping-only. Confirm:

- fresh install does not fabricate real question→Node/Family/Seed mappings;
- unmapped real questions are skipped by Universal Mastery;
- synthetic fixtures remain QA-only;
- legacy mastery remains authoritative for ordinary real content;
- there is no hidden path that treats QA fixture results as real learner mastery.

This is an accepted limitation if the claims hold; report it as a limitation, not a defect.

### J. Browser / UX checks if browser automation is available

At minimum:

- Chrome/Chromium desktop width;
- mobile width;
- keyboard-only navigation;
- 200% zoom;
- no broken primary student links;
- no console/server exceptions during register → dashboard → assessment → result → weak area/recovery → Study Plan → progress → logout.

Do not judge visual taste in this audit; report functional/accessibility failures.

## Required report format

Return:

1. Executive verdict: `BLOCK`, `NOT_READY`, `INTERNAL_LIVE_ACCEPTABLE_WITH_KNOWN_LIMITATIONS`, or `PASS_FOR_INTERNAL_LIVE`.
2. Exact environment and fresh-install procedure.
3. Reproduced inherited/new test totals — independently counted.
4. Finding table with ID, severity, component, reproduction, expected, actual, evidence, impact and minimum fix.
5. Explicit status for every first-audit finding: FIXED / PARTIAL / STILL_PRESENT / FALSE-POSITIVE / ACCEPTED-LIMITATION.
6. Mastery false-positive and false-negative findings.
7. Security/BOLA findings.
8. Concurrency/data-integrity findings.
9. Packaging/privacy findings.
10. Untested areas.
11. Top next attacks.

**Do not downgrade a real defect because the product is "internal only". Do not upgrade an architectural limitation into a defect if the product labels it honestly and isolates it correctly.**
