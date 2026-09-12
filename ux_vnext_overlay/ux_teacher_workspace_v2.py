from __future__ import annotations

import re
from pathlib import Path

from ux_vnext_overlay.ux_teacher_workspace_compat import apply_teacher_workspace as apply_teacher_workspace_v1


V2_STYLE = r'''<style id="ux-teacher-workspace-v2-style">
.ux-teacher-home .ux-teacher-actions a.ux-primary-action{background:linear-gradient(135deg,#2f7f7d,#3fa6a3);border-color:#2f7f7d;color:#fff;box-shadow:0 8px 20px rgba(47,127,125,.18)}
.ux-teacher-home .ux-teacher-actions a.ux-primary-action:after{color:#fff}.ux-teacher-home .ux-teacher-actions a.ux-primary-action:hover{background:linear-gradient(135deg,#286f6d,#378f8d);border-color:#286f6d}
.ux-class-quick-quiz{margin:0 0 12px;border:1px solid #cfe5e3;border-top:5px solid #3fa6a3;background:linear-gradient(135deg,#edf9f7,#fff 66%)}
.ux-class-quick-quiz .ux-quiz-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:10px}.ux-class-quick-quiz .ux-quiz-head h2{margin:.1rem 0 .25rem;color:#2f7f7d;font-size:1.25rem}.ux-class-quick-quiz .ux-quiz-head p{margin:0;color:#60706d;font-size:.74rem}
.ux-class-quick-quiz .ux-all-students{display:inline-flex;align-items:center;padding:7px 10px;border-radius:999px;background:#fff;border:1px solid #cfe5e3;color:#286f6d;font-size:.7rem;font-weight:850;white-space:nowrap}.ux-class-quick-quiz .ux-quiz-submit{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.ux-class-quick-quiz .ux-quiz-submit small{color:#6b7875}
.ux-teacher-referrals-brand .referral-hero{position:relative;overflow:hidden;border:1px solid #bcdedb;border-top:6px solid #2f7f7d;background:linear-gradient(135deg,#eaf8f6 0%,#f8fcff 58%,#fff8e8 100%);box-shadow:0 10px 28px rgba(47,127,125,.09)}
.ux-teacher-referrals-brand .referral-hero:after{content:'';position:absolute;width:180px;height:180px;border-radius:50%;right:-70px;top:-90px;background:radial-gradient(circle,rgba(214,167,77,.28),rgba(214,167,77,0) 70%);pointer-events:none}.ux-teacher-referrals-brand .referral-hero .eyebrow{color:#2f7f7d;font-weight:900}.ux-teacher-referrals-brand .referral-hero h1{max-width:780px;color:#173f3d;letter-spacing:-.025em}.ux-teacher-referrals-brand .referral-hero .muted{max-width:850px;color:#536966}
.ux-referral-hero-actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:14px}.ux-referral-code-chip{display:inline-flex;align-items:center;gap:8px;padding:9px 12px;border-radius:12px;background:#fff;border:1px solid #bcdedb;color:#315b58;font-size:.72rem;box-shadow:0 4px 12px rgba(47,127,125,.06)}.ux-referral-code-chip strong{font-size:.9rem;color:#2f7f7d;letter-spacing:.04em}.ux-referral-share-link{display:inline-flex;align-items:center;padding:9px 13px;border-radius:12px;background:#2f7f7d;color:#fff!important;text-decoration:none;font-size:.72rem;font-weight:900}.ux-referral-share-link:hover{background:#286f6d}
.ux-teacher-referrals-brand .referral-link-grid>.card{border-top:4px solid #3fa6a3;background:linear-gradient(180deg,#fff,#fbfefd)}.ux-teacher-referrals-brand .referral-link-grid>.card:nth-child(2){border-top-color:#d6a74d}.ux-teacher-referrals-brand .referral-code{display:inline-block;padding:6px 10px;border-radius:10px;background:#eaf8f6;color:#236765}.ux-teacher-referrals-brand .referral-link-grid .btn.alt{background:#edf8f7;border-color:#bcdedb;color:#236765;font-weight:850}.ux-teacher-referrals-brand .referral-link-grid .btn.alt:hover{background:#dff2f0}
.ux-teacher-referrals-brand .grid4 .metric{border-top:4px solid #3fa6a3;border-radius:14px}.ux-teacher-referrals-brand .grid4 .metric:nth-child(even){border-top-color:#d6a74d}.ux-teacher-referrals-brand .referral-money-strip{border-radius:14px;background:linear-gradient(135deg,#edf8f7,#fff9ec);border:1px solid #d9e9e6}
@media(max-width:760px){.ux-class-quick-quiz .ux-quiz-head{flex-direction:column}.ux-referral-hero-actions{align-items:stretch}.ux-referral-code-chip,.ux-referral-share-link{justify-content:center}}
</style>'''


