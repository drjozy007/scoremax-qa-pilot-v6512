"""Dependency-light acceptance for ScoreMax V6.5.11 synthetic learner pilot.

Runs without Flask/Werkzeug so the portable package can prove its QA-state and scoring
contracts even in constrained qualification sandboxes. Full Flask/browser-login runtime
acceptance remains a separate deployment gate.
"""
from __future__ import annotations

import ast
import json
import sqlite3
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mastery_lab_engine as lab
import qa_synthetic_learner as qa


REAL_R2_Q = {
    "programme": "FSc Part 2",
    "subject": "Biology",
    "chapter": "Chapter 18",
    "source_lineage": {
        "source": "PECTAA Biology Grade 12, Chapter 18, printed p.84-85",
        "r2_status": "PENDING",
        "approved_for_students": False,
    },
    "question_id": "BIO12-CH18-B04-Q220",
    "external_version": "R2-HOLD-v1.3.5",
    "family_type": "standard_mcq",
    "relation_type": "independent_seed",
    "mastery_level": "Exam Ready",
    "cognitive_demand": "Application",
    "stimulus": {
        "text": "Two heterozygous Rr pea plants are crossed for seed shape, where round is dominant to wrinkled."
    },
    "question": "State the expected F2 phenotypic ratio from a standard monohybrid cross of two heterozygotes with complete dominance.",
    "options": [
        {"id": "A", "text": "1 round: 1 wrinkled"},
        {"id": "B", "text": "3 round: 1 wrinkled"},
        {"id": "C", "text": "1 round: 2 intermediate: 1 wrinkled"},
        {"id": "D", "text": "9 round-yellow: 3 round-green: 3 wrinkled-yellow: 1 wrinkled-green"},
    ],
    "marking_config": {"marks": 1, "correct_option_ids": ["B"]},
    "answer_config": {},
}


def actual_live_marker():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted = {"safe_json", "canonical_question_type", "mark_question_response"}
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
    module = ast.Module(body=funcs, type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"json": json}
    exec(compile(module, "app.py::<marking-contract>", "exec"), ns)
    return ns["mark_question_response"]


def new_db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    lab.init_mastery_lab_schema(c)
    qa.init_schema(c)
    # Sentinels emulate live product tables; QA functions must never write them.
    c.executescript(
        """
        CREATE TABLE attempts(id INTEGER PRIMARY KEY, marker TEXT);
        CREATE TABLE mastery_records(id INTEGER PRIMARY KEY, marker TEXT);
        CREATE TABLE growth_events(id INTEGER PRIMARY KEY, marker TEXT);
        """
    )
    c.commit()
    return c


def import_real(c: sqlite3.Connection) -> sqlite3.Row:
    result = lab.import_candidate_batch(
        c,
        [REAL_R2_Q],
        filename="BIO_G12_CH18_R2_HOLD_ONLY_521Q_v1_3_5.xlsx",
        file_type="xlsx",
        source_system="POWER_HOUSE_R2_QA_ONLY",
        source_reference="BIO12 CH18 targeted R2 hold",
    )
    assert result["imported_count"] == 1
    row = c.execute(
        "SELECT * FROM mastery_lab_questions WHERE external_question_id=?",
        (REAL_R2_Q["question_id"],),
    ).fetchone()
    assert row is not None
    return row


def add_identity(c: sqlite3.Connection, *, user_id: int, kind: str, code: str) -> None:
    c.execute(
        """INSERT INTO mastery_lab_learner_identities(user_id,identity_code,learner_kind,status,release_flags_json)
           VALUES(?,?,?,'ACTIVE',?)""",
        (user_id, code, kind, qa.canonical_json(qa.QA_RELEASE_FLAGS)),
    )
    c.commit()


