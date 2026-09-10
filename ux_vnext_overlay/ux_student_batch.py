from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from flask import render_template, render_template_string, request, session, url_for
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
            conn.execute('''UPDATE users SET system_user_id=?,username=?,full_name=?,password_hash=?,role='student',province='Punjab',board='Punjab Board',academic_level='FSc Part 1',subjects='Biology,Chemistry,Physics',account_status='active',active_programme='FSc Part 1' WHERE id=?''',(TEST_STUDENT_ID,TEST_STUDENT_USERNAME,'ScoreMax UX Pre-Medical Student',password_hash,row['id']))
        else:
            conn.execute('''INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,province,board,academic_level,subjects,account_status,active_programme,login_provider) VALUES(?,'student',?,?,?,?,?,?,?,'Biology,Chemistry,Physics','active','FSc Part 1','password')''',(TEST_STUDENT_ID,'ScoreMax UX Pre-Medical Student',TEST_STUDENT_EMAIL,TEST_STUDENT_USERNAME,password_hash,'Punjab','Punjab Board','FSc Part 1'))
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
    future=[
      {'name':'MDCAT','badge':'Route','copy':'Medical admission preparation alongside your FSc journey.','url':url_for('ux_student_learn')+'#mdcat-route'},
      {'name':'Logical Reasoning','badge':'MDCAT','copy':'Reasoning practice for your MDCAT route.','url':url_for('ux_student_learn')+'#mdcat-route'},
      {'name':'English','badge':'MDCAT','copy':'English preparation for your MDCAT route.','url':url_for('ux_student_learn')+'#mdcat-route'},
    ]
    return subjects,future


def _progress_context(conn, student_id: int):
    attempts=conn.execute("SELECT COUNT(*) n,COALESCE(AVG(score),0) avg FROM attempts WHERE student_id=?",(student_id,)).fetchone(); mastery=conn.execute("SELECT COUNT(*) n FROM mastery_records WHERE student_id=?",(student_id,)).fetchone(); subjects=[]
    for name in _subjects_for_student(conn,student_id): snap=_subject_snapshot(conn,student_id,name); snap.update({'name':name,'url':url_for('subject_detail',subject=name)}); subjects.append(snap)
    actions=[{'title':'Open your subjects','copy':'Choose a chapter and continue from your current evidence.','url':url_for('ux_student_learn')},{'title':'Review weak areas','copy':'See where marks are being lost.','url':url_for('weak_areas_page')},{'title':'Open your exam plan','copy':'Let ScoreMax adapt your route to exam day.','url':url_for('study_plan_page')}]
    avg=round(float(attempts['avg'] or 0)); tests=int(attempts['n'] or 0); return {'avg_score':avg,'tests_completed':tests,'mastery_count':int(mastery['n'] or 0),'health':min(100,round((avg*.7)+(min(tests,10)*3)) if tests else 0),'subjects':subjects,'actions':actions}


def _pathway_context(conn, student_id: int) -> dict:
    row=conn.execute("SELECT COALESCE(academic_level,'') academic_level,COALESCE(subjects,'') subjects,COALESCE(active_programme,'') active_programme FROM users WHERE id=?",(student_id,)).fetchone()
    level=(row['academic_level'] if row else '') or 'FSc'; subjects=[x.strip() for x in ((row['subjects'] if row else '') or '').split(',') if x.strip()]
    lower={x.casefold() for x in subjects}; premed={'biology','chemistry','physics'}.issubset(lower)
    if premed:
        label='FSc Pre-Medical'
        routes=[
          ('Medicine & Dentistry','MBBS · BDS','Direct clinical-care routes for students who want to diagnose, treat and work closely with patients.','Patient care · high responsibility · competitive entry'),
          ('Pharmacy & Rehabilitation','Pharm-D · DPT','Routes combining applied science with medicines, rehabilitation, movement and patient outcomes.','Applied health science · patient contact'),
          ('Allied Health','Nursing · Medical Laboratory Sciences · Medical Imaging · Nutrition','High-value healthcare careers across hospitals, diagnostics, imaging, laboratories and community health.','Clinical teams · diagnostics · practical skills'),
          ('Life Sciences & Research','Biotechnology · Biochemistry · Genetics · Microbiology · Molecular Biology','For students drawn to discovery, laboratories, disease mechanisms, biotechnology and research.','Research · laboratories · postgraduate pathways'),
          ('Psychology & Public Health','Psychology · Public Health · Behavioural Science','Routes focused on people, behaviour, prevention, wellbeing and population-level health.','People · prevention · community impact'),
          ('Science + Technology','Bioinformatics · Health Data · selected Computing routes','Where university eligibility permits, combine biology with data, coding and rapidly growing health-technology fields.','Biology + data · emerging careers'),
        ]
    else:
        label=(level or 'FSc').replace('Part 1','').strip() or 'FSc'
        routes=[
          ('Engineering','Electrical · Mechanical · Civil · Chemical and more','Turn mathematics and physics into design, infrastructure, energy and technology careers.','Design · problem-solving · applied science'),
          ('Computing & AI','Computer Science · Software Engineering · AI · Data Science','Build technical careers around software, data, intelligent systems and digital products.','Logic · coding · fast-changing fields'),
          ('Physical Sciences','Physics · Chemistry · Mathematics','A strong route into research, teaching, industry, analytics and postgraduate specialisation.','Theory · analysis · research'),
          ('Business & Technology','Business Analytics · FinTech · Management','Combine quantitative ability with commercial decision-making and technology.','Commercial thinking · data · leadership'),
        ]
    return {'route_label':label,'routes':routes,'subjects':subjects}


