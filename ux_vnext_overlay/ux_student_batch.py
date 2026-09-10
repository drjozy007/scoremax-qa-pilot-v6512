from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from flask import render_template, request, session, url_for
from werkzeug.security import generate_password_hash

TEST_STUDENT_EMAIL='ux-premed-student@scoremax.test'
TEST_STUDENT_ID='STU-900001'
TEST_STUDENT_USERNAME='ux-premed-student'

FSC1_PUNJAB_CHAPTERS={
    'biology':['Biodiversity and Classification','Bacteria and Viruses','Cells and Subcellular Organelles','Molecular Biology','Enzymes','Bioenergetics','Structural and Computational Biology','Plant Physiology','Human Digestive System','Human Respiratory System','Human Circulatory System','Human Skeletal and Muscular Systems'],
    'chemistry':['Periodic Table and Periodic Properties','Atomic Structure','Chemical Bonding','Stoichiometry','States and Phases of Matter','Chemical Energetics','Reaction Kinetics','Chemical Equilibrium','Acid-Base Chemistry','Electrochemistry','Hydrocarbons','Nitrogen and Sulfur','Halogens','Atmosphere','Basic Separation Techniques','Lab Safety and Practical Skills'],
    'physics':['Measurements','Force and Motion','Circular and Rotational Motion','Work, Energy and Power','Solids and Fluid Dynamics','Heat and Thermodynamics','Waves and Vibrations','Physical Optics and Gravitational Waves','Electrostatics and Current Electricity','Electromagnetism','Special Theory of Relativity','Nuclear and Particle Physics'],
}


def _db_path() -> Path:
    return Path(os.environ.get('SCOREMAX_DB','/tmp/scoremax-ux-vnext/state/scoremax.db'))


def _connect() -> sqlite3.Connection:
    conn=sqlite3.connect(_db_path()); conn.row_factory=sqlite3.Row; conn.execute('PRAGMA busy_timeout=5000'); return conn


def _is_fsc1(level: str) -> bool:
    value=(level or '').strip().casefold(); return 'fsc' in value and ('part 1' in value or 'year 1' in value or value in {'fsc 1','fsc1'})


def _catalogue_for_student(conn: sqlite3.Connection, student_id: int, subject: str) -> list[str]:
    row=conn.execute("SELECT COALESCE(province,'') province,COALESCE(academic_level,'') academic_level FROM users WHERE id=?",(student_id,)).fetchone()
    if row and _is_fsc1(row['academic_level']) and (not (row['province'] or '').strip() or (row['province'] or '').strip().casefold()=='punjab'):
        governed=FSC1_PUNJAB_CHAPTERS.get((subject or '').strip().casefold())
        if governed: return list(governed)
    return [r['chapter'] for r in conn.execute("SELECT chapter,MIN(id) first_id FROM questions WHERE lower(subject)=lower(?) AND COALESCE(chapter,'')<>'' GROUP BY chapter ORDER BY first_id",(subject,)).fetchall()]


