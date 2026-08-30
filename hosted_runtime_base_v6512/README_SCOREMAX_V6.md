# ScoreMax V6.0 — Written Response Intelligence

## Purpose

V6.0 extends the frozen V5.5 blueprint/calibration baseline with a governed student-written-answer system. Power House remains authoritative for questions, mark schemes, propositions, misconceptions, scaffolds, unseen variants, academic approval and versioning. ScoreMax imports immutable approved packages and handles delivery, student evidence, marking workflow, feedback, recovery, reconfirmation and mastery evidence.

## First controlled scope

The supplied sample package represents an **FSc Biology Part I** pilot family. The architecture remains framework- and country-agnostic.

## Implemented and testable

- immutable Power House written-assessment package import;
- checksum validation and optional HMAC-signed production transport;
- Admin activation without direct editing of academic values;
- typed Practice and Mock answer workflows;
- autosaved/versioned answer evidence;
- transparent point-level deterministic pilot marking;
- factual contradiction, misconception and command-verb checks;
- two independent local marking strategies followed by conservative reconciliation;
- confirmed/provisional/more-evidence result states;
- original, improvement and unseen-reconfirmation answer versions;
- structured recovery tasks and Study Plan write-back;
- structured written mastery evidence without directly bypassing the existing Mastery Engine;
- Build the Answer delivery from approved Power House scaffold definitions;
- private multi-page handwriting upload architecture;
- image-quality evidence and retryable processing jobs;
- side-by-side OCR transcript confirmation workflow through an explicitly labelled local simulation provider;
- Approved Student Exemplar Library governance: perfect score, confirmed independent attempt, academic review, separate opt-in consent, anonymisation by default, hidden release state and premium/exam-window feature control;
- usage ledger foundations for later cost/allowance management.

## Deliberately not claimed

- Production-quality handwriting recognition is **not** included. The local OCR simulation exists only to test the workflow and audit model.
- The deterministic local marker is a transparent pilot harness, not a validated high-stakes certification engine.
- External AI/vision graders, production OCR providers and provider data-processing terms must be configured and validated before live use.
- Urdu handwriting, unrestricted freehand diagram marking, IRT/DIF and external percentile validation are deferred.
- Routine student submissions are designed not to require human marking, but academic validation of the automated system remains mandatory.

## Default release controls

- Written Response Intelligence: `PILOT`
- Handwriting/OCR: `PILOT`
- Build the Answer: `PILOT`
- Approved Student Exemplar Library: `HIDDEN`

Only explicitly enabled pilot users can access pilot features. The exemplar library remains unavailable to ordinary users until academically and commercially released.

## Start

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run:

```bash
python app.py
```

On Windows, use `start_scoremax_v6.bat`.

## Tests

```bash
python smoke_tests_v6.py
python smoke_tests_v5_5.py
```

The first verifies V6 written-response governance and workflows. The second is the complete V5.5 regression suite.