def _pathways_template() -> str:
    return r'''{% extends "base.html" %}{% block title %}Your Pathways · ScoreMax{% endblock %}{% block content %}
<style>
.ux-path-page{max-width:1200px;margin:0 auto;padding:24px 22px 52px}.ux-path-hero{padding:24px;border:1px solid #cae5e3;border-radius:22px;background:linear-gradient(135deg,#eff9f8,#fff 66%)}.ux-path-hero h1{margin:.12rem 0 .45rem;color:#3FA6A3;font-size:clamp(2rem,4vw,3rem);letter-spacing:-.04em}.ux-path-hero p{max-width:790px;margin:.3rem 0;color:#5f6d78;line-height:1.55}.ux-path-chip{display:inline-flex;margin-top:9px;padding:6px 9px;border-radius:999px;background:#E8F6F5;color:#236765;font-size:.7rem;font-weight:900}.ux-path-section{margin-top:20px}.ux-path-section h2{margin:.1rem 0 .35rem;color:#172033;font-size:1.35rem}.ux-path-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:11px}.ux-path-card{--accent:#3FA6A3;padding:16px;border:1px solid #dce7e6;border-top:5px solid var(--accent);border-radius:16px;background:#fff;box-shadow:0 7px 20px rgba(15,23,42,.04)}.ux-path-card:nth-child(3n+2){--accent:#4F7FB8}.ux-path-card:nth-child(3n+3){--accent:#7C68B5}.ux-path-card h3{margin:0;color:var(--accent);font-size:1.05rem}.ux-path-card strong{display:block;margin-top:6px;color:#1f2937;font-size:.78rem}.ux-path-card p{margin:7px 0;color:#62707b;font-size:.72rem;line-height:1.45}.ux-path-card small{display:block;padding-top:7px;border-top:1px solid #edf1f1;color:#6f7c87;font-size:.62rem}.ux-fit-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:10px}.ux-fit-grid div{padding:13px;border-radius:13px;background:#f7faf9;border:1px solid #e5eceb}.ux-fit-grid strong{display:block;color:#2F7F7D;font-size:.76rem}.ux-fit-grid span{display:block;margin-top:4px;color:#67757f;font-size:.65rem;line-height:1.35}.ux-path-check{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:10px}.ux-path-check div{padding:13px 14px;border:1px solid #e1e9e8;border-radius:13px;background:#fff}.ux-path-check strong{font-size:.75rem}.ux-path-check p{margin:4px 0 0;color:#65727d;font-size:.66rem;line-height:1.4}.ux-path-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.ux-path-note{margin-top:15px;padding:11px 13px;border-radius:12px;background:#f6f8f8;color:#697680;font-size:.64rem;line-height:1.45}@media(max-width:900px){.ux-path-grid{grid-template-columns:1fr 1fr}.ux-fit-grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.ux-path-page{padding:18px 13px 44px}.ux-path-grid,.ux-fit-grid,.ux-path-check{grid-template-columns:1fr}}
</style>
<main class="ux-path-page"><section class="ux-path-hero"><p class="eyebrow">YOUR FUTURE</p><h1>What can your {{route_label}} lead to?</h1><p>This page is built around your current studies — not a catalogue of programmes you have already passed. Explore realistic directions after FSc, compare the kind of work they lead to, and start narrowing the routes that fit you.</p><span class="ux-path-chip">Current route · {{route_label}}</span></section>
<section class="ux-path-section"><p class="eyebrow">EXPLORE OPTIONS</p><h2>Where you could go next</h2><div class="ux-path-grid">{% for title,examples,copy,fit in routes %}<article class="ux-path-card"><h3>{{title}}</h3><strong>{{examples}}</strong><p>{{copy}}</p><small>Good fit: {{fit}}</small></article>{% endfor %}</div></section>
<section class="ux-path-section"><p class="eyebrow">THINK ABOUT FIT</p><h2>Choose by the future you want, not just the degree name</h2><div class="ux-fit-grid"><div><strong>Work with people</strong><span>Clinical care, rehabilitation, psychology and community-facing roles.</span></div><div><strong>Investigate & diagnose</strong><span>Laboratories, imaging, diagnostics and evidence-led health work.</span></div><div><strong>Discover & research</strong><span>Life sciences, biotechnology, genetics and postgraduate research.</span></div><div><strong>Build with technology</strong><span>Bioinformatics, data and technology-enabled health or science careers.</span></div></div></section>
<section class="ux-path-section"><p class="eyebrow">BEFORE YOU APPLY</p><h2>Four checks that can save you from a poor choice</h2><div class="ux-path-check"><div><strong>1 · Eligibility</strong><p>Check the exact subject, marks and entry-test requirements for the university and admission year.</p></div><div><strong>2 · Recognition</strong><p>For regulated careers, confirm the degree and institution meet the relevant professional recognition requirements.</p></div><div><strong>3 · Real work</strong><p>Look beyond the course title: understand what graduates actually do day to day and where they work.</p></div><div><strong>4 · Your evidence</strong><p>Use your ScoreMax strengths, weak areas and exam targets to see which routes fit your current academic profile.</p></div></div>
<div class="ux-path-actions"><a class="btn" href="{{url_for('ux_calculators')}}">Check my target score</a><a class="btn alt" href="{{url_for('study_plan_page')}}">Open my exam plan</a><a class="btn alt" href="{{url_for('ux_register_interest',programme='Pathway guidance')}}">Register for pathway guidance</a></div><p class="ux-path-note">Admissions rules, entry tests, programme names and eligibility can change by institution and admission cycle. ScoreMax should always show the applicable current requirements before a student acts on a pathway.</p></section></main>
{% endblock %}'''


