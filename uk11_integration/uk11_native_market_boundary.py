"""Explicit UK learner market boundary for disposable native ScoreMax qualification.

UK account market is persisted independently of selected schools. A UK student
must never fall through to the Pakistan native student handler or native
practice/marking when UK route entitlements are not yet qualified.

This candidate is installed AFTER ScoreMax native authentication, session
revocation, synthetic learner fences and CSRF. For UK pages it renders a
minimal extension of ScoreMax's existing presentation conventions without
invoking the Pakistan learner dashboard or its Jinja context processors.
"""
from __future__ import annotations
from contextlib import closing
from html import escape
from flask import Response, redirect, request, session, g

UK_MARKET = "UK"
UK_PROGRAMME = "UK11"
UK_ALLOWED_ENDPOINTS = frozenset({
    "uk11_account.get_schools",
    "uk11_account.set_schools",
    "uk11_guardian.student_guardian_status",
    "uk11_guardian.guardian_student_page",
    "student_revoke_parent_link",
    "uk11_school_dashboard.uk11_my_learning",
    "logout",
    "static",
    "dashboard",
    "student_dashboard",
})
UK_ONLY_ENDPOINTS = frozenset({"uk11_account.get_schools", "uk11_account.set_schools", "uk11_school_dashboard.uk11_my_learning", "uk11_guardian.student_guardian_status", "uk11_guardian.guardian_student_page"})


