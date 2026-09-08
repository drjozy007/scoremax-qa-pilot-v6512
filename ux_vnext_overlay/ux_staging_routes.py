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


def _install_staging_page_guards(app) -> None:
    if getattr(app, "_ux_staging_page_guards_installed", False):
        return

    # Keep staging browser sessions valid across deploys. Render's start command
    # still creates an ephemeral SCOREMAX_SECRET, but UX staging deliberately
    # overrides it here with a separate stable staging-only secret.
    stable_secret = os.environ.get("SCOREMAX_STAGING_SESSION_SECRET", "").strip()
    if not stable_secret:
        raise RuntimeError("UX_STAGING_SESSION_SECRET_MISSING")
    app.secret_key = stable_secret
    app.config["SECRET_KEY"] = stable_secret

    base_loader = app.jinja_loader
    if base_loader is None:
        raise RuntimeError("UX_LOGIN_BASE_TEMPLATE_LOADER_MISSING")
    cleaner = _UxLoginCleanLoader(base_loader)
    cleaner.get_source(app.jinja_env, "login.html")
    app.jinja_loader = cleaner
    app.jinja_env.cache.clear()

    @app.after_request
    def _ux_staging_final_render_guards(response):
        if not response.is_sequence:
            return response
        content_type = (response.content_type or "").lower()
        if "text/html" not in content_type:
            return response

        html = response.get_data(as_text=True)

        if request.endpoint == "login" and "ux-login-final-guard" not in html:
            login_guard = r'''<script id="ux-login-final-guard">(function(){function clean(){var terms=['coming next','mdcat','ecat','fsc','matric','grade 9','grade 10'];var nodes=[].slice.call(document.querySelectorAll('aside,section,article,div'));nodes.forEach(function(el){if(el.querySelector('input[name="identity"],input[name="password"]'))return;var t=(el.textContent||'').toLowerCase();if(t.indexOf('coming next')===-1)return;if(!terms.some(function(x){return t.indexOf(x)!==-1;}))return;var child=[].slice.call(el.children).some(function(c){var ct=(c.textContent||'').toLowerCase();return ct.indexOf('coming next')!==-1;});if(!child||el.children.length<5){el.remove();}});}if(document.readyState==='loading'){document.addEventListener('DOMContentLoaded',clean);}else{clean();}})();</script>'''
            html = html.replace("</body>", login_guard + "</body>", 1) if "</body>" in html else html + login_guard

        endpoint = request.endpoint or ""
        learner_page = (
            "student-context-stack" in html
            or "student-home-v2" in html
            or endpoint == "dashboard"
            or endpoint.startswith("student_")
        )
        if learner_page and "ux-staging-disable-legacy-tour" not in html:
            tour_guard = r'''<script id="ux-staging-disable-legacy-tour">(function(){
var marker=/(?:part\s*)?[123]\s+of\s+3/i;
function text(el){return ((el&&el.textContent)||'').replace(/\s+/g,' ').trim();}
function isMarker(el){var t=text(el);return t.length>0&&t.length<1400&&marker.test(t);}
function removeLegacyTour(){
  var all=[].slice.call(document.querySelectorAll('body *'));
  var markers=all.filter(isMarker);
  if(!markers.length)return false;
  markers.sort(function(a,b){return text(a).length-text(b).length;});
  markers.slice(0,10).forEach(function(el){
    var n=el,victim=null;
    while(n&&n!==document.body){
      var cs=getComputedStyle(n),r=n.getBoundingClientRect(),z=parseInt(cs.zIndex||'0',10);
      var named=((n.id||'')+' '+(n.className||'')).toLowerCase();
      if((cs.position==='fixed'||cs.position==='absolute')&&r.width>220&&r.height>70&&(z>=30||/tour|onboard|walkthrough|coach.?mark/.test(named)))victim=n;
      n=n.parentElement;
    }
    (victim||el).remove();
  });
  all=[].slice.call(document.querySelectorAll('body *'));
  all.forEach(function(el){
    var cs=getComputedStyle(el),r=el.getBoundingClientRect(),z=parseInt(cs.zIndex||'0',10);
    var named=((el.id||'')+' '+(el.className||'')).toLowerCase();
    if((/tour|onboard|walkthrough|coach.?mark/.test(named))&&(cs.position==='fixed'||cs.position==='absolute')){el.remove();return;}
    if(cs.position==='fixed'&&z>=30&&r.width>=window.innerWidth*.88&&r.height>=window.innerHeight*.82){
      var bg=cs.backgroundColor||'';
      if(bg!=='rgba(0, 0, 0, 0)'&&parseFloat(cs.opacity||'1')>.05){el.remove();return;}
    }
    if(/tour|onboard|walkthrough|coach.?mark/.test(named)){
      [].slice.call(el.classList||[]).forEach(function(c){if(/tour|onboard|walkthrough|coach.?mark/i.test(c))el.classList.remove(c);});
    }
    var outline=parseFloat(cs.outlineWidth||'0');
    var visual=(cs.outlineColor||'')+' '+(cs.boxShadow||'');
    if(outline>=2&&/37,\s*99,\s*235|49,\s*94,\s*251|47,\s*98,\s*204|0,\s*102,\s*255/.test(visual))el.style.setProperty('outline','none','important');
    if((el.classList.contains('today-focus-card')||el.classList.contains('home-progress-card'))&&/37,\s*99,\s*235|49,\s*94,\s*251|0,\s*102,\s*255/.test(cs.boxShadow||''))el.style.setProperty('box-shadow','0 10px 30px rgba(15,23,42,.045)','important');
  });
  [].slice.call(document.body.classList||[]).forEach(function(c){if(/tour|onboard|walkthrough/i.test(c))document.body.classList.remove(c);});
  document.body.style.overflow='';document.documentElement.style.overflow='';
  return true;
}
function start(){
  removeLegacyTour();
  var count=0,obs=new MutationObserver(function(){removeLegacyTour();if(++count>120)obs.disconnect();});
  obs.observe(document.body,{childList:true,subtree:true,attributes:true});
  setTimeout(function(){obs.disconnect();removeLegacyTour();},12000);
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start();
})();</script>'''
            html = html.replace("</body>", tour_guard + "</body>", 1) if "</body>" in html else html + tour_guard

        response.set_data(html)
        response.content_length = len(response.get_data())
        return response

    app._ux_staging_page_guards_installed = True


def install_ux_staging_routes(app) -> None:
    _install_staging_page_guards(app)

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
