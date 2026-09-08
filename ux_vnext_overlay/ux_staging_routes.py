from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import render_template, request, session

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


def _is_fsc_level(level: str) -> bool:
    value = (level or "").casefold()
    return "fsc" in value and (
        "part 1" in value or "part 2" in value or "year 1" in value or "year 2" in value
        or value.strip() in {"fsc 1", "fsc 2"}
    )


def _student_refinement_markup() -> str:
    return r'''
<style id="ux-student-refinement">
.student-context-stack{min-height:48px!important;padding:7px max(18px,calc((100vw - 1200px)/2))!important;background:#fff!important;border-bottom:1px solid #e5ecec!important}
.student-context-stack .programme-context-strip{display:none!important}
.student-context-stack .subject-quick-strip{position:static!important;display:flex!important;align-items:center!important;gap:7px!important;padding:0!important;margin:0!important;border:0!important;background:transparent!important;overflow-x:auto!important;scrollbar-width:none!important}
.student-context-stack .subject-quick-strip::-webkit-scrollbar{display:none!important}
.student-context-stack .subject-quick-strip .subject-all{display:none!important}
.student-context-stack .subject-quick-strip>a{display:inline-flex!important;align-items:center!important;gap:5px!important;min-height:34px!important;padding:7px 13px!important;margin:0!important;border:1px solid #e4eaea!important;border-radius:999px!important;background:#f7f9f9!important;color:#42515f!important;text-decoration:none!important;font-size:.82rem!important;font-weight:850!important;white-space:nowrap!important}
.student-context-stack .subject-quick-strip>a.active{background:#E8F6F5!important;border-color:#9fd5d2!important;color:#236765!important}
.student-home-v2 .mastery-hero-card{padding:17px 19px!important;border-radius:19px!important}
.student-home-v2 .mastery-hero-top h2{font-size:clamp(1.3rem,2vw,1.8rem)!important;margin:.08rem 0!important}
.student-home-v2 .mastery-ladder{grid-template-columns:repeat(6,minmax(0,1fr))!important;margin:13px 0 11px!important}
.student-home-v2 .mastery-ladder:before{left:6%!important;right:6%!important;top:6px!important}
.student-home-v2 .mastery-step{font-size:.55rem!important;line-height:1.12!important;color:#7f94a5!important}
.student-home-v2 .mastery-step i{width:13px!important;height:13px!important;margin-bottom:5px!important;border-width:2px!important}
.student-home-v2 .mastery-step.current{color:#fff!important;font-weight:950!important}
.student-home-v2 .mastery-step.current i{background:#3FA6A3!important;box-shadow:0 0 0 4px rgba(63,166,163,.14),0 0 15px rgba(63,166,163,.38)!important}
.student-home-v2 .mastery-step.current span:after{content:'YOU';display:block;margin:3px auto 0;width:max-content;padding:2px 4px;border-radius:999px;background:rgba(63,166,163,.16);color:#9ce3df;font-size:.44rem;letter-spacing:.08em;font-weight:950}
.student-home-v2 .mastery-hero-card>p{margin:.5rem 0!important;font-size:.78rem!important}
.student-home-v2 .mastery-next{padding:7px 10px!important;margin:7px 0!important}
.ux-progress-top{padding-top:14px!important;padding-bottom:14px!important}
.ux-progress-top .ux-section-head{margin-bottom:9px!important}
.ux-progress-top .ux-section-head h2{font-size:clamp(1.2rem,2vw,1.65rem)!important;margin:.12rem 0 .25rem!important}
.ux-progress-top .ux-section-head>p:last-child{font-size:.8rem!important;margin:.2rem 0!important}
.ux-progress-top .ux-levels{gap:6px!important}
.ux-progress-top .ux-level{min-height:58px!important;padding:8px 9px!important;border-radius:11px!important}
.ux-progress-top .ux-level>span{font-size:.56rem!important}.ux-progress-top .ux-level strong{font-size:.76rem!important}.ux-progress-top .ux-level small{font-size:.6rem!important;line-height:1.2!important}
.ux-inline-calculator{max-width:1200px;margin:18px auto;padding:0 24px}.ux-inline-calculator-inner{padding:22px 24px;border:1px solid #cbe7e5;border-radius:20px;background:linear-gradient(135deg,#f0faf9,#fff 65%);box-shadow:0 10px 30px rgba(47,127,125,.06)}
.ux-inline-calculator-head{display:flex;justify-content:space-between;gap:22px;align-items:end;margin-bottom:16px}.ux-inline-calculator h2{margin:.08rem 0 .3rem;font-size:clamp(1.35rem,2.4vw,1.9rem)}.ux-inline-calculator p{margin:0;color:#617080;font-size:.86rem}.ux-inline-calc-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.ux-inline-calc-grid label{display:grid;gap:4px;font-size:.69rem;font-weight:850;color:#4c5b69}.ux-inline-calc-grid input{width:100%;padding:9px 10px;border:1px solid #cfdddc;border-radius:9px;background:#fff}.ux-inline-calc-result{grid-column:span 2;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 13px;border-radius:12px;background:#17383b;color:#fff}.ux-inline-calc-result span{font-size:.69rem;font-weight:800;opacity:.8}.ux-inline-calc-result strong{font-size:1.25rem}.ux-inline-calc-result.secondary{background:#E8F6F5;color:#236765;border:1px solid #b9e1df}
@media(max-width:900px){.student-context-stack{top:58px!important;padding:7px 12px!important}.ux-progress-top .ux-levels{grid-template-columns:repeat(3,1fr)!important}.ux-inline-calc-grid{grid-template-columns:repeat(2,1fr)}.ux-inline-calculator-head{align-items:flex-start;flex-direction:column}}
@media(max-width:560px){.student-home-v2 .mastery-ladder{overflow-x:auto!important;grid-template-columns:repeat(6,minmax(70px,1fr))!important}.ux-progress-top .ux-levels{grid-template-columns:repeat(2,1fr)!important}.ux-inline-calculator{padding:0 14px}.ux-inline-calc-grid{grid-template-columns:1fr}.ux-inline-calc-result{grid-column:auto}}
</style>
<script id="ux-student-navigation-refinement">(function(){
function refine(){
 var nav=document.querySelector('.site-header .desktop-nav');
 if(nav&&nav.querySelector('a[href*="student"]')){
   var account=nav.querySelector('.student-account-menu');
   var links=[].slice.call(nav.querySelectorAll(':scope > a'));
   var byText={}; links.forEach(function(a){byText[(a.textContent||'').trim()]=a;});
   var specs=[['Home','/student'],['Learn','/student/subjects'],['Practice','/test/setup'],['Weak Areas','/student/weak-areas'],['Mastery','/student/mastery'],['My Plan','/student/study-plan'],['Exams','/student/exams'],['Calculators','/student/calculators'],['Progress','/student/analytics']];
   links.forEach(function(a){a.remove();});
   specs.forEach(function(s){var a=byText[s[0]]||document.createElement('a');a.textContent=s[0];if(!a.getAttribute('href'))a.href=s[1];nav.insertBefore(a,account||null);});
 }
 document.querySelectorAll('.programme-context-strip,.subject-quick-strip .subject-all').forEach(function(el){el.remove();});
 var ladder=document.querySelector('.student-home-v2 .mastery-ladder');
 if(ladder){
   var existing=[].slice.call(ladder.querySelectorAll('.mastery-step')).map(function(x){return (x.textContent||'').trim();});
   ['Expert','Elite'].forEach(function(level){if(existing.indexOf(level)<0){var d=document.createElement('div');d.className='mastery-step';d.innerHTML='<i></i><span>'+level+'</span>';ladder.appendChild(d);}});
 }
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',refine);else refine();
})();</script>
'''