def _competition_template() -> str:
    return r'''{% extends "base.html" %}{% block title %}Science Genius of the Year · ScoreMax{% endblock %}{% block content %}
<style>
.ux-science-page{max-width:1180px;margin:0 auto;padding:28px 22px 54px}.ux-sg-hero{position:relative;overflow:hidden;padding:34px;border-radius:25px;background:radial-gradient(circle at 88% 15%,rgba(137,208,205,.24),transparent 30%),linear-gradient(140deg,#102f35,#214d51);color:#fff}.ux-sg-hero .eyebrow{color:#9fe0dc}.ux-sg-hero h1{max-width:780px;margin:.15rem 0 .55rem;font-size:clamp(2.35rem,5vw,4rem);letter-spacing:-.045em;line-height:1}.ux-sg-hero p{max-width:760px;color:#d8e8e7;line-height:1.55}.ux-sg-actions{display:flex;gap:9px;flex-wrap:wrap;margin-top:18px}.ux-sg-actions .btn.alt{background:rgba(255,255,255,.09)!important;color:#fff!important;border-color:rgba(255,255,255,.26)!important}.ux-sg-badge{display:inline-flex;margin-top:12px;padding:7px 10px;border-radius:999px;background:rgba(255,255,255,.1);font-size:.7rem;font-weight:900}.ux-sg-section{margin-top:23px}.ux-sg-section h2{margin:.1rem 0 .4rem;color:#3FA6A3;font-size:1.5rem}.ux-sg-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:12px}.ux-sg-card{padding:18px;border:1px solid #dce7e6;border-radius:16px;background:#fff;box-shadow:0 7px 22px rgba(15,23,42,.04)}.ux-sg-card span{font-size:.62rem;font-weight:900;color:#2F7F7D;letter-spacing:.06em}.ux-sg-card h3{margin:.3rem 0 .4rem}.ux-sg-card p{margin:0;color:#68757f;font-size:.73rem;line-height:1.45}.ux-sg-info{display:grid;grid-template-columns:1.1fr .9fr;gap:12px;margin-top:12px}.ux-sg-info article{padding:19px;border-radius:17px;background:#f6faf9;border:1px solid #dfebea}.ux-sg-info strong{display:block;color:#236765}.ux-sg-info p{margin:6px 0 0;color:#65737d;font-size:.73rem;line-height:1.5}.ux-sg-prize{background:linear-gradient(145deg,#fffaf0,#fff)!important;border-color:#ead9a5!important}@media(max-width:760px){.ux-sg-grid,.ux-sg-info{grid-template-columns:1fr}.ux-science-page{padding:20px 13px 46px}.ux-sg-hero{padding:25px 20px}}
</style>
<main class="ux-science-page"><section class="ux-sg-hero"><p class="eyebrow">SCIENCE GENIUS OF THE YEAR</p><h1>Compete from your district. Climb the leaderboard.</h1><p>ScoreMax is preparing a nationwide science competition across Pakistan, with participation planned across districts and a route from local performance to the national stage.</p><span class="ux-sg-badge">Competition starts · January 2027</span><div class="ux-sg-actions"><a class="btn" href="{{url_for('ux_register_interest',programme='Science Genius Leaderboard',view='leaderboard')}}">Compete</a><a class="btn alt" href="{{url_for('ux_register_interest',programme='Science Genius of the Year')}}">Register interest</a></div></section>
<section class="ux-sg-section"><p class="eyebrow">THE ROUTE</p><h2>One competition. A clear climb.</h2><div class="ux-sg-grid"><article class="ux-sg-card"><span>01 · DISTRICT</span><h3>District challenge</h3><p>Compete locally, build your score and earn a place on the district leaderboard.</p></article><article class="ux-sg-card"><span>02 · PROVINCIAL</span><h3>Provincial stage</h3><p>Top performers progress into a wider competitive field and stronger science challenges.</p></article><article class="ux-sg-card"><span>03 · NATIONAL</span><h3>National final</h3><p>The strongest performers compete for national recognition and the top awards.</p></article></div></section>
<section class="ux-sg-section"><div class="ux-sg-info"><article><strong>Who can take part?</strong><p>ScoreMax students with qualifying access levels will be eligible under the final competition rules. Students who are not ScoreMax members will also be able to participate through a competition entry fee.</p></article><article class="ux-sg-prize"><strong>Major cash prizes are planned.</strong><p>Top performers will compete for major cash prizes and national recognition. Prize amounts will be announced with the final competition rules.</p></article></div><div class="ux-sg-info"><article><strong>Be ready for January.</strong><p>Use the months before launch to strengthen your science knowledge, accuracy and problem solving. The leaderboard will open when the competition starts.</p></article><article><strong>Final details will follow.</strong><p>Eligibility, access requirements, entry fee, prize amounts, district format, dates and competition rules will be announced closer to launch.</p></article></div></section></main>{% endblock %}'''


def _leaderboard_template() -> str:
    return r'''{% extends "base.html" %}{% block title %}Science Genius Leaderboard · ScoreMax{% endblock %}{% block content %}
<style>
.ux-lb{max-width:1120px;margin:0 auto;padding:28px 22px 54px}.ux-lb-hero{padding:26px;border:1px solid #cbe5e3;border-radius:22px;background:linear-gradient(135deg,#eef9f8,#fff)}.ux-lb-hero h1{margin:.1rem 0 .4rem;color:#3FA6A3;font-size:clamp(2rem,4vw,3rem)}.ux-lb-hero p{max-width:760px;color:#64727d}.ux-lb-status{display:inline-flex;margin-top:10px;padding:6px 9px;border-radius:999px;background:#17383b;color:#fff;font-size:.68rem;font-weight:900}.ux-lb-tabs{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:18px}.ux-lb-tabs div{padding:15px;border:1px solid #dfe8e7;border-radius:14px;background:#fff}.ux-lb-tabs strong{display:block;color:#236765}.ux-lb-tabs span{display:block;margin-top:4px;color:#6a7882;font-size:.68rem}.ux-lb-board{margin-top:14px;padding:30px;border:1px dashed #bfd5d3;border-radius:18px;background:#fbfdfd;text-align:center}.ux-lb-board h2{margin:.1rem 0 .35rem}.ux-lb-board p{max-width:630px;margin:0 auto;color:#687680}.ux-lb-actions{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:15px}@media(max-width:650px){.ux-lb-tabs{grid-template-columns:1fr}.ux-lb{padding:20px 13px 46px}}
</style>
<main class="ux-lb"><section class="ux-lb-hero"><p class="eyebrow">SCIENCE GENIUS LEADERBOARD</p><h1>Your climb starts in January 2027.</h1><p>The live leaderboard will show verified competition performance from district level through the national stage. No placeholder rankings are shown before the competition begins.</p><span class="ux-lb-status">Leaderboard opens January 2027</span></section><div class="ux-lb-tabs"><div><strong>District</strong><span>See your position against competitors in your district.</span></div><div><strong>Province</strong><span>Track progression as the field narrows.</span></div><div><strong>Pakistan</strong><span>See the national leaders and finalists.</span></div></div><section class="ux-lb-board"><p class="eyebrow">GET READY</p><h2>No rankings yet — the competition has not started.</h2><p>When Science Genius begins, this space will become the competition leaderboard. Until then, build your science knowledge and register so you do not miss the launch details.</p><div class="ux-lb-actions"><a class="btn" href="{{url_for('ux_register_interest',programme='Science Genius of the Year')}}">Register interest</a><a class="btn alt" href="{{url_for('ux_register_interest',programme='Science Genius of the Year',view='competition')}}">Competition details</a></div></section></main>{% endblock %}'''


