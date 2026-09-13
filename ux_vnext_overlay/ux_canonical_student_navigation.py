from __future__ import annotations

import re
from pathlib import Path

_MARKER='SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V2'

_CANONICAL_SUBJECT_NAV=r'''  <nav class="subject-quick-strip" aria-label="Subject selector">
    <!-- SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V2 -->
    <a class="subject-all {{'active' if request.endpoint=='subject_browser' else ''}}" href="{{url_for('subject_browser')}}">All subjects</a>
    {% for s in subject_nav_global %}
      {% if s.subject not in ['English','Logical Reasoning','MDCAT'] %}
      <a class="{{'active' if request.endpoint=='subject_detail' and (active_subject_global|lower)==(s.subject|lower) else ''}} state-{{s.access_state|lower}}" href="{{url_for('access_account',locked_subject=s.subject) if s.access_state=='LOCKED' else url_for('subject_detail',subject=s.subject)}}">
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


def _patch_subject_strip(root: Path) -> None:
    path=Path(root)/'templates'/'base.html'
    text=path.read_text(encoding='utf-8')
    rx=re.compile(r'  <nav class="subject-quick-strip" aria-label="Subject selector">.*?  </nav>',re.S)
    text,count=rx.subn(_CANONICAL_SUBJECT_NAV,text,count=1)
    if count!=1:
        raise SystemExit(f'SCOREMAX_CANONICAL_SUBJECT_NAV_ANCHOR_MISMATCH:matches={count}')
    path.write_text(text,encoding='utf-8')


def _disable_hash_shortcut(root: Path) -> None:
    path=Path(root)/'ux_student_batch.py'
    text=path.read_text(encoding='utf-8')
    rx=re.compile(r"function addPremedTabs\(\)\{.*?\}\nfunction addOverall\(\)",re.S)
    replacement="function addPremedTabs(){/* canonical server-rendered subject navigation */}\nfunction addOverall()"
    text,count=rx.subn(replacement,text,count=1)
    if count!=1:
        raise SystemExit(f'SCOREMAX_LEGACY_PREMED_TAB_SCRIPT_MISMATCH:matches={count}')
    path.write_text(text,encoding='utf-8')


def apply_canonical_student_navigation(root: Path) -> None:
    _patch_subject_strip(root)
    _disable_hash_shortcut(root)

    base=(Path(root)/'templates'/'base.html').read_text(encoding='utf-8')
    batch=(Path(root)/'ux_student_batch.py').read_text(encoding='utf-8')
    required=(
        _MARKER,
        "url_for('ux_catalogue_track',track='mdcat')",
        "url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning')",
        "url_for('ux_catalogue_subject',track='mdcat',subject='English')",
        '>MDCAT</a>',
        '>Logical Reasoning</a>',
        '>English</a>',
        "request.endpoint=='subject_detail'",
        "request.endpoint=='ux_catalogue_track'",
    )
    missing=[token for token in required if token not in base]
    if missing:
        raise SystemExit('SCOREMAX_CANONICAL_SUBJECT_NAV_CONTROL_MISSING:'+','.join(missing))
    forbidden=(
        "LEARN+'#'+hash",
        "[['MDCAT','mdcat-route']",
        "a.href=LEARN+'#'",
        'nav.has_biology',
        'nav.has_chemistry',
        'nav.has_physics',
    )
    survived=[token for token in forbidden if token in batch or token in base]
    if survived:
        raise SystemExit('SCOREMAX_LEGACY_OR_CONDITIONAL_MDCAT_NAV_SURVIVED:'+','.join(survived))

    print(
        'SCOREMAX_CANONICAL_STUDENT_NAV_PASS '
        'fsc_science=/student/subject/* mdcat=/student/catalogue/mdcat '
        'logical_reasoning=/student/catalogue/mdcat/Logical_Reasoning '
        'english=/student/catalogue/mdcat/English mdcat_always_visible=true '
        'hash_shortcut=false conditional_mdcat_visibility=false '
        'single_routing_contract=true server_rendered=true',
        flush=True,
    )
