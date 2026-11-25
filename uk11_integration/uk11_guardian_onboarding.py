"""UK 11+ parent-linked onboarding acknowledgement.

This is a gated onboarding acknowledgement, NOT proof of legal guardianship,
parental responsibility or UK GDPR consent for every processing purpose.
The existing ScoreMax account and parent_student_links own identities/linking.
All tables are UK-only. No teacher messaging access is implied.
"""
from contextlib import closing
from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request, session

SCOPE = "UK11_ONBOARDING"
TEXT_VERSION = "UK11-ONBOARDING-CANDIDATE-20261125"


def create_uk11_guardian_blueprint(db_factory):
    bp = Blueprint("uk11_guardian", __name__, url_prefix="/uk11/api")

    def connection():
        c = db_factory()
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def member(c, user_id, expected_role):
        row = c.execute(
            "SELECT id, role, account_status FROM users WHERE id=?", (user_id,)
        ).fetchone()
        if row is None or row["role"] != expected_role or row["account_status"] != "active":
            abort(403)
        return row

    def id_for_role(role):
        uid = session.get("user_id")
        if type(uid) is not int or uid <= 0 or session.get("role") != role:
            abort(403)
        return uid

    def uk_student(c, uid):
        member(c, uid, "student")
        row = c.execute(
            "SELECT market_id, programme_id FROM uk11_learner_markets WHERE student_user_id=?",
            (uid,),
        ).fetchone()
        if row is None or row["market_id"] != "UK" or row["programme_id"] != "UK11":
            abort(403)

    def guardian_status(c, student_id):
        # Only a currently linked AND actively approving parent qualifies.
        # Revocation of the parent link automatically removes effective approval.
        row = c.execute(
            """SELECT g.parent_user_id, g.status, g.consent_text_version, g.updated_at
               FROM uk11_guardian_onboarding g
               JOIN parent_student_links p ON p.parent_user_id=g.parent_user_id
                 AND p.student_user_id=g.student_user_id AND p.status='active'
               JOIN users parent ON parent.id=g.parent_user_id
                 AND parent.role='parent' AND parent.account_status='active'
               WHERE g.student_user_id=? AND g.status='APPROVED'
                 AND g.consent_text_version=?
               ORDER BY g.updated_at DESC LIMIT 1""",
            (student_id, TEXT_VERSION),
        ).fetchone()
        return {
            "status": "ACKNOWLEDGED" if row else "PENDING_GUARDIAN",
            "text_version": TEXT_VERSION,
            "learning_unlocked": False,
            "legal_guardianship_verified": False,
        }

    @bp.get("/me/guardian-status")
    def student_guardian_status():
        uid = id_for_role("student")
        with closing(connection()) as c:
            uk_student(c, uid)
            return jsonify(guardian_status(c, uid))

    @bp.get("/guardian/students")
    def guardian_students():
        parent_id = id_for_role("parent")
        with closing(connection()) as c:
            member(c, parent_id, "parent")
            rows = c.execute(
                """SELECT s.id, s.full_name FROM parent_student_links link
                   JOIN users s ON s.id=link.student_user_id
                     AND s.role='student' AND s.account_status='active'
                   JOIN uk11_learner_markets m ON m.student_user_id=s.id
                     AND m.market_id='UK' AND m.programme_id='UK11'
                   WHERE link.parent_user_id=? AND link.status='active'
                   ORDER BY s.id LIMIT 100""", (parent_id,),
            ).fetchall()
            return jsonify({"students": [
                {"student_id": r["id"], "student_name": r["full_name"],
                 "status": guardian_status(c, r["id"])["status"]}
                for r in rows
            ], "scope": SCOPE, "text_version": TEXT_VERSION})

    @bp.post("/guardian/students/<int:student_id>/decision")
    def guardian_decision(student_id):
        parent_id = id_for_role("parent")
        if not request.is_json or request.content_length is None or request.content_length > 1024:
            abort(400)
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != {"decision", "text_version"}:
            abort(400)
        if data["decision"] not in ("APPROVED", "REVOKED") or data["text_version"] != TEXT_VERSION:
            abort(400)
        with closing(connection()) as c:
            c.execute("BEGIN IMMEDIATE")
            member(c, parent_id, "parent")
            uk_student(c, student_id)
            link = c.execute(
                """SELECT id FROM parent_student_links
                   WHERE parent_user_id=? AND student_user_id=? AND status='active'""",
                (parent_id, student_id),
            ).fetchone()
            if link is None:
                abort(403)
            stamp = datetime.now(timezone.utc).isoformat()
            c.execute(
                """INSERT INTO uk11_guardian_onboarding
                   (parent_user_id, student_user_id, consent_scope, status,
                    consent_text_version, updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(parent_user_id,student_user_id,consent_scope)
                   DO UPDATE SET status=excluded.status,
                     consent_text_version=excluded.consent_text_version,
                     updated_at=excluded.updated_at""",
                (parent_id, student_id, SCOPE, data["decision"], TEXT_VERSION, stamp),
            )
            c.commit()
            return jsonify(guardian_status(c, student_id))

    return bp
