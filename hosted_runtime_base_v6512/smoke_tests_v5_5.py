"""ScoreMax V5.5 deterministic smoke/regression suite.

This suite exercises real ScoreMax schema, migration, blueprint validation,
publication governance, assembly, pinning, projections and policy logic against
a temporary SQLite database.  It uses a lightweight Flask/Werkzeug compatibility
stub so it can also run in restricted build environments without a web server.
Browser acceptance remains separate and is documented in the V5.5 checklist.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import types
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def install_framework_stubs() -> tuple[types.ModuleType, object]:
    flask = types.ModuleType("flask")

    class JinjaEnv:
        def __init__(self):
            self.globals = {}

    class Config(dict):
        pass

    class Flask:
        def __init__(self, *args, **kwargs):
            self.jinja_env = JinjaEnv()
            self.config = Config()
            self.routes = []

        def route(self, *args, **kwargs):
            def decorator(fn):
                self.routes.append((args, kwargs, fn))
                return fn
            return decorator

        def before_request(self, fn):
            return fn

        def context_processor(self, fn):
            return fn

        def run(self, *args, **kwargs):
            return None

    class Request:
        method = "GET"
        form = {}
        headers = {}
        path = ""
        endpoint = ""
        args = {}
        files = {}
        host_url = "http://test/"
        referrer = ""

    request = Request()
    flask.Flask = Flask
    flask.render_template = lambda *args, **kwargs: ("render", args, kwargs)
    flask.request = request
    flask.redirect = lambda value: value
    flask.url_for = lambda name, **kwargs: "/" + name
    flask.session = {}
    flask.flash = lambda *args, **kwargs: None
    flask.send_file = lambda *args, **kwargs: ("file", args, kwargs)
    flask.jsonify = lambda *args, **kwargs: args[0] if len(args) == 1 else args

    def abort(*args, **kwargs):
        raise RuntimeError(f"abort{args}")

    flask.abort = abort
    sys.modules["flask"] = flask

    werkzeug = types.ModuleType("werkzeug")
    security = types.ModuleType("werkzeug.security")
    security.generate_password_hash = lambda value: "hash:" + hashlib.sha256(str(value).encode()).hexdigest()
    security.check_password_hash = lambda stored, value: stored == "hash:" + hashlib.sha256(str(value).encode()).hexdigest()
    sys.modules["werkzeug"] = werkzeug
    sys.modules["werkzeug.security"] = security
    return flask, request


def upload_for(payload: dict, filename: str = "blueprint.json"):
    class Upload:
        def __init__(self):
            self.filename = filename

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return Upload()


def recalc(payload: dict, calculate_checksum) -> dict:
    out = deepcopy(payload)
    out.pop("signature", None)
    out["checksum"] = calculate_checksum(out)
    return out


def add_governed_inventory(app, c, counts: dict[str, int]) -> dict[str, list[int]]:
    levels = ["Foundation", "Exam Ready", "Advanced", "Distinction", "Expert", "Elite"]
    ids: dict[str, list[int]] = {}
    for subject, count in counts.items():
        ids[subject] = []
        chapter_count = 10 if subject in {"Biology", "Chemistry", "Physics"} else 3
        for index in range(count):
            family_id = f"{subject[:3].upper()}-BP-{index + 1:04d}"
            row = {
                "family_id": family_id,
                "country": "Pakistan",
                "qualification": "MDCAT",
                "programme": "MDCAT",
                "subject": subject,
                "exam_board": "PMDC",
                "curriculum_version": "2026",
                "concept": f"{subject} construct {index + 1}",
                "construct_signature": f"{subject} construct {index + 1}",
                "invariants_json": "[]",
            }
            family_key = app.upsert_question_family(c, row, review_status="Approved", active=1)
            level = levels[index % len(levels)]
            difficulty = ["Easy", "Moderate", "Difficult"][index % 3]
            cur = c.execute(
                """INSERT INTO questions(
                  question_id,family_id,variant,programme,qualification,exam_board,curriculum_version,
                  subject,chapter,topic,subtopic,qtype,level,question,option_a,option_b,option_c,option_d,
                  answer,explanation,status,review_status,active,family_key,is_demo,difficulty,
                  rights_status,scoremax_ready,assessment_purpose,difficulty_source)
                  VALUES(?,?,?,?,?,?,?,?,?,?,'Subtopic','MCQ',?,?,?,?,?,?,?,'Explanation',
                  'Approved','Approved',1,?,0,?,'ScoreMax Original',1,'practice|test|mock|mastery','authoring')""",
                (
                    f"BP-{subject[:3].upper()}-{index + 1:04d}",
                    family_id,
                    "A",
                    "MDCAT",
                    "MDCAT",
                    "PMDC",
                    "2026",
                    subject,
                    f"Chapter {(index % chapter_count) + 1}",
                    f"Topic {index + 1}",
                    level,
                    f"{subject} question {index + 1}?",
                    "A",
                    "B",
                    "C",
                    "D",
                    "A",
                    family_key,
                    difficulty,
                ),
            )
            ids[subject].append(cur.lastrowid)
    c.commit()
    return ids


def add_attempt(app, c, student_id: int, question_ids: list[int], correct: bool, kind: str = "standard") -> int:
    score = 100.0 if correct else 0.0
    cur = c.execute(
        """INSERT INTO attempts(student_id,scope,programme,subject,chapters,level,score,correct_count,total_count,assessment_kind)
           VALUES(?,'smoke','MDCAT','','','',?,?,?,?)""",
        (student_id, score, len(question_ids) if correct else 0, len(question_ids), kind),
    )
    attempt_id = cur.lastrowid
    c.executemany(
        """INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,marks_awarded,
          question_version,misconception_triggered,confidence,response_time_seconds)
          VALUES(?,?,?,?,?,1,'','confident',20)""",
        [(attempt_id, qid, "A" if correct else "B", 1 if correct else 0, 1 if correct else 0) for qid in question_ids],
    )
    c.commit()
    return attempt_id


def main() -> None:
    flask, request = install_framework_stubs()
    temp_root = Path(tempfile.mkdtemp(prefix="scoremax_v55_smoke_"))
    os.environ["SCOREMAX_DB"] = str(temp_root / "scoremax.db")
    os.environ["SCOREMAX_ENV"] = "local"
    os.environ.pop("SCOREMAX_POWERHOUSE_SHARED_SECRET", None)
    os.environ.pop("SCOREMAX_REQUIRE_POWERHOUSE_SIGNATURE", None)
    sys.path.insert(0, str(ROOT))

    import app  # noqa: WPS433
    from blueprint_engine import calculate_checksum, calculate_signature, validate_blueprint_payload

    checks: list[str] = []

    def ok(name: str, condition: bool = True):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print("PASS:", name)

    app.init()
    app.init()
    c = app.db()
    ok("fresh schema and idempotent migration", c.execute("SELECT COUNT(*) n FROM assessment_blueprints").fetchone()["n"] == 0)
    ok("V5.4.2 demo bank preserved", c.execute("SELECT COUNT(*) n FROM questions").fetchone()["n"] == 95)
    c.close()

    sample = json.loads((ROOT / "sample_powerhouse_mdcat_2026_blueprint.json").read_text())
    valid = validate_blueprint_payload(sample)
    ok("valid 180-question blueprint passes", valid["valid"] and valid["normalized"]["total_questions"] == 180)

    bad_counts = recalc(sample, calculate_checksum)
    bad_counts["sections"][0]["question_count"] = 80
    bad_counts = recalc(bad_counts, calculate_checksum)
    ok("counts not summing to total fail", not validate_blueprint_payload(bad_counts)["valid"])

    bad_percent = deepcopy(sample)
    bad_percent["sections"][0]["weight_percent"] = 44
    bad_percent = recalc(bad_percent, calculate_checksum)
    ok("percentages not summing to 100 fail", not validate_blueprint_payload(bad_percent)["valid"])

    duplicate_subject = deepcopy(sample)
    duplicate_subject["sections"][1]["subject"] = "Biology"
    duplicate_subject = recalc(duplicate_subject, calculate_checksum)
    ok("duplicate subject fails", not validate_blueprint_payload(duplicate_subject)["valid"])

    tampered = deepcopy(sample)
    tampered["sections"][0]["question_count"] = 79
    ok("tampered checksum fails", not validate_blueprint_payload(tampered)["valid"])

    signed = deepcopy(sample)
    secret = "scoremax-powerhouse-smoke-secret"
    signed["signature"] = calculate_signature(signed, secret)
    ok("signed payload verifies", validate_blueprint_payload(signed, shared_secret=secret)["valid"])

    flask.session.update({"user_id": 1, "role": "admin", "full_name": "Admin"})
    request.files = {"blueprint_file": upload_for(sample)}
    request.form = {}
    request.referrer = ""
    app.admin_import_assessment_blueprint()
    c = app.db()
    bp = c.execute("SELECT * FROM assessment_blueprints").fetchone()
    ok("approved Power House snapshot imports as VALIDATED", bp and bp["local_status"] == "VALIDATED")
    ok("blueprint section count is five", c.execute("SELECT COUNT(*) n FROM assessment_blueprint_sections WHERE blueprint_id=?", (bp["id"],)).fetchone()["n"] == 5)
    c.close()

    request.files = {"blueprint_file": upload_for(sample)}
    app.admin_import_assessment_blueprint()
    c = app.db()
    ok("identical duplicate import is idempotent", c.execute("SELECT COUNT(*) n FROM assessment_blueprints").fetchone()["n"] == 1)
    c.close()

    conflicting = deepcopy(sample)
    conflicting["governance_note"] = "Changed content under the same version — should be rejected."
    conflicting = recalc(conflicting, calculate_checksum)
    request.files = {"blueprint_file": upload_for(conflicting)}
    app.admin_import_assessment_blueprint()
    c = app.db()
    ok("same ID/version with changed checksum does not overwrite", c.execute("SELECT COUNT(*) n FROM assessment_blueprints").fetchone()["n"] == 1)
    ok("checksum mismatch is logged", c.execute("SELECT COUNT(*) n FROM assessment_blueprint_sync_events WHERE action='CHECKSUM_MISMATCH'").fetchone()["n"] == 1)
    c.close()

    request.form = {"reason": "Smoke academic activation"}
    app.admin_activate_assessment_blueprint(1)
    c = app.db()
    ok("explicit admin activation makes blueprint ACTIVE", c.execute("SELECT local_status FROM assessment_blueprints WHERE id=1").fetchone()["local_status"] == "ACTIVE")

    required = {"Biology": 81, "Chemistry": 45, "Physics": 36, "English": 9, "Logical Reasoning": 9}
    inventory = add_governed_inventory(app, c, required)
    preflight = app.assemble_blueprint_mock(c, 1, seed="v55-smoke")
    selected_by_subject = {row["subject"]: row["selected"] for row in preflight["sections"]}
    ok("authentic full mock selects exactly 81/45/36/9/9", preflight["ready"] and selected_by_subject == required)
    ok("authentic mock total is exactly 180", preflight["selected_total"] == 180)

    english_last = inventory["English"][-1]
    c.execute("UPDATE questions SET active=0 WHERE id=?", (english_last,))
    c.commit()
    blocked = app.assemble_blueprint_mock(c, 1, seed="missing-english")
    ok("missing English inventory blocks authentic release", not blocked["ready"] and any("English" in x for x in blocked["blockers"]))
    c.execute("UPDATE questions SET active=1 WHERE id=?", (english_last,))
    c.commit()

    student_id = c.execute(
        """INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,academic_level,access_override_code)
           VALUES('STU-BP','student','Blueprint Student','blueprint@test','blueprint','x','MDCAT','full_access')"""
    ).lastrowid
    free_student_id = c.execute(
        """INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,academic_level)
           VALUES('STU-FREE','student','Free Student','free@test','free','x','MDCAT')"""
    ).lastrowid
    c.commit()

    flask.session.update({"user_id": 1, "role": "admin", "full_name": "Admin"})
    request.form = {"title": "V5.5 Authentic Smoke Mock", "seed": "paper-smoke"}
    c.close()
    app.admin_generate_blueprint_mock(1)
    c = app.db()
    paper = c.execute("SELECT * FROM exam_papers WHERE assessment_blueprint_id=1 ORDER BY id DESC LIMIT 1").fetchone()
    ok("generated mock is marked authentic and blueprint pinned", paper and paper["authenticity_status"] == "AUTHENTIC_BLUEPRINT" and paper["blueprint_version"] == "1")
    ok("generated paper contains 180 pinned questions", c.execute("SELECT COUNT(*) n FROM exam_paper_questions WHERE paper_id=?", (paper["id"],)).fetchone()["n"] == 180)
    structure = app.exam_structure_snapshot(c, bp["id"])
    ok("student-facing exam structure uses the active immutable blueprint",
       structure["blueprint"]["powerhouse_blueprint_id"] == sample["blueprint_id"] and
       len(structure["sections"]) == 5 and sum(x["question_count"] for x in structure["sections"]) == 180)
    compliance = app.paper_blueprint_compliance(c, paper["id"])
    ok("authentic mock compliance report passes structure, content and pinned rigor",
       compliance["relation"]["code"] == "AUTHENTIC_FULL_MOCK" and
       compliance["structural_status"] == "COMPLIANT" and compliance["content_status"] == "COMPLIANT" and
       compliance["rigor_status"] == "PINNED")

    try:
        app.start_exam_paper_session(c, free_student_id, paper, guided=False)
        free_blocked = False
    except PermissionError:
        free_blocked = True
    ok("Free Access cannot bypass higher-level authentic mock", free_blocked)

    assessment_id = app.start_exam_paper_session(c, student_id, paper, guided=False)
    session_row = c.execute("SELECT * FROM assessment_sessions WHERE id=?", (assessment_id,)).fetchone()
    ok("assessment session pins blueprint and assembly policy", session_row["assessment_blueprint_id"] == 1 and session_row["blueprint_version"] == "1" and bool(session_row["blueprint_snapshot_json"]))

    # Submit the real pinned assessment and verify the final attempt carries the same immutable references.
    answer_map = {str(qid): "A" for qid in app.parse_ids(session_row["question_ids"])}
    c.execute("UPDATE assessment_sessions SET saved_answers=? WHERE id=?", (json.dumps(answer_map), assessment_id))
    c.commit()
    c.close()
    flask.session.update({"user_id": student_id, "role": "student", "full_name": "Blueprint Student"})
    request.form = {}
    app.submit_assessment_v4(assessment_id)
    c = app.db()
    attempt = c.execute("SELECT * FROM attempts WHERE student_id=? ORDER BY id DESC LIMIT 1", (student_id,)).fetchone()
    ok("submitted result retains exact blueprint version", attempt["assessment_blueprint_id"] == 1 and attempt["blueprint_version"] == "1" and attempt["assembly_policy_version"] == paper["assembly_policy_version"])
    result_structure = app.attempt_blueprint_result(c, attempt["id"])
    ok("result page explains performance against the pinned exam structure",
       result_structure["blueprint_pinned"] and result_structure["blueprint_version"] == "1" and
       len(result_structure["breakdown"]) == 5 and result_structure["relation"]["code"] == "AUTHENTIC_FULL_MOCK")

    # Student need can outweigh a low official weight while stable high-weight performance remains lower priority.
    priority_student_id = c.execute(
        """INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,academic_level,access_override_code)
           VALUES('STU-PRI','student','Priority Student','priority@test','priority','x','MDCAT','full_access')"""
    ).lastrowid
    c.commit()
    add_attempt(app, c, priority_student_id, inventory["Biology"], True, "priority_smoke")
    add_attempt(app, c, priority_student_id, inventory["English"], False, "priority_smoke")
    priority = app.blueprint_priority_snapshot(c, priority_student_id, 1)
    priority_by_subject = {row["subject"]: row["priority_score"] for row in priority["subjects"]}
    ok("severe low-weight weakness can outrank stable high-weight subject",
       priority_by_subject["English"] > priority_by_subject["Biology"])
    projection = app.blueprint_projection_snapshot(c, student_id, 1)
    ok("projection uses all five blueprint sections", projection["total_questions"] == 180 and len(projection["subjects"]) == 5)
    ok("projection subject counts aggregate to blueprint total", sum(x["question_count"] for x in projection["subjects"]) == 180)
    ok("sparse/uneven evidence produces explicit confidence", projection["confidence"] in {"Low", "Moderate", "High"})

    bank = app.blueprint_bank_sufficiency(c, 1, target_parallel_mocks=3)
    ok("bank sufficiency calculates required-per-mock depth", {x["subject"]: x["required_per_mock"] for x in bank["subjects"]} == required)
    english_bank = next(x for x in bank["subjects"] if x["subject"] == "English")
    ok("low-weight thin subject triggers content need", english_bank["shortage_for_target"] > 0)

    # Question import must remain governed despite spreadsheet approval claims.
    imported_row = {
        "Question ID": "IMP-001", "Family ID": "FAM-001", "Variant": "A", "Programme": "MDCAT",
        "Subject": "Biology", "Chapter": "Cell", "Topic": "Membrane", "Sub-topic": "Transport", "Type": "MCQ",
        "Level": "Foundation", "Question": "What is diffusion?", "A": "High to low", "B": "Low to high",
        "C": "Active only", "D": "None", "Answer": "A", "Explanation": "Movement down a gradient",
        "Status": "Approved", "Review Status": "Approved", "Country": "Pakistan", "Qualification": "MDCAT",
        "Exam Board": "PMDC", "Curriculum Version": "2026", "Learning Outcome": "LO-1", "Concept": "Diffusion",
        "Concept ID": "BIO-DIFF", "Capsule ID": "", "Misconception ID": "MIS-1", "Difficulty": "Moderate",
        "Cognitive Skill": "Understand", "Command Word": "Identify", "Marks": "1", "Estimated Time Seconds": "60",
        "Misconception Tags": "gradient reversal", "Prerequisite Tags": "membrane", "Source Type": "ScoreMax Original",
        "Secure Bank": "Yes", "Rights Status": "ScoreMax Original", "ScoreMax Ready": "Yes",
        "Assessment Purpose": "practice|test|mock|mastery", "Difficulty Source": "authoring",
        "Family Construct": "Explain diffusion", "Family Invariants": "movement down concentration gradient",
    }
    c.close()
    flask.session.update({"user_id": 1, "role": "admin", "full_name": "Admin", "pending_import_rows": [imported_row]})
    app.admin_import_confirm()
    c = app.db()
    imported = c.execute("SELECT * FROM questions WHERE question_id='IMP-001'").fetchone()
    imported_family = c.execute("SELECT * FROM question_families WHERE family_id='FAM-001'").fetchone()
    ok("spreadsheet Approved cannot publish imported question", imported["status"] == "Draft" and imported["review_status"] == "Draft" and imported["active"] == 0)
    ok("imported family is also Draft and inactive", imported_family["review_status"] == "Draft" and imported_family["active"] == 0)
    ok("difficulty remains independent metadata", imported["level"] == "Foundation" and imported["difficulty"] == "Moderate")

    # Version 2 activation must govern future work without rewriting v1 history.
    version2 = deepcopy(sample)
    version2["blueprint_id"] = "PH-BP-MDCAT-2026-002"
    version2["blueprint_version"] = 2
    version2["sections"][0]["question_count"] = 80
    version2["sections"][1]["question_count"] = 46
    version2["governance_note"] = "Smoke version 2."
    version2 = recalc(version2, calculate_checksum)
    c.close()
    flask.session.update({"user_id": 1, "role": "admin", "full_name": "Admin"})
    request.files = {"blueprint_file": upload_for(version2, "v2.json")}
    request.form = {}
    app.admin_import_assessment_blueprint()
    c = app.db()
    bp2 = c.execute("SELECT * FROM assessment_blueprints WHERE blueprint_version='2'").fetchone()
    c.close()
    request.form = {"reason": "Activate new approved structure"}
    app.admin_activate_assessment_blueprint(bp2["id"])
    c = app.db()
    old_paper = c.execute("SELECT * FROM exam_papers WHERE id=?", (paper["id"],)).fetchone()
    old_attempt = c.execute("SELECT * FROM attempts WHERE id=?", (attempt["id"],)).fetchone()
    ok("new blueprint supersedes old only for future use", c.execute("SELECT local_status FROM assessment_blueprints WHERE id=1").fetchone()["local_status"] == "SUPERSEDED")
    ok("historical paper remains pinned to v1", old_paper["assessment_blueprint_id"] == 1 and old_paper["blueprint_version"] == "1")
    ok("historical result remains pinned to v1", old_attempt["assessment_blueprint_id"] == 1 and old_attempt["blueprint_version"] == "1")

    # Rigor policy is a separate versioned layer; tightening creates Verification Due, never a hard downgrade.
    c.execute(
        """INSERT INTO mastery_records(student_id,scope_type,scope_key,programme,subject,chapter,mastery_level,status,
          verified_at,verification_due_at,updated_at) VALUES(?,?,?,?,?,?,?,?,datetime('now'),date('now','+30 day'),CURRENT_TIMESTAMP)""",
        (student_id, "subject", "MDCAT|Biology", "MDCAT", "Biology", "", "Expert", "Verified"),
    )
    c.commit()
    c.close()
    flask.session.update({"user_id": 1, "role": "admin", "full_name": "Admin"})
    request.form = {
        "name": "MDCAT V2 Rigor", "policy_version": "2", "scope_type": "blueprint", "scope_key": "",
        "blueprint_id": str(bp2["id"]), "rigor_score": "75", "mastery_standard_score": "70",
        "reason": "Pilot academic tightening",
    }
    app.admin_create_assessment_policy()
    c = app.db()
    policy = c.execute("SELECT * FROM assessment_assembly_policies WHERE policy_version='2'").fetchone()
    ok("blueprint-scoped policy stores canonical scope key", policy["scope_key"] == str(bp2["id"]))
    policy_preview = json.loads(policy["preview_json"] or "{}")
    ok("policy draft includes transparent historical simulation without percentile claims",
       "historical_simulation" in policy_preview and
       policy_preview["historical_simulation"].get("external_percentile_claim") is False)
    c.close()
    request.form = {"reason": "Academic approval after preview"}
    app.admin_activate_assessment_policy(policy["id"])
    c = app.db()
    mastery = c.execute("SELECT * FROM mastery_records WHERE student_id=?", (student_id,)).fetchone()
    ok("material policy tightening triggers Verification Due, not downgrade", mastery["mastery_level"] == "Expert" and mastery["status"] == "Verification Due")
    ok("policy creation/activation are audited", c.execute("SELECT COUNT(*) n FROM assessment_policy_audit WHERE policy_id=?", (policy["id"],)).fetchone()["n"] == 2)
    base_expert = app.mastery_policy(c, "Expert")
    effective_expert = app.effective_mastery_requirements(base_expert, c.execute("SELECT * FROM assessment_assembly_policies WHERE id=?", (policy["id"],)).fetchone())
    ok("mastery-standard slider tightens future evidence without relabelling items",
       effective_expert["min_accuracy"] > float(base_expert["min_accuracy"]) and
       effective_expert["min_questions"] > int(base_expert["min_questions"]))
    mastery_rows, mastery_meta = app.build_mastery_form(c, student_id, "subject", "Expert", "MDCAT", "Biology", "")
    ok("future mastery form pins active rigor-policy version",
       mastery_meta["assembly_policy_version"] == "2" and mastery_meta["mastery_effective_policy"]["mastery_standard_score"] == 70)
    ok("rigor-aware mastery form remains broad and sufficiently deep",
       len(mastery_rows) >= effective_expert["min_questions"] and mastery_meta["mastery_breadth_ok"])

    proportional = app.assemble_blueprint_practice(c, bp2["id"], student_id, 60, "proportional_full", seed="practice-smoke")
    ok("blueprint-balanced practice allocates 60 questions without claiming authenticity",
       proportional["ready"] and proportional["selected_total"] == 60 and
       proportional["authenticity_status"] == "PROPORTIONAL_BLUEPRINT_PRACTICE")
    ok("60-question practice follows blueprint proportions",
       proportional["allocations"] == {"Biology": 27, "Chemistry": 15, "Physics": 12, "English": 3, "Logical Reasoning": 3})
    diagnostic = app.assemble_blueprint_practice(c, bp2["id"], priority_student_id, 60, "diagnostic", seed="diagnostic-smoke")
    ok("diagnostic practice is clearly labelled and may deviate for learner need",
       diagnostic["ready"] and diagnostic["authenticity_status"] == "DIAGNOSTIC_BLUEPRINT_AWARE" and
       diagnostic["allocations"] != proportional["allocations"])

    # Ordinary student tests also pin the active policy/blueprint while keeping local scope.
    class FormDict(dict):
        def getlist(self, key):
            value = self.get(key, [])
            return value if isinstance(value, list) else ([value] if value not in (None, "") else [])
    c.close()
    flask.session.update({"user_id": student_id, "role": "student", "full_name": "Blueprint Student"})
    request.form = FormDict({"programme": "MDCAT", "subject": "Biology", "scope": "subject", "count": "20", "level": "", "mode": "practice"})
    app.test_start()
    c = app.db()
    ordinary_session = c.execute("SELECT * FROM assessment_sessions WHERE student_id=? ORDER BY id DESC LIMIT 1", (student_id,)).fetchone()
    ordinary_meta = json.loads(ordinary_session["meta_json"] or "{}")
    ok("ordinary practice pins blueprint and active rigor policy",
       ordinary_session["assessment_blueprint_id"] == bp2["id"] and ordinary_session["assembly_policy_version"] == "2" and
       ordinary_meta["authenticity_status"] == "BLUEPRINT_AWARE_PRACTICE")

    # Static integration checks.
    from jinja2 import Environment

    env = Environment()
    template_errors = []
    templates = list((ROOT / "templates").glob("*.html"))
    for path in templates:
        try:
            env.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - reported below
            template_errors.append((path.name, str(exc)))
    ok("all Jinja templates parse", not template_errors)

    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    endpoints = set()
    paths = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute) and decorator.func.attr == "route":
                endpoints.add(node.name)
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    paths.append(decorator.args[0].value)
    ok("route map has no duplicate paths", len(paths) == len(set(paths)))

    url_pattern = re.compile(r"url_for\(\s*['\"]([^'\"]+)['\"]")
    missing_urls = []
    missing_csrf = []
    for path in templates:
        text = path.read_text(encoding="utf-8")
        for match in url_pattern.finditer(text):
            if match.group(1) not in endpoints and match.group(1) != "static":
                missing_urls.append((path.name, match.group(1)))
        for match in re.finditer(r"<form\b[^>]*method=['\"]post['\"][^>]*>(.*?)</form>", text, re.I | re.S):
            if "_csrf" not in match.group(0):
                missing_csrf.append(path.name)
    ok("all literal template route references resolve", not missing_urls)
    ok("all explicit POST forms include CSRF", not missing_csrf)

    c.close()
    print(f"\nScoreMax V5.5 smoke suite: {len(checks)} checks passed.")
    print("Temporary database:", os.environ["SCOREMAX_DB"])


if __name__ == "__main__":
    main()
