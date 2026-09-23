from __future__ import annotations

import re
from pathlib import Path

_MARKER='SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V6_VISIBLE_FALLBACK'

_CANONICAL_NAV=r'''  <nav class="subject-quick-strip" aria-label="Subject selector" data-programme="{{active_programme_global}}">
    <!-- SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V6_VISIBLE_FALLBACK -->
    <a class="subject-all {{'active' if not active_subject_global else ''}}" href="{{url_for('subject_browser')}}">All subjects</a>
    {% for s in subject_nav_global %}
      <a data-subject="{{s.subject}}" class="{{'active' if (active_subject_global|lower)==(s.subject|lower) else ''}} state-{{s.access_state|lower}}" href="{{url_for('access_account',locked_subject=s.subject) if s.access_state=='LOCKED' else s.url}}">
        {{s.subject}}{% if s.access_state=='LOCKED' %}<small>Upgrade</small>{% elif s.answered %}<small>{{s.accuracy|round(0)|int}}%</small>{% endif %}
      </a>
    {% endfor %}
    {% if active_programme_global!='MDCAT' %}
    <a data-pathway="mdcat" href="{{url_for('ux_catalogue_track',track='mdcat')}}">MDCAT</a>
    <a data-pathway="mdcat" href="{{url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning')}}">Logical Reasoning</a>
    <a data-pathway="mdcat" href="{{url_for('ux_catalogue_subject',track='mdcat',subject='English')}}">English</a>
    {% endif %}
  </nav>'''

# The native server surface is authoritative, including the intentional absence of
# navigation during an assessment. Cosmetic scripts must not invent another list.
_CANONICAL_JS="""function addPremedTabs(){/* Subject navigation is server-owned. */}
function addOverall()"""


def _patch_base_template(root: Path) -> None:
    path=Path(root)/'templates'/'base.html'
    if not path.is_file():
        raise SystemExit('SCOREMAX_BASE_TEMPLATE_MISSING')
    text=path.read_text(encoding='utf-8')
    rx=re.compile(r'  <nav class="subject-quick-strip" aria-label="Subject selector">.*?  </nav>',re.S)
    text,count=rx.subn(_CANONICAL_NAV,text,count=1)
    if count!=1:
        raise SystemExit(f'SCOREMAX_BASE_SUBJECT_NAV_ANCHOR_MISMATCH:matches={count}')
    path.write_text(text,encoding='utf-8')


def _patch_visible_js_fallback(root: Path) -> None:
    path=Path(root)/'ux_student_batch.py'
    if not path.is_file():
        raise SystemExit('SCOREMAX_STUDENT_BATCH_RUNTIME_MISSING')
    text=path.read_text(encoding='utf-8')
    rx=re.compile(r"function addPremedTabs\(\)\{.*?\}\nfunction addOverall\(\)",re.S)
    text,count=rx.subn(_CANONICAL_JS,text,count=1)
    if count!=1:
        raise SystemExit(f'SCOREMAX_PREMED_TAB_SCRIPT_MISMATCH:matches={count}')
    path.write_text(text,encoding='utf-8')


