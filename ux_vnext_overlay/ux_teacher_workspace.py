from __future__ import annotations

import re
from pathlib import Path

STYLE = r'''<style id="ux-teacher-workspace-style">
.ux-teacher-home{max-width:1220px;margin:0 auto;padding-bottom:48px}.ux-teacher-home .dashboard-hero{margin-bottom:10px;background:linear-gradient(135deg,#eff9f8,#fff 62%);border:1px solid #cfe5e3}.ux-teacher-home .dashboard-hero h2{color:#2f7f7d;font-size:clamp(1.65rem,3vw,2.3rem);letter-spacing:-.03em}.ux-teacher-home .grid3{gap:9px;margin-bottom:10px}.ux-teacher-home .metric{border-top:4px solid #3fa6a3;border-radius:14px;box-shadow:0 5px 16px rgba(15,23,42,.035)}
.ux-teacher-actions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 12px}.ux-teacher-actions a{display:flex;align-items:center;justify-content:space-between;min-height:50px;padding:10px 12px;border:1px solid #dce7e6;border-radius:13px;background:#fff;color:#244c4a;text-decoration:none;font-size:.78rem;font-weight:850;box-shadow:0 4px 14px rgba(15,23,42,.025)}.ux-teacher-actions a:after{content:'→';color:#3fa6a3}.ux-teacher-actions a:hover{border-color:#bcdad7;background:#f7fbfa}
.ux-teacher-home .next-action-card{border:1px solid #e5d4ae;border-top:5px solid #d6a74d;background:linear-gradient(135deg,#fffaf0,#fff)}.ux-teacher-home .next-action-card h2{margin:.15rem 0 .3rem}.ux-teacher-home .grid{gap:10px}.ux-teacher-create,.ux-teacher-activity,.ux-teacher-classes{border-radius:15px}.ux-teacher-section-head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:20px 2px 8px}.ux-teacher-section-head h2{margin:.1rem 0;color:#2f7f7d;font-size:1.35rem}.ux-teacher-section-head p{margin:0;color:#6b7875;font-size:.72rem}.ux-teacher-classes table th{font-size:.66rem}.ux-teacher-classes table td{vertical-align:middle}.ux-teacher-classes a{font-weight:850;color:#236765}
.ux-teacher-secondary-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px}.ux-teacher-secondary-grid>.card,.ux-teacher-secondary-grid>section.card{margin:0}.ux-teacher-secondary-grid .teacher-referral-callout{display:block}.ux-teacher-secondary-grid .teacher-referral-callout .btn{margin-top:9px}.ux-teacher-secondary-grid h2,.ux-teacher-secondary-grid h3{font-size:1rem}.ux-teacher-secondary-grid p{font-size:.7rem}.ux-teacher-secondary-grid .eyebrow{font-size:.58rem}
.ux-classroom-home{max-width:1220px;margin:0 auto;padding-bottom:48px}.ux-classroom-home .dashboard-hero{background:linear-gradient(135deg,#eff9f8,#fff 62%);border:1px solid #cfe5e3}.ux-classroom-home .dashboard-hero h2{color:#2f7f7d}.ux-classroom-home .grid3{gap:9px;margin-bottom:11px}.ux-classroom-home .metric{border-top:4px solid #3fa6a3;border-radius:14px}.ux-classroom-home .next-action-card{border-top:5px solid #d6a74d}.ux-classroom-home .ux-class-blueprint{margin-top:14px;background:#fafcfc}.ux-classroom-home .ux-class-section-label{margin:20px 2px 8px}.ux-classroom-home .ux-class-section-label h2{margin:.1rem 0;color:#2f7f7d;font-size:1.3rem}
.ux-teacher-nav-menu{position:relative}.ux-teacher-nav-menu>summary{cursor:pointer;list-style:none;font-weight:700}.ux-teacher-nav-menu>summary::-webkit-details-marker{display:none}.ux-teacher-nav-menu>div{display:none;position:absolute;right:0;top:calc(100% + 8px);z-index:80;min-width:180px;padding:8px;border:1px solid #d9e5e3;border-radius:12px;background:#fff;box-shadow:0 12px 30px rgba(15,23,42,.12)}.ux-teacher-nav-menu[open]>div{display:grid}.ux-teacher-nav-menu>div a{padding:8px 10px;border-radius:8px;white-space:nowrap}.ux-teacher-nav-menu>div a:hover{background:#f2f8f7}
@media(max-width:900px){.ux-teacher-actions{grid-template-columns:1fr 1fr}.ux-teacher-secondary-grid{grid-template-columns:1fr}}
@media(max-width:620px){.ux-teacher-home,.ux-classroom-home{padding-left:0;padding-right:0}.ux-teacher-actions{grid-template-columns:1fr 1fr}.ux-teacher-actions a{min-height:44px}.ux-teacher-section-head{align-items:flex-start;flex-direction:column}.ux-teacher-home .table-wrap,.ux-classroom-home .table-wrap{margin-left:-2px;margin-right:-2px}.ux-teacher-home table,.ux-classroom-home table{font-size:.72rem}}
</style>'''


