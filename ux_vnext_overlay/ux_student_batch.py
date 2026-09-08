from __future__ import annotations

import json
import sqlite3
from pathlib import Path
import os

from flask import render_template, request, session, url_for


def _db_path() -> Path:
    return Path(os.environ.get("SCOREMAX_DB", "/tmp/scoremax-ux-vnext/state/scoremax.db"))


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _subjects_for_student(conn, student_id: int) -> list[str]:
    row = conn.execute("SELECT COALESCE(subjects,'') subjects FROM users WHERE id=?", (student_id,)).fetchone()
    subjects = [x.strip() for x in ((row['subjects'] if row else '') or '').split(',') if x.strip()]
    return subjects or ['Biology','Chemistry','Physics']


def _subject_snapshot(conn, student_id: int, subject: str) -> dict:
    chapters = [r['chapter'] for r in conn.execute("SELECT DISTINCT COALESCE(chapter,'') chapter FROM questions WHERE lower(subject)=lower(?) AND COALESCE(chapter,'')<>'' ORDER BY id", (subject,)).fetchall()]
    answered = conn.execute("SELECT COUNT(*) n,COALESCE(AVG(CASE WHEN aa.is_correct=1 THEN 100.0 ELSE 0 END),0) acc FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_db_id WHERE a.student_id=? AND lower(q.subject)=lower(?)", (student_id,subject)).fetchone()
    started = conn.execute("SELECT COUNT(DISTINCT q.chapter) n FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_db_id WHERE a.student_id=? AND lower(q.subject)=lower(?) AND COALESCE(q.chapter,'')<>''", (student_id,subject)).fetchone()
    return {'chapter_count':len(chapters),'started_chapters':int(started['n'] or 0),'answered':int(answered['n'] or 0),'avg_accuracy':round(float(answered['acc'] or 0)),'progress_pct':round((int(started['n'] or 0)/len(chapters))*100) if chapters else 0}


def _chapter_snapshots(conn, student_id: int, subject: str) -> list[dict]:
    rows=conn.execute("SELECT chapter,MIN(id) first_id FROM questions WHERE lower(subject)=lower(?) AND COALESCE(chapter,'')<>'' GROUP BY chapter ORDER BY first_id",(subject,)).fetchall()
    out=[]
    for idx,row in enumerate(rows,1):
        chapter=row['chapter']
        ans=conn.execute("SELECT COUNT(*) n,COALESCE(AVG(CASE WHEN aa.is_correct=1 THEN 100.0 ELSE 0 END),0) acc FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_db_id WHERE a.student_id=? AND lower(q.subject)=lower(?) AND q.chapter=?",(student_id,subject,chapter)).fetchone()
        total=conn.execute("SELECT COUNT(*) n FROM questions WHERE lower(subject)=lower(?) AND chapter=?",(subject,chapter)).fetchone()['n']
        answered=int(ans['n'] or 0); acc=round(float(ans['acc'] or 0))
        mastery=conn.execute("SELECT mastery_level FROM mastery_records WHERE student_id=? AND lower(subject)=lower(?) AND chapter=? ORDER BY id DESC LIMIT 1",(student_id,subject,chapter)).fetchone()
        progress=min(100,round((answered/max(int(total or 1),1))*100))
        out.append({'number':idx,'name':chapter,'answered':answered,'accuracy':acc,'progress_pct':progress,'mastery_level':mastery['mastery_level'] if mastery else ('Foundation' if answered else 'Not started'),'url':url_for('chapter_page',subject=subject,chapter=chapter)})
    return out


def _learn_context(conn, student_id: int):
    subjects=[]
    for name in _subjects_for_student(conn,student_id):
        snap=_subject_snapshot(conn,student_id,name); snap.update({'name':name,'url':url_for('subject_detail',subject=name)}); subjects.append(snap)
    future=[
      {'name':'MDCAT','badge':'Next route','copy':'Medical admission preparation alongside your FSc journey.','url':url_for('ux_register_interest',programme='MDCAT')},
      {'name':'Logical Reasoning','badge':'MDCAT','copy':'Reasoning practice for your future MDCAT preparation.','url':url_for('ux_register_interest',programme='MDCAT Logical Reasoning')},
      {'name':'English','badge':'MDCAT','copy':'English preparation remains visible even before access opens.','url':url_for('ux_register_interest',programme='MDCAT English')},
    ]
    return subjects,future