def _community_template() -> str:
    return r'''{% extends "base.html" %}{% block title %}Community · ScoreMax{% endblock %}{% block content %}
<style>
.ux-community{max-width:1160px;margin:0 auto;padding:28px 22px 54px}.ux-community-hero{padding:26px;border-radius:22px;background:linear-gradient(135deg,#f0faf9,#fff);border:1px solid #cde7e5}.ux-community-hero h1{margin:.1rem 0 .45rem;color:#3FA6A3;font-size:clamp(2rem,4vw,3rem)}.ux-community-hero p{max-width:760px;margin:0;color:#65737d}.ux-community-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:16px}.ux-community-card{display:flex;flex-direction:column;padding:18px;border:1px solid #dfe8e7;border-radius:16px;background:#fff;box-shadow:0 7px 21px rgba(15,23,42,.04)}.ux-community-card h2{margin:.12rem 0 .4rem;color:#2F7F7D;font-size:1.05rem}.ux-community-card p{margin:0;color:#687680;font-size:.72rem;line-height:1.45;flex:1}.ux-community-card a{margin-top:12px;color:#236765;font-size:.7rem;font-weight:900;text-decoration:none}@media(max-width:800px){.ux-community-grid{grid-template-columns:1fr 1fr}}@media(max-width:560px){.ux-community{padding:20px 13px 46px}.ux-community-grid{grid-template-columns:1fr}}
</style>
<main class="ux-community"><section class="ux-community-hero"><p class="eyebrow">SCOREMAX COMMUNITY</p><h1>Compete, contribute, connect.</h1><p>Your community space is where ScoreMax learning extends beyond question practice — competitions, student voice, teacher connections and useful learning opportunities.</p></section><div class="ux-community-grid"><article class="ux-community-card"><p class="eyebrow">COMPETE</p><h2>Science Genius of the Year</h2><p>Prepare for the nationwide competition starting in January 2027 and follow the route to the leaderboard.</p><a href="{{url_for('ux_register_interest',programme='Science Genius of the Year',view='competition')}}">Explore competition →</a></article><article class="ux-community-card"><p class="eyebrow">STUDENT VOICE</p><h2>Student Council</h2><p>Help shape ScoreMax, surface student needs and represent learners from your area.</p><a href="{{url_for('ux_register_interest',programme='Student Council')}}">Register interest →</a></article><article class="ux-community-card"><p class="eyebrow">SUPPORT</p><h2>Find a Teacher</h2><p>Tell us what subject or support you need and register for future teacher-matching options.</p><a href="{{url_for('ux_register_interest',programme='Find a Teacher')}}">Register interest →</a></article><article class="ux-community-card"><p class="eyebrow">LEARN</p><h2>Recorded Learning</h2><p>Register for updates on future recorded lessons and guided learning resources.</p><a href="{{url_for('ux_register_interest',programme='Recorded Learning')}}">Register interest →</a></article><article class="ux-community-card"><p class="eyebrow">EXPLORE</p><h2>Knowledge Hub</h2><p>Use articles and resources that help with learning, exams and student decisions.</p><a href="{{url_for('knowledge_home')}}">Open Knowledge Hub →</a></article><article class="ux-community-card"><p class="eyebrow">CONTACT</p><h2>Talk to ScoreMax</h2><p>Questions, ideas or feedback? Send your details and tell us what you need.</p><a href="{{url_for('ux_register_interest',programme='Contact Us')}}">Contact us →</a></article></div></main>{% endblock %}'''


def _landing_tiers_markup() -> str:
    register=url_for('register',role='student')
    return f'''<section id="scoremax-access" class="ux-landing-tiers" aria-labelledby="uxTierTitle"><div class="ux-tier-head"><p class="ux-kicker">CHOOSE YOUR SCOREMAX ACCESS</p><h2 id="uxTierTitle">Silver, Gold or Platinum.</h2><p>Start with the level of support that fits you — and move up as your ambitions grow.</p></div><div class="ux-tier-grid"><a class="ux-tier-card ux-tier-silver" href="{register}"><span class="ux-tier-shine"></span><small>SILVER</small><h3>Silver</h3><p>Build strong foundations with structured practice, progress and a clear route forward.</p><b>Explore Silver →</b></a><a class="ux-tier-card ux-tier-gold" href="{register}"><span class="ux-tier-shine"></span><small>GOLD</small><h3>Gold</h3><p>Go deeper with broader mastery support and stronger exam preparation.</p><b>Explore Gold →</b></a><a class="ux-tier-card ux-tier-platinum" href="{register}"><span class="ux-tier-shine"></span><small>PLATINUM</small><h3>Platinum</h3><p>Use the fullest ScoreMax learning, mastery and exam-preparation journey.</p><b>Explore Platinum →</b></a></div></section>'''


