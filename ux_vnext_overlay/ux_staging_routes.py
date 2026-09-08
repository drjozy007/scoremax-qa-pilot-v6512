from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from flask import render_template, request, session, url_for

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


def _normalise_student_profile() -> tuple[str, list[str]]:
    if session.get("role") != "student" or not session.get("user_id"):
        return "", []
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COALESCE(academic_level,'') academic_level,COALESCE(subjects,'') subjects FROM users WHERE id=?",
            (session["user_id"],),
        ).fetchone()
        if not row:
            return "", []
        academic_level = (row["academic_level"] or "").strip()
        subjects = [x.strip() for x in (row["subjects"] or "").split(",") if x.strip()]
        if not subjects and (_is_fsc_level(academic_level) or not academic_level):
            subjects = list(_PREMED_DEFAULT_SUBJECTS)
            conn.execute("UPDATE users SET subjects=? WHERE id=?", (",".join(subjects), session["user_id"]))
        try:
            conn.execute("UPDATE plans SET name='Silver Access' WHERE code='level_1_access'")
            conn.execute("UPDATE plans SET name='Gold Access' WHERE code='level_2_access'")
            conn.execute("UPDATE plans SET name='Platinum Access' WHERE code='full_access'")
        except sqlite3.OperationalError:
            pass
        conn.commit()
        return academic_level, subjects
    finally:
        conn.close()


def _legacy_tour_guard() -> str:
    return r'''<script id="ux-staging-disable-legacy-tour">(function(){function clean(){var all=[].slice.call(document.querySelectorAll('body *'));all.forEach(function(el){var t=((el.textContent||'').replace(/\s+/g,' ').trim());var n=((el.id||'')+' '+(el.className||'')).toLowerCase();if(/(?:part\s*)?[123]\s+of\s+3/i.test(t)&&t.length<1400){var p=el;while(p&&p!==document.body){var s=getComputedStyle(p),r=p.getBoundingClientRect();if((s.position==='fixed'||s.position==='absolute')&&r.width>220&&r.height>70){p.remove();break;}p=p.parentElement;}}if(/tour|walkthrough|coach.?mark/.test(n)&&(getComputedStyle(el).position==='fixed'||getComputedStyle(el).position==='absolute'))el.remove();});document.body.style.overflow='';document.documentElement.style.overflow='';}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',clean);else clean();})();</script>'''