def _take_once(text: str, pattern: str, label: str) -> tuple[str, str]:
    rx=re.compile(pattern,re.S)
    matches=list(rx.finditer(text))
    if len(matches)!=1:
        raise SystemExit(f'UX_TEACHER_{label}_ANCHOR_MISMATCH:{len(matches)}')
    m=matches[0]
    return text[:m.start()]+text[m.end():],m.group(0)


def _refine_teacher_template(path: Path) -> None:
    text=path.read_text(encoding='utf-8')
    required=('TEACHER DASHBOARD','Create classroom','RECENT ASSIGNMENTS','My classrooms','teacher-referral-callout')
    missing=[x for x in required if x not in text]
    if missing:
        raise SystemExit('UX_TEACHER_TEMPLATE_BASELINE_MISSING:'+','.join(missing))

    text,structures=_take_once(text,r"\{% if active_structures %\}<section class=\"card\">.*?\{% endif %\}\s*",'BLUEPRINT')
    text,referral=_take_once(text,r"<section class=['\"]card teacher-referral-callout['\"]>.*?</section>\s*",'REFERRAL')

    opening="{% extends 'base.html' %}{% block content %}"
    if opening not in text:
        raise SystemExit('UX_TEACHER_CONTENT_BLOCK_MISSING')
    text=text.replace(opening,"{% extends 'base.html' %}{% block title %}Teacher Home · ScoreMax{% endblock %}{% block content %}\n"+STYLE+"\n<section class=\"ux-teacher-home\">",1)
    text=text.replace('TEACHER DASHBOARD','TEACHER HOME',1)
    text=text.replace('PRIORITY INTERVENTION','PRIORITY TODAY')
    text=text.replace('Open the relevant classroom to identify affected students and assign targeted recovery work.','Open the relevant class to see who needs support and assign focused recovery work.')
    text=text.replace("<div class='card'><h3>Create classroom</h3>","<div class='card ux-teacher-create'><p class='eyebrow'>SETUP</p><h3>Create a class</h3>",1)
    text=text.replace("<div class='card'><p class='eyebrow'>RECENT ASSIGNMENTS</p><h3>Intervention activity</h3>","<div class='card ux-teacher-activity'><p class='eyebrow'>RECENT ACTIVITY</p><h3>Assignments</h3>",1)
    text=text.replace("<div class='card'><h3>My classrooms</h3>","<section class='ux-teacher-section-head'><div><p class='eyebrow'>MY CLASSES</p><h2>Classes at a glance</h2></div><p>Open a class to view progress, weak areas and assignment activity.</p></section><div class='card ux-teacher-classes' id='ux-my-classes'><h3>My classes</h3>",1)
    text=text.replace('Open intervention view →','Open class →')

    hero_marker="<span class='health green'>{{ students }} students</span></div>"
    if hero_marker not in text:
        raise SystemExit('UX_TEACHER_HERO_MARKER_MISSING')
    actions='''<nav class="ux-teacher-actions" aria-label="Teacher quick actions">
<a href="#ux-my-classes">My classes</a>
<a href="{{url_for('academic_messages_inbox')}}">Messages</a>
<a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Corner</a>
<a href="{{url_for('knowledge_home')}}">Resources</a>
</nav>'''
    text=text.replace(hero_marker,hero_marker+'\n'+actions,1)

    secondary='''<section class="ux-teacher-section-head"><div><p class="eyebrow">MORE TOOLS</p><h2>Teacher tools and programme context</h2></div><p>Useful when you need them, without competing with daily class work.</p></section>
<div class="ux-teacher-secondary-grid">'''+referral+'\n'+structures+'''</div>'''
    if '{% endblock %}' not in text:
        raise SystemExit('UX_TEACHER_ENDBLOCK_MISSING')
    text=text.replace('{% endblock %}',secondary+'\n</section>\n{% endblock %}',1)
    path.write_text(text,encoding='utf-8')