def _global_finish_patch() -> str:
    interest=json.dumps(url_for('ux_register_interest'))
    return r'''<style id="ux-global-finish-style">
.ux-contact-fixed{position:fixed;left:16px;bottom:18px;z-index:84;display:inline-flex;align-items:center;gap:6px;padding:9px 12px;border:1px solid #a8d8d5;border-radius:999px;background:rgba(255,255,255,.96);box-shadow:0 10px 26px rgba(15,23,42,.12);color:#236765!important;text-decoration:none!important;font-size:.72rem;font-weight:900;backdrop-filter:blur(10px)}.ux-contact-fixed:before{content:'✉';font-size:.8rem}
.coach-toggle{position:fixed!important;left:12px!important;right:auto!important;top:52%!important;bottom:auto!important;transform:translateY(-50%)!important;z-index:74!important}.coach-toggle:hover{transform:translateY(-50%) scale(1.02)!important}
.ux-landing-tiers{max-width:1200px;margin:26px auto;padding:32px 28px}.ux-tier-head{max-width:720px;margin-bottom:16px}.ux-tier-head h2{margin:.1rem 0 .35rem;font-size:clamp(1.8rem,3vw,2.45rem);letter-spacing:-.04em;color:#3FA6A3}.ux-tier-head p{margin:0;color:#657383}.ux-tier-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.ux-tier-card{position:relative;overflow:hidden;min-height:210px;padding:25px 23px 21px;border:1px solid #dce5e5;border-top-width:7px;border-radius:20px;text-decoration:none;color:#182220;box-shadow:0 14px 34px rgba(15,23,42,.07);transition:.18s ease}.ux-tier-card:hover{transform:translateY(-4px);box-shadow:0 21px 44px rgba(15,23,42,.11)}.ux-tier-card small{display:inline-block;padding:4px 7px;border-radius:999px;font-size:.58rem;font-weight:950;letter-spacing:.1em}.ux-tier-card h3{margin:12px 0 7px;font-size:1.55rem;letter-spacing:-.03em}.ux-tier-card p{max-width:310px;margin:0;color:#5f6d76;font-size:.78rem;line-height:1.5}.ux-tier-card b{display:block;margin-top:16px;font-size:.73rem}.ux-tier-shine{position:absolute;right:-36px;top:-48px;width:150px;height:150px;border-radius:50%;filter:blur(4px);opacity:.5;pointer-events:none}.ux-tier-silver{border-top-color:#9ca8b3;background:linear-gradient(145deg,#fff 0%,#f4f7f8 58%,#e9eef0 100%)}.ux-tier-silver small{background:#e7ecef;color:#53606a}.ux-tier-silver .ux-tier-shine{background:radial-gradient(circle,#fff,rgba(190,202,211,.25) 58%,transparent 70%)}.ux-tier-silver b{color:#536875}.ux-tier-gold{border-color:#e3cf8d;border-top-color:#c49a35;background:radial-gradient(circle at 90% 12%,rgba(244,213,116,.32),transparent 30%),linear-gradient(145deg,#fffdf5,#fff8df 55%,#fff)}.ux-tier-gold small{background:#f5e7b7;color:#725718}.ux-tier-gold h3,.ux-tier-gold b{color:#8a681d}.ux-tier-gold .ux-tier-shine{background:radial-gradient(circle,#fff5bf,rgba(230,190,72,.28) 55%,transparent 70%)}.ux-tier-platinum{border-color:#bfcdd0;border-top-color:#5f777b;background:radial-gradient(circle at 88% 10%,rgba(137,208,205,.25),transparent 32%),linear-gradient(145deg,#f8fbfb,#eef4f4 55%,#fff)}.ux-tier-platinum small{background:#dfe8e9;color:#3e565a}.ux-tier-platinum h3,.ux-tier-platinum b{color:#2F7F7D}.ux-tier-platinum .ux-tier-shine{background:radial-gradient(circle,#dff9f6,rgba(102,151,151,.24) 58%,transparent 70%)}
.commercial-paywall .access-card.ux-tier-silver,.commercial-paywall .access-card.ux-tier-gold,.commercial-paywall .access-card.ux-tier-platinum{position:relative;overflow:hidden;min-height:285px!important;padding:24px 21px!important;border-width:1.5px!important;border-top-width:8px!important;border-radius:20px!important;box-shadow:0 14px 32px rgba(15,23,42,.07)!important;transition:.18s ease!important}.commercial-paywall .access-card.ux-tier-silver:hover,.commercial-paywall .access-card.ux-tier-gold:hover,.commercial-paywall .access-card.ux-tier-platinum:hover{transform:translateY(-3px)!important;box-shadow:0 20px 40px rgba(15,23,42,.1)!important}.commercial-paywall .access-card.ux-tier-silver{border-top-color:#9ca8b3!important;background:linear-gradient(145deg,#fff,#eef3f5)!important}.commercial-paywall .access-card.ux-tier-gold{border-color:#e4d19a!important;border-top-color:#c49a35!important;background:radial-gradient(circle at 90% 12%,rgba(244,213,116,.27),transparent 28%),linear-gradient(145deg,#fffdf6,#fff)!important}.commercial-paywall .access-card.ux-tier-platinum{border-color:#c4d1d2!important;border-top-color:#5f777b!important;background:radial-gradient(circle at 90% 12%,rgba(137,208,205,.22),transparent 28%),linear-gradient(145deg,#f7fbfb,#fff)!important}.commercial-paywall .access-card.ux-tier-silver h2,.commercial-paywall .access-card.ux-tier-gold h2,.commercial-paywall .access-card.ux-tier-platinum h2{font-size:1.55rem!important;letter-spacing:-.025em!important}.commercial-paywall .access-card.ux-tier-gold h2{color:#8a681d!important}.commercial-paywall .access-card.ux-tier-platinum h2{color:#2F7F7D!important}.commercial-paywall .mastery-mini-ladder{margin:14px 0!important}
@media(max-width:760px){.ux-tier-grid{grid-template-columns:1fr}.ux-landing-tiers{padding:25px 16px}.ux-tier-card{min-height:auto}.coach-toggle{left:7px!important;top:48%!important}.ux-contact-fixed{bottom:78px;left:10px}}
</style><a id="uxContactFixed" class="ux-contact-fixed" href="/register-interest?programme=Contact%20Us">Contact Us</a><script id="ux-global-finish-script">(function(){const INTEREST=__INTEREST__;
function interest(programme,view){return INTEREST+'?programme='+encodeURIComponent(programme)+(view?'&view='+encodeURIComponent(view):'');}
function rewrite(){document.querySelectorAll('a').forEach(a=>{if(a.closest('.ux-science-page,.ux-community,.ux-lb'))return;const t=(a.textContent||'').replace(/\s+/g,' ').trim().toLowerCase();if(t.includes('find a teacher'))a.href=interest('Find a Teacher');else if(t.includes('recorded learning'))a.href=interest('Recorded Learning');else if(t==='community'||t.includes('scoremax community'))a.href=interest('ScoreMax Community','community');else if(t.includes('science genius'))a.href=interest('Science Genius of the Year','competition');});}
function tiers(){document.querySelectorAll('.commercial-paywall .access-card').forEach(c=>{const t=(c.querySelector('h2')?.textContent||'').toLowerCase();c.classList.remove('ux-tier-silver','ux-tier-gold','ux-tier-platinum');if(t.includes('silver'))c.classList.add('ux-tier-silver');if(t.includes('gold'))c.classList.add('ux-tier-gold');if(t.includes('platinum'))c.classList.add('ux-tier-platinum');});}
function run(){rewrite();tiers();}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run);else run();[150,600,1400].forEach(x=>setTimeout(run,x));})();</script>'''.replace('__INTEREST__',interest)