def _student_refinement_markup(subjects: list[str]) -> str:
    routes = {
        "home": url_for("student_dashboard"),
        "learn": url_for("subject_browser"),
        "practice": url_for("test_setup"),
        "weak": url_for("weak_areas_page"),
        "mastery": url_for("mastery_page"),
        "plan": url_for("study_plan_page"),
        "createPlan": url_for("create_study_plan"),
        "exams": url_for("exam_centre"),
        "calculators": url_for("ux_calculators"),
        "progress": url_for("student_analytics_page"),
        "pathways": url_for("student_pathways"),
    }
    subject_data = []
    for name in subjects:
        try:
            subject_data.append({"name": name, "url": url_for("subject_detail", subject=name)})
        except Exception:
            subject_data.append({"name": name, "url": routes["learn"]})
    csrf = str(session.get("_csrf_token") or "")
    markup = r'''
<style id="ux-student-refinement">
.site-header .desktop-nav{gap:3px!important}.site-header .desktop-nav>a{margin-left:5px!important;font-size:.82rem!important;padding:8px 7px!important;white-space:nowrap!important}.site-header .desktop-nav>a.active{background:#E8F6F5!important;color:#236765!important;border-radius:9px!important}
.student-context-stack{min-height:48px!important;padding:7px max(18px,calc((100vw - 1200px)/2))!important;background:#fff!important;border-bottom:1px solid #e5ecec!important}.student-context-stack .programme-context-strip{display:none!important}.student-context-stack .subject-quick-strip{position:static!important;display:flex!important;align-items:center!important;gap:7px!important;padding:0!important;margin:0!important;border:0!important;background:transparent!important;overflow-x:auto!important;scrollbar-width:none!important}.student-context-stack .subject-quick-strip::-webkit-scrollbar{display:none!important}.student-context-stack .subject-quick-strip .subject-all{display:none!important}.student-context-stack .subject-quick-strip>a{display:inline-flex!important;align-items:center!important;gap:5px!important;min-height:34px!important;padding:7px 13px!important;margin:0!important;border:1px solid #e4eaea!important;border-radius:999px!important;background:#f7f9f9!important;color:#42515f!important;text-decoration:none!important;font-size:.82rem!important;font-weight:850!important;white-space:nowrap!important}.student-context-stack .subject-quick-strip>a.active{background:#E8F6F5!important;border-color:#9fd5d2!important;color:#236765!important}
.home-priority-grid.ux-single-priority{grid-template-columns:1fr!important}.home-priority-grid.ux-single-priority .today-focus-card{min-height:auto!important}
.student-home-v2 .mastery-hero-card{padding:17px 19px!important;border-radius:19px!important}.student-home-v2 .mastery-hero-top h2{font-size:clamp(1.28rem,2vw,1.75rem)!important;margin:.08rem 0!important}.student-home-v2 .mastery-ladder{display:grid!important;grid-template-columns:repeat(6,minmax(0,1fr))!important;gap:6px!important;margin:12px 0 10px!important}.student-home-v2 .mastery-ladder:before{display:none!important}.student-home-v2 .mastery-step{min-height:48px!important;display:flex!important;flex-direction:column!important;align-items:center!important;justify-content:center!important;padding:6px 4px!important;border:1px solid rgba(255,255,255,.09)!important;border-radius:9px!important;background:rgba(255,255,255,.035)!important;color:#8da1b1!important;font-size:.54rem!important;line-height:1.12!important;text-align:center!important}.student-home-v2 .mastery-step i{width:8px!important;height:8px!important;margin:0 0 5px!important;border:0!important;background:#425d70!important;box-shadow:none!important}.student-home-v2 .mastery-step.reached{color:#d9fffc!important;background:rgba(63,166,163,.06)!important}.student-home-v2 .mastery-step.reached i{background:#5fbdb9!important}.student-home-v2 .mastery-step.current{color:#fff!important;background:rgba(63,166,163,.18)!important;border-color:rgba(115,211,206,.48)!important;font-weight:950!important}.student-home-v2 .mastery-step.current i{background:#70d2cd!important;box-shadow:0 0 12px rgba(112,210,205,.45)!important}.student-home-v2 .mastery-step.current span:after{content:'YOU';display:block;margin:3px auto 0;width:max-content;padding:2px 4px;border-radius:999px;background:#3FA6A3;color:#fff;font-size:.42rem;letter-spacing:.08em;font-weight:950}.student-home-v2 .mastery-hero-card>p{margin:.48rem 0!important;font-size:.78rem!important}.student-home-v2 .mastery-next{padding:7px 10px!important;margin:7px 0!important}
.home-subject-card{position:relative!important}.home-subject-card .ux-open-chapters{display:block;margin-top:7px;color:#2F7F7D;font-size:.72rem;font-weight:850}.chapter-mastery-card{transition:transform .15s ease,border-color .15s ease,box-shadow .15s ease}.chapter-mastery-card:hover{transform:translateY(-1px);border-color:#a8d8d5!important;box-shadow:0 10px 24px rgba(47,127,125,.08)!important}
.home-daily-spark.ux-spark-prominent,.ux-daily-spark-placeholder{margin:14px 0 16px!important;border-color:#c7e7e4!important;background:linear-gradient(135deg,#f2fbfa,#fff)!important}.ux-daily-spark-placeholder{padding:18px 20px!important}.ux-daily-spark-placeholder h2{margin:.15rem 0 .4rem!important;font-size:1.15rem!important}
.ux-plan-launcher{display:grid;grid-template-columns:1fr auto;gap:18px;align-items:center;margin:14px 0 16px;padding:18px 20px;border:1px solid #dce7e7;border-radius:17px;background:#fff}.ux-plan-launcher h2{margin:.12rem 0 .35rem;font-size:1.16rem}.ux-plan-launcher p{margin:0;color:#657383;font-size:.82rem}.ux-plan-launcher-actions{display:flex;gap:7px;flex-wrap:wrap}.ux-plan-choice{margin:16px 0 18px;padding:18px;border:1px solid #dbe7e6;border-radius:18px;background:linear-gradient(135deg,#f7fcfb,#fff)}.ux-plan-choice-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}.ux-plan-choice-card{padding:15px;border:1px solid #dfe8e8;border-radius:14px;background:#fff}.ux-plan-choice-card h3{margin:.1rem 0 .35rem}.ux-plan-choice-card p{font-size:.8rem;color:#687686;line-height:1.45}.ux-self-plan-form{display:none;margin-top:13px;padding-top:13px;border-top:1px solid #e7eeee}.ux-self-plan-form.is-open{display:grid;grid-template-columns:1fr 1fr;gap:9px}.ux-self-plan-form label{font-size:.74rem}.ux-self-plan-form button{grid-column:1/-1}.ux-self-plan-form input{width:100%}
.ux-progress-top{padding-top:14px!important;padding-bottom:14px!important}.ux-progress-top .ux-section-head{margin-bottom:9px!important}.ux-progress-top .ux-section-head h2{font-size:clamp(1.2rem,2vw,1.65rem)!important;margin:.12rem 0 .25rem!important}.ux-progress-top .ux-section-head>p:last-child{font-size:.8rem!important;margin:.2rem 0!important}.ux-progress-top .ux-levels{gap:6px!important}.ux-progress-top .ux-level{min-height:58px!important;padding:8px 9px!important;border-radius:11px!important}.ux-progress-top .ux-level>span{font-size:.56rem!important}.ux-progress-top .ux-level strong{font-size:.76rem!important}.ux-progress-top .ux-level small{font-size:.6rem!important;line-height:1.2!important}
.ux-inline-calculator{max-width:1200px;margin:18px auto;padding:0 24px}.ux-inline-calculator-inner{padding:22px 24px;border:1px solid #cbe7e5;border-radius:20px;background:linear-gradient(135deg,#f0faf9,#fff 65%);box-shadow:0 10px 30px rgba(47,127,125,.06)}.ux-inline-calculator-head{display:flex;justify-content:space-between;gap:22px;align-items:end;margin-bottom:16px}.ux-inline-calculator h2{margin:.08rem 0 .3rem;font-size:clamp(1.35rem,2.4vw,1.9rem)}.ux-inline-calculator p{margin:0;color:#617080;font-size:.86rem}.ux-inline-calc-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}.ux-inline-calc-grid label{display:grid;gap:4px;font-size:.69rem;font-weight:850;color:#4c5b69}.ux-inline-calc-grid input{width:100%;padding:9px 10px;border:1px solid #cfdddc;border-radius:9px;background:#fff}.ux-inline-calc-result{grid-column:span 2;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 13px;border-radius:12px;background:#17383b;color:#fff}.ux-inline-calc-result span{font-size:.69rem;font-weight:800;opacity:.8}.ux-inline-calc-result strong{font-size:1.25rem}.ux-inline-calc-result.secondary{background:#E8F6F5;color:#236765;border:1px solid #b9e1df}
@media(max-width:1050px){.site-header .desktop-nav>a{font-size:.76rem!important;padding-left:5px!important;padding-right:5px!important}}@media(max-width:900px){.student-context-stack{top:58px!important;padding:7px 12px!important}.ux-progress-top .ux-levels{grid-template-columns:repeat(3,1fr)!important}.ux-inline-calc-grid{grid-template-columns:repeat(2,1fr)}.ux-plan-launcher{grid-template-columns:1fr}.ux-plan-choice-grid{grid-template-columns:1fr}}@media(max-width:560px){.student-home-v2 .mastery-ladder{overflow-x:auto!important;grid-template-columns:repeat(6,minmax(76px,1fr))!important}.ux-progress-top .ux-levels{grid-template-columns:repeat(2,1fr)!important}.ux-inline-calculator{padding:0 14px}.ux-inline-calc-grid{grid-template-columns:1fr}.ux-inline-calc-result{grid-column:auto}.ux-self-plan-form.is-open{grid-template-columns:1fr}}
</style>
<script id="ux-student-navigation-refinement">(function(){
const subjects=__SUBJECTS__;const routes=__ROUTES__;const csrf=__CSRF__;const levels=['Foundation','Exam Ready','Advanced','Distinction','Expert','Elite'];
function pathOf(u){try{return new URL(u,location.origin).pathname}catch(e){return u||''}}
function makeA(label,href){const a=document.createElement('a');a.textContent=label;a.href=href;const p=pathOf(href),here=location.pathname;if((label==='Home'&&here===p)||(label!=='Home'&&p!=='/'&&here.startsWith(p)))a.classList.add('active');return a;}
function refineTopNav(){const nav=document.querySelector('.site-header .desktop-nav');if(!nav)return;const account=nav.querySelector('.student-account-menu');if(!account)return;[].slice.call(nav.querySelectorAll(':scope > a')).forEach(a=>a.remove());[['Home',routes.home],['Learn',routes.learn],['Practice',routes.practice],['Weak Areas',routes.weak],['Mastery',routes.mastery],['My Plan',routes.plan],['Exams',routes.exams],['Calculators',routes.calculators],['Progress',routes.progress],['Pathways',routes.pathways]].forEach(s=>nav.insertBefore(makeA(s[0],s[1]),account));}
function ensureSubjects(){let stack=document.querySelector('.student-context-stack');if(!stack){stack=document.createElement('div');stack.className='student-context-stack';stack.setAttribute('aria-label','Subjects');const header=document.querySelector('.site-header');if(header)header.insertAdjacentElement('afterend',stack);}stack.querySelectorAll('.programme-context-strip').forEach(x=>x.remove());let strip=stack.querySelector('.subject-quick-strip');if(!strip){strip=document.createElement('nav');strip.className='subject-quick-strip';strip.setAttribute('aria-label','Subject selector');stack.appendChild(strip);}strip.innerHTML='';subjects.forEach(s=>strip.appendChild(makeA(s.name,s.url)));const grid=document.querySelector('.home-subject-grid');if(grid){let cards=[].slice.call(grid.querySelectorAll('.home-subject-card'));if(!cards.length){subjects.forEach(s=>{const a=document.createElement('a');a.className='home-subject-card';a.href=s.url;a.innerHTML='<div><strong>'+s.name+'</strong></div><b>Open</b><small>See chapters and progress</small><span class="ux-open-chapters">Open chapters →</span>';grid.appendChild(a);});}else{cards.forEach(a=>{if(!a.querySelector('.ux-open-chapters')){const x=document.createElement('span');x.className='ux-open-chapters';x.textContent='Open chapters →';a.appendChild(x);}});}}}
function refineMastery(){const card=document.querySelector('.student-home-v2 .mastery-hero-card');if(!card)return;const h2=card.querySelector('.mastery-hero-top h2');const current=(h2?.textContent||'').trim();let currentIndex=levels.findIndex(x=>current.toLowerCase().includes(x.toLowerCase()));const ladder=card.querySelector('.mastery-ladder');if(ladder){ladder.innerHTML='';levels.forEach((level,i)=>{const d=document.createElement('div');d.className='mastery-step'+(currentIndex>=i?' reached':'')+(currentIndex===i?' current':'');d.innerHTML='<i></i><span>'+level+'</span>';ladder.appendChild(d);});}if(currentIndex<0){if(h2)h2.textContent='Mastery not yet established';const status=card.querySelector('.mastery-status-pill');if(status)status.textContent='Diagnostic needed';card.querySelector('.mastery-start')?.remove();}const momentum=document.querySelector('.home-progress-card');if(momentum&&/your journey starts here|starting point/i.test(momentum.textContent||'')){momentum.remove();document.querySelector('.home-priority-grid')?.classList.add('ux-single-priority');}}
function refineChapterLanguage(){document.querySelectorAll('.mastery-compare-labels span').forEach(el=>{const t=(el.textContent||'').trim();if(t==='Existing mastery')el.textContent='Your mastery';if(t==='Potential mastery')el.textContent='Next potential';});}
function makeSparkVisible(){const priority=document.querySelector('.home-priority-grid');if(!priority)return;let spark=document.querySelector('#daily-spark');if(spark){spark.classList.add('ux-spark-prominent');priority.insertAdjacentElement('afterend',spark);}else if(!document.querySelector('.ux-daily-spark-placeholder')){const s=document.createElement('section');s.className='card ux-daily-spark-placeholder';s.innerHTML='<p class="eyebrow">DAILY SPARK</p><h2>Your quick daily boost.</h2><p>Today’s Spark will appear here as soon as it is assigned.</p><a class="btn small" href="'+routes.practice+'">Do a quick practice</a>';priority.insertAdjacentElement('afterend',s);}}
function addPlanLauncher(){const home=document.querySelector('.student-home-v2');if(!home||document.querySelector('.ux-plan-launcher'))return;const anchor=document.querySelector('.home-section')||document.querySelector('.home-two-column');const box=document.createElement('section');box.className='ux-plan-launcher';box.innerHTML='<div><p class="eyebrow">EXAM PLAN</p><h2>Build a plan to exam day.</h2><p>Let ScoreMax organise your route from your evidence, or build the plan yourself.</p></div><div class="ux-plan-launcher-actions"><a class="btn small" href="'+routes.plan+'?mode=scoremax">Let ScoreMax build it</a><a class="btn alt small" href="'+routes.plan+'?mode=self">Build my own plan</a></div>';if(anchor)anchor.insertAdjacentElement('beforebegin',box);else home.appendChild(box);}
function addStudyPlanChoice(){if(!location.pathname.startsWith(pathOf(routes.plan)))return;const page=document.querySelector('.compact-page');if(!page||document.querySelector('.ux-plan-choice'))return;const heading=page.querySelector('.page-heading');if(!heading)return;const chooser=document.createElement('section');chooser.className='ux-plan-choice';chooser.innerHTML='<p class="eyebrow">CHOOSE HOW TO PLAN</p><h2>Your exam plan, your way.</h2><div class="ux-plan-choice-grid"><article class="ux-plan-choice-card"><h3>Let ScoreMax build it</h3><p>ScoreMax uses your target, exam date and learning evidence to organise priorities and adapt the future route.</p><button type="button" class="btn small" data-plan-mode="scoremax">Use ScoreMax plan</button></article><article class="ux-plan-choice-card"><h3>Build my own plan</h3><p>Set the exam, date, target score and starting coverage yourself. ScoreMax keeps the plan visible while you work.</p><button type="button" class="btn alt small" data-plan-mode="self">Build it myself</button><form method="post" action="'+routes.createPlan+'" class="ux-self-plan-form"><input type="hidden" name="_csrf_token" value="'+csrf+'"><input type="hidden" name="source" value="self"><label>Exam / target<input name="target_exam" required placeholder="e.g. FSc Part 1 Biology"></label><label>Exam date<input type="date" name="target_date" required></label><label>Target score %<input type="number" min="0" max="100" step="0.1" name="target_percentage"></label><label>Current syllabus coverage %<input type="number" min="0" max="100" step="1" name="starting_coverage"></label><button class="btn" type="submit">Create my plan</button></form></article></div>';heading.insertAdjacentElement('afterend',chooser);const selfForm=chooser.querySelector('.ux-self-plan-form');chooser.querySelector('[data-plan-mode="self"]')?.addEventListener('click',()=>selfForm.classList.toggle('is-open'));chooser.querySelector('[data-plan-mode="scoremax"]')?.addEventListener('click',()=>{document.querySelector('.pathway-grid')?.scrollIntoView({behavior:'smooth',block:'start'});});const mode=new URLSearchParams(location.search).get('mode');if(mode==='self')selfForm.classList.add('is-open');if(mode==='scoremax')setTimeout(()=>document.querySelector('.pathway-grid')?.scrollIntoView({behavior:'smooth',block:'start'}),100);}
function run(){refineTopNav();ensureSubjects();refineMastery();refineChapterLanguage();makeSparkVisible();addPlanLauncher();addStudyPlanChoice();}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();
})();</script>
'''
    return markup.replace("__SUBJECTS__", json.dumps(subject_data, separators=(",", ":"))).replace("__ROUTES__", json.dumps(routes, separators=(",", ":"))).replace("__CSRF__", json.dumps(csrf))


