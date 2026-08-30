# ScoreMax V6.5.8 — Integration Control Handoff

Use the same frozen connected release `PH-SM-CONNECTED-BATCH01-300-20260823`, release version `2`.

Re-run only the reserved learner chain:
`learner delivery → attempt pin → marking → Weak Area → Recovery → successful recall/reconfirmation → mastery → SM_PH_DELIVERY_EVIDENCE_V1 → Power House advisory receipt/replay`.

Expected corrections:
1. Unsuppressed recovery/reconfirmation telemetry reflects immutable attempt evidence instead of false zeroes; below-minimum-N aggregates remain suppressed/privacy-safe.
2. Successful recall/reconfirmation does not regress an already recovered area to Weak Area solely because cumulative historic accuracy remains below 75%.

Target: `confirmed_total=0 · P0=0 · P1=0`.

Power House requires no change from this learner-chain finding. Growth Engine remains untouched.