def _student_shell_patch() -> str:
    learn_url=json.dumps(url_for('ux_student_learn')); plan_url=json.dumps(url_for('study_plan_page')); access_url=json.dumps(url_for('access_account'))
    return r'''<style id="ux-batch-student-style">
.ux-home-overall{margin-top:14px;padding-top:12px;border-top:1px solid #e6eeee}.ux-home-overall-head{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.ux-home-overall-head span{font-size:.6rem;font-weight:900;letter-spacing:.055em;color:#657383}.ux-home-overall-head strong{font-size:.78rem;color:#236765}.ux-home-overall-track{height:8px;margin-top:6px;border-radius:999px;background:#e9efee;overflow:hidden}.ux-home-overall-track i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#3FA6A3,#2F7F7D)}.ux-home-overall.unverified .ux-home-overall-track{background:#f1dede}.ux-home-overall.unverified .ux-home-overall-track i{background:#C95858}.ux-home-overall-labels{display:grid;grid-template-columns:repeat(6,1fr);gap:2px;margin-top:4px;color:#73807d;font-size:.47rem;font-weight:650}.ux-home-overall-labels span{text-align:center}.ux-home-overall-labels span:first-child{text-align:left}.ux-home-overall-labels span:last-child{text-align:right}
.ux-start-merged{grid-template-columns:1fr!important}.ux-start-journey{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:13px;padding-top:10px;border-top:1px solid rgba(0,0,0,.08)}.ux-start-journey span{padding:5px 8px;border-radius:999px;background:#f5f8f8;color:#53625f;font-size:.63rem;font-weight:800}.ux-start-journey span:first-child{background:#E8F6F5;color:#236765}.ux-start-journey i{font-style:normal;color:#9aa5a2}
.ux-home-exam-plan{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(250px,.7fr);gap:18px;align-items:center;margin:15px 0;padding:20px 22px;border:1px solid #bfe1df;border-radius:19px;background:linear-gradient(135deg,#eef9f8,#fff 64%);box-shadow:0 10px 28px rgba(47,127,125,.065)}.ux-home-exam-plan h2{margin:.1rem 0 .35rem;color:#236765;font-size:clamp(1.25rem,2vw,1.65rem)}.ux-home-exam-plan p{margin:0;color:#657383}.ux-home-exam-points{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-top:12px}.ux-home-exam-points div{padding:8px;border:1px solid #dcebea;border-radius:10px;background:#fff}.ux-home-exam-points strong,.ux-home-exam-points span{display:block}.ux-home-exam-points strong{font-size:.68rem}.ux-home-exam-points span{font-size:.56rem;color:#71807c;margin-top:2px}.ux-home-exam-actions{display:grid;gap:7px}.ux-home-exam-actions a{text-align:center;text-decoration:none}
.ux-home-plans{margin:20px 0}.ux-home-plans-head{display:flex;justify-content:space-between;gap:12px;align-items:end;margin-bottom:10px}.ux-home-plans-head h2{margin:.1rem 0 0;color:#3FA6A3;font-size:1.35rem}.ux-home-plans-head a{color:#2F7F7D;font-size:.7rem;font-weight:850}.ux-home-plan-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:11px}.ux-home-plan{position:relative;overflow:hidden;min-height:150px;padding:20px 18px 16px;border:1px solid #dfe7e7;border-top:7px solid #9ca8b3;border-radius:17px;background:#fff;text-decoration:none;color:inherit;box-shadow:0 10px 26px rgba(15,23,42,.055);transition:.17s ease}.ux-home-plan:hover{transform:translateY(-3px);box-shadow:0 16px 34px rgba(15,23,42,.09)}.ux-home-plan.silver{background:linear-gradient(145deg,#fff,#f1f5f6)}.ux-home-plan.gold{border-color:#e4d19a;border-top-color:#c49a35;background:radial-gradient(circle at 90% 12%,rgba(244,213,116,.25),transparent 28%),linear-gradient(145deg,#fffdf6,#fff)}.ux-home-plan.platinum{border-color:#c4d1d2;border-top-color:#5f777b;background:radial-gradient(circle at 90% 12%,rgba(137,208,205,.2),transparent 28%),linear-gradient(145deg,#f7fbfb,#fff)}.ux-home-plan strong,.ux-home-plan span,.ux-home-plan b{display:block}.ux-home-plan strong{font-size:1.15rem}.ux-home-plan.gold strong{color:#8a681d}.ux-home-plan.platinum strong{color:#2F7F7D}.ux-home-plan span{margin-top:7px;color:#71807c;font-size:.72rem;line-height:1.4}.ux-home-plan b{margin-top:11px;color:#2F7F7D;font-size:.7rem}
.ux-science-corner{margin:12px 0 0;padding:14px 16px;border-radius:15px;background:linear-gradient(135deg,#102f35,#214d51);color:#fff}.ux-science-head{display:flex;justify-content:space-between;gap:10px;align-items:center}.ux-science-corner .eyebrow{color:#9fe0dc;margin:0}.ux-science-corner h3{margin:.15rem 0 0;font-size:1rem}.ux-science-corner button{padding:7px 10px;border:1px solid rgba(255,255,255,.22);border-radius:999px;background:rgba(255,255,255,.1);color:#fff;font-size:.67rem;font-weight:900;cursor:pointer}.ux-science-fact{display:none;margin:9px 0 0;padding-top:9px;border-top:1px solid rgba(255,255,255,.14);color:#e3eeee;font-size:.78rem;line-height:1.42}.ux-science-fact.show{display:block}.ux-science-tag{display:none;margin-top:7px;padding:3px 7px;border-radius:999px;background:rgba(255,255,255,.1);font-size:.57rem;font-weight:850;color:#bfe7e4}.ux-science-tag.show{display:inline-block}.ux-hide-verification{display:none!important}
@media(max-width:900px){.ux-home-exam-plan{grid-template-columns:1fr}.ux-home-exam-points{grid-template-columns:repeat(3,1fr)}}@media(max-width:640px){.ux-home-plan-grid,.ux-home-exam-points{grid-template-columns:1fr}.ux-science-head{align-items:flex-start;flex-direction:column}.ux-home-overall-labels{font-size:.42rem}}
</style><script id="ux-batch-student-script">(function(){const LEARN=__LEARN__,PLAN=__PLAN__,ACCESS=__ACCESS__;const stages=['Foundation','Exam Ready','Advanced','Distinction','Expert','Elite'];
function currentStage(){const s=document.querySelector('#uxStudentMasteryStrip .ux-mastery-current strong');if(s)return (s.textContent||'').trim();const h=document.querySelector('.mastery-hero-card h2');const t=(h&&h.textContent||'').trim();return stages.find(x=>t.toLowerCase().includes(x.toLowerCase()))||'Not verified';}
function addPremedTabs(){const strip=document.querySelector('.student-context-stack .subject-quick-strip');if(!strip)return;const names=[...strip.querySelectorAll('a')].map(a=>(a.textContent||'').trim().toLowerCase());if(!['biology','chemistry','physics'].every(x=>names.includes(x)))return;[['MDCAT','mdcat-route'],['Logical Reasoning','mdcat-route'],['English','mdcat-route']].forEach(([name,hash])=>{if([...strip.querySelectorAll('a')].some(a=>(a.textContent||'').trim()===name))return;const a=document.createElement('a');a.textContent=name;a.href=LEARN+'#'+hash;strip.appendChild(a);});}
function addOverall(){const greet=document.querySelector('.home-greeting-block');if(!greet||greet.querySelector('.ux-home-overall'))return;const stage=currentStage(),idx=stages.indexOf(stage),pct=idx<0?0:Math.round((idx+1)/6*100);const box=document.createElement('div');box.className='ux-home-overall'+(idx<0?' unverified':'');box.innerHTML='<div class="ux-home-overall-head"><span>OVERALL MASTERY</span><strong>'+(idx<0?'Not verified':stage)+'</strong></div><div class="ux-home-overall-track"><i style="width:'+pct+'%"></i></div><div class="ux-home-overall-labels">'+stages.map(x=>'<span>'+x+'</span>').join('')+'</div>';greet.appendChild(box);}
function mergeStart(){const grid=document.querySelector('.home-priority-grid'),focus=grid&&grid.querySelector('.today-focus-card'),momentum=grid&&grid.querySelector('.home-progress-card');if(!grid||!focus||!momentum)return;if(!/find your starting point/i.test(focus.textContent||'')||!/your journey starts here|starting point/i.test(momentum.textContent||''))return;if(!focus.querySelector('.ux-start-journey')){const j=document.createElement('div');j.className='ux-start-journey';j.innerHTML='<span>Starting Point</span><i>→</i><span>Build Mastery</span><i>→</i><span>Exam Ready</span>';focus.appendChild(j);}momentum.remove();grid.classList.add('ux-start-merged');}
function upgradePlan(){const home=document.querySelector('.student-home-v2');if(!home)return;let old=document.querySelector('.ux-plan-launcher');if(old)old.remove();if(document.querySelector('.ux-home-exam-plan'))return;const anchor=document.querySelector('.home-section')||document.querySelector('.home-two-column');if(!anchor)return;const box=document.createElement('section');box.className='ux-home-exam-plan';box.innerHTML='<div><p class="eyebrow">EXAM PLAN</p><h2>Your route to exam day deserves its own space.</h2><p>Set your target and exam date, then let ScoreMax organise priorities as your evidence grows.</p><div class="ux-home-exam-points"><div><strong>Target</strong><span>Keep the score you want visible.</span></div><div><strong>Priorities</strong><span>Focus on what matters most.</span></div><div><strong>Next action</strong><span>Know what to do when you return.</span></div></div></div><div class="ux-home-exam-actions"><a class="btn" href="'+PLAN+'?mode=scoremax">Let ScoreMax build it</a><a class="btn alt" href="'+PLAN+'?mode=self">Build my own plan</a></div>';anchor.insertAdjacentElement('beforebegin',box);}
function addPlans(){const home=document.querySelector('.student-home-v2');if(!home||document.querySelector('.ux-home-plans'))return;const anchor=document.querySelector('.home-two-column');if(!anchor)return;const s=document.createElement('section');s.className='ux-home-plans';s.innerHTML='<div class="ux-home-plans-head"><div><p class="eyebrow">YOUR SCOREMAX ACCESS</p><h2>Silver, Gold and Platinum.</h2></div><a href="'+ACCESS+'">Compare access →</a></div><div class="ux-home-plan-grid"><a class="ux-home-plan silver" href="'+ACCESS+'"><strong>Silver</strong><span>Build strong foundations and structured progress.</span><b>Explore Silver →</b></a><a class="ux-home-plan gold" href="'+ACCESS+'"><strong>Gold</strong><span>Go deeper with broader mastery and exam preparation.</span><b>Explore Gold →</b></a><a class="ux-home-plan platinum" href="'+ACCESS+'"><strong>Platinum</strong><span>Use the fullest ScoreMax learning and mastery journey.</span><b>Explore Platinum →</b></a></div>';anchor.insertAdjacentElement('beforebegin',s);}
function addScience(){const home=document.querySelector('.student-home-v2');if(!home||document.querySelector('#uxScienceCorner'))return;const anchor=document.querySelector('.home-two-column')||document.querySelector('.home-history');if(!anchor)return;const box=document.createElement('section');box.id='uxScienceCorner';box.className='ux-science-corner';box.innerHTML='<div class="ux-science-head"><div><p class="eyebrow">SCIENCE CORNER</p><h3>A fact, discovery or joke — just for curiosity.</h3></div><button type="button">Surprise me</button></div><p class="ux-science-fact"></p><span class="ux-science-tag"></span>';anchor.insertAdjacentElement('beforebegin',box);const btn=box.querySelector('button'),out=box.querySelector('.ux-science-fact'),tag=box.querySelector('.ux-science-tag');const items=[['Biology','Octopuses have three hearts — two move blood through the gills and one pumps it around the body.'],['Space','A day on Venus, measured by one full rotation, lasts longer than a Venusian year.'],['Physics','A photon checks into a hotel. “Any luggage?” asks the receptionist. “No,” says the photon, “I’m travelling light.”'],['Chemistry','Why are chemists good at solving problems? Because they have all the solutions.'],['Biology','Tardigrades can enter a near-suspended state called cryptobiosis when conditions become extreme.'],['Astronomy','Neutron stars are so dense that a teaspoon of their material would have an extraordinary mass on Earth.'],['Science joke','Why can’t you trust an atom? Because it makes up everything.'],['Earth science','Antarctica is technically the world’s largest desert because it receives so little precipitation.'],['Physics','Lightning can heat the surrounding air to temperatures several times hotter than the surface of the Sun.'],['Biology','Your body hosts vast communities of microorganisms; many are useful partners in digestion and immune function.'],['Chemistry','Diamond and graphite are both carbon. Their radically different properties come from how the carbon atoms are arranged.'],['Science joke','What did one tectonic plate say to the other? “Sorry — my fault.”']];let i=(new Date().getDate()+new Date().getMonth())%items.length;btn.addEventListener('click',()=>{const item=items[i++%items.length];out.textContent=item[1];out.classList.add('show');tag.textContent=item[0];tag.classList.add('show');btn.textContent='Another one';});}
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
        endpoint=request.endpoint or ''
        if endpoint=='ux_register_interest':
            view=(request.args.get('view') or '').strip().casefold()
            if view=='competition': return render_template_string(_competition_template())
            if view=='leaderboard': return render_template_string(_leaderboard_template())
            if view=='community': return render_template_string(_community_template())
        if session.get('role')!='student' or not session.get('user_id'): return None
        if endpoint=='student_pathways':
            conn=_connect()
            try: ctx=_pathway_context(conn,session['user_id'])
            finally: conn.close()
            return render_template_string(_pathways_template(),**ctx)
        if endpoint=='subject_browser':
            conn=_connect()
            try: subjects,future=_learn_context(conn,session['user_id'])
            finally: conn.close()
            return render_template('ux_student_learn.html',subjects=subjects,future_options=future,programme_label='FSc PRE-MEDICAL')
        if endpoint=='subject_detail':
            subject=(request.view_args or {}).get('subject','').strip(); conn=_connect()
            try: chapters=_chapter_snapshots(conn,session['user_id'],subject); snap=_subject_snapshot(conn,session['user_id'],subject)
            finally: conn.close()
            return render_template('ux_subject_chapters.html',subject=subject,chapters=chapters,chapter_count=snap['chapter_count'],started_chapters=snap['started_chapters'],answered=snap['answered'],avg_accuracy=snap['avg_accuracy'],learn_url=url_for('ux_student_learn'))
        if endpoint=='student_analytics_page':
            conn=_connect()
            try: ctx=_progress_context(conn,session['user_id'])
            finally: conn.close()
            return render_template('ux_progress.html',**ctx)
        return None

    @app.after_request
    def _ux_batch_render_patch(response):
        if not response.is_sequence or 'text/html' not in (response.content_type or '').lower(): return response
        html=response.get_data(as_text=True); endpoint=request.endpoint or ''
        if endpoint=='index' and 'ux-landing-tiers' not in html:
            tiers=_landing_tiers_markup()
            marker='<section class="ux-how"'
            html=html.replace(marker,tiers+'\n'+marker,1) if marker in html else html.replace('</main>',tiers+'</main>',1)
        if 'ux-global-finish-style' not in html:
            global_patch=_global_finish_patch(); html=html.replace('</body>',global_patch+'</body>',1) if '</body>' in html else html+global_patch
        if session.get('role')=='student' and session.get('user_id') and 'ux-batch-student-style' not in html:
            patch=_student_shell_patch(); html=html.replace('</body>',patch+'</body>',1) if '</body>' in html else html+patch
        response.set_data(html); response.content_length=len(response.get_data()); return response

    app._ux_student_batch_installed=True
