from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from flask import render_template, request, session
from jinja2 import BaseLoader

_LOGIN_PROMO_MARKER = "coming next"
_LOGIN_PROGRAMME_TERMS = ("mdcat", "ecat", "fsc", "matric", "grade 9", "grade 10")
_PREMED_DEFAULT_SUBJECTS = ("Biology", "Chemistry", "Physics")


def _db_path() -> Path:
    return Path(os.environ.get("SCOREMAX_DB", "/tmp/scoremax-ux-vnext/state/scoremax.db"))


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _clean(value: str | None, limit: int = 500) -> str:
    return (value or "").strip()[:limit]


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ux_interest_registrations(
          id INTEGER PRIMARY KEY,
          programme TEXT NOT NULL,
          full_name TEXT NOT NULL,
          email TEXT,
          mobile TEXT,
          role TEXT NOT NULL,
          school TEXT,
          city TEXT,
          note TEXT,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_ux_interest_programme ON ux_interest_registrations(programme);
        CREATE INDEX IF NOT EXISTS idx_ux_interest_email ON ux_interest_registrations(lower(email));
        CREATE TABLE IF NOT EXISTS ux_school_nominations(
          id INTEGER PRIMARY KEY,
          nominator_name TEXT NOT NULL,
          email TEXT,
          role TEXT NOT NULL,
          school_name TEXT NOT NULL,
          city TEXT,
          relationship TEXT,
          reason TEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_ux_school_nomination_school ON ux_school_nominations(lower(school_name));
        """
    )
    conn.commit()


def _matching_element_end(source: str, start: int, tag: str) -> int | None:
    token_re = re.compile(rf"</?{re.escape(tag)}\b[^>]*>", re.I)
    depth = 0
    for match in token_re.finditer(source, start):
        token = match.group(0).lstrip()
        if token.startswith("</"):
            depth -= 1
            if depth == 0:
                return match.end()
        elif not token.rstrip().endswith("/>"):
            depth += 1
    return None


def _strip_login_programme_promo(source: str) -> str:
    lower = source.lower()
    marker_at = lower.find(_LOGIN_PROMO_MARKER)
    if marker_at < 0:
        return source
    candidates: list[tuple[int, str]] = []
    for match in re.finditer(r"<(aside|article|section|div)\b[^>]*>", source[:marker_at], re.I):
        candidates.append((match.start(), match.group(1).lower()))
    for start, tag in reversed(candidates):
        end = _matching_element_end(source, start, tag)
        if end is None or not (start < marker_at < end):
            continue
        block = source[start:end]
        block_lower = block.lower()
        if _LOGIN_PROMO_MARKER not in block_lower:
            continue
        if not any(term in block_lower for term in _LOGIN_PROGRAMME_TERMS):
            continue
        if 'name="identity"' in block_lower or 'name="password"' in block_lower or "<form" in block_lower:
            continue
        return source[:start] + source[end:]
    return source


def _transform_student_base(source: str) -> str:
    old_nav = '''{% if learner_ui_global %}
        <a class="{{'active' if student_nav_section_global=='dashboard' else ''}}" href="{{url_for('student_dashboard')}}">Home</a>
        <a class="{{'active' if student_nav_section_global=='learn' else ''}}" href="{{url_for('subject_browser')}}">Learn</a>
        <a class="{{'active' if student_nav_section_global=='plan' else ''}}" href="{{url_for('study_plan_page')}}">My Plan</a>
        <a class="{{'active' if student_nav_section_global=='tests' else ''}}" href="{{url_for('test_setup')}}">Practice</a>
        <a class="{{'active' if student_nav_section_global=='exams' else ''}}" href="{{url_for('exam_centre')}}">Exams</a>
        <a class="{{'active' if student_nav_section_global=='progress' else ''}}" href="{{url_for('student_analytics_page')}}">Progress</a>'''
    new_nav = '''{% if learner_ui_global %}
        <a class="{{'active' if student_nav_section_global=='dashboard' else ''}}" href="{{url_for('student_dashboard')}}">Home</a>
        <a class="{{'active' if student_nav_section_global=='learn' else ''}}" href="{{url_for('subject_browser')}}">Learn</a>
        <a class="{{'active' if student_nav_section_global=='tests' and request.endpoint not in ['weak_areas_page','mastery_page'] else ''}}" href="{{url_for('test_setup')}}">Practice</a>
        <a class="{{'active' if request.endpoint=='weak_areas_page' else ''}}" href="{{url_for('weak_areas_page')}}">Weak Areas</a>
        <a class="{{'active' if request.endpoint=='mastery_page' else ''}}" href="{{url_for('mastery_page')}}">Mastery</a>
        <a class="{{'active' if student_nav_section_global=='plan' else ''}}" href="{{url_for('study_plan_page')}}">My Plan</a>
        <a class="{{'active' if student_nav_section_global=='exams' else ''}}" href="{{url_for('exam_centre')}}">Exams</a>
        <a class="{{'active' if request.endpoint=='ux_calculators' else ''}}" href="{{url_for('ux_calculators')}}">Calculators</a>
        <a class="{{'active' if student_nav_section_global=='progress' else ''}}" href="{{url_for('student_analytics_page')}}">Progress</a>'''
    if old_nav not in source:
        raise RuntimeError("UX_STUDENT_PRIMARY_NAV_MARKER_MISSING")
    source = source.replace(old_nav, new_nav, 1)

    start_marker = "{% if learner_ui_global and request.endpoint not in ['take_test_v4','assessment_review_v4','qa_synthetic_session'] %}"
    start = source.find(start_marker)
    main = source.find('<main id="mainContent"', start)
    if start < 0 or main < 0:
        raise RuntimeError("UX_STUDENT_CONTEXT_MARKER_MISSING")
    subject_only = '''{% if learner_ui_global and show_subject_nav_global and request.endpoint not in ['take_test_v4','assessment_review_v4','qa_synthetic_session','ux_calculators'] %}
<div class="student-context-stack subject-only-context" aria-label="Subjects">
  <nav class="subject-quick-strip" aria-label="Subject selector">
    {% for s in subject_nav_global %}
      <a class="{{'active' if (active_subject_global|lower)==(s.subject|lower) else ''}} state-{{s.access_state|lower}}" href="{{url_for('access_account',locked_subject=s.subject) if s.access_state=='LOCKED' else url_for('subject_detail',subject=s.subject)}}">{{s.subject}}{% if s.access_state=='LOCKED' %}<small>Upgrade</small>{% elif s.availability=='COMING_SOON' %}<small>Soon</small>{% elif s.answered %}<small>{{s.accuracy|round(0)|int}}%</small>{% endif %}</a>
    {% endfor %}
  </nav>
</div>
{% endif %}
'''
    return source[:start] + subject_only + source[main:]


def _validate_clean_login(source: str) -> None:
    for required in ('name="identity"', 'name="password"', "csrf_token"):
        if required not in source:
            raise RuntimeError("UX_LOGIN_AUTH_CONTROL_MISSING:" + required)


class _UxStagingLoader(BaseLoader):
    def __init__(self, base_loader):
        self.base_loader = base_loader

    def get_source(self, environment, template):
        source, filename, uptodate = self.base_loader.get_source(environment, template)
        if template == "login.html":
            source = _strip_login_programme_promo(source)
            _validate_clean_login(source)
        elif template == "base.html":
            source = _transform_student_base(source)
        return source, filename, uptodate


def _is_fsc_level(level: str) -> bool:
    value = (level or "").casefold()
    return "fsc" in value and ("part 1" in value or "part 2" in value or "year 1" in value or "year 2" in value or value.strip() in {"fsc 1", "fsc 2"})


def _install_staging_page_guards(app) -> None:
    if getattr(app, "_ux_staging_page_guards_installed", False):
        return

    stable_secret = os.environ.get("SCOREMAX_STAGING_SESSION_SECRET", "").strip()
    if not stable_secret:
        raise RuntimeError("UX_STAGING_SESSION_SECRET_MISSING")
    app.secret_key = stable_secret
    app.config["SECRET_KEY"] = stable_secret

    base_loader = app.jinja_loader
    if base_loader is None:
        raise RuntimeError("UX_BASE_TEMPLATE_LOADER_MISSING")
    loader = _UxStagingLoader(base_loader)
    loader.get_source(app.jinja_env, "login.html")
    loader.get_source(app.jinja_env, "base.html")
    app.jinja_loader = loader
    app.jinja_env.cache.clear()

    @app.before_request
    def _ux_staging_subject_defaults():
        if session.get("role") != "student" or not session.get("user_id"):
            return None
        conn = _connect()
        try:
            row = conn.execute("SELECT academic_level,COALESCE(subjects,'') subjects FROM users WHERE id=?", (session["user_id"],)).fetchone()
            if row and _is_fsc_level(row["academic_level"] or "") and not (row["subjects"] or "").strip():
                conn.execute("UPDATE users SET subjects=? WHERE id=?", (",".join(_PREMED_DEFAULT_SUBJECTS), session["user_id"]))
                conn.commit()
        finally:
            conn.close()
        return None

    @app.after_request
    def _ux_staging_final_render_guards(response):
        if not response.is_sequence or "text/html" not in (response.content_type or "").lower():
            return response
        html = response.get_data(as_text=True)
        endpoint = request.endpoint or ""
        learner_page = "student-context-stack" in html or "student-home-v2" in html or endpoint == "dashboard" or endpoint.startswith("student_")
        if learner_page and "ux-staging-disable-legacy-tour" not in html:
            tour_guard = r'''<script id="ux-staging-disable-legacy-tour">(function(){function clean(){var all=[].slice.call(document.querySelectorAll('body *'));all.forEach(function(el){var t=((el.textContent||'').replace(/\s+/g,' ').trim());var n=((el.id||'')+' '+(el.className||'')).toLowerCase();if(/(?:part\s*)?[123]\s+of\s+3/i.test(t)&&t.length<1400){var p=el;while(p&&p!==document.body){var s=getComputedStyle(p),r=p.getBoundingClientRect();if((s.position==='fixed'||s.position==='absolute')&&r.width>220&&r.height>70){p.remove();break;}p=p.parentElement;}}if(/tour|walkthrough|coach.?mark/.test(n)&&(getComputedStyle(el).position==='fixed'||getComputedStyle(el).position==='absolute'))el.remove();});document.body.style.overflow='';document.documentElement.style.overflow='';}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',clean);else clean();})();</script>'''
            html = html.replace("</body>", tour_guard + "</body>", 1) if "</body>" in html else html + tour_guard
            response.set_data(html)
            response.content_length = len(response.get_data())
        return response

    app._ux_staging_page_guards_installed = True


def install_ux_staging_routes(app) -> None:
    _install_staging_page_guards(app)
    if "ux_register_interest" in app.view_functions:
        return

    @app.route("/student/calculators", methods=["GET"], endpoint="ux_calculators")
    def ux_calculators():
        if session.get("role") != "student":
            return render_template("ux_target_score.html")
        return render_template("ux_target_score.html")

    @app.route("/register-interest", methods=["GET", "POST"], endpoint="ux_register_interest")
    def ux_register_interest():
        programme = _clean(request.values.get("programme"), 100) or "ScoreMax programme"
        success = False
        error = ""
        values = {
            "programme": programme,
            "full_name": _clean(request.form.get("full_name"), 120),
            "email": _clean(request.form.get("email"), 180),
            "mobile": _clean(request.form.get("mobile"), 60),
            "role": _clean(request.form.get("role"), 30) or "Student",
            "school": _clean(request.form.get("school"), 180),
            "city": _clean(request.form.get("city"), 120),
            "note": _clean(request.form.get("note"), 1000),
        }
        if request.method == "POST":
            if not values["full_name"]:
                error = "Please enter your name."
            elif not values["email"] and not values["mobile"]:
                error = "Please provide an email address or mobile number so we can contact you."
            else:
                conn = _connect()
                try:
                    _ensure_schema(conn)
                    conn.execute("""INSERT INTO ux_interest_registrations(programme,full_name,email,mobile,role,school,city,note) VALUES(?,?,?,?,?,?,?,?)""", (values["programme"], values["full_name"], values["email"], values["mobile"], values["role"], values["school"], values["city"], values["note"]))
                    conn.commit()
                    success = True
                finally:
                    conn.close()
        return render_template("ux_register_interest.html", success=success, error=error, values=values)

    @app.route("/nominate-school", methods=["GET", "POST"], endpoint="ux_nominate_school")
    def ux_nominate_school():
        success = False
        error = ""
        values = {
            "nominator_name": _clean(request.form.get("nominator_name"), 120),
            "email": _clean(request.form.get("email"), 180),
            "role": _clean(request.form.get("role"), 30) or "Student",
            "school_name": _clean(request.form.get("school_name"), 180),
            "city": _clean(request.form.get("city"), 120),
            "relationship": _clean(request.form.get("relationship"), 180),
            "reason": _clean(request.form.get("reason"), 1200),
        }
        if request.method == "POST":
            if not values["nominator_name"]:
                error = "Please enter your name."
            elif not values["school_name"]:
                error = "Please enter the school or college name."
            elif not values["reason"]:
                error = "Please tell us why you are nominating this school."
            else:
                conn = _connect()
                try:
                    _ensure_schema(conn)
                    conn.execute("""INSERT INTO ux_school_nominations(nominator_name,email,role,school_name,city,relationship,reason) VALUES(?,?,?,?,?,?,?)""", (values["nominator_name"], values["email"], values["role"], values["school_name"], values["city"], values["relationship"], values["reason"]))
                    conn.commit()
                    success = True
                finally:
                    conn.close()
        return render_template("ux_nominate_school.html", success=success, error=error, values=values)
