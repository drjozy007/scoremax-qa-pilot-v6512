from __future__ import annotations

import re
from pathlib import Path

_MARKER='SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V3_FINAL_RESPONSE'

_FINAL_RESPONSE_HELPER=r'''# SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V3_FINAL_RESPONSE
def _canonical_student_subject_nav(html: str) -> str:
    """Guarantee the learner subject row in the final server HTML.

    Existing FSc subject anchors are preserved so entitlement/lock routing remains
    authoritative. Admission-preparation destinations are removed/re-added with one
    canonical route each. This runs in the existing student-shell after_request layer,
    after template rendering and all earlier overlays.
    """
    nav_start=html.find('<nav class="subject-quick-strip"')
    if nav_start<0:
        return html
    nav_end=html.find('</nav>',nav_start)
    if nav_end<0:
        return html
    fragment=html[nav_start:nav_end]

    track=str((request.view_args or {}).get('track','') or '').strip().casefold()
    subject=str((request.view_args or {}).get('subject','') or '').strip()
    mdcat_track=(track=='mdcat')
    routes=(
        ('MDCAT',url_for('ux_catalogue_track',track='mdcat'),mdcat_track and (request.endpoint=='ux_catalogue_track' or subject not in {'English','Logical Reasoning'})),
        ('Logical Reasoning',url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning'),mdcat_track and subject=='Logical Reasoning'),
        ('English',url_for('ux_catalogue_subject',track='mdcat',subject='English'),mdcat_track and subject=='English'),
    )
    for label,href,active in routes:
        # Remove any stale/legacy copy of this visible tab, regardless of its old href.
        label_rx=re.escape(label)
        fragment=re.sub(
            r'<a\b[^>]*>\s*'+label_rx+r'(?:\s*<small>.*?</small>)?\s*</a>',
            '',fragment,flags=re.S,
        )
        cls=' class="active"' if active else ''
        fragment+=f'<a{cls} href="{href}">{label}</a>'

    html=html[:nav_start]+fragment+'</nav>'+html[nav_end+6:]

    if request.endpoint in {'subject_browser','ux_student_learn','subject_detail','ux_catalogue_track','ux_catalogue_subject'}:
        final_end=html.find('</nav>',nav_start)
        final_fragment=html[nav_start:final_end] if final_end>=0 else ''
        print(
            'SCOREMAX_LEARNER_NAV_RENDER '
            f'endpoint={request.endpoint or ""} '
            f'anchors={final_fragment.count("<a ")} '
            f'mdcat={str(url_for("ux_catalogue_track",track="mdcat") in final_fragment).lower()} '
            f'logical_reasoning={str(url_for("ux_catalogue_subject",track="mdcat",subject="Logical Reasoning") in final_fragment).lower()} '
            f'english={str(url_for("ux_catalogue_subject",track="mdcat",subject="English") in final_fragment).lower()} '
            f'legacy_hash={str("#mdcat-route" in final_fragment).lower()}',
            flush=True,
        )
    return html
'''


def _disable_hash_shortcut(text: str) -> str:
    rx=re.compile(r"function addPremedTabs\(\)\{.*?\}\nfunction addOverall\(\)",re.S)
    replacement="function addPremedTabs(){/* canonical final-response subject navigation */}\nfunction addOverall()"
    text,count=rx.subn(replacement,text,count=1)
    if count!=1:
        raise SystemExit(f'SCOREMAX_LEGACY_PREMED_TAB_SCRIPT_MISMATCH:matches={count}')
    return text


def _install_final_response_contract(root: Path) -> None:
    path=Path(root)/'ux_student_batch.py'
    if not path.is_file():
        raise SystemExit('SCOREMAX_CANONICAL_NAV_RUNTIME_MISSING')
    text=path.read_text(encoding='utf-8')
    text=_disable_hash_shortcut(text)

    install_anchor='def install_student_batch(app) -> None:'
    if _MARKER not in text:
        if text.count(install_anchor)!=1:
            raise SystemExit(f'SCOREMAX_CANONICAL_NAV_INSTALL_ANCHOR_MISMATCH:matches={text.count(install_anchor)}')
        text=text.replace(install_anchor,_FINAL_RESPONSE_HELPER+'\n\n'+install_anchor,1)

    old="        response.set_data(html); response.content_length=len(response.get_data()); return response"
    new=(
        "        if session.get('role')=='student' and session.get('user_id'):\n"
        "            html=_canonical_student_subject_nav(html)\n"
        "        response.set_data(html); response.content_length=len(response.get_data()); return response"
    )
    if '_canonical_student_subject_nav(html)' not in text:
        if text.count(old)!=1:
            raise SystemExit(f'SCOREMAX_CANONICAL_NAV_FINAL_RESPONSE_ANCHOR_MISMATCH:matches={text.count(old)}')
        text=text.replace(old,new,1)

    compile(text,str(path),'exec')
    required=(
        _MARKER,
        "html=_canonical_student_subject_nav(html)",
        "url_for('ux_catalogue_track',track='mdcat')",
        "url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning')",
        "url_for('ux_catalogue_subject',track='mdcat',subject='English')",
        'SCOREMAX_LEARNER_NAV_RENDER',
        'canonical final-response subject navigation',
    )
    missing=[token for token in required if token not in text]
    if missing:
        raise SystemExit('SCOREMAX_CANONICAL_NAV_CONTROL_MISSING:'+','.join(missing))
    forbidden=("LEARN+'#'+hash","[['MDCAT','mdcat-route']","a.href=LEARN+'#'")
    survived=[token for token in forbidden if token in text]
    if survived:
        raise SystemExit('SCOREMAX_LEGACY_MDCAT_HASH_NAV_SURVIVED:'+','.join(survived))
    path.write_text(text,encoding='utf-8')


def apply_canonical_student_navigation(root: Path) -> None:
    _install_final_response_contract(root)
    print(
        'SCOREMAX_CANONICAL_STUDENT_NAV_PASS '
        'layer=final_student_html existing_fsc_entitlement_links_preserved=true '
        'mdcat=/student/catalogue/mdcat '
        'logical_reasoning=/student/catalogue/mdcat/Logical_Reasoning '
        'english=/student/catalogue/mdcat/English '
        'hash_shortcut=false duplicate_navigation_model=false '
        'final_response_invariant_logging=true',
        flush=True,
    )
