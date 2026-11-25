"""UK 11+ parent-linked onboarding acknowledgement.

This is a gated onboarding acknowledgement, NOT proof of legal guardianship,
parental responsibility or UK GDPR consent for every processing purpose.
The existing ScoreMax account and parent_student_links own identities/linking.
All tables are UK-only. No teacher messaging access is implied.
"""
from contextlib import closing
from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request, session, render_template_string, redirect, g

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

    def save_guardian_decision(c, parent_id, student_id, decision):
        """Native-linked parent authorisation is rechecked under the write lock."""
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
            (parent_id, student_id, SCOPE, decision, TEXT_VERSION, stamp),
        )
        c.commit()
        return guardian_status(c, student_id)

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
            return jsonify(save_guardian_decision(c, parent_id, student_id, data["decision"]))

    STYLE = """
    :root{font-family:system-ui,sans-serif;color:#19343c;background:#f5f8fa}
    body{max-width:880px;margin:auto;padding:16px}main{max-width:880px}
    section{background:#fff;border:1px solid #d7e2e6;border-radius:12px;padding:18px;margin:14px 0}
    a{color:#135c77}input,button{font:inherit;max-width:100%}input{padding:10px;display:block;margin:6px 0 16px}
    button{padding:10px 14px;margin:5px 5px 5px 0;background:#135c77;color:#fff;border:0;border-radius:6px}
    .quiet{background:#f3f6f9;color:#19343c}.code{font-weight:700;overflow-wrap:anywhere}
    .notice{padding:10px;border-left:4px solid #8a6232;background:#fff7e5}
    @media(max-width:500px){body{padding:9px}section{padding:12px}}
    """
    CHILD = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Parent or guardian access · ScoreMax UK 11+</title>
    <style>{{ style|safe }}</style></head><body><main>
    <nav aria-label="UK student navigation"><a href="/student">My ScoreMax home</a></nav>
    <h1>Parent or guardian access</h1>
    <section><h2>Share access securely</h2>
      <p>Ask your trusted parent or guardian to sign in with their own ScoreMax account.
      Share your registered email address and the private linking code below with that person only.</p>
      <p class="code" aria-label="Parent account linking code">{{ link_code }}</p>
      <p>Keep your code private. A link allows access to your ScoreMax information;
      it does not independently verify legal guardianship or approve academic messaging.</p>
    </section>
    <section><h2>Guardian onboarding</h2>
      <p aria-live="polite">{{ "Acknowledgement recorded" if status.status == "ACKNOWLEDGED" else "Guardian onboarding pending" }}</p>
      <p class="notice">The acknowledgement does not grant access to practice, exams, marks or mastery while the UK learning routes are unqualified.</p>
    </section>
    <section><h2>Manage linked parents</h2>
      {% if links %}{% for link in links %}
        <p>{{ link.parent_name }}
        <form method="post" action="/student/parent-link/{{ link.id }}/revoke">
          <input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">
          <button type="submit" class="quiet" aria-label="Revoke access for {{ link.parent_name }}">Revoke access</button>
        </form></p>
      {% endfor %}{% else %}<p>No parent or guardian is currently linked.</p>{% endif %}
    </section>
    </main></body></html>"""
    PARENT = """<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Family onboarding · ScoreMax UK 11+</title>
    <style>{{ style|safe }}</style></head><body><main>
    <nav aria-label="Parent navigation"><a href="/logout">Log out</a></nav>
    <h1>ScoreMax UK 11+ — Parent or guardian</h1>
    <p>Use your own account to link to a learner. School selection alone does not establish admission eligibility.</p>
    <section><h2>Link a learner</h2>
      <form method="post" action="/parent/link-student">
        <input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">
        <label for="email">Learner's registered email</label>
        <input id="email" name="student_email" type="email" autocomplete="off" required>
        <label for="code">Private parent access code from learner</label>
        <input id="code" name="link_code" autocomplete="off" required>
        <input type="hidden" name="relationship" value="Guardian">
        <button type="submit">Link learner using existing ScoreMax account</button>
      </form>
    </section>
    <section><h2>Linked UK 11+ learners</h2>
      {% for learner in learners %}
      <article aria-label="Onboarding for {{ learner.name }}">
        <h3>{{ learner.name }}</h3>
        <p aria-live="polite">{{ "Acknowledgement recorded" if learner.status == "ACKNOWLEDGED" else "Onboarding pending" }}</p>
        <form method="post" action="/uk11/api/guardian/students/{{ learner.id }}/form-decision">
          <input type="hidden" name="_csrf_token" value="{{ csrf_token() }}">
          <input type="hidden" name="text_version" value="{{ text_version }}">
          <p>This is an acknowledgement that you have reviewed the UK 11+ onboarding information.
          It is not proof of parental responsibility, legal consent for all processing, or permission for academic messaging.</p>
          <button type="submit" name="decision" value="APPROVED">Record acknowledgement</button>
          <button type="submit" name="decision" value="REVOKED" class="quiet">Withdraw acknowledgement</button>
        </form>
      </article>
      {% else %}<p>No linked UK 11+ learners yet. Use the form above to link a learner.</p>{% endfor %}
    </section><p class="notice">UK school-specific practice, mocks and mastery remain unavailable until qualified.</p>
    </main></body></html>"""

    def safe_html(html):
        # Other native response hooks can append Pakistan navigation after
        # this view is returned. The UK market boundary restores exact HTML.
        g.uk11_family_html = html
        from flask import Response
        return Response(html, mimetype="text/html", headers={
            "Cache-Control":"no-store, private", "X-Content-Type-Options":"nosniff",
            "Referrer-Policy":"no-referrer"
        })

    @bp.get("/me/guardian-onboarding")
    def guardian_student_page():
        uid = id_for_role("student")
        with closing(connection()) as c:
            uk_student(c, uid)
            student = c.execute("SELECT parent_link_code FROM users WHERE id=?", (uid,)).fetchone()
            links = c.execute(
                """SELECT link.id, parent.full_name AS parent_name
                   FROM parent_student_links link
                   JOIN users parent ON parent.id=link.parent_user_id AND parent.role='parent'
                   WHERE link.student_user_id=? AND link.status='active'
                   ORDER BY link.id LIMIT 30""", (uid,),
            ).fetchall()
            html = render_template_string(CHILD, style=STYLE, link_code=student["parent_link_code"] or "Not yet available",
                                          status=guardian_status(c, uid),
                                          links=[dict(link) for link in links])
            return safe_html(html)

    @bp.get("/guardian/home")
    def guardian_home():
        uid = id_for_role("parent")
        with closing(connection()) as c:
            member(c, uid, "parent")
            learners = c.execute(
                """SELECT child.id, child.full_name AS name
                   FROM parent_student_links link
                   JOIN users child ON child.id=link.student_user_id AND child.role='student'
                     AND child.account_status='active'
                   JOIN uk11_learner_markets m ON m.student_user_id=child.id
                     AND m.market_id='UK' AND m.programme_id='UK11'
                   WHERE link.parent_user_id=? AND link.status='active'
                   ORDER BY child.id LIMIT 50""", (uid,),
            ).fetchall()
            projected = [dict(learner, status=guardian_status(c, learner["id"])["status"]) for learner in learners]
            return safe_html(render_template_string(PARENT, style=STYLE, learners=projected,
                                                    text_version=TEXT_VERSION))

    @bp.post("/guardian/students/<int:student_id>/form-decision")
    def guardian_form_decision(student_id):
        parent_id = id_for_role("parent")
        if request.content_length is None or request.content_length > 1024:
            abort(400)
        if set(request.form.keys()) != {"_csrf_token", "text_version", "decision"}:
            abort(400)
        choice = request.form.get("decision")
        if request.form.get("text_version") != TEXT_VERSION or choice not in ("APPROVED", "REVOKED"):
            abort(400)
        with closing(connection()) as c:
            save_guardian_decision(c, parent_id, student_id, choice)
        return redirect("/uk11/api/guardian/home", code=303)

    return bp