def _landing_calculator_markup() -> str:
    return r'''
<section class="ux-inline-calculator" aria-labelledby="publicCalculatorTitle">
 <div class="ux-inline-calculator-inner">
  <div class="ux-inline-calculator-head"><div><p class="ux-kicker">ADMISSION CALCULATORS</p><h2 id="publicCalculatorTitle">Calculate your aggregate. Know the score you need.</h2><p>Punjab medical: 10% Matric · 40% FSc · 50% MDCAT.</p></div></div>
  <div class="ux-inline-calc-grid">
   <label>Matric obtained<input id="pubSscO" type="number" min="0" step="0.01"></label><label>Matric total<input id="pubSscT" type="number" min="1" step="0.01"></label>
   <label>FSc obtained<input id="pubFscO" type="number" min="0" step="0.01"></label><label>FSc total<input id="pubFscT" type="number" min="1" step="0.01"></label>
   <label>MDCAT obtained<input id="pubMdO" type="number" min="0" step="0.01"></label><label>MDCAT total<input id="pubMdT" type="number" min="1" step="0.01"></label>
   <div class="ux-inline-calc-result"><span>Your aggregate</span><strong id="pubAgg">—</strong></div>
   <label>Target aggregate %<input id="pubTarget" type="number" min="0" max="100" step="0.0001"></label><label>Target MDCAT total<input id="pubTargetTotal" type="number" min="1" step="1"></label>
   <div class="ux-inline-calc-result secondary"><span>MDCAT score needed</span><strong id="pubNeed">—</strong></div>
  </div>
 </div>
</section>
<script id="ux-public-calculator-script">(function(){var q=function(id){return document.getElementById(id)},n=function(id){var v=parseFloat(q(id)&&q(id).value);return Number.isFinite(v)?v:null},ok=function(o,t){return o!==null&&t!==null&&t>0&&o>=0&&o<=t};function calc(){var so=n('pubSscO'),st=n('pubSscT'),fo=n('pubFscO'),ft=n('pubFscT'),mo=n('pubMdO'),mt=n('pubMdT');var s=ok(so,st)?so/st*10:null,f=ok(fo,ft)?fo/ft*40:null,m=ok(mo,mt)?mo/mt*50:null;q('pubAgg').textContent=(s!==null&&f!==null&&m!==null)?(s+f+m).toFixed(4)+'%':'—';var tar=n('pubTarget'),tt=n('pubTargetTotal');if(s!==null&&f!==null&&tar!==null&&tt!==null&&tt>0){var need=(tar-s-f)/50*tt;q('pubNeed').textContent=need<=0?'0 / '+Math.round(tt):need>tt?'Above maximum':Math.ceil(need)+' / '+Math.round(tt);}else q('pubNeed').textContent='—';}['pubSscO','pubSscT','pubFscO','pubFscT','pubMdO','pubMdT','pubTarget','pubTargetTotal'].forEach(function(id){q(id)&&q(id).addEventListener('input',calc);});})();</script>
'''


