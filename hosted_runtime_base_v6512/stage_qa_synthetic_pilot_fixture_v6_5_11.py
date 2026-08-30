"""Stage one governed real R2-held question into the existing ScoreMax Mastery Laboratory.

This is a qualification-fixture wrapper, NOT a second importer. It calls the existing
mastery_lab_engine.import_candidate_batch() and refuses to run unless explicitly enabled.
Use only against a disposable/pilot SCOREMAX_DB.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

if os.getenv("SCOREMAX_QA_SYNTHETIC_STAGE_CONFIRM", "").strip().upper() != "YES":
    raise SystemExit(
        "Refusing QA fixture staging. Set SCOREMAX_QA_SYNTHETIC_STAGE_CONFIRM=YES "
        "and point SCOREMAX_DB at the intended disposable/pilot database."
    )
if not os.getenv("SCOREMAX_DB", "").strip():
    raise SystemExit("Refusing QA fixture staging: SCOREMAX_DB must be set explicitly.")

import app
import mastery_lab_engine as lab

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "qualification_fixtures" / "BIO_G12_CH18_R2_HOLD_QA_FIXTURE_001.json"
EXPECTED_FLAGS = dict(lab.LAB_RELEASE_FLAGS)

app.init()
c = app.db()
try:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    row = payload["question"]
    qid = str(row["question_id"])
    version = str(row["external_version"])
    existing = c.execute(
        """SELECT * FROM mastery_lab_questions
           WHERE active=1 AND external_question_id=? AND external_version=? ORDER BY id""",
        (qid, version),
    ).fetchall()
    if len(existing) > 1:
        raise RuntimeError("Fail closed: duplicate active QA rows exist for the exact opaque Question ID/version")
    if existing:
        q = existing[0]
        action = "ALREADY_STAGED_EXACT_VERSION"
    else:
        result = lab.import_candidate_batch(
            c,
            [row],
            filename=FIXTURE.name,
            file_type="json",
            source_system="POWER_HOUSE_R2_QA_ONLY",
            source_reference="BIO12 CH18 targeted R2 hold synthetic learner pilot",
        )
        if not result.get("ok"):
            raise RuntimeError("Existing Mastery Laboratory importer rejected fixture: " + json.dumps(result, ensure_ascii=False))
        c.commit()
        q = c.execute(
            """SELECT * FROM mastery_lab_questions
               WHERE active=1 AND external_question_id=? AND external_version=? ORDER BY id""",
            (qid, version),
        ).fetchone()
        action = "STAGED_VIA_EXISTING_MASTERY_LAB_IMPORTER"
    if q is None:
        raise RuntimeError("QA fixture was not found after staging")
    actual = {
        "content_environment": q["content_environment"],
        "student_release_status": q["student_release_status"],
        "bank_approval_status": q["bank_approval_status"],
        "mastery_validity": q["mastery_validity"],
    }
    if actual != EXPECTED_FLAGS:
        raise RuntimeError(f"QA partition mismatch: {actual!r}")
    print(json.dumps({
        "action": action,
        "database": str(app.DB),
        "external_question_id": qid,
        "external_version": version,
        "release_flags": actual,
        "academic_clearance_conferred": False,
        "learner_release_conferred": False,
    }, indent=2, sort_keys=True))
finally:
    c.close()
