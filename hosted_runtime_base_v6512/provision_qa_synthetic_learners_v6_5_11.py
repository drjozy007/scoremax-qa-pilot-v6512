"""Provision the two ScoreMax V6.5.11 synthetic learner pilot identities.

Safety: the script refuses to run unless SCOREMAX_QA_SYNTHETIC_PROVISION_CONFIRM=YES.
Use a disposable/pilot SCOREMAX_DB for qualification. Plaintext passwords are never
persisted by this script; generated credentials are printed only on first creation.
"""
from __future__ import annotations

import json
import os

if os.getenv("SCOREMAX_QA_SYNTHETIC_PROVISION_CONFIRM", "").strip().upper() != "YES":
    raise SystemExit(
        "Refusing synthetic learner provisioning. Set SCOREMAX_QA_SYNTHETIC_PROVISION_CONFIRM=YES "
        "and point SCOREMAX_DB at the intended disposable/pilot database."
    )

import app
import qa_synthetic_learner as qa

app.init()
c = app.db()
try:
    qa.init_schema(c)
    rows = [
        qa.provision_identity(c, "DETERMINISTIC", password=os.getenv("SCOREMAX_QA_DETERMINISTIC_PASSWORD") or None),
        qa.provision_identity(c, "VISUAL_SEMANTIC", password=os.getenv("SCOREMAX_QA_VISUAL_PASSWORD") or None),
    ]
    c.commit()
finally:
    c.close()

print(json.dumps({"database": str(app.DB), "identities": rows, "plaintext_persisted": False}, indent=2))