def _landing_calculator_markup() -> str:
    return r'''
<section class="ux-inline-calculator" aria-labelledby="publicCalculatorTitle"><div class="ux-inline-calculator-inner"><div class="ux-inline-calculator-head"><div><p class="ux-kicker">ADMISSION CALCULATORS</p><h2 id="publicCalculatorTitle">Calculate your aggregate. Know the score you need.</h2><p>Punjab medical: 10% Matric · 40% FSc · 50% MDCAT.</p></div></div><div class="ux-inline-calc-grid"><label>Matric obtained<input id="pubSscO" type="number" min="0" step="0.01"></label><label>Matric total<input id="pubSscT" type="number" min="1" step="0.01"></label><label>FSc obtained<input id="pubFscO" type="number" min="0" step="0.01"></label><label>FSc total<input id="pubFscT" type="number" min="1" step="0.01"></label><label>MDCAT obtained<input id="pubMdO" type="number" min="0" step="0.01"></label><label>MDCAT total<input id="pubMdT" type="number" min="1" step="0.01"></label><div class="ux-inline-calc-result"><span>Your aggregate</span><strong id="pubAgg">—</strong></div><label>Target aggregate %<input id="pubTarget" type="number" min="0" max="100" step="0.0001"></label><label>Target MDCAT total<input id="pubTargetTotal" type="number" min="1" step="1"></label><div class="ux-inline-calc-result secondary"><span>MDCAT score needed</span><strong id="pubNeed">—</strong></div></div></div></section>
<script id="ux-public-calculator-script">(function(){var q=function(id){return document.getElementById(id)},n=function(id){var v=parseFloat(q(id)&&q(id).value);return Number.isFinite(v)?v:null},ok=function(o,t){return o!==null&&t!==null&&t>0&&o>=0&&o<=t};function calc(){var so=n('pubSscO'),st=n('pubSscT'),fo=n('pubFscO'),ft=n('pubFscT'),mo=n('pubMdO'),mt=n('pubMdT');var s=ok(so,st)?so/st*10:null,f=ok(fo,ft)?fo/ft*40:null,m=ok(mo,mt)?mo/mt*50:null;q('pubAgg').textContent=(s!==null&&f!==null&&m!==null)?(s+f+m).toFixed(4)+'%':'—';var tar=n('pubTarget'),tt=n('pubTargetTotal');if(s!==null&&f!==null&&tar!==null&&tt!==null&&tt>0){var need=(tar-s-f)/50*tt;q('pubNeed').textContent=need<=0?'0 / '+Math.round(tt):need>tt?'Above maximum':Math.ceil(need)+' / '+Math.round(tt);}else q('pubNeed').textContent='—';}['pubSscO','pubSscT','pubFscO','pubFscT','pubMdO','pubMdT','pubTarget','pubTargetTotal'].forEach(function(id){q(id)&&q(id).addEventListener('input',calc);});})();</script>
'''