def install_uk11_market_boundary(app, db_factory, route_projection):
    if app.extensions.get("scoremax_uk11_market_gate") is not None:
        raise RuntimeError("UK11_MARKET_BOUNDARY_DUPLICATE")
    if not app.before_request_funcs.get(None):
        raise RuntimeError("UK11_NATIVE_SECURITY_GATE_REQUIRED")

    def find_market(uid):
        with closing(db_factory()) as c:
            return c.execute(
                "SELECT market_id,programme_id FROM uk11_learner_markets WHERE student_user_id=?",
                (uid,),
            ).fetchone()

    def home_page():
        # Reuse the native account projection: no duplicate school/test resolver.
        response = route_projection()
        if response.status_code != 200:
            return response
        context = response.get_json()
        schools = context["schools"]
        routes = context["routes"]
        subjects = context["subjects"]
        pending = context["pending"]
        guardian_endpoint = app.view_functions.get("uk11_guardian.student_guardian_status")
        if guardian_endpoint is None:
            raise RuntimeError("UK11_GUARDIAN_STATUS_NOT_MOUNTED")
        guardian_response = guardian_endpoint()
        if guardian_response.status_code != 200:
            return guardian_response
        guardian = guardian_response.get_json()
        guardian_text = ("Guardian acknowledgement recorded; formal guardian verification and learning access are still pending."
                         if guardian.get("status") == "ACKNOWLEDGED"
                         else "Guardian onboarding pending. Ask your parent or guardian to link their existing ScoreMax account.")
        # Escape every school/source-provided value. Only display metadata is
        # rendered; no internal IDs, QA statuses, answer/rubric or user data.
        rows = lambda xs,field: "<ul>" + "".join(
            "<li>" + escape(str(v.get(field) or "")) + "</li>"
            for v in xs if isinstance(v,dict) and v.get(field)
        ) + "</ul>"
        school_html = rows(schools,"name") or "<p>No target schools selected.</p>"
        if not schools: school_html = "<p>No target schools selected.</p>"
        route_html = rows(routes,"name") if routes else "<p>No verified tests assigned.</p>"
        subject_html = "<ul>" + "".join("<li>"+escape(str(s))+"</li>" for s in subjects)+"</ul>" if subjects else "<p>Subjects not yet established.</p>"
        pending_html = ("<p role='status'>Admissions verification pending; no unsupported subjects added.</p>" +
            rows(pending,"message")) if pending else ""
        body = """<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>My UK 11+ ScoreMax</title><style>
body{margin:0;background:#f6f8fa;color:#1c303a;font:16px system-ui,sans-serif}
header,main{max-width:1100px;padding:20px;margin:auto}
nav a{margin-right:18px;color:#176b70}
section{background:white;padding:22px;margin:15px 0;border-radius:15px;border:1px solid #dbe5e5}
h1,h2{margin:0 0 14px}li{padding:5px 0}
.levels span{display:inline-block;border:1px solid #c6d5d5;padding:8px;margin:4px;border-radius:8px}
@media(max-width:500px){header,main{padding:12px}section{padding:15px}}
</style></head><body>
<header><strong>ScoreMax · UK 11+</strong><nav aria-label='Student navigation'>
<a href='/student'>Home</a><a href='/uk11/my-learning'>My schools and subjects</a><a href='/uk11/api/me/guardian-onboarding'>Parent access</a>
<a href='/logout'>Log out</a></nav></header>
<main><h1>My UK 11+ learning</h1>
<p>Your preparation follows your saved schools. Selecting a school does not establish admissions eligibility.</p>
<section id='uk11-school-context'><h2>Selected schools</h2>""" + school_html + """
<h2>Relevant examinations</h2>""" + route_html + """
<h2>Relevant subjects</h2>""" + subject_html + pending_html + """</section>
<section aria-label='Guardian onboarding'><h2>Parent or guardian onboarding</h2>
<p>""" + escape(guardian_text) + """</p></section>
<section><h2>Six mastery levels</h2><div class='levels'>
<span>Foundation</span><span>Exam Ready</span><span>Advanced</span>
<span>Distinction</span><span>Expert</span><span>Elite</span></div>
<p><strong>Current status: Not Yet Established</strong></p>
<p>Practice, exams and study plans will be available when their UK mappings and native marking are qualified.</p>
</section></main></body></html>"""
        # Other native/UX after_response hooks may append Pakistan navigation
        # and subject scripts. Preserve this exact child-safe response in g,
        # then restore it after those hooks while retaining their headers.
        g.uk11_final_home_html = body
        return Response(body,status=200,mimetype="text/html",
                        headers={"Cache-Control":"no-store, private","X-Content-Type-Options":"nosniff"})

    @app.before_request
    def uk11_parent_market_route():
        # Parent home for accounts linked to UK learners uses the existing
        # parent session, but skips the Pakistan-only analytics view entirely.
        # Unlinked/legacy parents retain the existing native home and linking.
        uid = session.get("user_id")
        if type(uid) is not int or session.get("role") != "parent":
            return None
        with closing(db_factory()) as c:
            market = c.execute(
                "SELECT market_id,programme_id FROM uk11_parent_markets WHERE parent_user_id=?",
                (uid,),
            ).fetchone()
        if market is None:
            # A Pakistan or legacy parent cannot enter the UK onboarding UI,
            # regardless of guessing routes or a learner's numeric user ID.
            if request.path.startswith("/uk11/"):
                return Response("UK 11+ parent account required", status=403)
            return None
        if market["market_id"] != UK_MARKET or market["programme_id"] != UK_PROGRAMME:
            return Response("Unsupported parent market", status=403)
        if request.endpoint == "parent_dashboard":
            return redirect("/uk11/api/guardian/home")
        if request.endpoint in ("uk11_guardian.guardian_home",
                                "uk11_guardian.guardian_students",
                                "uk11_guardian.guardian_decision",
                                "uk11_guardian.guardian_form_decision",
                                "logout", "static"):
            return None
        if request.path.startswith("/uk11/"):
            return Response("Unqualified UK parent action", status=403)
        # UK parents may use the original ScoreMax link-code endpoint,
        # but never enter legacy parent analytics or student learning routes.
        if request.endpoint in ("parent_link_student",):
            return None
        return Response("This UK 11+ parent feature is not yet available.",
                        status=403, mimetype="text/plain",
                        headers={"Cache-Control":"no-store, private"})

    @app.before_request
    def uk11_learner_market_gate():
        # This boundary is specific to the authenticated UK student. It cannot
        # override /login or existing parent/admin/reviewer behaviour.
        uid = session.get("user_id")
        if type(uid) is not int or session.get("role") != "student":
            return None
        record = find_market(uid)
        if record is None:
            # Legacy/Pakistan users must not acquire UK access by adding schools.
            if request.endpoint in UK_ONLY_ENDPOINTS or request.path.startswith("/uk11/"):
                return Response("UK learner account required", status=403)
            return None
        if record["market_id"] != UK_MARKET or record["programme_id"] != UK_PROGRAMME:
            return Response("Unsupported learner market", status=403)
        if request.endpoint in ("dashboard",):
            return redirect("/student")
        if request.endpoint in ("student_dashboard", "uk11_school_dashboard.uk11_my_learning"):
            if request.method != "GET":
                return Response("UK method not qualified", status=405)
            return home_page()
        if request.endpoint in UK_ALLOWED_ENDPOINTS:
            return None
        # Do not let a UK student traverse the native Pakistan subject, question,
        # mock, study plan, marking or mastery routes until explicitly qualified.
        return Response("This UK 11+ learning feature is not yet available.",
                        status=403, mimetype="text/plain",
                        headers={"Cache-Control":"no-store, private"})

    # Registered at the beginning so Flask executes this LAST among the
    # global after_request hooks. Do not remove native session/security headers.
    def uk11_final_response_boundary(response):
        family_html = getattr(g, "uk11_family_html", None)
        if family_html is not None and request.endpoint in (
            "uk11_guardian.guardian_student_page", "uk11_guardian.guardian_home"
        ):
            response.set_data(family_html.encode("utf-8"))
            response.mimetype = "text/html"
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
        registration_html = getattr(g, "uk11_registration_base_html", None)
        if registration_html is not None and request.endpoint == "register" and request.method == "GET":
            response.set_data(registration_html.encode("utf-8"))
            response.mimetype = "text/html"
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["X-Content-Type-Options"] = "nosniff"
        safe_html = getattr(g, "uk11_final_home_html", None)
        if safe_html is not None and request.endpoint in ("student_dashboard", "uk11_school_dashboard.uk11_my_learning"):
            response.set_data(safe_html.encode("utf-8"))
            response.mimetype = "text/html"
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    app.after_request_funcs.setdefault(None, []).insert(0, uk11_final_response_boundary)

    app.extensions["scoremax_uk11_market_gate"] = {"market":UK_MARKET,"programme":UK_PROGRAMME,
                                                       "test_only":True,"method":"explicit_account_mapping"}
    return {"installed":True,"test_only":True,"default_market_unchanged":True,
            "unqualified_native_routes_blocked":True}