def _progress_context(conn, student_id: int):
    attempts=conn.execute("SELECT COUNT(*) n,COALESCE(AVG(score),0) avg FROM attempts WHERE student_id=?",(student_id,)).fetchone()
    mastery=conn.execute("SELECT COUNT(*) n FROM mastery_records WHERE student_id=?",(student_id,)).fetchone()
    subjects=[]
    for name in _subjects_for_student(conn,student_id):
        snap=_subject_snapshot(conn,student_id,name); snap.update({'name':name,'url':url_for('subject_detail',subject=name)}); subjects.append(snap)
    actions=[
      {'title':'Open your subjects','copy':'Choose a chapter and continue from your current evidence.','url':url_for('ux_student_learn')},
      {'title':'Review weak areas','copy':'See where marks are being lost.','url':url_for('weak_areas_page')},
      {'title':'Open your exam plan','copy':'Let ScoreMax adapt your route to exam day.','url':url_for('study_plan_page')},
    ]
    avg=round(float(attempts['avg'] or 0)); tests=int(attempts['n'] or 0)
    return {'avg_score':avg,'tests_completed':tests,'mastery_count':int(mastery['n'] or 0),'health':min(100,round((avg*.7)+(min(tests,10)*3)) if tests else 0),'subjects':subjects,'actions':actions}


def _science_corner_markup() -> str:
    return r'''<section class="ux-science-corner"><div><p class="eyebrow">SCIENCE CORNER</p><h3 id="uxScienceCornerTitle">A little science for today.</h3><p id="uxScienceCornerText"></p></div><span id="uxScienceCornerTag"></span></section><script id="ux-science-corner-script">(function(){const facts=[['Biology','Your body makes roughly two million new red blood cells every second.'],['Chemistry','A catalyst speeds up a reaction by lowering activation energy, but it is not used up by the reaction.'],['Physics','Sunlight takes about eight minutes to travel from the Sun to Earth.'],['Biology','DNA in one human cell is about two metres long if fully stretched out.'],['Chemistry','Diamond and graphite are both made only of carbon; their very different properties come from how the atoms are arranged.'],['Physics','Astronauts in orbit feel weightless because they and their spacecraft are continuously falling around Earth.'],['Science smile','Why can’t you trust an atom? Because it makes up everything.']];const d=new Date(),item=facts[(d.getFullYear()*372+d.getMonth()*31+d.getDate())%facts.length];document.getElementById('uxScienceCornerTag').textContent=item[0];document.getElementById('uxScienceCornerText').textContent=item[1];})();</script>'''


def _student_shell_patch() -> str:
    return r'''<style id="ux-batch-student-style">
.ux-science-corner{display:flex;justify-content:space-between;gap:18px;align-items:center;margin:12px 0 0;padding:15px 17px;border-radius:15px;background:linear-gradient(135deg,#102f35,#214d51);color:#fff}.ux-science-corner .eyebrow{color:#9fe0dc}.ux-science-corner h3{margin:.1rem 0 .25rem;font-size:1rem}.ux-science-corner p{margin:0;font-size:.8rem;line-height:1.45;color:#d7e8e7}.ux-science-corner>span{padding:6px 8px;border-radius:999px;background:rgba(255,255,255,.1);font-size:.63rem;font-weight:900;white-space:nowrap}
.mastery-hero-card{background:#fff!important;color:#172033!important;border-color:#dfe7e7!important}.mastery-hero-card .eyebrow{color:#2F7F7D!important}.mastery-hero-card>p{color:#657383!important}.mastery-status-pill{background:#E8F6F5!important;border-color:#b9e1df!important;color:#236765!important}.mastery-step{background:#f7f9f9!important;border-color:#e1e9e8!important;color:#7b8791!important}.mastery-step.reached{background:#edf8f7!important;color:#315d5b!important}.mastery-step.current{background:#DDF3F1!important;border-color:#7bc3bf!important;color:#163f3d!important}.mastery-step.current span:after{background:#3FA6A3!important;color:#fff!important}.mastery-step i{background:#bac8c7!important}.mastery-step.reached i,.mastery-step.current i{background:#3FA6A3!important}.mastery-hero-card .text-link{color:#2F7F7D!important}.mastery-next{background:#f3f7f7!important}.mastery-next span{color:#667b79!important}
.access-grid{order:1}.package-card-grid{order:2}.commercial-paywall>section:nth-of-type(2){order:2}.commercial-paywall>section:nth-of-type(3){order:1}.commercial-paywall{display:flex;flex-direction:column}.access-card{position:relative;overflow:hidden;min-height:245px!important;border-width:2px!important}.access-card:before{content:'';position:absolute;inset:0 0 auto;height:7px}.access-card:nth-child(1):before{background:#88949e}.access-card:nth-child(2):before{background:linear-gradient(90deg,#b9c2c8,#edf1f3)}.access-card:nth-child(3):before{background:linear-gradient(90deg,#c49a35,#f0d57b)}.access-card:nth-child(4):before{background:linear-gradient(90deg,#9ba4b0,#e5e8ec,#8b97a4)}.access-card.current{box-shadow:0 14px 34px rgba(47,127,125,.12)!important;border-color:#72beb9!important}.access-card h2{font-size:1.35rem!important}.package-card-grid{margin-top:4px!important}
.student-account-dropdown .ux-pathways-menu{display:block}
@media(max-width:700px){.ux-science-corner{align-items:flex-start;flex-direction:column}.ux-science-corner>span{align-self:flex-start}}
</style><script id="ux-batch-student-script">(function(){function run(){const nav=document.querySelector('.site-header .desktop-nav');if(nav){[...nav.querySelectorAll(':scope > a')].forEach(a=>{if(['Practice','Pathways'].includes((a.textContent||'').trim()))a.remove();});}const menu=document.querySelector('.student-account-dropdown');if(menu&&!menu.querySelector('.ux-pathways-menu')){const a=document.createElement('a');a.className='ux-pathways-menu';a.href='/student/pathways';a.textContent='Pathways';menu.insertBefore(a,menu.querySelector('a[href*="knowledge"]')||menu.firstElementChild?.nextSibling);}const spark=document.querySelector('#daily-spark,.home-daily-spark,.ux-daily-spark-placeholder');if(spark&&!document.querySelector('.ux-science-corner'))spark.insertAdjacentHTML('beforeend',__SCIENCE__);document.querySelectorAll('a').forEach(a=>{const t=(a.textContent||'').trim().toLowerCase();if(t.includes('recorded learning')){a.href='/register-interest?programme=Recorded%20Learning';}if(t.includes('science genius')){a.href='/register-interest?programme=Science%20Genius%20of%20the%20Year';}});const access=document.querySelector('.commercial-paywall');if(access){const sections=[...access.children];const coverage=sections.find(s=>(s.textContent||'').includes('SUBJECT COVERAGE'));const levels=sections.find(s=>(s.textContent||'').includes('ACCESS LEVEL'));if(coverage&&levels)access.insertBefore(levels,coverage);}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();})();</script>'''.replace('__SCIENCE__', json.dumps(_science_corner_markup()))