def _replace_role_block(text: str, role_pattern: str, next_pattern: str, replacement: str, label: str) -> str:
    rx = re.compile(r"(" + role_pattern + r"\s*)(.*?)(\s*" + next_pattern + r")", re.S)
    matches = list(rx.finditer(text))
    if len(matches) != 1:
        raise SystemExit(f'UX_TEACHER_V2_{label}_MISMATCH:{len(matches)}')
    m = matches[0]
    return text[:m.start()] + m.group(1) + replacement + m.group(3) + text[m.end():]


def _flatten_teacher_navigation(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    desktop = '''<a href="{{url_for('teacher_dashboard')}}">Home</a><a href="{{url_for('teacher_dashboard')}}#ux-my-classes">Classes</a><a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Corner</a><a href="{{url_for('referral_account')}}">Referrals</a><a href="{{url_for('academic_messages_inbox')}}">Messages</a><a href="{{url_for('knowledge_home')}}">Resources</a><a href="{{url_for('institution_dashboard')}}">Institution</a><a href="{{url_for('account_settings')}}">Settings</a><a href="{{url_for('logout')}}">Logout</a>'''
    text = _replace_role_block(
        text,
        r"\{% elif session\.get\('role'\)=='teacher' %\}",
        r"\{% elif session\.get\('role'\)=='parent' %\}",
        desktop,
        'DESKTOP_NAV',
    )
    mobile = '''<a href="{{url_for('teacher_dashboard')}}">Teacher Home</a><a href="{{url_for('teacher_dashboard')}}#ux-my-classes">Classes</a><a href="{{url_for('teacher_marketplace_dashboard')}}">Teacher Corner</a><a href="{{url_for('referral_account')}}">Referrals</a><a href="{{url_for('academic_messages_inbox')}}">Messages</a><a href="{{url_for('knowledge_home')}}">Resources</a><a href="{{url_for('institution_dashboard')}}">Institution</a><a href="{{url_for('account_settings')}}">Settings</a><a href="{{url_for('logout')}}">Logout</a>'''
    text = _replace_role_block(
        text,
        r"\{% elif session\.get\('user_id'\) and session\.get\('role'\)=='teacher' %\}",
        r"\{% elif session\.get\('user_id'\) and session\.get\('role'\)=='parent' %\}",
        mobile,
        'MOBILE_NAV',
    )
    # The earlier dropdown is deliberately removed: desktop has sufficient width for direct teacher actions.
    if '<details class="ux-teacher-nav-menu">' in text:
        raise SystemExit('UX_TEACHER_V2_DROPDOWN_SURVIVED')
    for token in ('>Classes</a>', '>Referrals</a>', '>Settings</a>', '>Logout</a>'):
        if token not in text:
            raise SystemExit('UX_TEACHER_V2_DIRECT_NAV_MISSING:' + token)
    path.write_text(text, encoding='utf-8')


def _promote_teacher_class_actions(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    old_actions = re.compile(r'<nav class="ux-teacher-actions" aria-label="Teacher quick actions">.*?</nav>', re.S)
    if len(old_actions.findall(text)) != 1:
        raise SystemExit('UX_TEACHER_V2_QUICK_ACTIONS_MISMATCH')
    actions = '''<nav class="ux-teacher-actions" aria-label="Teacher quick actions">
<a href="#ux-my-classes">My classes</a>
<a class="ux-primary-action" href="#ux-my-classes">Issue a quiz</a>
<a href="{{url_for('referral_account')}}">Referrals</a>
<a href="{{url_for('academic_messages_inbox')}}">Messages</a>
</nav>'''
    text = old_actions.sub(actions, text, count=1)
    text = text.replace(
        'Open a class to view progress, weak areas and assignment activity.',
        'Open a class to manage students, issue a quiz, view progress and track assignments.',
        1,
    )
    if 'Open class →' not in text:
        raise SystemExit('UX_TEACHER_V2_CLASS_ACTION_BASELINE_MISSING')
    text = text.replace('Open class →', 'Manage class / issue quiz →')
    if V2_STYLE not in text:
        marker = '<section class="ux-teacher-home">'
        if marker not in text:
            raise SystemExit('UX_TEACHER_V2_HOME_STYLE_ANCHOR_MISSING')
        text = text.replace(marker, V2_STYLE + '\n' + marker, 1)
    path.write_text(text, encoding='utf-8')


def _add_quick_quiz(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    if 'id="issue-quiz"' in text:
        return
    anchor = "\n{% if priority %}\n<div class='card next-action-card'>"
    if anchor not in text:
        raise SystemExit('UX_TEACHER_V2_QUIZ_ANCHOR_MISSING')
    quiz = '''
<section class="card ux-class-quick-quiz" id="issue-quiz">
  <div class="ux-quiz-head"><div><p class="eyebrow">QUICK ACTION</p><h2>Issue a quiz</h2><p>Create a whole-class quiz from the governed {{cl.subject}} question bank.</p></div><span class="ux-all-students">{{students|length}} students</span></div>
  <form method="post" action="{{url_for('teacher_assign',cid=cl.id)}}" class="form-grid">
    {% if csrf_token %}<input type="hidden" name="_csrf_token" value="{{csrf_token()}}">{% endif %}
    <input type="hidden" name="subject" value="{{cl.subject}}"><input type="hidden" name="level" value="{{cl.level}}"><input type="hidden" name="focus_type" value=""><input type="hidden" name="focus_name" value="">
    <label>Quiz title<input name="title" value="{{cl.subject}} class quiz"></label>
    <label>Questions<input type="number" min="3" max="30" name="question_count" value="10"></label>
    <label>Mode<select name="assessment_mode"><option value="exam" selected>Quiz / test</option><option value="practice">Practice</option></select></label>
    <label>Duration (minutes)<input type="number" min="1" name="duration_minutes" value="15"></label>
    <label>Due date/time<input type="datetime-local" name="due_at"></label>
    <div class="full ux-quiz-submit"><button class="btn" type="submit">Issue quiz to class</button><small>All students currently in this class will receive it.</small></div>
  </form>
</section>
'''
    text = text.replace(anchor, '\n' + quiz + anchor, 1)
    if V2_STYLE not in text:
        marker = '<section class="ux-classroom-home">'
        if marker not in text:
            raise SystemExit('UX_TEACHER_V2_CLASS_STYLE_ANCHOR_MISSING')
        text = text.replace(marker, V2_STYLE + '\n' + marker, 1)
    path.write_text(text, encoding='utf-8')


def _brand_teacher_referrals(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    opening = '<section class="page-shell referral-page-v640">'
    replacement = '<section class="page-shell referral-page-v640 {{\'ux-teacher-referrals-brand\' if user.role==\'teacher\' else \'\'}}">'
    if opening not in text:
        raise SystemExit('UX_TEACHER_V2_REFERRAL_PAGE_ANCHOR_MISSING')
    text = text.replace(opening, replacement, 1)
    hero_end = '''      <p class="muted">Your direct student reward and the smaller one-level teacher-introduction reward are calculated only from eligible cleared payments. Registration alone never creates commission.</p>'''
    if hero_end not in text:
        raise SystemExit('UX_TEACHER_V2_REFERRAL_HERO_ANCHOR_MISSING')
    hero_actions = '''      <p class="muted">Your direct student reward and the smaller one-level teacher-introduction reward are calculated only from eligible cleared payments. Registration alone never creates commission.</p>
      <div class="ux-referral-hero-actions"><span class="ux-referral-code-chip">Your code <strong>{{user.own_referral_code}}</strong></span><a class="ux-referral-share-link" href="#ux-referral-links">Share now ↓</a></div>'''
    text = text.replace(hero_end, hero_actions, 1)
    link_grid = '<section class="grid referral-link-grid">'
    if link_grid not in text:
        raise SystemExit('UX_TEACHER_V2_REFERRAL_LINK_GRID_MISSING')
    text = text.replace(link_grid, '<section class="grid referral-link-grid" id="ux-referral-links">', 1)
    style = "{% if user.role=='teacher' %}\n" + V2_STYLE + "\n{% endif %}\n"
    title_marker = '{% block content %}\n'
    if title_marker not in text:
        raise SystemExit('UX_TEACHER_V2_REFERRAL_STYLE_ANCHOR_MISSING')
    text = text.replace(title_marker, title_marker + style, 1)
    path.write_text(text, encoding='utf-8')


def apply_teacher_workspace(root: Path) -> None:
    # Start from the already-qualified Teacher Corner refinement, then make only bounded UX changes.
    apply_teacher_workspace_v1(root)
    teacher = root / 'templates' / 'teacher.html'
    classroom = root / 'templates' / 'classroom.html'
    base = root / 'templates' / 'base.html'
    referrals = root / 'templates' / 'referrals.html'
    for path in (teacher, classroom, base, referrals):
        if not path.is_file():
            raise SystemExit('UX_TEACHER_V2_REQUIRED_FILE_MISSING:' + path.name)

    _flatten_teacher_navigation(base)
    _promote_teacher_class_actions(teacher)
    _add_quick_quiz(classroom)
    _brand_teacher_referrals(referrals)

    teacher_text = teacher.read_text(encoding='utf-8')
    classroom_text = classroom.read_text(encoding='utf-8')
    base_text = base.read_text(encoding='utf-8')
    referral_text = referrals.read_text(encoding='utf-8')
    checks = {
        'teacher': ('Issue a quiz', 'Manage class / issue quiz', 'Referrals'),
        'classroom': ('id="issue-quiz"', "url_for('teacher_assign',cid=cl.id)", 'Issue quiz to class', 'name="level" value="{{cl.level}}"'),
        'base': ('>Classes</a>', '>Referrals</a>', '>Logout</a>'),
        'referrals': ('ux-teacher-referrals-brand', 'ux-referral-code-chip', 'ux-referral-links'),
    }
    haystacks = {'teacher': teacher_text, 'classroom': classroom_text, 'base': base_text, 'referrals': referral_text}
    missing = [f'{label}:{token}' for label, tokens in checks.items() for token in tokens if token not in haystacks[label]]
    if '<details class="ux-teacher-nav-menu">' in base_text:
        missing.append('base:teacher-dropdown-survived')
    if missing:
        raise SystemExit('UX_TEACHER_V2_POSTBUILD_CONTROL_MISSING:' + ','.join(missing))
    print('SCOREMAX_UX_TEACHER_WORKSPACE_V2_PASS flat_nav=true class_quiz_promoted=true assignment_engine_reused=true referrals_branded=true referral_engine_unchanged=true', flush=True)