def _preserve_native_context_controls(root: Path) -> None:
    """Keep native forms and links; remove competing profile-based JS navigation."""
    path=Path(root)/'ux_staging_routes.py'
    text=path.read_text(encoding='utf-8')
    replacements=(
        (".student-context-stack .programme-context-strip{display:none!important}", ""),
        ("stack.querySelectorAll('.programme-context-strip').forEach(x=>x.remove());", ""),

    )
    for old,new in replacements:
        if text.count(old)!=1:
            raise SystemExit('SCOREMAX_NATIVE_CONTEXT_OVERLAY_ANCHOR_MISMATCH')
        text=text.replace(old,new,1)
    # A missing subject nav can mean an assessment or deliberately non-study page.
    # Never reconstruct it from home-profile subjects or defeat that absence.
    pattern=r"function ensureSubjects\(\)\{.*?(?=\nfunction refineMastery\(\))"
    owned="""function ensureSubjects(){document.querySelectorAll('.home-subject-card').forEach(a=>{
if(!a.querySelector('.ux-open-chapters')){const x=document.createElement('span');x.className='ux-open-chapters';x.textContent='Open chapters →';a.appendChild(x);}
});}"""
    text,count=re.subn(pattern,owned,text,count=1,flags=re.S)
    if count!=1:raise SystemExit('SCOREMAX_SUBJECT_FALLBACK_ANCHOR_MISMATCH')
    compile(text,str(path),'exec')
    path.write_text(text,encoding='utf-8')
    if any(old in text for old,_ in replacements):
        raise SystemExit('SCOREMAX_DESTRUCTIVE_NAVIGATION_OVERLAY_SURVIVED')
    # The native programme POST already owns access checks and the state change.
    # Its safe redirect helper lives in the shared request-security module.
    app_path=Path(root)/'app.py'
    app_text=app_path.read_text(encoding='utf-8')
    old="    target=safe_relative_path(request.form.get('return_to') or '')"
    new="    target=request_security.safe_relative_path(request.form.get('return_to') or '')"
    if app_text.count(old)!=1:
        raise SystemExit('SCOREMAX_PROGRAMME_REDIRECT_HELPER_ANCHOR_MISMATCH')
    app_text=app_text.replace(old,new,1)
    compile(app_text,str(app_path),'exec')
    app_path.write_text(app_text,encoding='utf-8')
    print('SCOREMAX_NATIVE_CONTEXT_BROWSER_AUTHORITY_PASS programme_forms_preserved=true governed_subject_links_preserved=true cosmetic_replacement=false native_safe_redirect=true',flush=True)


def _patch_native_subject_context(root: Path) -> None:
    path=Path(root)/'app.py';text=path.read_text(encoding='utf-8')
    old="'learn':{'subject_browser','subject_detail','chapter_page','weak_areas_page','mastery_page','written_practice_home','written_question_page'},"
    new="'learn':{'subject_browser','subject_detail','chapter_page','weak_areas_page','mastery_page','written_practice_home','written_question_page','ux_student_learn','ux_catalogue_home','ux_catalogue_track','ux_catalogue_subject'},"
    if text.count(old)!=1:raise SystemExit('SCOREMAX_SUBJECT_CONTEXT_ENDPOINT_ANCHOR')
    text=text.replace(old,new,1)
    anchor="                active_programme_label=programme_short_label(active_programme) if 'programme_short_label' in globals() else active_programme"
    insert="""                # Reuse the existing catalogue/profile filter used by Learn cards.
                # Existing scoped statistics/access checks remain authoritative.
                from ux_student_batch import _subjects_for_student, _programme_track
                track=_programme_track(active_programme)
                if track:
                    existing={item['subject'].casefold():item for item in subject_nav}
                    subject_nav=[dict(existing.get(name.casefold()) or {
                      'subject':name,'answered':0,'accuracy':0,'availability':'COMING_SOON',
                      'access_state':'COMING_SOON'},
                      url=url_for('ux_catalogue_subject',track='mdcat',subject=name) if track=='mdcat'
                          else url_for('subject_detail',subject=name))
                      for name in _subjects_for_student(c,session['user_id'])]
                else:
                    subject_nav=[dict(item,url=url_for('subject_detail',subject=item['subject'])) for item in subject_nav]
                if endpoint=='ux_catalogue_subject':active_subject=str(view_args.get('subject') or '').strip()
"""
    if text.count(anchor)!=1:raise SystemExit('SCOREMAX_SUBJECT_CONTEXT_PROGRAMME_ANCHOR')
    text=text.replace(anchor,insert+anchor,1)
    compile(text,str(path),'exec');path.write_text(text,encoding='utf-8')