def _install_staging_page_guards(app) -> None:
    if getattr(app, "_ux_staging_page_guards_installed", False):
        return
    stable_secret = os.environ.get("SCOREMAX_STAGING_SESSION_SECRET", "").strip()
    if not stable_secret:
        raise RuntimeError("UX_STAGING_SESSION_SECRET_MISSING")
    app.secret_key = stable_secret
    app.config["SECRET_KEY"] = stable_secret

    @app.before_request
    def _ux_staging_student_defaults():
        _normalise_student_profile()
        return None

    @app.after_request
    def _ux_staging_final_render_guards(response):
        if not response.is_sequence or "text/html" not in (response.content_type or "").lower():
            return response
        html = response.get_data(as_text=True)
        endpoint = request.endpoint or ""
        is_student = session.get("role") == "student" and bool(session.get("user_id"))
        if is_student:
            for old, new in (("Level 1 Access", "Silver Access"), ("Level 2 Access", "Gold Access"), ("Level 3 Access", "Platinum Access"), ("Full Access", "Platinum Access")):
                html = html.replace(old, new)
            _, subjects = _normalise_student_profile()
            if "ux-student-refinement" not in html:
                injection = _student_refinement_markup(subjects) + _legacy_tour_guard()
                html = html.replace("</body>", injection + "</body>", 1) if "</body>" in html else html + injection
        if endpoint == "index" and "ux-inline-calculator" not in html:
            hero_marker = '<section class="ux-hero"'
            if hero_marker in html:
                shared_styles = _student_refinement_markup([]).split('<script id="ux-student-navigation-refinement">', 1)[0]
                html = html.replace(hero_marker, shared_styles + _landing_calculator_markup() + hero_marker, 1)
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
        values = {"programme": programme, "full_name": _clean(request.form.get("full_name"), 120), "email": _clean(request.form.get("email"), 180), "mobile": _clean(request.form.get("mobile"), 60), "role": _clean(request.form.get("role"), 30) or "Student", "school": _clean(request.form.get("school"), 180), "city": _clean(request.form.get("city"), 120), "note": _clean(request.form.get("note"), 1000)}
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
        values = {"nominator_name": _clean(request.form.get("nominator_name"), 120), "email": _clean(request.form.get("email"), 180), "role": _clean(request.form.get("role"), 30) or "Student", "school_name": _clean(request.form.get("school_name"), 180), "city": _clean(request.form.get("city"), 120), "relationship": _clean(request.form.get("relationship"), 180), "reason": _clean(request.form.get("reason"), 1200)}
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
