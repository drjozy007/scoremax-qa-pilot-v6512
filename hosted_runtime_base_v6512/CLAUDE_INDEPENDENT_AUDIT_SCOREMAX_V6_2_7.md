# Independent Audit — ScoreMax V6.2.7 (Reviewer Assurance & Navigation)

Auditor: Claude (Anthropic), acting as an independent, adversarial reviewer.
Scope: the complete `ScoreMax_V6_2_7_Reviewer_Assurance_Navigation.zip` package.
**No source code was modified at any point in this review.** All work was performed on an
extracted copy in a separate working directory; the original package was only read.

---

## 1. Executive verdict

**READY WITH RESTRICTIONS.**

Not *Verified safe*: four real, narrow-scope Medium findings were confirmed, one of them
(a duplicate-batch race condition) reproduced deterministically under genuine concurrency.
Not *Not ready*: zero Critical or High findings, and every core confidentiality, isolation,
and governance property that the release claims was adversarially tested — live, against a
running instance — and held. The package's own claimed test totals (366 checks across 11
releases) were independently reproduced exactly.

**Recommendation:** proceed to a controlled pilot with a small number of named, trusted
reviewers, conditional on closing the four Medium findings (all are small, well-scoped code
changes) and completing the human-testing items the release's own acceptance checklist
already lists as outstanding (real browser/assistive-technology testing, live SMTP delivery,
legal/confidentiality wording review, realistic concurrent-load testing).

---

## 2. Environment and limitations

- Extracted into `/home/claude/audit/ScoreMax_V6_2_7_Reviewer_Assurance_Navigation/`; all
  dynamic testing ran against copies in `/home/claude/audit/runtime_test/`, never the
  original.
- Isolated virtualenv, dependencies installed exactly as pinned in `requirements.txt`
  (Flask 3.1.0, Werkzeug 3.1.3, openpyxl 3.1.5, Pillow 11.3.0). Python 3.12.3.
- All dynamic tests ran against fresh, throwaway SQLite databases created via the
  application's own `app.init()` — no real student, teacher, parent, or reviewer data was
  used or created anywhere in this review.
- **Not available in this environment:** a real web browser, mobile devices, assistive
  technology (screen readers), a live SMTP server, or multiple physical machines. Anywhere
  this matters, the finding below is explicitly marked as code-level verification only, not
  runtime confirmation — consistent with the release's own acceptance checklist, which
  independently lists these as still required.
- Genuine concurrency was tested using Python threading against the real application
  functions and a shared SQLite database — a legitimate proxy for concurrent HTTP requests,
  though not identical to a production multi-worker WSGI deployment.
- One race-condition reproduction used a test-only monkeypatch (a delay injected into an
  imported function *inside the test process*) to widen a normally-microsecond timing window
  into something that reproduces deterministically rather than depending on lucky OS thread
  scheduling. This does not alter any file on disk.
- My own first pass at a "blind review" dynamic test produced a false-positive failure
  (a substring match against a shared `<option>` value in the decision dropdown, not an
  actual data leak); I traced it down with a follow-up query and disconfirmed it. Noted here
  for transparency about the review's own methodology, not as an application defect.

---

## 3. Files inspected

- `app.py` (10,647 lines / 715 KB — the full Flask application, all 214 routes).
- `reviewer_workspace_engine.py` (the core new module for this release, read in full).
- `migrate_v6_2_6_to_v6_2_7.py`, and the four prior migration scripts, for lineage context.
- All 107 files under `templates/`, parsed programmatically with a real Jinja2 environment;
  `reviewer_item.html`, `reviewer_invite.html`, `teacher_of_year.html`, `index.html` and
  `admin_reviewer_workspace.html`'s route logic read in full.
- `V6_2_7_CHANGELOG.md`, `V6_2_7_BUILD_REPORT.md`, `V6_2_7_ACCEPTANCE_CHECKLIST.md`,
  `V6_2_7_MIGRATION_GUIDE.md`, `V6_2_6_ASSURANCE_GATE_MODEL.md`, `README.md`.