def _ensure_fixed_test_student() -> None:
    password=os.environ.get('SCOREMAX_STAGING_TEST_STUDENT_PASSWORD','').strip()
    if not password: return
    conn=_connect()
    try:
        row=conn.execute("SELECT id FROM users WHERE lower(COALESCE(email,''))=?",(TEST_STUDENT_EMAIL,)).fetchone(); password_hash=generate_password_hash(password)
        if row:
            conn.execute("""UPDATE users SET system_user_id=?,username=?,full_name=?,password_hash=?,role='student',province='Punjab',board='Punjab Board',academic_level='FSc Part 1',subjects='Biology,Chemistry,Physics',account_status='active',active_programme='FSc Part 1' WHERE id=?""",(TEST_STUDENT_ID,TEST_STUDENT_USERNAME,'ScoreMax UX Pre-Medical Student',password_hash,row['id']))
        else:
            conn.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,province,board,academic_level,subjects,account_status,active_programme,login_provider) VALUES(?,'student',?,?,?,?,?,?,?,'Biology,Chemistry,Physics','active','FSc Part 1','password')""",(TEST_STUDENT_ID,'ScoreMax UX Pre-Medical Student',TEST_STUDENT_EMAIL,TEST_STUDENT_USERNAME,password_hash,'Punjab','Punjab Board','FSc Part 1'))
        conn.commit()
    finally: conn.close()


def _subjects_for_student(conn, student_id: int) -> list[str]:
    row=conn.execute("SELECT COALESCE(subjects,'') subjects FROM users WHERE id=?",(student_id,)).fetchone(); subjects=[x.strip() for x in ((row['subjects'] if row else '') or '').split(',') if x.strip()]
    return subjects or ['Biology','Chemistry','Physics']


def _subject_snapshot(conn, student_id: int, subject: str) -> dict:
    chapters=_catalogue_for_student(conn,student_id,subject)
    answered=conn.execute("SELECT COUNT(*) n,COALESCE(AVG(CASE WHEN aa.is_correct=1 THEN 100.0 ELSE 0 END),0) acc FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_db_id WHERE a.student_id=? AND lower(q.subject)=lower(?)",(student_id,subject)).fetchone()
    started=conn.execute("SELECT COUNT(DISTINCT q.chapter) n FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_db_id WHERE a.student_id=? AND lower(q.subject)=lower(?) AND COALESCE(q.chapter,'')<>''",(student_id,subject)).fetchone(); started_count=min(int(started['n'] or 0),len(chapters)) if chapters else 0
    return {'chapter_count':len(chapters),'started_chapters':started_count,'answered':int(answered['n'] or 0),'avg_accuracy':round(float(answered['acc'] or 0)),'progress_pct':round((started_count/len(chapters))*100) if chapters else 0}


def _chapter_snapshots(conn, student_id: int, subject: str) -> list[dict]:
    import app as runtime
    chapters=_catalogue_for_student(conn,student_id,subject); out=[]
    for idx,chapter in enumerate(chapters,1):
        ans=conn.execute("SELECT COUNT(*) n,COALESCE(AVG(CASE WHEN aa.is_correct=1 THEN 100.0 ELSE 0 END),0) acc FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_db_id WHERE a.student_id=? AND lower(q.subject)=lower(?) AND lower(COALESCE(q.chapter,''))=lower(?)",(student_id,subject,chapter)).fetchone(); answered=int(ans['n'] or 0); acc=round(float(ans['acc'] or 0))
        mastery=runtime.chapter_mastery_opportunity(conn,student_id,subject,chapter); total=int(mastery.get('production_questions') or 0); available=total>0
        evidence='No evidence' if answered==0 else runtime.evidence_strength(answered); performance='No practice evidence' if answered==0 else runtime.performance_status(acc,answered)
        if mastery.get('existing_status')=='Verification Due': next_action,next_reason='Reconfirm mastery','Your previous mastery needs fresh independent evidence.'
        elif answered==0: next_action,next_reason='Find your starting point','Start with practice, then prove what you can do independently.'
        elif answered<3: next_action,next_reason='Build more evidence','A few more answers will make the recommendation more reliable.'
        elif acc<60: next_action,next_reason='Strengthen this chapter','Your recent practice shows this chapter is costing you marks.'
        elif not mastery.get('has_formal_mastery'): next_action,next_reason='Prove your mastery','Practice is going well; formal mastery still needs independent evidence.'
        elif int(mastery.get('opportunity_pct') or 0)>0: next_action,next_reason=f"Build toward {mastery.get('potential_level') or 'the next stage'}",'Your current evidence can support a higher verified chapter stage.'
        else: next_action,next_reason='Keep it strong','Maintain this chapter with spaced practice and reconfirmation.'
        out.append({'number':idx,'name':chapter,'answered':answered,'accuracy':acc,'mastery_level':mastery.get('existing_level') or 'Not verified','mastery':mastery,'question_count':total,'available':available,'evidence_strength':evidence,'performance_status':performance,'next_action':next_action,'next_reason':next_reason,'url':url_for('chapter_page',subject=subject,chapter=chapter) if available else ''})
    return out


def _learn_context(conn, student_id: int):
    subjects=[]
    for name in _subjects_for_student(conn,student_id):
        snap=_subject_snapshot(conn,student_id,name); snap.update({'name':name,'url':url_for('subject_detail',subject=name)}); subjects.append(snap)
    future=[{'name':'MDCAT','badge':'Route','copy':'Medical admission preparation alongside your FSc journey.','url':url_for('ux_student_learn')+'#mdcat-route'},{'name':'Logical Reasoning','badge':'MDCAT','copy':'Reasoning practice for your MDCAT route.','url':url_for('ux_student_learn')+'#mdcat-route'},{'name':'English','badge':'MDCAT','copy':'English preparation for your MDCAT route.','url':url_for('ux_student_learn')+'#mdcat-route'}]
    return subjects,future


def _progress_context(conn, student_id: int):
    attempts=conn.execute("SELECT COUNT(*) n,COALESCE(AVG(score),0) avg FROM attempts WHERE student_id=?",(student_id,)).fetchone(); mastery=conn.execute("SELECT COUNT(*) n FROM mastery_records WHERE student_id=?",(student_id,)).fetchone(); subjects=[]
    for name in _subjects_for_student(conn,student_id): snap=_subject_snapshot(conn,student_id,name); snap.update({'name':name,'url':url_for('subject_detail',subject=name)}); subjects.append(snap)
    actions=[{'title':'Open your subjects','copy':'Choose a chapter and continue from your current evidence.','url':url_for('ux_student_learn')},{'title':'Review weak areas','copy':'See where marks are being lost.','url':url_for('weak_areas_page')},{'title':'Open your exam plan','copy':'Let ScoreMax adapt your route to exam day.','url':url_for('study_plan_page')}]
    avg=round(float(attempts['avg'] or 0)); tests=int(attempts['n'] or 0); return {'avg_score':avg,'tests_completed':tests,'mastery_count':int(mastery['n'] or 0),'health':min(100,round((avg*.7)+(min(tests,10)*3)) if tests else 0),'subjects':subjects,'actions':actions}


def _student_shell_patch() -> str:
    learn_url=json.dumps(url_for('ux_student_learn')); plan_url=json.dumps(url_for('study_plan_page')); access_url=json.dumps(url_for('access_account'))
    return r'''<style id="ux-batch-student-style">
.ux-home-overall{margin-top:14px;padding-top:12px;border-top:1px solid #e6eeee}.ux-home-overall-head{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.ux-home-overall-head span{font-size:.6rem;font-weight:900;letter-spacing:.055em;color:#657383}.ux-home-overall-head strong{font-size:.78rem;color:#236765}.ux-home-overall-track{height:8px;margin-top:6px;border-radius:999px;background:#e9efee;overflow:hidden}.ux-home-overall-track i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#3FA6A3,#2F7F7D)}.ux-home-overall.unverified .ux-home-overall-track{background:#f1dede}.ux-home-overall.unverified .ux-home-overall-track i{background:#C95858}.ux-home-overall-labels{display:grid;grid-template-columns:repeat(6,1fr);gap:2px;margin-top:4px;color:#73807d;font-size:.47rem;font-weight:650}.ux-home-overall-labels span{text-align:center}.ux-home-overall-labels span:first-child{text-align:left}.ux-home-overall-labels span:last-child{text-align:right}
.ux-start-merged{grid-template-columns:1fr!important}.ux-start-journey{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:13px;padding-top:10px;border-top:1px solid rgba(0,0,0,.08)}.ux-start-journey span{padding:5px 8px;border-radius:999px;background:#f5f8f8;color:#53625f;font-size:.63rem;font-weight:800}.ux-start-journey span:first-child{background:#E8F6F5;color:#236765}.ux-start-journey i{font-style:normal;color:#9aa5a2}
.ux-home-exam-plan{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(250px,.7fr);gap:18px;align-items:center;margin:15px 0;padding:20px 22px;border:1px solid #bfe1df;border-radius:19px;background:linear-gradient(135deg,#eef9f8,#fff 64%);box-shadow:0 10px 28px rgba(47,127,125,.065)}.ux-home-exam-plan h2{margin:.1rem 0 .35rem;color:#236765;font-size:clamp(1.25rem,2vw,1.65rem)}.ux-home-exam-plan p{margin:0;color:#657383}.ux-home-exam-points{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px}.ux-home-exam-points div{padding:8px;border:1px solid #dcebea;border-radius:10px;background:#fff}.ux-home-exam-points strong,.ux-home-exam-points span{display:block}.ux-home-exam-points strong{font-size:.68rem}.ux-home-exam-points span{font-size:.56rem;color:#71807c;margin-top:2px}.ux-home-exam-actions{display:grid;gap:7px}.ux-home-exam-actions a{text-align:center;text-decoration:none}
.ux-home-plans{margin:16px 0}.ux-home-plans-head{display:flex;justify-content:space-between;gap:12px;align-items:end;margin-bottom:8px}.ux-home-plans-head h2{margin:.1rem 0 0;color:#3FA6A3;font-size:1.18rem}.ux-home-plans-head a{color:#2F7F7D;font-size:.7rem;font-weight:850}.ux-home-plan-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.ux-home-plan{position:relative;padding:12px 13px;border:1px solid #dfe7e7;border-radius:13px;background:#fff;text-decoration:none;color:inherit;overflow:hidden}.ux-home-plan:before{content:'';position:absolute;inset:0 0 auto;height:5px}.ux-home-plan.silver:before{background:linear-gradient(90deg,#89949e,#e8edf0)}.ux-home-plan.gold:before{background:linear-gradient(90deg,#b88725,#efd46d)}.ux-home-plan.platinum:before{background:linear-gradient(90deg,#8993a0,#edf0f2,#7d8793)}.ux-home-plan strong,.ux-home-plan span,.ux-home-plan b{display:block}.ux-home-plan strong{font-size:.9rem}.ux-home-plan span{margin-top:4px;color:#71807c;font-size:.63rem;line-height:1.3}.ux-home-plan b{margin-top:6px;color:#2F7F7D;font-size:.63rem}
.ux-science-corner{margin:12px 0 0;padding:14px 16px;border-radius:15px;background:linear-gradient(135deg,#102f35,#214d51);color:#fff}.ux-science-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.ux-science-corner .eyebrow{color:#9fe0dc;margin:0}.ux-science-corner h3{margin:.15rem 0 0;font-size:1rem}.ux-science-corner button{padding:7px 10px;border:1px solid rgba(255,255,255,.22);border-radius:999px;background:rgba(255,255,255,.1);color:#fff;font-size:.67rem;font-weight:900;cursor:pointer}.ux-science-fact{display:none;margin:9px 0 0;padding-top:9px;border-top:1px solid rgba(255,255,255,.14);color:#e3eeee;font-size:.78rem;line-height:1.42}.ux-science-fact.show{display:block}.ux-science-tag{display:none;margin-top:7px;padding:3px 7px;border-radius:999px;background:rgba(255,255,255,.1);font-size:.57rem;font-weight:850;color:#bfe7e4}.ux-science-tag.show{display:inline-block}
.ux-hide-verification{display:none!important}
@media(max-width:900px){.ux-home-exam-plan{grid-template-columns:1fr}.ux-home-exam-points{grid-template-columns:repeat(3,1fr)}}@media(max-width:640px){.ux-home-plan-grid,.ux-home-exam-points{grid-template-columns:1fr}.ux-science-head{align-items:flex-start;flex-direction:column}.ux-home-overall-labels{font-size:.42rem}}
</style><script id="ux-batch-student-script">(function(){const LEARN=__LEARN__,PLAN=__PLAN__,ACCESS=__ACCESS__;const stages=['Foundation','Exam Ready','Advanced','Distinction','Expert','Elite'];
function currentStage(){const s=document.querySelector('#uxStudentMasteryStrip .ux-mastery-current strong');if(s)return (s.textContent||'').trim();const h=document.querySelector('.mastery-hero-card h2');const t=(h&&h.textContent||'').trim();return stages.find(x=>t.toLowerCase().includes(x.toLowerCase()))||'Not verified';}
function addPremedTabs(){const strip=document.querySelector('.student-context-stack .subject-quick-strip');if(!strip)return;const names=[...strip.querySelectorAll('a')].map(a=>(a.textContent||'').trim().toLowerCase());if(!['biology','chemistry','physics'].every(x=>names.includes(x)))return;[['MDCAT','mdcat-route'],['Logical Reasoning','mdcat-route'],['English','mdcat-route']].forEach(([name,hash])=>{if([...strip.querySelectorAll('a')].some(a=>(a.textContent||'').trim()===name))return;const a=document.createElement('a');a.textContent=name;a.href=LEARN+'#'+hash;strip.appendChild(a);});}
function addOverall(){const greet=document.querySelector('.home-greeting-block');if(!greet||greet.querySelector('.ux-home-overall'))return;const stage=currentStage(),idx=stages.indexOf(stage),pct=idx<0?0:Math.round((idx+1)/6*100);const box=document.createElement('div');box.className='ux-home-overall'+(idx<0?' unverified':'');box.innerHTML='<div class="ux-home-overall-head"><span>OVERALL MASTERY</span><strong>'+(idx<0?'Not verified':stage)+'</strong></div><div class="ux-home-overall-track"><i style="width:'+pct+'%"></i></div><div class="ux-home-overall-labels">'+stages.map(x=>'<span>'+x+'</span>').join('')+'</div>';greet.appendChild(box);}
function mergeStart(){const grid=document.querySelector('.home-priority-grid'),focus=grid&&grid.querySelector('.today-focus-card'),momentum=grid&&grid.querySelector('.home-progress-card');if(!grid||!focus||!momentum)return;if(!/find your starting point/i.test(focus.textContent||'')||!/your journey starts here|starting point/i.test(momentum.textContent||''))return;if(!focus.querySelector('.ux-start-journey')){const j=document.createElement('div');j.className='ux-start-journey';j.innerHTML='<span>Starting Point</span><i>→</i><span>Build Mastery</span><i>→</i><span>Exam Ready</span>';focus.appendChild(j);}momentum.remove();grid.classList.add('ux-start-merged');}
function upgradePlan(){const home=document.querySelector('.student-home-v2');if(!home)return;let old=document.querySelector('.ux-plan-launcher');if(old)old.remove();if(document.querySelector('.ux-home-exam-plan'))return;const anchor=document.querySelector('.home-section')||document.querySelector('.home-two-column');if(!anchor)return;const box=document.createElement('section');box.className='ux-home-exam-plan';box.innerHTML='<div><p class="eyebrow">EXAM PLAN</p><h2>Your route to exam day deserves its own space.</h2><p>Set your target and exam date, then let ScoreMax organise priorities as your evidence grows.</p><div class="ux-home-exam-points"><div><strong>Target</strong><span>Keep the score you want visible.</span></div><div><strong>Priorities</strong><span>Focus on what matters most.</span></div><div><strong>Next action</strong><span>Know what to do when you return.</span></div></div></div><div class="ux-home-exam-actions"><a class="btn" href="'+PLAN+'?mode=scoremax">Let ScoreMax build it</a><a class="btn alt" href="'+PLAN+'?mode=self">Build my own plan</a></div>';anchor.insertAdjacentElement('beforebegin',box);}
function addPlans(){const home=document.querySelector('.student-home-v2');if(!home||document.querySelector('.ux-home-plans'))return;const anchor=document.querySelector('.home-two-column');if(!anchor)return;const s=document.createElement('section');s.className='ux-home-plans';s.innerHTML='<div class="ux-home-plans-head"><div><p class="eyebrow">YOUR SCOREMAX ACCESS</p><h2>Silver, Gold and Platinum.</h2></div><a href="'+ACCESS+'">Compare access →</a></div><div class="ux-home-plan-grid"><a class="ux-home-plan silver" href="'+ACCESS+'"><strong>Silver</strong><span>Build strong foundations and structured progress.</span><b>Explore Silver →</b></a><a class="ux-home-plan gold" href="'+ACCESS+'"><strong>Gold</strong><span>Go deeper with broader mastery and exam preparation.</span><b>Explore Gold →</b></a><a class="ux-home-plan platinum" href="'+ACCESS+'"><strong>Platinum</strong><span>Use the fullest ScoreMax learning and mastery journey.</span><b>Explore Platinum →</b></a></div>';anchor.insertAdjacentElement('beforebegin',s);}
function addScience(){const home=document.querySelector('.student-home-v2');if(!home||document.querySelector('#uxScienceCorner'))return;const anchor=document.querySelector('.home-two-column')||document.querySelector('.home-history');if(!anchor)return;const box=document.createElement('section');box.id='uxScienceCorner';box.className='ux-science-corner';box.innerHTML='<div class="ux-science-head"><div><p class="eyebrow">SCIENCE CORNER</p><h3>Discover something surprising.</h3></div><button type="button">Reveal a science fact</button></div><p class="ux-science-fact"></p><span class="ux-science-tag"></span>';anchor.insertAdjacentElement('beforebegin',box);const btn=box.querySelector('button'),out=box.querySelector('.ux-science-fact'),tag=box.querySelector('.ux-science-tag');const pools={Foundation:[['Biology','Your lungs contain hundreds of millions of tiny air sacs, creating a very large surface for gas exchange.'],['Chemistry','Water dissolves many ionic and polar substances because its molecules have an uneven distribution of electrical charge.'],['Physics','Light from the Sun takes a little over eight minutes to reach Earth.']],ExamReady:[['Biology','Red blood cells lose their nucleus during development, leaving more internal space for haemoglobin.'],['Chemistry','A catalyst lowers activation energy by providing a different reaction pathway without being consumed overall.'],['Physics','A satellite stays in orbit because gravity continuously bends its motion toward Earth.']],Advanced:[['Biology','Enzyme activity depends on molecular shape, temperature, pH, substrate concentration and the availability of active sites.'],['Chemistry','Dynamic equilibrium does not mean reactions stop; forward and reverse reactions continue at equal rates.'],['Physics','Interference patterns arise from superposition: amplitudes reinforce at some positions and cancel at others.']],Distinction:[['Biology','Antibody diversity comes partly from recombining a limited set of gene segments and then refining activated cells.'],['Chemistry','Entropy is linked to the number of microscopic arrangements consistent with a macroscopic state, not simply to everyday “disorder”.'],['Physics','Relativity keeps the measured speed of light invariant by allowing measured time intervals and lengths to depend on relative motion.']],Expert:[['Biology','The same signalling molecule can trigger different cellular responses because receptor networks and gene-regulatory states differ between cells.'],['Chemistry','Thermodynamic favourability and reaction rate are separate: a favourable reaction can still be extremely slow when its activation barrier is high.'],['Physics','Single particles can build an interference pattern over repeated trials, revealing the role of quantum probability amplitudes.']],Elite:[['Biology','Biological robustness often emerges from redundancy and feedback, allowing stable function despite perturbations.'],['Chemistry','Chemical potential provides a unified way to describe the direction of matter transfer, phase equilibrium and reaction equilibrium.'],['Physics','Symmetry and conservation are deeply connected; time-translation symmetry is associated with conservation of energy.']]};let i=0;btn.addEventListener('click',()=>{const stage=currentStage(),key=stage==='Exam Ready'?'ExamReady':(pools[stage]?stage:'Foundation'),p=pools[key],item=p[i++%p.length];out.textContent=item[1];out.classList.add('show');tag.textContent=item[0]+' · '+(stage==='Not verified'?'Foundation':stage);tag.classList.add('show');btn.textContent='Another fact';});}
function hideVerification(){document.querySelectorAll('h2').forEach(h=>{if((h.textContent||'').trim().toLowerCase()==='how verification works'){const s=h.closest('.card,section');if(s)s.classList.add('ux-hide-verification');}});}
function run(){addPremedTabs();addOverall();mergeStart();upgradePlan();addPlans();addScience();hideVerification();}
function boot(){run();[80,250,700,1400].forEach(t=>setTimeout(run,t));const o=new MutationObserver(run);o.observe(document.body,{childList:true,subtree:true});setTimeout(()=>o.disconnect(),4500);}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();})();</script>'''.replace('__LEARN__',learn_url).replace('__PLAN__',plan_url).replace('__ACCESS__',access_url)


def install_student_batch(app) -> None:
    if getattr(app,'_ux_student_batch_installed',False): return
    _ensure_fixed_test_student()

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
            subject=(request.view_args or {}).get('subject','').strip(); conn=_connect()
            try: chapters=_chapter_snapshots(conn,session['user_id'],subject); snap=_subject_snapshot(conn,session['user_id'],subject)
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
            patch=_student_shell_patch(); html=html.replace('</body>',patch+'</body>',1) if '</body>' in html else html+patch
        response.set_data(html); response.content_length=len(response.get_data()); return response

    app._ux_student_batch_installed=True
