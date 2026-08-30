# ScoreMax V6.4.0 — Local Candidate Acceptance

**Candidate status:** `LIVE_PILOT_CANDIDATE_PENDING_DOMAIN_AND_FOUNDER_BROWSER_ACCEPTANCE`

## Automated/local gates

| Gate | Status | Evidence |
|---|---|---|
| Python compilation | **PASSED** | 11 critical Python modules/scripts compile. |
| Template syntax | **PASSED** | 107 Jinja templates parse. |
| Inherited deterministic regression | **PASSED** | 441 inherited checks. |
| V6.3 Universal Mastery/application | **PASSED** | 82 checks. |
| Student UX V2 | **PASSED** | 27 checks. |
| Governed chapter identity | **PASSED** | 14 checks. |
| V6.4 UX/referral/intake/operations delta | **PASSED** | 41 checks. |
| **Total deterministic** | **PASSED** | **605/605**. |
| Quick synthetic mastery replay | **PASSED** | 1,000 learners + 10,000 randomized invariant checks, 0 failures, 0 QA→LIVE leakage. |
| Large synthetic mastery attack | **PASSED** | 10,000 learners + 200,000 randomized invariant checks, 0 detailed/fuzz failures, 0 QA→LIVE leakage. |
| Emergency Direct Intake scale | **PASSED** | 3,000-row Power House-style XLSX → preview → Draft/inactive import → governed eligible release; SQLite integrity `ok`. |
| Package hygiene / manifest | **PENDING SEAL** | Must pass against the final ZIP bytes before handoff. |

## External/live gates

| Gate | Status |
|---|---|
| Domain/DNS/HTTPS/production process | **PENDING** |
| Production secrets/persistent DB identity | **PENDING** |
| Live SMTP/password reset | **PENDING** |
| Edge + Chrome desktop | **PENDING** |
| Mobile/touch | **PENDING** |
| Keyboard-only / 200% zoom | **PENDING** |
| One real approved Power House chapter end-to-end | **PENDING** |
| Founder live UX acceptance | **PENDING** |

Automated/local PASS is not represented as public-live acceptance. See `V6_4_0_LIVE_AUDIT_STATUS.md`.
