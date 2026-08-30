"""ScoreMax V6.5.11 — Power House synthetic learner qualification pilot.

This module extends the existing Mastery Laboratory. It deliberately keeps synthetic
learner identity, sessions, attempts, visual captures and judgements outside live
learner attempts/mastery/evidence.

Hard boundary:
- identity role is ``qa_student`` (never ``student``);
- laboratory questions remain QA_SANDBOX_ONLY;
- no row is written to attempts / attempt_answers / mastery_records;
- no Growth Engine event is emitted for QA learner login or activity;
- no candidate is promoted or student-released by this module.
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping


QA_RELEASE_FLAGS = {
    "content_environment": "QA_SANDBOX_ONLY",
    "student_release_status": "NOT_STUDENT_RELEASED",
    "bank_approval_status": "NOT_BANK_APPROVED",
    "mastery_validity": "NOT_VALID_FOR_REAL_MASTERY",
    "growth_event_eligible": False,
    "real_learner_evidence_eligible": False,
}
KINDS = {"DETERMINISTIC", "VISUAL_SEMANTIC"}
DEFAULT_IDENTITIES = {
    "DETERMINISTIC": {
        "identity_code": "PH_QA_DETERMINISTIC_001",
        "system_user_id": "QA-DET-000001",
        "username": "ph_qa_deterministic_001",
        "full_name": "Power House QA Deterministic Learner",
    },
    "VISUAL_SEMANTIC": {
        "identity_code": "PH_QA_VISUAL_001",
        "system_user_id": "QA-VIS-000001",
        "username": "ph_qa_visual_001",
        "full_name": "Power House QA Visual Learner",
    },
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def init_schema(c) -> None:
    """Idempotent QA-only schema. No live learner table is extended."""
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS mastery_lab_learner_identities(
          id INTEGER PRIMARY KEY,
          user_id INTEGER UNIQUE NOT NULL,
          identity_code TEXT UNIQUE NOT NULL,
          learner_kind TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'ACTIVE',
          release_flags_json TEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          last_used_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS mastery_lab_e2e_sessions(
          id INTEGER PRIMARY KEY,
          session_code TEXT UNIQUE NOT NULL,
          identity_id INTEGER NOT NULL,
          batch_id INTEGER NOT NULL,
          question_id INTEGER NOT NULL,
          expected_mode TEXT NOT NULL DEFAULT 'OBSERVE_ONLY',
          expected_response_json TEXT DEFAULT 'null',
          expected_correctness INTEGER,
          source_question_checksum TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'READY',
          render_checksum_sha256 TEXT DEFAULT '',
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          completed_at TEXT DEFAULT '',
          UNIQUE(identity_id,question_id,session_code)
        );

        CREATE TABLE IF NOT EXISTS mastery_lab_e2e_attempts(
          id INTEGER PRIMARY KEY,
          e2e_session_id INTEGER NOT NULL,
          attempt_seq INTEGER NOT NULL DEFAULT 1,
          response_json TEXT NOT NULL,
          expected_correctness INTEGER,
          live_adapter_correct INTEGER,
          lab_scorer_correct INTEGER,
          live_adapter_marks REAL DEFAULT 0,
          lab_scorer_marks REAL DEFAULT 0,
          result TEXT NOT NULL,
          evidence_json TEXT NOT NULL DEFAULT '{}',
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(e2e_session_id,attempt_seq)
        );

        CREATE TABLE IF NOT EXISTS mastery_lab_visual_reviews(
          id INTEGER PRIMARY KEY,
          e2e_session_id INTEGER NOT NULL,
          screenshot_sha256 TEXT NOT NULL,
          screenshot_path TEXT DEFAULT '',
          viewport_json TEXT DEFAULT '{}',
          render_metadata_json TEXT DEFAULT '{}',
          judgement TEXT NOT NULL DEFAULT 'PENDING',
          findings_json TEXT DEFAULT '[]',
          judge_type TEXT DEFAULT '',
          judge_version TEXT DEFAULT '',
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          judged_at TEXT DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_lab_e2e_identity_status
          ON mastery_lab_e2e_sessions(identity_id,status,created_at);
        CREATE INDEX IF NOT EXISTS idx_lab_visual_session
          ON mastery_lab_visual_reviews(e2e_session_id,created_at);
        """
    )


def identity_for_user(c, user_id: int | None) -> dict[str, Any] | None:
    if not user_id:
        return None
    row = c.execute(
        "SELECT * FROM mastery_lab_learner_identities WHERE user_id=? AND status='ACTIVE'",
        (int(user_id),),
    ).fetchone()
    return dict(row) if row else None