- `V6_2_7_FILE_SHA256SUMS.txt`, `MANIFEST` cross-checked against the extracted files.
- All 11 `smoke_tests_*.py` suites (V5.5 through V6.2.7), each executed independently.
- `requirements.txt`, `static/styles.css` (scanned, not deeply reviewed).
- The three previously-undisclosed package contents: `private_uploads/written/attempt_3_*/page_1.jpg`,
  the three `content_intake_uploads/*.csv` files, and the empty `pilot_backups/` directory —
  each opened and inspected directly.

---

## 4. Commands and tests executed (representative, not exhaustive)

- `sha256sum`-equivalent verification in Python of all 241 manifest entries against the
  extracted files, in both directions (nothing missing, nothing extra, no mismatches).
- `py_compile` against all 28 `.py` files in the package.
- A real `jinja2.Environment().parse()` against all 107 templates.
- `pip install -r requirements.txt` into a clean virtualenv; confirmed exact pinned versions.
- `python migrate_v6_2_6_to_v6_2_7.py <db> --dry-run` against a **simulated realistic
  pre-V6.2.7 database** (booted via `app.init()`, then had the eight new `reviewer_*` tables
  and all reviewer-role users manually stripped to reproduce a genuine "before" state, then
  seeded with real user and question rows) — run to completion, verified end to end.
- All 11 `smoke_tests_*.py` suites run independently, each against its own fresh database.
- A multi-stage Flask `test_client()` harness exercising, live, against a running instance:
  admin login → batch import (with deliberately injected fake-confidential fields and an
  XSS payload) → reviewer creation → invitation → acceptance → 10-route isolation probe →
  IDOR probes → CSRF-omission probe → timer-clamp and timer-flood probes → batch-size-limit
  probes (100 accepted, 101 rejected) → duplicate-ID probe → full first-review/second-review
  agreement and disagreement flow, including decision locking and blind-review verification
  → a genuine mid-batch logout/re-login resume test → a threaded concurrency reproduction of
  the duplicate-batch race condition.

---

## 5. Claimed test totals vs. independently reproduced totals

Every suite was deleted and re-run from a completely fresh database; every count matched
the build report exactly.

| Release | Claimed | Independently reproduced |
|---|---|---|
| V5.5 | 52 | 52 |
| V6.0 | 34 | 34 |
| V6.1 | 41 | 41 |
| V6.2 | 30 | 30 |
| V6.2.1 | 10 | 10 |
| V6.2.2 | 19 | 19 |
| V6.2.3 | 33 | 33 |
| V6.2.4 | 14 | 14 |
| V6.2.5 | 34 | 34 |
| V6.2.6 | 66 | 66 |
| V6.2.7 | 33 | 33 |
| **Total** | **366** | **366** |

Additional build-report claims independently reproduced: all Python modules compile (28/28,
including files not named in the report); 107/107 templates parse; the 241-entry SHA-256
manifest is fully intact; the V6.2.6→V6.2.7 dry-run migration preserves all core-table counts
and creates the eight new tables empty except a `QA_ONLY`-state control row.

---

## 6. Findings

**Critical: none. High: none.**

### Finding 1 — Second-reviewer independence is enforced by the caller, not the shared function
- **Severity:** Medium
- **File/line:** `reviewer_workspace_engine.py`, `create_assignment()`, lines 201–206
- **Reproduction:** Call `create_assignment(c, batch_id=<batch>, reviewer_user_id=<the round-1
  reviewer>, created_by=1, round_no=2, parent_assignment_id=None)` directly against a batch
  that already has a round-1 assignment for that same reviewer. Confirmed live: this
  succeeds and commits a round-2 "independent" assignment where the second reviewer is the
  same person as the first.
- **Expected behaviour:** The function should refuse to make any reviewer their own
  independent second reviewer, unconditionally.
- **Actual behaviour:** The independence check only runs when the caller supplies a truthy
  `parent_assignment_id` (`if int(round_no)==2 and parent_assignment_id:`). Omit that
  argument and the check is skipped entirely.
- **Impact:** No live exploit today — the single call site in `app.py`
  (`admin_reviewer_workspace()`, `action=='second_review'`, line ~10486) always derives and
  passes `parent_assignment_id` correctly, and additionally repeats the independence check at
  the route level before calling the library function. This is a "missing assurance" gap in
  a function whose entire purpose is enforcing independence — any future caller (a new admin
  feature, a bulk-assignment script, a refactor) that doesn't happen to supply
  `parent_assignment_id` would silently reintroduce a governance-defeating bug.
