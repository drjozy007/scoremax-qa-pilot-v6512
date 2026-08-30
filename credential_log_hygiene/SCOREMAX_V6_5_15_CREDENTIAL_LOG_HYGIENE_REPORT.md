# ScoreMax V6.5.15 Credential-Log Hygiene — Fix Candidate

Status: **PRE-DEPLOYMENT HARDENING · NOT YET PRODUCTION-AUTHORIZED**

## Why this exists

The final 3-in-1 Synthetic QA qualification passed functionally but explicitly left production authorization blocked because bootstrap/provisioning paths could expose plaintext credentials in runtime logs. A further attack also found the local password-reset fallback could print a reset URL containing a live reset token.

## Exact defects found

1. `app.py` printed the initial bootstrap-admin password.
2. `app.py` printed the rotated legacy-demo admin password.
3. `qa_synthetic_learner.provision_identity()` returned plaintext password material on creation/explicit rotation.
4. `provision_qa_synthetic_learners_v6_5_11.py` JSON-printed that return payload.
5. local forgot-password fallback printed `reset_url`, exposing the single-use reset token in logs.

## Candidate controls

- initial admin creation/legacy rotation requires configured `SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD`; no random password is generated and then leaked through logs;
- stdout reports only that a configured secret was used, never its value;
- synthetic-QA provisioning requires both `SCOREMAX_QA_DETERMINISTIC_PASSWORD` and `SCOREMAX_QA_VISUAL_PASSWORD`;
- `provision_identity()` never returns plaintext password material;
- provisioning output contains safe metadata only (`credential_supplied`, not credential value);
- reset URLs are never printed. In local development, an operator may explicitly configure `SCOREMAX_LOCAL_RESET_OUTBOX`; the URL is appended through an OS file descriptor created with mode `0600`. Otherwise the reset URL is suppressed and the operator is instructed to configure SMTP/outbox.

## Exact source identities

Before patch:
- `app.py` SHA-256 `d6b12c9f22158ba5bce54b9b0da306e20f68512cdbc492e79ef1b7921ac59e60`
- `qa_synthetic_learner.py` SHA-256 `f92411486a6d821360f9feb987332b929ededc91c15144401a874b42247fe1c2`
- `provision_qa_synthetic_learners_v6_5_11.py` SHA-256 `60bd096589455b662492f758c9af03f0efe77c1d9ee03025ea1651813f3bc036`

After patch:
- `app.py` SHA-256 `bd1b6703b8cc0f26588a2236a1451acffb081655e975c08490ddfbbc2e560c21`
- `qa_synthetic_learner.py` SHA-256 `7cca387fd48b42cb21c20c98acb666027acea55a054cd898dce7d489dbccd4b6`
- `provision_qa_synthetic_learners_v6_5_11.py` SHA-256 `e4a165458306e533f094e49983dbc80ac6063728bf5577106d71a98bb1aa912a`

## Evidence already executed locally

Against a complete extracted V6.5.15 candidate with these three patched files:

- Python compile: **PASS** for all 3 changed files.
- Existing dependency-light `tests/test_v6_5_11_synthetic_learner_contract.py`: **5/5 PASS**.
- Dependency-free AST/source credential-log attack: **PASS**.

The attempted application-startup stdout capture could not run in the current container because Flask is not installed. That is an environment limitation, not a PASS. Therefore the final production-authorization gate remains:

> Apply the exact patch in an isolated V6.5.15 runtime/QA service, run bootstrap + QA provisioning + password-reset negative controls, capture stdout/stderr, prove no credential/token values occur, then rerun the qualified Synthetic QA regression/E2E subset.

## Deployment boundary

This branch does **not** deploy ScoreMax and does not alter the current qualified QA service. It carries exact patch bytes, exact before/after hashes, and a dependency-free verifier so the fix can be incorporated into the next governed ScoreMax QA runtime candidate.