def provision_identity(c, learner_kind: str, *, password: str | None = None) -> dict[str, Any]:
    """Provision one pilot identity without persisting plaintext credentials.

    If the identity already exists and ``password`` is omitted, its password is left
    unchanged and the returned ``password`` value is ``None``.
    """
    from werkzeug.security import generate_password_hash
    kind = str(learner_kind or "").strip().upper()
    if kind not in KINDS:
        raise ValueError(f"Unsupported synthetic learner kind: {kind!r}")
    spec = DEFAULT_IDENTITIES[kind]
    existing = c.execute(
        "SELECT * FROM users WHERE system_user_id=? OR lower(username)=lower(?) ORDER BY id LIMIT 1",
        (spec["system_user_id"], spec["username"]),
    ).fetchone()
    created = False
    plaintext = password
    if existing:
        user_id = int(existing["id"])
        if str(existing["role"] or "") != "qa_student":
            raise ValueError("Synthetic learner identity collides with a non-QA user")
        if password:
            c.execute(
                "UPDATE users SET password_hash=?,full_name=?,account_status='active' WHERE id=?",
                (generate_password_hash(password), spec["full_name"], user_id),
            )
    else:
        plaintext = password or secrets.token_urlsafe(18)
        cur = c.execute(
            """INSERT INTO users(system_user_id,role,full_name,username,password_hash,account_status)
               VALUES(?,?,?,?,?,'active')""",
            (
                spec["system_user_id"],
                "qa_student",
                spec["full_name"],
                spec["username"],
                generate_password_hash(plaintext),
            ),
        )
        user_id = int(cur.lastrowid)
        created = True
    c.execute(
        """INSERT INTO mastery_lab_learner_identities(
             user_id,identity_code,learner_kind,status,release_flags_json)
           VALUES(?,?,?,'ACTIVE',?)
           ON CONFLICT(identity_code) DO UPDATE SET
             user_id=excluded.user_id,learner_kind=excluded.learner_kind,status='ACTIVE',
             release_flags_json=excluded.release_flags_json""",
        (user_id, spec["identity_code"], kind, canonical_json(QA_RELEASE_FLAGS)),
    )
    c.execute(
        """INSERT INTO mastery_lab_audit_events(actor_user_id,event_type,subject_type,subject_id,metadata_json)
           VALUES(?,?,?,?,?)""",
        (
            user_id,
            "SYNTHETIC_LEARNER_PROVISIONED" if created else "SYNTHETIC_LEARNER_RECONFIRMED",
            "mastery_lab_learner_identity",
            spec["identity_code"],
            canonical_json({"learner_kind": kind, "release_flags": QA_RELEASE_FLAGS}),
        ),
    )
    return {
        "user_id": user_id,
        "identity_code": spec["identity_code"],
        "learner_kind": kind,
        "username": spec["username"],
        "password": plaintext if created or password else None,
        "created": created,
        "release_flags": dict(QA_RELEASE_FLAGS),
    }