def counts(c: sqlite3.Connection) -> tuple[int, int, int]:
    return tuple(int(c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"]) for t in ("attempts", "mastery_records", "growth_events"))


def test_real_r2_qa_partition_and_identity() -> None:
    c = new_db()
    q = import_real(c)
    assert q["content_environment"] == "QA_SANDBOX_ONLY"
    assert q["student_release_status"] == "NOT_STUDENT_RELEASED"
    assert q["bank_approval_status"] == "NOT_BANK_APPROVED"
    assert q["mastery_validity"] == "NOT_VALID_FOR_REAL_MASTERY"
    assert q["external_question_id"] == "BIO12-CH18-B04-Q220"
    assert q["external_version"] == "R2-HOLD-v1.3.5"
    assert qa.learner_type_for_lab_question(q) == "single_choice"
    assert qa.correct_response_for_lab_question(q) == "B"
    assert qa.incorrect_response_for_lab_question(q) != "B"


def test_actual_live_marker_parity_and_safe_rejections() -> None:
    marker = actual_live_marker()
    c = new_db()
    sample = lab.sample_candidate_corpus()["questions"]
    result = lab.import_candidate_batch(c, sample, filename="technical_sample.json", file_type="json")
    assert result["imported_count"] == len(sample)
    tested = 0
    rejected = {}
    for row in c.execute("SELECT * FROM mastery_lab_questions WHERE active=1 ORDER BY id").fetchall():
        eligible, reason = qa.deterministic_eligibility(row)
        if not eligible:
            rejected.setdefault(row["family_type"], set()).add(reason)
            continue
        live_q = qa.live_adapter_question(row)
        for response in (qa.correct_response_for_lab_question(row), qa.incorrect_response_for_lab_question(row)):
            selected = ",".join(response) if isinstance(response, list) else str(response)
            live_ok, live_marks, _ = marker(live_q, selected, {})
            lab_result = lab.score_lab_response(row, selected)
            assert bool(live_ok) == bool(lab_result["is_correct"])
            assert abs(float(live_marks) - float(lab_result["awarded_marks"])) < 1e-9
            tested += 1
    assert tested >= 20
    assert "matching" in rejected
    assert "ordering" in rejected
    assert "constructed_response" in rejected
    assert "cloze" in rejected  # technical sample is deliberately two-blank
    multi = {
        "family_type": "cloze",
        "answer_config_json": json.dumps({"blanks": [{"accepted_answers": ["a"]}, {"accepted_answers": ["b"]}]}),
        "marking_config_json": json.dumps({"marks": 2}),
    }
    relative = {
        "family_type": "numerical_interpretation",
        "answer_config_json": "{}",
        "marking_config_json": json.dumps({"marks": 1, "correct_value": 10, "tolerance": 0.1, "relative_tolerance": 0.05}),
    }
    negative = {
        "family_type": "standard_mcq",
        "answer_config_json": "{}",
        "marking_config_json": json.dumps({"marks": 1, "correct_option_ids": ["A"], "negative_marks": -0.25}),
    }
    assert qa.deterministic_eligibility(multi)[0] is False
    assert qa.deterministic_eligibility(relative)[0] is False
    assert qa.deterministic_eligibility(negative)[0] is False


def test_deterministic_attempt_writes_qa_only_and_mismatch_fails_closed() -> None:
    marker = actual_live_marker()
    c = new_db()
    q = import_real(c)
    add_identity(c, user_id=101, kind="DETERMINISTIC", code="PH_QA_DETERMINISTIC_001")
    before = counts(c)
    session = qa.create_e2e_session(c, user_id=101, question_id=int(q["id"]), expected_mode="CORRECT")
    live_q = qa.live_adapter_question(q)
    live_ok, live_marks, misconception = marker(live_q, "B", {})
    lab_result = lab.score_lab_response(q, "B")
    outcome = qa.record_attempt(
        c,
        session_id=int(session["id"]),
        user_id=101,
        response="B",
        live_result={"is_correct": live_ok, "awarded_marks": live_marks, "misconception": misconception},
        lab_result=lab_result,
    )
    assert outcome["result"] == "PASS"
    assert counts(c) == before == (0, 0, 0)

    second = qa.create_e2e_session(c, user_id=101, question_id=int(q["id"]), expected_mode="CORRECT")
    failed = qa.record_attempt(
        c,
        session_id=int(second["id"]),
        user_id=101,
        response="B",
        live_result={"is_correct": True, "awarded_marks": 1},
        lab_result={"is_correct": False, "awarded_marks": 0},
    )
    assert failed["result"] == "FAIL"
    assert counts(c) == (0, 0, 0)


def test_visual_evidence_is_identity_bound() -> None:
    c = new_db()
    q = import_real(c)
    add_identity(c, user_id=201, kind="VISUAL_SEMANTIC", code="PH_QA_VISUAL_001")
    add_identity(c, user_id=202, kind="VISUAL_SEMANTIC", code="PH_QA_VISUAL_002")
    session = qa.create_e2e_session(c, user_id=201, question_id=int(q["id"]), expected_mode="OBSERVE_ONLY")
    with tempfile.TemporaryDirectory() as td:
        shot = Path(td) / "capture.png"
        shot.write_bytes(b"synthetic-browser-png-evidence")
        capture = qa.record_visual_capture(c, session_id=int(session["id"]), user_id=201, screenshot_path=str(shot))
        try:
            qa.record_visual_judgement(
                c,
                visual_review_id=int(capture["visual_review_id"]),
                session_id=int(session["id"]),
                user_id=202,
                judgement="PASS",
                findings=[],
                judge_type="TEST",
            )
        except ValueError:
            pass
        else:
            raise AssertionError("Cross-identity visual evidence mutation was not rejected")
        good = qa.record_visual_judgement(
            c,
            visual_review_id=int(capture["visual_review_id"]),
            session_id=int(session["id"]),
            user_id=201,
            judgement="PASS",
            findings=[],
            judge_type="TEST",
        )
        assert good["judgement"] == "PASS"


def test_static_route_and_renderer_fences() -> None:
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    route_start = app_source.index("@app.route('/qa/synthetic')")
    route_end = app_source.index("@app.route('/admin/mastery-lab", route_start)
    region = app_source[route_start:route_end]
    for forbidden in (
        "process_mastery_result",
        "update_learning_intelligence_from_attempt",
        "capture_scoremax_attempt",
        "INSERT INTO attempts",
        "INSERT INTO attempt_answers",
        "emit_growth_event",
        "mastery_records",
        "learning_plan",
    ):
        assert forbidden not in region
    assert "if u['role']!='qa_student':" in app_source
    assert "q.external_question_id=?" in region  # exact opaque-ID lookup, not numeric inference
    assert "q.external_version=?" in region  # version-pinned qualification; fail closed on ID/version ambiguity
    stager = (ROOT / "stage_qa_synthetic_pilot_fixture_v6_5_11.py").read_text(encoding="utf-8")
    assert "lab.import_candidate_batch" in stager  # reuse existing Mastery Laboratory importer; no parallel importer
    assert "SCOREMAX_QA_SYNTHETIC_STAGE_CONFIRM" in stager
    assert "external_question_id=? AND external_version=?" in stager
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
    learner = (ROOT / "templates" / "take_test_v4.html").read_text(encoding="utf-8")
    assert "qa_synthetic_session" in base
    assert 'data-qa-sandbox="true"' in learner
    assert "Review & Submit" in learner
    assert "if not qa_sandbox" in learner


def run_all() -> None:
    tests = [
        test_real_r2_qa_partition_and_identity,
        test_actual_live_marker_parity_and_safe_rejections,
        test_deterministic_attempt_writes_qa_only_and_mismatch_fails_closed,
        test_visual_evidence_is_identity_bound,
        test_static_route_and_renderer_fences,
    ]
    for test in tests:
        test()
        print("PASS", test.__name__)
    print(f"PASS ALL {len(tests)} ScoreMax V6.5.11 dependency-light acceptance tests")


if __name__ == "__main__":
    run_all()