def _patch_non_obstructive_coach(root: Path) -> None:
    path=Path(root)/'templates'/'base.html';text=path.read_text(encoding='utf-8')
    start=text.index("{% if session.get('role')=='student' and show_scoremax_coach_global and scoremax_coach_global %}")
    end=text.index('{% endif %}',start)+len('{% endif %}')
    block=text[start:end]
    block=block.replace('and scoremax_coach_global %}',"and scoremax_coach_global and request.endpoint not in ['ux_content_review_staged','ux_content_review_staged_question','ux_content_review_question','written_question_page'] %}")
    block=block.replace('aria-expanded="false"','aria-expanded="false" aria-controls="coachDockPanel"').replace('<div class="coach-dock-panel">','<div class="coach-dock-panel" id="coachDockPanel">')
    text=text[:start]+text[end:]
    anchor='<main id="mainContent"'
    if text.count(anchor)!=1:raise SystemExit('SCOREMAX_COACH_FLOW_ANCHOR')
    text=text.replace(anchor,block+'\n'+anchor,1)
    path.write_text(text,encoding='utf-8')

    # Reuse the existing cosmetic style owner, not a new override stylesheet.
    runtime=Path(root)/'ux_student_batch.py';style=runtime.read_text(encoding='utf-8')
    old='.coach-toggle{position:fixed!important;left:12px!important;right:auto!important;top:52%!important;bottom:auto!important;transform:translateY(-50%)!important;z-index:74!important}.coach-toggle:hover{transform:translateY(-50%) scale(1.02)!important}'
    new='.coach-dock{position:static!important;margin:8px max(18px,calc((100vw - 1180px)/2));z-index:auto!important}.coach-toggle{position:static!important;transform:none!important;min-height:44px}.coach-toggle:hover{transform:none!important}.coach-dock-panel{position:static!important;margin-top:8px;width:auto;max-width:600px}'
    if style.count(old)!=1:raise SystemExit('SCOREMAX_COACH_STYLE_ANCHOR')
    style=style.replace(old,new,1).replace('.coach-toggle{left:7px!important;top:48%!important}','')
    style=style.replace('.ux-contact-fixed{position:fixed;','.ux-contact-fixed{position:static;')
    compile(style,str(runtime),'exec');runtime.write_text(style,encoding='utf-8')
    # Keep Save available as an optional in-flow offer; no overlay during question review.
    old="['take_test_v4','assessment_review_v4','qa_synthetic_session']"
    new="['take_test_v4','assessment_review_v4','qa_synthetic_session','ux_content_review_staged','ux_content_review_staged_question','ux_content_review_question','written_question_page']"
    if text.count(old)!=1:raise SystemExit('SCOREMAX_INSTALL_SURFACE_ANCHOR')
    text=text.replace(old,new,1)
    button='  <button id="scoremaxInstallButton" type="button">Save</button>'
    if text.count(button)!=1:raise SystemExit('SCOREMAX_INSTALL_LATER_ANCHOR')
    text=text.replace(button,button+'\n  <button id="scoremaxInstallLater" type="button">Later</button>',1)
    path.write_text(text,encoding='utf-8')


def apply_canonical_student_navigation(root: Path) -> None:
    _patch_base_template(root)
    _patch_visible_js_fallback(root)
    _preserve_native_context_controls(root)
    _patch_native_subject_context(root)
    _patch_non_obstructive_coach(root)

    base=(Path(root)/'templates'/'base.html').read_text(encoding='utf-8')
    batch=(Path(root)/'ux_student_batch.py').read_text(encoding='utf-8')

    required_base=(
        _MARKER,
        "url_for('ux_catalogue_track',track='mdcat')",
        "url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning')",
        "url_for('ux_catalogue_subject',track='mdcat',subject='English')",
        '>MDCAT</a>',
        '>Logical Reasoning</a>',
        '>English</a>',
    )
    missing=[token for token in required_base if token not in base]
    if missing:
        raise SystemExit('SCOREMAX_BASE_NAV_CONTROL_MISSING:'+','.join(missing))

    if 'Subject navigation is server-owned.' not in batch:
        raise SystemExit('SCOREMAX_SERVER_SUBJECT_NAV_OWNER_MISSING')

    forbidden=(
        "LEARN+'#'+hash",
        "[['MDCAT','mdcat-route']",
        "a.href=LEARN+'#'",
        '_canonical_student_subject_nav(',
    )
    survived=[token for token in forbidden if token in batch]
    if survived:
        raise SystemExit('SCOREMAX_DUPLICATE_NAVIGATION_LOGIC_SURVIVED:'+','.join(survived))

    print(
        'SCOREMAX_CANONICAL_STUDENT_NAV_PASS '
        'server_base=true client_recreation=false programme_scoped=true '
        'mdcat=/student/catalogue/mdcat '
        'logical_reasoning=/student/catalogue/mdcat/Logical_Reasoning '
        'english=/student/catalogue/mdcat/English '
        'legacy_hash=false direct_routes=true',
        flush=True,
    )