def _refine_classroom_template(path: Path) -> None:
    text=path.read_text(encoding='utf-8')
    required=('CLASSROOM INTERVENTION','RECOMMENDED INTERVENTION','Learning outcomes / concepts','Misconception signals')
    missing=[x for x in required if x not in text]
    if missing:
        raise SystemExit('UX_TEACHER_CLASSROOM_BASELINE_MISSING:'+','.join(missing))

    blueprint=''
    rx=re.compile(r"\{% if blueprint_summary %\}<section class=\"card\">.*?\{% endif %\}\s*",re.S)
    matches=list(rx.finditer(text))
    if len(matches)==1:
        m=matches[0]; blueprint=m.group(0); text=text[:m.start()]+text[m.end():]
    elif len(matches)>1:
        raise SystemExit('UX_TEACHER_CLASSROOM_BLUEPRINT_ANCHOR_MISMATCH')

    opening="{% extends 'base.html' %}{% block content %}"
    if opening not in text:
        raise SystemExit('UX_TEACHER_CLASSROOM_CONTENT_BLOCK_MISSING')
    text=text.replace(opening,"{% extends 'base.html' %}{% block title %}Class Overview · ScoreMax{% endblock %}{% block content %}\n"+STYLE+"\n<section class=\"ux-classroom-home\">",1)
    text=text.replace('CLASSROOM INTERVENTION','CLASS OVERVIEW',1)
    text=text.replace('RECOMMENDED INTERVENTION','RECOMMENDED NEXT STEP',1)
    text=text.replace('Learning outcomes / concepts','Learning areas',1)
    text=text.replace('Misconception signals','Common misconceptions',1)
    text=text.replace('OPTIONAL STUDY PLANS','STUDY PLANS',1)
    text=text.replace('Students needing attention','Needs attention',1)
    text=text.replace('No assessment activity','No activity yet',1)

    if blueprint:
        blueprint=blueprint.replace('<section class="card">','<section class="card ux-class-blueprint">',1)
        label='<section class="ux-class-section-label"><p class="eyebrow">EXAM CONTEXT</p><h2>Assessment structure</h2></section>'
        text=text.replace('{% endblock %}',label+'\n'+blueprint+'\n</section>\n{% endblock %}',1)
    else:
        text=text.replace('{% endblock %}','</section>\n{% endblock %}',1)
    path.write_text(text,encoding='utf-8')