- **Recommended correction:** Inside `create_assignment()`, when `round_no==2`, always look
  up the batch's round-1 assignment directly (`SELECT reviewer_user_id FROM
  reviewer_assignments WHERE batch_id=? AND round_no=1`) and reject a matching
  `reviewer_user_id`, regardless of whether `parent_assignment_id` was supplied.
- **Confidence:** High (reproduced live; DB state inspected before and after).

### Finding 2 — No rate limit on the active-time timer endpoint
- **Severity:** Medium
- **File/line:** `app.py` lines 10586–10593 (`reviewer_timer`); `reviewer_workspace_engine.py`
  lines 274–284 (`record_active_time`)
- **Reproduction:** Authenticate as a reviewer with an open item. Send 20 consecutive
  `POST /review/item/<id>/time` requests with `seconds=30` each, with no delay between them.
  Reproduced live: all 20 accepted, crediting exactly 600 seconds (10 minutes) of "active
  time" in well under one second of real wall-clock time.
- **Expected behaviour:** Each server-side tick is correctly clamped to 0–30 seconds
  (confirmed: `seconds=999999` → 30 accepted; `seconds=-500` → 0 accepted) — but nothing
  limits how *often* a tick can be submitted.
- **Actual behaviour:** `last_ping_at` is written on every call but never compared against
  the current time to enforce a minimum interval, and this endpoint is not covered by the
  `rate_limit()` helper already used elsewhere in `app.py` (login, registration, written-response
  submission, teacher enquiries, academic messages all use it; this endpoint does not).
- **Impact:** A reviewer (or a compromised/malicious reviewer session) can script arbitrarily
  inflated `active_seconds` values for their own items, specifically defeating the
  `VERY_FAST_REVIEW` / `FAST_REVIEW` risk flags that `assignment_quality()` relies on. Scoped
  to gaming a quality-assurance *signal* about the reviewer's own work — it does not expose
  data or bypass access control.
- **Recommended correction:** Reject or silently discard a tick whose `last_ping_at` is less
  than ~4 seconds old for that item, or apply the app's existing `rate_limit()` helper to this
  route.
- **Confidence:** High (reproduced live with an exact, reproducible number).

### Finding 3 — Invitation acceptance has no separate identity check beyond token possession
- **Severity:** Medium
- **File/line:** `app.py` lines 10528–10549 (`reviewer_invite`)
- **Reproduction (code-level; the "first to submit wins" property follows directly from the
  logic, and was exercised live in the normal accept-invitation flow):** the account is
  created with a random, never-communicated password (`app.py` line 10470). The *only* way
  to ever set a usable password is submitting `POST /review/invite/<token>` with a valid,
  unexpired token — which immediately sets the password to whatever was submitted and
  auto-logs-in the submitter as that reviewer (line 10547), with no confirmation loop back to
  the reviewer's registered email.
- **Expected behaviour:** Only the intended named reviewer should be able to activate their
  account.
- **Actual behaviour:** Whoever submits the form first, while the token is still valid,
  becomes that reviewer — the system cannot distinguish the intended person from anyone else
  who obtained the link.
- **Impact:** Bounded (single-use, 7-day expiry, tied to one specific pre-named account — this
  is not an unrestricted public link, and it does not grant access to anything beyond that one
  reviewer identity), but real: a forwarded or intercepted invitation lets an unintended party
  claim a named reviewer's identity with no separate verification step.
- **Recommended correction:** Send the confidentiality/password-setup step through a
  second channel tied to the reviewer's registered email (e.g., a confirmation code emailed
  separately), or otherwise require a factor the intended recipient alone would have.
- **Confidence:** High (the logic is unambiguous; live-tested that a valid token's holder is
  auto-logged-in on first successful submission).

### Finding 4 — Three check-then-act patterns race ahead of the write lock
- **Severity:** Medium
- **File/line:** `reviewer_workspace_engine.py`: `import_batch()` lines 172–174 (duplicate
  checksum), `create_assignment()` line 205 (one round-1 per batch), lines 217–219 (round-2
  question overlap)
- **Reproduction:** Reproduced live and deterministically for the first case. Two threads
  each called `import_batch()` with byte-identical question content (same checksum), started
  50ms apart, against the real function (a test-only monkeypatch added a delay inside the
  checksum step to widen the window — no source file was modified). **Result: both succeeded,
  producing two `reviewer_batches` rows sharing the identical checksum** — the application's
  own rule ("this exact review batch has already been imported") was bypassed under
  concurrency. The other two instances of the same pattern (one-first-review-per-batch,
  round-2 overlap) share the identical structure — a `SELECT` check followed later by
  `BEGIN IMMEDIATE` — and were not separately reproduced under threading in this pass, but the
  code-level mechanism is the same one just proven live.
- **Expected behaviour:** Each of these three business rules should hold even under
  concurrent requests.
- **Actual behaviour:** Each check runs as a plain autocommit-mode `SELECT` *before* the
  function acquires a write lock via `BEGIN IMMEDIATE`, leaving a window where two concurrent
  callers can both see "not found" and both proceed to insert.
- **Impact:** Requires genuinely concurrent identical requests (double-click, retry-on-timeout,
  or a scripted double-submit) — not remotely triggerable by a single actor in the way an
  access-control bug would be. Consequence is duplicate data/violated governance invariants,
  not unauthorized access.
- **Recommended correction:** Move each check inside the `BEGIN IMMEDIATE` transaction
  immediately before the corresponding `INSERT`, and add a `UNIQUE` constraint on
  `reviewer_batches.source_checksum` as a hard backstop (the schema currently declares it
  `NOT NULL` but not `UNIQUE`).
- **Confidence:** High for the reproduced case (batch duplication); Medium (code-pattern
  analysis, not independently threaded) for the other two instances of the same pattern.

### Finding 5 — Test/demo artifacts are present inside the verified release package
- **Severity:** Low
- **File/line:** `private_uploads/written/attempt_3_a185f7ae13a6/page_1.jpg`;
  `content_intake_uploads/IMP-20260804122305-*.csv` (×3); empty `pilot_backups/`
- **Reproduction:** Opened directly. The image is a synthetic placeholder (repeated "Biology
  answer line N" text at regular intervals — not real handwriting or student content). The
  three CSVs are near-duplicate synthetic import-test fixtures (same sample enzyme-specificity
  question, three auto-generated import IDs), consistent with leftover artifacts from testing
  the import feature shortly before packaging (timestamps all `2026-08-04 12:22–12:23`,
  minutes before the package was built).
- **Expected behaviour:** A distributable release package should not bundle test/dev-session
  artifacts.
- **Actual behaviour:** All of the above are present and are correctly included in the
  release's own 241-entry SHA-256 manifest (i.e., this is not a corrupted or tampered
  package — it is exactly what was intentionally packaged).
- **Impact:** None to confidentiality or correctness — verified directly that none of it is
  real personal data. Purely a packaging-hygiene issue.
- **Recommended correction:** Exclude `private_uploads/`, `content_intake_uploads/`, and
  `pilot_backups/` from the packaging step, and regenerate the manifest.
- **Confidence:** High.

### Finding 6 — `app.py` is a single 10,647-line file
- **Severity:** Informational
- Compiles and runs correctly; not a functional defect. Flagged as a maintainability/review-
  difficulty cost worth addressing at some point (e.g., splitting into blueprints), unrelated
  to this release's correctness.

### Finding 7 — Comment-length validation can be satisfied without meaningful content
- **Severity:** Informational
- `reviewer_workspace_engine.py` line 311 requires 8+ characters (after stripping whitespace)
  for any non-`ACCEPT_UNCHANGED` decision — correctly rejects empty/whitespace-only comments
  (verified live), but a string like `"........"` would technically pass. Low practical impact;
  noted for completeness since the brief specifically asks about this class of check.

---

## 7. Verified / partially verified / unverified / contradicted claims

**Verified (static and dynamic, both):**
package integrity (241/241 hash-verified); all Python compiles; all 107 templates parse;
eight `reviewer_*` tables exactly as claimed; confidential fields excluded from reviewer
snapshots (code-read *and* live injection test); CSRF enforced globally (live 400 on missing
token); reviewer route-fencing across 10 distinct protected routes (live); cross-reviewer IDOR
denied (live); invitation single-use (live replay rejected); timer server-side clamping (live);
batch size cap at exactly 100/101 (live); duplicate-ID-in-batch rejection (live); comment
requirement (live); second-reviewer independence *at the actual application layer* (live);
agreement → `SECOND_REVIEW_AGREED` (live); disagreement → `ADJUDICATION_REQUIRED` (live);
decision locking after independent agreement (live); blind review — no leak of the first
reviewer's decision to the second before their own submission (live, after disconfirming an
initial false positive in my own test); zero live-bank writes from the reviewer engine
(full source-text scan); zero `|safe`/`Markup()` escape-disabling anywhere in 107 templates,
plus a live script/image-tag injection test confirming correct HTML-escaping; Teacher of the
Year — no nomination route/form anywhere, button genuinely disabled, not in student core nav
(code read); migration dry-run — isolates from source, preserves all core counts, creates
new schema correctly empty (live, against a realistic simulated pre-upgrade database); all
366 claimed smoke-test checks (live, fresh run per suite); genuine mid-batch stop/save/resume
— completed 2 of 5 items, logged out, logged back in, landed exactly on item 3 with no
duplicated or lost decisions (live); the duplicate-batch race condition (Finding 4, live,
deterministic).

**Partially verified:**
SQL-injection resistance — every dynamic-SQL construction site I checked uses either
hardcoded or allowlist-validated identifiers with parameterized values throughout; this was
spot-checked across the highest-risk-looking patterns, not exhaustively verified line-by-line
across all 214 routes. Accessibility (keyboard focus/ARIA) — verified structurally (skip-link,
`aria-label`, `aria-disabled` present in the relevant markup) but not with a real
screen reader or keyboard-only session. Admin quality/timing analytics — the underlying
`assignment_progress()`/`assignment_quality()` math (median, percentages, division-by-zero
guards) was checked by hand and cannot exceed 100%, but the rendered admin page was not
visually inspected in a browser.

**Unverified (outside this environment's reach):**
real browser/cross-browser rendering; live SMTP invitation delivery; realistic concurrent
multi-reviewer load at production scale; legal/confidentiality wording adequacy (not a
technical question); 200% zoom and assistive-technology testing.

**Contradicted by evidence:** none. Every specific, checkable claim in the changelog, build
report, and acceptance checklist was either fully confirmed or confirmed-with-a-caveat; the
four Medium findings above are gaps the documents never explicitly claimed were covered, not
contradictions of a stated claim.

---

## 8. Specific verdicts

- **Reviewer-confidentiality verdict:** **Pass.** Adversarially tested (fenced routes, IDOR,
  injected fake-confidential fields, XSS injection) and held in every case.
- **Live-system write-boundary verdict:** **Pass.** `reviewer_workspace_engine.py` contains no
  reference to the live `questions`, `attempts`, `mastery_records`, or `study_plans` tables
  anywhere in its source.
- **First-review/second-review/adjudication verdict:** **Pass, with Finding 1.** The state
  machine itself (agree/disagree/lock routing) is correctly implemented and live-verified;
  the independence guard is correctly enforced at the application layer today but has a
  defense-in-depth gap at the shared-library layer.
- **Active-time tracking verdict:** **Pass, with Finding 2.** Per-tick clamping is correct
  and live-verified; tick *frequency* is unthrottled.
- **Migration and rollback verdict:** **Pass.** Dry-run correctly isolates from the source
  database and preserves all core data; rollback is a documented backup-restore, not
  independently exercised in this pass (restoring a file is low-risk and was not felt to need
  separate live reproduction given the backup step's checksum was independently confirmed).
- **Release-blocker register:** None of the four Medium findings block a controlled pilot
  with a small, known reviewer population. All four are recommended fixes before a larger or
  external reviewer population is onboarded.

---

## 9. Controlled-pilot recommendation

Proceed to a controlled pilot with a small number of named, trusted reviewers, conditional on:

1. Closing Findings 1–4 (all are small, well-scoped code changes with clear fixes above).
2. Excluding the test artifacts in Finding 5 from the shipped package.
3. Completing the acceptance-checklist items the release itself already lists as outstanding:
   real browser/mobile/assistive-technology testing, live SMTP delivery test, legal/
   confidentiality wording review, and a realistic concurrent-reviewer load test.

---

## 10. Confirmation

No source file inside the package was created, edited, or deleted during this review. All
work was performed against copies in a separate working directory and against disposable
SQLite databases created solely for this audit.