def _legacy_tour_guard() -> str:
    return r'''<script id="ux-staging-disable-legacy-tour">(function(){function clean(){var all=[].slice.call(document.querySelectorAll('body *'));all.forEach(function(el){var t=((el.textContent||'').replace(/\s+/g,' ').trim());var n=((el.id||'')+' '+(el.className||'')).toLowerCase();if(/(?:part\s*)?[123]\s+of\s+3/i.test(t)&&t.length<1400){var p=el;while(p&&p!==document.body){var s=getComputedStyle(p),r=p.getBoundingClientRect();if((s.position==='fixed'||s.position==='absolute')&&r.width>220&&r.height>70){p.remove();break;}p=p.parentElement;}}if(/tour|walkthrough|coach.?mark/.test(n)&&(getComputedStyle(el).position==='fixed'||getComputedStyle(el).position==='absolute'))el.remove();});document.body.style.overflow='';document.documentElement.style.overflow='';}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',clean);else clean();})();</script>'''


def _install_staging_page_guards(app) -> None:
    if getattr(app, "_ux_staging_page_guards_installed", False):
        return

    stable_secret = os.environ.get("SCOREMAX_STAGING_SESSION_SECRET", "").strip()
    if not stable_secret:
        raise RuntimeError("UX_STAGING_SESSION_SECRET_MISSING")
    app.secret_key = stable_secret
    app.config["SECRET_KEY"] = stable_secret

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

        learner_page = "student-context-stack" in html or "student-home-v2" in html or endpoint == "dashboard" or endpoint.startswith("student_") or endpoint == "ux_calculators"
        if learner_page and "ux-student-refinement" not in html:
            html = html.replace("</body>", _student_refinement_markup() + _legacy_tour_guard() + "</body>", 1) if "</body>" in html else html + _student_refinement_markup() + _legacy_tour_guard()

        if endpoint == "index" and "ux-inline-calculator" not in html:
            hero_marker = '<section class="ux-hero"'
            if hero_marker in html:
                html = html.replace(hero_marker, _student_refinement_markup().split('<script id="ux-student-navigation-refinement">',1)[0] + _landing_calculator_markup() + hero_marker, 1)

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