def _refine_teacher_navigation(path: Path) -> None:
    text=path.read_text(encoding='utf-8')
    desktop_old='''<a href="{{url_for('teacher_dashboard')}}">Dashboard</a><a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Marketplace</a><a href="{{url_for('referral_account')}}">Referrals</a><a href="{{url_for('academic_messages_inbox')}}">Messages</a><a href="{{url_for('institution_dashboard')}}">Institution</a><a href="{{url_for('knowledge_home')}}">Knowledge Hub</a><a href="{{url_for('account_settings')}}">Settings</a><a href="{{url_for('logout')}}">Logout</a>'''
    desktop_new='''<a href="{{url_for('teacher_dashboard')}}">Home</a><a href="{{url_for('academic_messages_inbox')}}">Messages</a><a href="{{url_for('institution_dashboard')}}">Institution</a><a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Corner</a><a href="{{url_for('knowledge_home')}}">Resources</a><details class="ux-teacher-nav-menu"><summary>More</summary><div><a href="{{url_for('referral_account')}}">Referrals</a><a href="{{url_for('account_settings')}}">Settings</a><a href="{{url_for('logout')}}">Logout</a></div></details>'''
    if desktop_old not in text:
        raise SystemExit('UX_TEACHER_DESKTOP_NAV_BASELINE_MISSING')
    text=text.replace(desktop_old,desktop_new,1)

    mobile_old='''<a href="{{url_for('teacher_dashboard')}}">Teacher Dashboard</a><a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Marketplace</a><a href="{{url_for('academic_messages_inbox')}}">Messages</a><a href="{{url_for('institution_dashboard')}}">Institution</a><a href="{{url_for('knowledge_home')}}">Knowledge Hub</a><a href="{{url_for('account_settings')}}">Settings</a><a href="{{url_for('logout')}}">Logout</a>'''
    mobile_new='''<a href="{{url_for('teacher_dashboard')}}">Teacher Home</a><a href="{{url_for('academic_messages_inbox')}}">Messages</a><a href="{{url_for('institution_dashboard')}}">Institution</a><a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Corner</a><a href="{{url_for('knowledge_home')}}">Resources</a><a href="{{url_for('referral_account')}}">Referrals</a><a href="{{url_for('account_settings')}}">Settings</a><a href="{{url_for('logout')}}">Logout</a>'''
    if mobile_old not in text:
        raise SystemExit('UX_TEACHER_MOBILE_NAV_BASELINE_MISSING')
    text=text.replace(mobile_old,mobile_new,1)

    if 'ux-teacher-nav-menu' not in text:
        raise SystemExit('UX_TEACHER_NAV_POSTCHECK_FAILED')
    path.write_text(text,encoding='utf-8')


def apply_teacher_workspace(root: Path) -> None:
    teacher=root/'templates'/'teacher.html'
    classroom=root/'templates'/'classroom.html'
    base=root/'templates'/'base.html'
    for path in (teacher,classroom,base):
        if not path.is_file():
            raise SystemExit('UX_TEACHER_REQUIRED_FILE_MISSING:'+path.name)
    _refine_teacher_template(teacher)
    _refine_classroom_template(classroom)
    _refine_teacher_navigation(base)

    teacher_text=teacher.read_text(encoding='utf-8')
    classroom_text=classroom.read_text(encoding='utf-8')
    base_text=base.read_text(encoding='utf-8')
    checks={
        'teacher':['TEACHER HOME','PRIORITY TODAY','Classes at a glance','Teacher tools and programme context'],
        'classroom':['CLASS OVERVIEW','RECOMMENDED NEXT STEP','Assessment structure'],
        'base':['Teacher Corner','ux-teacher-nav-menu'],
    }
    missing=[]
    for label,tokens in checks.items():
        hay={'teacher':teacher_text,'classroom':classroom_text,'base':base_text}[label]
        missing.extend(f'{label}:{token}' for token in tokens if token not in hay)
    if missing:
        raise SystemExit('UX_TEACHER_POSTBUILD_CONTROL_MISSING:'+','.join(missing))
    print('SCOREMAX_UX_TEACHER_WORKSPACE_REFINED dashboard=true classroom=true nav=true teacher_corner_reused=true marketplace_preserved=true referrals_preserved=true',flush=True)
