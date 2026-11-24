"""UK11 account preference adapter — integration candidate, not production mounted.

Existing ScoreMax Flask app owns login, user identity, session revocation, CSRF
and database connection. Mount only in an isolated UK runtime after approval.
No changes to Pakistan programme selection, questions, attempts or mastery.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from contextlib import closing

from flask import Blueprint, abort, jsonify, request, session

MAX_SCHOOLS = 20
MAX_BYTES = 4096
ENTRY_YEAR_MIN = 2027
ENTRY_YEAR_MAX = 2032


def create_uk11_blueprint(db_factory, school_catalogue, route_resolver):
    """Inject canonical, evidence-reviewed school data and a DB factory.

    school_catalogue is a mapping {canonical_school_key: display_metadata}.
    route_resolver(keys, entry_year) returns an authoritative, bounded learner
    projection: schools, routes, subjects, pending, revision.
    Unverified school membership MUST NOT generate required subjects or mocks.
    """
    bp = Blueprint("uk11_account", __name__, url_prefix="/uk11/api")

    def student_id():
        uid = session.get("user_id")
        if not isinstance(uid, int) or uid <= 0 or session.get("role") != "student":
            abort(403)
        return uid

    def safe_year(value):
        if type(value) is not int or not (ENTRY_YEAR_MIN <= value <= ENTRY_YEAR_MAX):
            abort(400, description="Invalid entry year")
        return value

    def canonical_keys(keys):
        if not isinstance(keys, list) or len(keys) > MAX_SCHOOLS:
            abort(400, description="Invalid school selection")
        if any(not isinstance(v, str) or len(v) > 128 or v not in school_catalogue for v in keys):
            abort(400, description="Unknown or invalid school")
        if len(set(keys)) != len(keys):
            abort(400, description="Duplicate schools")
        return keys

    def ensure_storage(c):
        # Run only through an approved, explicit migration on the disposable UK DB.
        # This is a guard: requests must never silently migrate a live DB.
        row = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='uk11_student_preferences'").fetchone()
        if row is None:
            raise RuntimeError("UK11_MIGRATION_NOT_APPLIED")

    def current_user(c, uid):
        row = c.execute("SELECT id,role,account_status FROM users WHERE id=?", (uid,)).fetchone()
        if row is None or row["role"] != "student" or row["account_status"] not in (None, "", "active"):
            abort(403)

    def selection(c, uid):
        row = c.execute(
            "SELECT entry_year,selected_school_keys_json,revision FROM uk11_student_preferences WHERE student_user_id=?",
            (uid,),
        ).fetchone()
        if not row:
            return {"entry_year": 2028, "school_keys": [], "revision": 0}
        try:
            keys = json.loads(row["selected_school_keys_json"])
        except (TypeError, ValueError):
            raise RuntimeError("UK11_PREFERENCE_CORRUPT")
        if not isinstance(keys, list):
            raise RuntimeError("UK11_PREFERENCE_CORRUPT")
        # Removed schools do not accidentally grant an obsolete exam.
        keys = [k for k in keys if isinstance(k, str) and k in school_catalogue]
        return {"entry_year": int(row["entry_year"]), "school_keys": keys, "revision": int(row["revision"])}

    def projection(preferences):
        resolved = route_resolver(preferences["school_keys"], preferences["entry_year"])
        if not isinstance(resolved, dict):
            raise RuntimeError("UK11_ROUTE_RESOLVER_INVALID")
        permitted = {"schools", "routes", "subjects", "pending", "evidence_revision"}
        if not {"schools", "routes", "subjects", "pending"}.issubset(resolved):
            raise RuntimeError("UK11_ROUTE_RESOLVER_INCOMPLETE")
        if any(not isinstance(resolved[k], list) for k in ("schools", "routes", "subjects", "pending")):
            raise RuntimeError("UK11_ROUTE_RESOLVER_INVALID_SHAPE")
        if any(not isinstance(k, str) or k not in ("Maths", "English", "Verbal Reasoning", "Non-Verbal Reasoning") for k in resolved["subjects"]):
            raise RuntimeError("UK11_ROUTE_RESOLVER_INVALID_SUBJECTS")
        if len(set(resolved["subjects"])) != len(resolved["subjects"]):
            raise RuntimeError("UK11_ROUTE_RESOLVER_DUPLICATE_SUBJECT")
        if len(resolved["schools"]) > MAX_SCHOOLS or len(resolved["routes"]) > 50:
            raise RuntimeError("UK11_ROUTE_RESOLVER_UNBOUNDED")
        result = {k: resolved[k] for k in permitted if k in resolved}
        result["entry_year"] = preferences["entry_year"]
        result["school_keys"] = preferences["school_keys"]
        result["revision"] = preferences["revision"]
        return result

    @bp.get("/me/schools")
    def get_schools():
        uid = student_id()
        with closing(db_factory()) as c:
            ensure_storage(c)
            current_user(c, uid)
            return jsonify(projection(selection(c, uid)))

    @bp.post("/me/schools")
    def set_schools():
        uid = student_id()
        if request.content_length is None or request.content_length > MAX_BYTES or not request.is_json:
            abort(400)
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            abort(400)
        keys = canonical_keys(body.get("school_keys"))
        entry_year = safe_year(body.get("entry_year"))
        expected_revision = body.get("revision")
        if type(expected_revision) is not int or expected_revision < 0:
            abort(400, description="Missing preference revision")
        # Resolve and validate the requested learner context before writing.
        # Invalid route mapping must never commit preferences and then fail.
        candidate = projection({"entry_year": entry_year, "school_keys": keys, "revision": expected_revision + 1})
        with closing(db_factory()) as c:
            ensure_storage(c)
            current_user(c, uid)
            existing = selection(c, uid)
            if existing["revision"] != expected_revision:
                return jsonify({"error": "revision_conflict", "revision": existing["revision"]}), 409
            # One account-scoped update; no arbitrary student ID from client.
            # SQLite IMMEDIATE lock prevents competing read-modify-write requests.
            c.execute("BEGIN IMMEDIATE")
            current_user(c, uid)
            latest = selection(c, uid)
            if latest["revision"] != expected_revision:
                c.rollback()
                return jsonify({"error": "revision_conflict", "revision": latest["revision"]}), 409
            timestamp = datetime.now(timezone.utc).isoformat()
            c.execute(
                """INSERT INTO uk11_student_preferences
                   (student_user_id,entry_year,selected_school_keys_json,revision,updated_at)
                   VALUES(?,?,?,?,?)
                   ON CONFLICT(student_user_id) DO UPDATE SET
                     entry_year=excluded.entry_year,
                     selected_school_keys_json=excluded.selected_school_keys_json,
                     revision=excluded.revision, updated_at=excluded.updated_at""",
                (uid, entry_year, json.dumps(keys, separators=(",", ":")), latest["revision"] + 1, timestamp),
            )
            c.commit()
            return jsonify(candidate)

    return bp