def _safe_json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list, tuple, int, float, bool)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _slug(value: Any) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _row_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize SQLite rows and other Mapping-like DB records at the QA boundary."""
    try:
        return dict(value)
    except Exception as exc:
        raise TypeError("Synthetic learner question must be mapping-compatible") from exc


def learner_type_for_lab_question(q: Mapping[str, Any]) -> str:
    q = _row_dict(q)
    family = _slug(q.get("family_type") or q.get("qtype"))
    response_mode = _slug(q.get("response_mode"))
    if family in {"standard_mcq", "four_statement_selection"}:
        return "single_choice"
    if family == "true_false":
        return "true_false"
    if family == "multiple_response":
        return "multiple_select"
    if family == "cloze":
        return "fill_blank"
    if family == "numerical_interpretation":
        return "numerical"
    if family == "constructed_response":
        return "extended_response" if response_mode == "extended_response" else "short_response"
    if family in {"matching", "ordering"}:
        return family
    if family in {"diagram_data_stimulus", "misconception_probe", "adaptive_recovery"}:
        return response_mode or "single_choice"
    return response_mode or family or "single_choice"


def deterministic_eligibility(q: Mapping[str, Any]) -> tuple[bool, str]:
    """Return whether the current live learner renderer/marker can be parity-tested safely.

    This is deliberately narrower than Mastery Laboratory family support. Unsupported
    families remain eligible for VISUAL_SEMANTIC observation but cannot earn a
    deterministic PASS until the production learner renderer/marker supports them.
    """
    q = _row_dict(q)
    family = _slug(q.get("family_type") or q.get("qtype"))
    response_mode = _slug(q.get("response_mode"))
    answer_cfg = _safe_json(q.get("answer_config_json"), {})
    marking = _safe_json(q.get("marking_config_json"), {})
    if not isinstance(answer_cfg, dict):
        answer_cfg = {}
    if not isinstance(marking, dict):
        marking = {}
    if float(marking.get("negative_marks") or 0) != 0:
        return False, "negative_marking_not_parity_supported"
    if family in {"standard_mcq", "four_statement_selection", "true_false"}:
        return True, "supported_single_choice"
    if family == "multiple_response":
        return True, "supported_multiple_select"
    if family == "cloze":
        blanks = answer_cfg.get("blanks") or []
        if len(blanks) != 1:
            return False, "live_renderer_supports_single_blank_only"
        return True, "supported_single_blank"
    if family == "numerical_interpretation":
        if float(marking.get("relative_tolerance") or 0) != 0:
            return False, "relative_tolerance_not_supported_by_live_marker"
        return True, "supported_numerical"
    if family in {"diagram_data_stimulus", "misconception_probe", "adaptive_recovery"}:
        mode = _slug(marking.get("response_mode") or answer_cfg.get("response_mode") or response_mode or "single_choice")
        if mode in {"single_choice", "true_false", "multiple_select", "multiple_response"}:
            return True, f"supported_{mode}"
        if mode in {"numerical", "numeric"}:
            if float(marking.get("relative_tolerance") or 0) != 0:
                return False, "relative_tolerance_not_supported_by_live_marker"
            return True, "supported_numerical"
        return False, f"live_marker_not_active_for_{mode or family}"
    if family == "constructed_response":
        return False, "constructed_response_live_automarking_not_active"
    if family in {"matching", "ordering"}:
        return False, f"{family}_live_interactive_renderer_not_active"
    return False, f"family_not_live_parity_supported:{family or 'unknown'}"


def live_adapter_question(q: Mapping[str, Any]) -> dict[str, Any]:
    """Adapt a QA-only lab record to the same marking/rendering shape as live questions."""
    q = _row_dict(q)
    answer_cfg = _safe_json(q.get("answer_config_json"), {})
    marking_cfg = _safe_json(q.get("marking_config_json"), {})
    options = _safe_json(q.get("options_json"), [])
    if not isinstance(answer_cfg, dict):
        answer_cfg = {}
    if not isinstance(marking_cfg, dict):
        marking_cfg = {}
    if isinstance(options, list) and options and not answer_cfg.get("options"):
        answer_cfg["options"] = options
    family = _slug(q.get("family_type"))
    qtype = learner_type_for_lab_question(q)

    # Bridge a single-cloze lab contract to the existing learner fill-blank adapter.
    if family == "cloze" and not answer_cfg.get("accepted_answers"):
        blanks = answer_cfg.get("blanks") or []
        if len(blanks) == 1 and isinstance(blanks[0], Mapping):
            answer_cfg["accepted_answers"] = list(blanks[0].get("accepted_answers") or [])
            answer_cfg["case_sensitive"] = bool(blanks[0].get("case_sensitive"))
    correct_ids = marking_cfg.get("correct_option_ids") or answer_cfg.get("correct_option_ids") or []
    answer = str(correct_ids[0]) if isinstance(correct_ids, list) and correct_ids else ""
    option_map = {str(x.get("id", "")).upper(): str(x.get("text", "")) for x in options if isinstance(x, Mapping)}
    stimulus = _safe_json(q.get("stimulus_json"), {})
    if isinstance(stimulus, Mapping):
        stimulus_text = str(
            stimulus.get("text")
            or stimulus.get("stimulus")
            or stimulus.get("prompt")
            or stimulus.get("content")
            or ""
        )
    else:
        stimulus_text = str(stimulus or "")
    return {
        "id": int(q["id"]),
        "question_id": str(q.get("external_question_id") or ""),
        "question_version": str(q.get("external_version") or "1"),
        "qtype": qtype.replace("_", " "),
        "level": str(q.get("mastery_level") or "Foundation"),
        "question": str(q.get("question_text") or ""),
        "option_a": option_map.get("A", ""),
        "option_b": option_map.get("B", ""),
        "option_c": option_map.get("C", ""),
        "option_d": option_map.get("D", ""),
        "answer": answer,
        "answer_config": canonical_json(answer_cfg),
        "marking_config": canonical_json(marking_cfg),
        "marks": float(marking_cfg.get("marks") or 1),
        "stimulus_data": stimulus_text,
        "misconception_tags": canonical_json(_safe_json(q.get("misconception_tags_json"), [])),
    }


def correct_response_for_lab_question(q: Mapping[str, Any]) -> Any:
    q = _row_dict(q)
    family = _slug(q.get("family_type"))
    answer_cfg = _safe_json(q.get("answer_config_json"), {})
    marking = _safe_json(q.get("marking_config_json"), {})
    if not isinstance(answer_cfg, dict):
        answer_cfg = {}
    if not isinstance(marking, dict):
        marking = {}
    if family in {"standard_mcq", "four_statement_selection", "true_false", "diagram_data_stimulus", "misconception_probe", "adaptive_recovery"}:
        vals = marking.get("correct_option_ids") or answer_cfg.get("correct_option_ids") or []
        return str(vals[0]) if vals else ""
    if family == "multiple_response":
        vals = marking.get("correct_option_ids") or []
        return ",".join(str(x) for x in vals)
    if family == "cloze":
        blanks = answer_cfg.get("blanks") or []
        vals = []
        for blank in blanks:
            accepted = blank.get("accepted_answers") if isinstance(blank, Mapping) else [blank]
            vals.append(str((accepted or [""])[0]))
        return vals[0] if len(vals) == 1 else vals
    if family == "matching":
        return dict(marking.get("correct_pairs") or {})
    if family == "ordering":
        return list(marking.get("correct_order") or [])
    if family == "numerical_interpretation":
        return marking.get("correct_value")
    return ""


def incorrect_response_for_lab_question(q: Mapping[str, Any]) -> Any:
    q = _row_dict(q)
    correct = correct_response_for_lab_question(q)
    options = _safe_json(q.get("options_json"), [])
    if isinstance(options, list):
        for opt in options:
            if isinstance(opt, Mapping):
                oid = str(opt.get("id") or "")
                if oid and oid.casefold() != str(correct).casefold():
                    return oid
    if isinstance(correct, (int, float)):
        return float(correct) + 999.0
    if isinstance(correct, list):
        return list(reversed(correct)) if len(correct) > 1 else ["__wrong__"]
    if isinstance(correct, dict):
        return {str(k): "__wrong__" for k in correct}
    return "__wrong__"


def create_e2e_session(
    c,
    *,
    user_id: int,
    question_id: int,
    expected_mode: str = "OBSERVE_ONLY",
    expected_response: Any = None,
) -> dict[str, Any]:
    identity = identity_for_user(c, user_id)
    if not identity:
        raise PermissionError("Active synthetic learner identity required")
    qrow = c.execute("SELECT * FROM mastery_lab_questions WHERE id=? AND active=1", (int(question_id),)).fetchone()
    if not qrow:
        raise ValueError("QA laboratory question not found")
    q = dict(qrow)
    flags = {
        "content_environment": q.get("content_environment"),
        "student_release_status": q.get("student_release_status"),
        "bank_approval_status": q.get("bank_approval_status"),
        "mastery_validity": q.get("mastery_validity"),
    }
    expected_flags = {
        k: QA_RELEASE_FLAGS[k]
        for k in ("content_environment", "student_release_status", "bank_approval_status", "mastery_validity")
    }
    if flags != expected_flags:
        raise ValueError("Question is not safely partitioned as QA_SANDBOX_ONLY")
    if str(identity.get("learner_kind") or "").upper() == "DETERMINISTIC":
        eligible, reason = deterministic_eligibility(q)
        if not eligible:
            raise ValueError(f"Question is not deterministic-parity eligible: {reason}")
    mode = str(expected_mode or "OBSERVE_ONLY").strip().upper()
    if mode not in {"CORRECT", "INCORRECT", "OBSERVE_ONLY", "EXPLICIT"}:
        raise ValueError("Unsupported E2E expected mode")
    if mode == "CORRECT":
        expected_response = correct_response_for_lab_question(q)
        expected_correctness = 1
    elif mode == "INCORRECT":
        expected_response = incorrect_response_for_lab_question(q)
        expected_correctness = 0
    elif mode == "EXPLICIT":
        expected_correctness = None
    else:
        expected_correctness = None
        expected_response = None
    code = "SM-QA-" + secrets.token_hex(10).upper()
    cur = c.execute(
        """INSERT INTO mastery_lab_e2e_sessions(
             session_code,identity_id,batch_id,question_id,expected_mode,expected_response_json,
             expected_correctness,source_question_checksum,status)
           VALUES(?,?,?,?,?,?,?,?, 'READY')""",
        (
            code,
            int(identity["id"]),
            int(q["batch_id"]),
            int(q["id"]),
            mode,
            canonical_json(expected_response),
            expected_correctness,
            str(q["content_checksum"]),
        ),
    )
    sid = int(cur.lastrowid)
    c.execute(
        "UPDATE mastery_lab_learner_identities SET last_used_at=? WHERE id=?",
        (datetime.now().isoformat(timespec="seconds"), int(identity["id"])),
    )
    c.execute(
        """INSERT INTO mastery_lab_audit_events(actor_user_id,event_type,subject_type,subject_id,metadata_json)
           VALUES(?,?,?,?,?)""",
        (
            int(user_id),
            "SYNTHETIC_E2E_SESSION_CREATED",
            "mastery_lab_e2e_session",
            str(sid),
            canonical_json({"session_code": code, "expected_mode": mode, "question_id": int(q["id"])}),
        ),
    )
    c.commit()
    return session_summary(c, sid, user_id=user_id)


def session_summary(c, session_id: int, *, user_id: int | None = None) -> dict[str, Any] | None:
    params = [int(session_id)]
    where = "s.id=?"
    if user_id is not None:
        where += " AND i.user_id=?"
        params.append(int(user_id))
    row = c.execute(
        f"""SELECT s.*,i.user_id,i.identity_code,i.learner_kind,q.external_question_id,q.external_version,
                   q.family_type,q.response_mode,q.programme,q.subject,q.chapter,q.topic,q.subtopic,
                   q.mastery_level,q.question_text,q.stimulus_json,q.options_json,q.answer_config_json,
                   q.marking_config_json,q.misconception_tags_json,q.content_environment,q.student_release_status,
                   q.bank_approval_status,q.mastery_validity,q.content_checksum
            FROM mastery_lab_e2e_sessions s
            JOIN mastery_lab_learner_identities i ON i.id=s.identity_id
            JOIN mastery_lab_questions q ON q.id=s.question_id
            WHERE {where}""",
        tuple(params),
    ).fetchone()
    if not row:
        return None
    data = dict(row)
    data["question"] = live_adapter_question(data)
    data["expected_response"] = _safe_json(data.get("expected_response_json"), None)
    return data


def record_attempt(
    c,
    *,
    session_id: int,
    user_id: int,
    response: Any,
    live_result: Mapping[str, Any],
    lab_result: Mapping[str, Any],
) -> dict[str, Any]:
    s = session_summary(c, session_id, user_id=user_id)
    if not s:
        raise PermissionError("Synthetic learner session not found for this identity")
    expected = s.get("expected_correctness")
    live_correct = bool(live_result.get("is_correct"))
    lab_correct = bool(lab_result.get("is_correct"))
    live_marks = float(live_result.get("awarded_marks") or 0)
    lab_marks = float(lab_result.get("awarded_marks") or 0)
    parity = live_correct == lab_correct and abs(live_marks - lab_marks) < 1e-9
    expectation = True if expected is None else (live_correct == bool(expected) and lab_correct == bool(expected))
    result = "PASS" if parity and expectation else "FAIL"
    seq = int(
        c.execute(
            "SELECT COALESCE(MAX(attempt_seq),0)+1 n FROM mastery_lab_e2e_attempts WHERE e2e_session_id=?",
            (int(session_id),),
        ).fetchone()["n"]
    )
    evidence = {
        "qa_release_flags": QA_RELEASE_FLAGS,
        "live_adapter": dict(live_result),
        "laboratory_scorer": dict(lab_result),
        "parity": parity,
        "expectation_met": expectation,
        "live_attempt_table_written": False,
        "real_mastery_written": False,
        "growth_event_written": False,
    }
    c.execute(
        """INSERT INTO mastery_lab_e2e_attempts(
             e2e_session_id,attempt_seq,response_json,expected_correctness,live_adapter_correct,
             lab_scorer_correct,live_adapter_marks,lab_scorer_marks,result,evidence_json)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (
            int(session_id),
            seq,
            canonical_json(response),
            expected,
            int(live_correct),
            int(lab_correct),
            live_marks,
            lab_marks,
            result,
            canonical_json(evidence),
        ),
    )
    c.execute(
        "UPDATE mastery_lab_e2e_sessions SET status=?,completed_at=? WHERE id=?",
        ("PASSED" if result == "PASS" else "FAILED", datetime.now().isoformat(timespec="seconds"), int(session_id)),
    )
    c.execute(
        """INSERT INTO mastery_lab_audit_events(actor_user_id,event_type,subject_type,subject_id,metadata_json)
           VALUES(?,?,?,?,?)""",
        (
            int(user_id),
            "SYNTHETIC_E2E_ATTEMPT_RECORDED",
            "mastery_lab_e2e_session",
            str(session_id),
            canonical_json({"attempt_seq": seq, "result": result, "parity": parity, "expectation_met": expectation}),
        ),
    )
    c.commit()
    return {"result": result, "attempt_seq": seq, "evidence": evidence}


