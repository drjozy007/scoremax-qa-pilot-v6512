from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from flask import render_template, request
from jinja2 import BaseLoader


_LOGIN_PROMO_MARKER = "coming next"
_LOGIN_PROGRAMME_TERMS = ("mdcat", "ecat", "fsc", "matric", "grade 9", "grade 10")


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


def _validate_clean_login(source: str) -> None:
    for required in ('name="identity"', 'name="password"', "csrf_token"):
        if required not in source:
            raise RuntimeError("UX_LOGIN_AUTH_CONTROL_MISSING:" + required)


class _UxLoginCleanLoader(BaseLoader):
    def __init__(self, base_loader):
        self.base_loader = base_loader

    def get_source(self, environment, template):
        source, filename, uptodate = self.base_loader.get_source(environment, template)
        if template == "login.html":
            source = _strip_login_programme_promo(source)
            _validate_clean_login(source)
        return source, filename, uptodate


def _install_login_cleaner(app) -> None:
    if getattr(app, "_ux_login_cleaner_installed", False):
        return
    base_loader = app.jinja_loader
    if base_loader is None:
        raise RuntimeError("UX_LOGIN_BASE_TEMPLATE_LOADER_MISSING")
    cleaner = _UxLoginCleanLoader(base_loader)
    cleaner.get_source(app.jinja_env, "login.html")
    app.jinja_loader = cleaner
    app.jinja_env.cache.clear()

    @app.after_request
    def _ux_login_final_render_guard(response):
        if request.endpoint != "login" or not response.is_sequence:
            return response
        content_type = (response.content_type or "").lower()
        if "text/html" not in content_type:
            return response
        html = response.get_data(as_text=True)
        guard = r'''<script id="ux-login-final-guard">(function(){function clean(){var terms=['coming next','mdcat','ecat','fsc','matric','grade 9','grade 10'];var nodes=[].slice.call(document.querySelectorAll('aside,section,article,div'));nodes.forEach(function(el){if(el.querySelector('input[name="identity"],input[name="password"]'))return;var t=(el.textContent||'').toLowerCase();if(t.indexOf('coming next')===-1)return;if(!terms.some(function(x){return t.indexOf(x)!==-1;}))return;var child=[].slice.call(el.children).some(function(c){var ct=(c.textContent||'').toLowerCase();return ct.indexOf('coming next')!==-1;});if(!child||el.children.length<5){el.remove();}});}if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',clean);}else{clean();}})();</script>'''
        if "ux-login-final-guard" not in html:
            if "</body>" in html:
                html = html.replace("</body>", guard + "</body>", 1)
            else:
                html += guard
            response.set_data(html)
            response.content_length = len(response.get_data())
        return response

    app._ux_login_cleaner_installed = True


def install_ux_staging_routes(app) -> None:
    _install_login_cleaner(app)

    if "ux_register_interest" in app.view_functions:
        return

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
                    conn.execute(
                        """INSERT INTO ux_interest_registrations(programme,full_name,email,mobile,role,school,city,note)
                           VALUES(?,?,?,?,?,?,?,?)""",
                        (
                            values["programme"], values["full_name"], values["email"], values["mobile"],
                            values["role"], values["school"], values["city"], values["note"],
                        ),
                    )
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
                    conn.execute(
                        """INSERT INTO ux_school_nominations(nominator_name,email,role,school_name,city,relationship,reason)
                           VALUES(?,?,?,?,?,?,?)""",
                        (
                            values["nominator_name"], values["email"], values["role"], values["school_name"],
                            values["city"], values["relationship"], values["reason"],
                        ),
                    )
                    conn.commit()
                    success = True
                finally:
                    conn.close()
        return render_template("ux_nominate_school.html", success=success, error=error, values=values)
