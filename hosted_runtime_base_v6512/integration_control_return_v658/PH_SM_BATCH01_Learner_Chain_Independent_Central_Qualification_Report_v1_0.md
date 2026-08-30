# Power House × ScoreMax Batch01 — Learner Chain Independent Central Qualification Report v1.0

**Date:** 23 August 2026  
**Central decision:** **RECTIFICATION REQUIRED**  
**Confirmed:** `2 · P0=0 · P1=2`

## Frozen candidates under test

- **ScoreMax V6.5.7** — SHA-256 `a93edef7a4ea6cc4b8d5d8e27ef2eecdba29d0be441f974ecec5bebfcef9c118`
- **Power House CHANGE013H Batch01 two-tier rectification** — SHA-256 `22c133587d932854575c830609d720fb847f7e5e9930c9baab58e8635adcacc4`
- Existing connected content release: `PH-SM-CONNECTED-BATCH01-300-20260823`, release version `2`, already centrally accepted for 300-question staging/activation.

No frozen candidate was edited during the attack. Disposable copies of the already-connected ScoreMax and Power House databases were used.

## Mission

Exercise the next frozen vertical slice on the same connected 300-question release:

`learner delivery → response → exact-version attempt pinning → marking → weak area → recovery → recall/reconfirmation → formal mastery/reconfirmation → SM_PH_DELIVERY_EVIDENCE_V1 → Power House advisory intake/replay`

## What passed

### Exact question-version attempt pinning and marking — PASS

A real ScoreMax assessment session was created from the activated Power House inventory. After the session pin was created, the mutable current question projection for one item was deliberately altered, including its displayed text and current marking key.

The learner-facing assessment route still rendered the **pinned original projection**, not the mutated current row. The learner submitted the original correct answer and ScoreMax marked it correct using the pinned snapshot. `attempt_answers` retained the original Power House question-version ID, checksum, release ID/version/checksum and snapshot.

This proves historical attempt evidence is not re-attributed by a later current-state change.

### Weak-area creation — PASS

A controlled 10-question attempt on the learning outcome **“Negative feedback reduces system activity”** scored **40%**.

ScoreMax produced:

- evidence count: `10`
- correct count: `4`
- accuracy: `40.0%`
- state: **Weak Area**
- recall status: `repair_first`

The recovery selector correctly resolved the same learning outcome and returned sufficient governed live questions.

### Targeted recovery — PASS

A 3-question targeted recovery attempt on governed `RECOVERY` items scored **100%**.

ScoreMax changed the learning state to **Recovered**, and scheduled spaced recall. The cumulative accuracy remained `53.8%`, showing the explicit recovery transition is intentionally stronger than the raw historic average.

### Formal mastery and formal mastery reconfirmation — PASS

The frozen mastery-form builder generated a governed Foundation chapter form. A 100% form earned **Verified Foundation**. The verification due date was then moved into the past in the disposable qualification database and a fresh governed same-level form was generated under the normal unseen-family rules.

The second form passed and mastery history recorded:

`earned → verification_due → reconfirmed`

The resulting mastery state remained **Verified Foundation**.

### ScoreMax → Power House authenticated delivery-evidence transport — PASS

ScoreMax generated a real `SM_PH_DELIVERY_EVIDENCE_V1` outbox message from immutable attempt pins and dispatched it through the frozen worker signing path. The network socket was substituted with the exact Power House receiver in-process, while preserving bearer/HMAC headers, message identity, payload checksum, receipt validation and durable outbox state.

Power House returned `ACCEPTED`. Exact replay returned the **same durable receipt**. Power House created one advisory record and one inbox identity only.

### Power House authority boundary — PASS

Power House accepted the evidence as advisory only. A hash of all non-integration academic tables was identical before and after delivery evidence receipt:

`25cbce6dbc4d47261a076b3d885399a31f1140d8ad0e2dd6ea5384933efb756e`

Power House DB integrity remained `ok` with `0` foreign-key violations.

ScoreMax DB integrity also remained `ok` with `0` foreign-key violations.