def install_student_batch(app) -> None:
    if getattr(app,'_ux_student_batch_installed',False): return

    @app.route('/student/learn-vnext',endpoint='ux_student_learn')
    def ux_student_learn():
        if session.get('role')!='student': return render_template('ux_student_learn.html',subjects=[],future_options=[],programme_label='MY STUDIES')
        conn=_connect()
        try: subjects,future=_learn_context(conn,session['user_id'])
        finally: conn.close()
        return render_template('ux_student_learn.html',subjects=subjects,future_options=future,programme_label='FSc PRE-MEDICAL')

    @app.before_request
    def _ux_batch_page_override():
        if session.get('role')!='student' or not session.get('user_id'): return None
        if request.endpoint=='subject_browser':
            conn=_connect()
            try: subjects,future=_learn_context(conn,session['user_id'])
            finally: conn.close()
            return render_template('ux_student_learn.html',subjects=subjects,future_options=future,programme_label='FSc PRE-MEDICAL')
        if request.endpoint=='subject_detail':
            subject=(request.view_args or {}).get('subject','').strip()
            conn=_connect()
            try:
                chapters=_chapter_snapshots(conn,session['user_id'],subject)
                snap=_subject_snapshot(conn,session['user_id'],subject)
            finally: conn.close()
            return render_template('ux_subject_chapters.html',subject=subject,chapters=chapters,chapter_count=snap['chapter_count'],started_chapters=snap['started_chapters'],answered=snap['answered'],avg_accuracy=snap['avg_accuracy'],learn_url=url_for('ux_student_learn'))
        if request.endpoint=='student_analytics_page':
            conn=_connect()
            try: ctx=_progress_context(conn,session['user_id'])
            finally: conn.close()
            return render_template('ux_progress.html',**ctx)
        return None

    @app.after_request
    def _ux_batch_render_patch(response):
        if not response.is_sequence or 'text/html' not in (response.content_type or '').lower(): return response
        if session.get('role')!='student' or not session.get('user_id'): return response
        html=response.get_data(as_text=True)
        if 'ux-batch-student-style' not in html:
            patch=_student_shell_patch()
            html=html.replace('</body>',patch+'</body>',1) if '</body>' in html else html+patch
        response.set_data(html); response.content_length=len(response.get_data()); return response

    app._ux_student_batch_installed=True