def record_visual_capture(
    c,
    *,
    session_id: int,
    user_id: int,
    screenshot_path: str,
    viewport: Mapping[str, Any] | None = None,
    render_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    s = session_summary(c, session_id, user_id=user_id)
    if not s:
        raise PermissionError("Synthetic learner session not found for this identity")
    path = Path(screenshot_path)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    cur = c.execute(
        """INSERT INTO mastery_lab_visual_reviews(
             e2e_session_id,screenshot_sha256,screenshot_path,viewport_json,render_metadata_json,
             judgement,findings_json,judge_type,judge_version)
           VALUES(?,?,?,?,?,'PENDING','[]','','')""",
        (
            int(session_id),
            digest,
            str(path),
            canonical_json(dict(viewport or {})),
            canonical_json(dict(render_metadata or {})),
        ),
    )
    c.execute(
        """INSERT INTO mastery_lab_audit_events(actor_user_id,event_type,subject_type,subject_id,metadata_json)
           VALUES(?,?,?,?,?)""",
        (
            int(user_id),
            "SYNTHETIC_VISUAL_CAPTURE_RECORDED",
            "mastery_lab_e2e_session",
            str(session_id),
            canonical_json({"visual_review_id": int(cur.lastrowid), "screenshot_sha256": digest}),
        ),
    )
    c.commit()
    return {"visual_review_id": int(cur.lastrowid), "screenshot_sha256": digest, "judgement": "PENDING"}


def record_visual_judgement(
    c,
    *,
    visual_review_id: int,
    session_id: int,
    user_id: int,
    judgement: str,
    findings: list[Mapping[str, Any]] | None,
    judge_type: str,
    judge_version: str = "",
) -> dict[str, Any]:
    allowed = {"PASS", "FLAG_TECHNICAL", "FLAG_ACADEMIC_R2", "UNABLE_TO_JUDGE"}
    verdict = str(judgement or "").strip().upper()
    if verdict not in allowed:
        raise ValueError("Unsupported visual judgement")
    row = c.execute(
        """SELECT v.*,s.identity_id,i.user_id FROM mastery_lab_visual_reviews v
           JOIN mastery_lab_e2e_sessions s ON s.id=v.e2e_session_id
           JOIN mastery_lab_learner_identities i ON i.id=s.identity_id
           WHERE v.id=? AND s.id=? AND i.user_id=? AND i.learner_kind='VISUAL_SEMANTIC'""",
        (int(visual_review_id), int(session_id), int(user_id)),
    ).fetchone()
    if not row:
        raise ValueError("Visual review not found")
    normalized = [dict(x) for x in (findings or [])]
    c.execute(
        """UPDATE mastery_lab_visual_reviews SET judgement=?,findings_json=?,judge_type=?,judge_version=?,judged_at=?
           WHERE id=?""",
        (
            verdict,
            canonical_json(normalized),
            str(judge_type or ""),
            str(judge_version or ""),
            datetime.now().isoformat(timespec="seconds"),
            int(visual_review_id),
        ),
    )
    c.execute(
        """INSERT INTO mastery_lab_audit_events(actor_user_id,event_type,subject_type,subject_id,metadata_json)
           VALUES(?,?,?,?,?)""",
        (
            int(row["user_id"]),
            "SYNTHETIC_VISUAL_JUDGEMENT_RECORDED",
            "mastery_lab_visual_review",
            str(visual_review_id),
            canonical_json({"judgement": verdict, "finding_count": len(normalized), "judge_type": str(judge_type or "")}),
        ),
    )
    c.commit()
    return {"visual_review_id": int(visual_review_id), "judgement": verdict, "findings": normalized}