---

# Confirmed findings

## INT-PHSM-B01-LRN-P1-001 — P1 — ScoreMax delivery-evidence recovery/reconfirmation counters are false zeros

The frozen `queue_delivery_evidence()` implementation groups immutable attempt evidence correctly, but unconditionally emits:

`recovery_attempts=0 · recovery_successes=0 · reconfirmation_attempts=0 · reconfirmation_successes=0`

To remove any privacy/minimum-N ambiguity, central qualification created **10 real recovery responses on each of three exact question versions** and **10 real recall/reconfirmation responses on each of three exact question versions**. All six item aggregates were unsuppressed (`sample_suppressed=false`).

### Recovery evidence

| Question | Actual recovery attempts | Actual correct | Emitted recovery attempts | Emitted successes | Suppressed |
|---|---:|---:|---:|---:|---|
| `BIO12-CH13-B01-147` | 10 | 10 | 0 | 0 | false |
| `BIO12-CH13-B02-104` | 10 | 10 | 0 | 0 | false |
| `BIO12-CH13-B03-065` | 10 | 10 | 0 | 0 | false |

### Reconfirmation evidence

| Question | Actual recall/reconfirmation attempts | Actual correct | Emitted reconfirmation attempts | Emitted successes | Suppressed |
|---|---:|---:|---:|---:|---|
| `BIO12-CH13-B03-104` | 10 | 10 | 0 | 0 | false |
| `BIO12-CH13-B04-036` | 10 | 10 | 0 | 0 | false |
| `BIO12-CH13-B05-048` | 10 | 10 | 0 | 0 | false |


This is materially false advisory telemetry. Power House correctly treats it as advisory, so the defect does not rewrite academic truth, but the data sent to academic review is wrong.

**Severity: P1.**

## INT-PHSM-B01-LRN-P1-002 — P1 — successful recall reopens an already recovered weak area

The same learner journey produced:

1. initial 40% evidence → **Weak Area**
2. targeted 100% recovery → **Recovered**
3. targeted 100% recall/reconfirmation → **Weak Area** again

After the successful recall, the recall scheduler itself correctly recorded:

- `successful_recalls=2`
- `last_score=100.0%`
- next interval `21` days

but the learner learning-state row regressed to:

- status: **Weak Area**
- cumulative accuracy: `62.5%`

The cause is the transition condition in `update_learning_intelligence_from_attempt()`: a clean targeted success forces `Recovered` only when the prior state is `Weak Area` or `Recovery`; it does not preserve `Recovered` on a successful `recall`. The function then falls back to cumulative historic accuracy, which is still below 75%, and incorrectly reopens the weak area.

A successful reconfirmation must not make a previously recovered area weaker.

**Severity: P1.**

---

## Central decision

> **PH → ScoreMax Batch01 learner chain — RECTIFICATION REQUIRED**
>
> `confirmed_total=2 · P0=0 · P1=2`

The core learner delivery, immutable pinning, marking, weak-area creation, targeted recovery, formal mastery, formal mastery reconfirmation, authenticated ScoreMax→Power House dispatch, replay and Power House advisory-only boundary are otherwise green.

### Ownership

Both confirmed findings belong to **ScoreMax**. **No Power House rectification is required from this learner-chain evidence.** Growth Engine remains untouched.

### Freeze rule

Do not start the 1,500 connected batch yet. Keep the exact same 300-question Batch01 release frozen. Rectify only these two ScoreMax learner/evidence semantics, rerun this exact learner chain, and if `P0=0 · P1=0`, continue immediately to 1,500 and then the Growth Engine chain.

## Qualification caveat

This was a portable/in-process central qualification using ScoreMax's own lightweight Flask/Werkzeug compatibility stubs from its deterministic test harness because the central environment does not contain the Flask runtime package. The actual ScoreMax route/business functions, SQLite transactions, session pinning, marking, mastery, outbox signing/receipt logic and exact Power House receiver logic were exercised. Supported-Windows/browser and externally deployed HTTPS remain separate environment gates.
