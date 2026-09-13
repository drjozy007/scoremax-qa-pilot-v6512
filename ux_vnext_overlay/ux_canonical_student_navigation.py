from __future__ import annotations

import re
from pathlib import Path

_MARKER='SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V6_VISIBLE_FALLBACK'

_CANONICAL_NAV=r'''  <nav class="subject-quick-strip" aria-label="Subject selector">
    <!-- SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V6_VISIBLE_FALLBACK -->
    <a class="subject-all {{'active' if not active_subject_global else ''}}" href="{{url_for('subject_browser')}}">All subjects</a>
    {% for s in subject_nav_global %}
      {% if s.subject not in ['English','Logical Reasoning','MDCAT'] %}
      <a class="{{'active' if (active_subject_global|lower)==(s.subject|lower) else ''}} state-{{s.access_state|lower}}" href="{{url_for('access_account',locked_subject=s.subject) if s.access_state=='LOCKED' else url_for('subject_detail',subject=s.subject)}}">
        {{s.subject}}{% if s.access_state=='LOCKED' %}<small>Upgrade</small>{% elif s.availability=='COMING_SOON' %}<small>Soon</small>{% elif s.answered %}<small>{{s.accuracy|round(0)|int}}%</small>{% endif %}
      </a>
      {% endif %}
    {% endfor %}
    {% set mdcat_track = request.view_args and request.view_args.get('track')=='mdcat' %}
    {% set mdcat_subject = request.view_args.get('subject') if mdcat_track else '' %}
    <a class="{{'active' if mdcat_track and (request.endpoint=='ux_catalogue_track' or mdcat_subject not in ['English','Logical Reasoning']) else ''}}" href="{{url_for('ux_catalogue_track',track='mdcat')}}">MDCAT</a>
    <a class="{{'active' if mdcat_track and mdcat_subject=='Logical Reasoning' else ''}}" href="{{url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning')}}">Logical Reasoning</a>
    <a class="{{'active' if mdcat_track and mdcat_subject=='English' else ''}}" href="{{url_for('ux_catalogue_subject',track='mdcat',subject='English')}}">English</a>
  </nav>'''

_CANONICAL_JS="""function addPremedTabs(){
  const strip=document.querySelector('.student-context-stack .subject-quick-strip');
  if(!strip)return;
  const routes=[
    ['MDCAT','/student/catalogue/mdcat'],
    ['Logical Reasoning','/student/catalogue/mdcat/Logical%20Reasoning'],
    ['English','/student/catalogue/mdcat/English']
  ];
  routes.forEach(([name,href])=>{
    let a=[...strip.querySelectorAll('a')].find(x=>(x.textContent||'').trim()===name);
    if(!a){a=document.createElement('a');a.textContent=name;strip.appendChild(a);}
    a.href=href;
    a.style.display='flex';
  });
}
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


def apply_canonical_student_navigation(root: Path) -> None:
    _patch_base_template(root)
    _patch_visible_js_fallback(root)

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

    required_js=(
        "['MDCAT','/student/catalogue/mdcat']",
        "['Logical Reasoning','/student/catalogue/mdcat/Logical%20Reasoning']",
        "['English','/student/catalogue/mdcat/English']",
        "a.style.display='flex'",
    )
    missing_js=[token for token in required_js if token not in batch]
    if missing_js:
        raise SystemExit('SCOREMAX_VISIBLE_NAV_FALLBACK_MISSING:'+','.join(missing_js))

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
        'server_base=true visible_js_fallback=true idempotent=true '
        'mdcat=/student/catalogue/mdcat '
        'logical_reasoning=/student/catalogue/mdcat/Logical_Reasoning '
        'english=/student/catalogue/mdcat/English '
        'legacy_hash=false direct_routes=true',
        flush=True,
    )
