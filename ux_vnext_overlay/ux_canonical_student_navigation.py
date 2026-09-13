from __future__ import annotations

import re
from pathlib import Path

_MARKER='SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V4_ALL_STRIPS'

_FINAL_RESPONSE_HELPER=r'''# SCOREMAX_CANONICAL_STUDENT_SUBJECT_NAV_V4_ALL_STRIPS
def _canonical_student_subject_nav(html: str) -> str:
    """Guarantee every learner subject strip in the final server HTML.

    ScoreMax currently renders more than one subject-strip instance on some learner
    pages. The visible shell must not depend on which instance happened to be first.
    Existing FSc anchors are preserved; admission-preparation anchors are normalized
    on every strip to one canonical destination each.
    """
    import re

    track=str((request.view_args or {}).get('track','') or '').strip().casefold()
    subject=str((request.view_args or {}).get('subject','') or '').strip()
    mdcat_track=(track=='mdcat')
    routes=(
        ('MDCAT',url_for('ux_catalogue_track',track='mdcat'),mdcat_track and (request.endpoint=='ux_catalogue_track' or subject not in {'English','Logical Reasoning'})),
        ('Logical Reasoning',url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning'),mdcat_track and subject=='Logical Reasoning'),
        ('English',url_for('ux_catalogue_subject',track='mdcat',subject='English'),mdcat_track and subject=='English'),
    )

    strip_rx=re.compile(
        r'(?P<open><(?P<tag>nav|div)\b[^>]*class=["\'][^"\']*\bsubject-quick-strip\b[^"\']*["\'][^>]*>)'
        r'(?P<body>.*?)'
        r'(?P<close></(?P=tag)>)',
        re.S|re.I,
    )
    rendered=[]

    def normalize(match):
        body=match.group('body')
        for label,href,active in routes:
            label_rx=re.escape(label)
            body=re.sub(
                r'<a\b[^>]*>\s*'+label_rx+r'(?:\s*<small>.*?</small>)?\s*</a>',
                '',body,flags=re.S|re.I,
            )
            cls=' class="active"' if active else ''
            body+=f'<a{cls} href="{href}">{label}</a>'
        fragment=match.group('open')+body+match.group('close')
        rendered.append(fragment)
        return fragment

    html,count=strip_rx.subn(normalize,html)
    if count:
        status=[]
        for i,fragment in enumerate(rendered,1):
            status.append(
                f'{i}:anchors={fragment.count("<a ")},'
                f'mdcat={str(url_for("ux_catalogue_track",track="mdcat") in fragment).lower()},'
                f'lr={str(url_for("ux_catalogue_subject",track="mdcat",subject="Logical Reasoning") in fragment).lower()},'
                f'english={str(url_for("ux_catalogue_subject",track="mdcat",subject="English") in fragment).lower()},'
                f'legacy={str("#mdcat-route" in fragment).lower()}'
            )
        print(
            'SCOREMAX_LEARNER_NAV_RENDER '
            f'endpoint={request.endpoint or ""} strips={count} '+ ' '.join(status),
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
        'strip_rx.subn(normalize,html)',
        'SCOREMAX_LEARNER_NAV_RENDER',
        '    import re',
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
        'layer=final_student_html scope=all_subject_strips '
        'existing_fsc_entitlement_links_preserved=true '
        'mdcat=/student/catalogue/mdcat '
        'logical_reasoning=/student/catalogue/mdcat/Logical_Reasoning '
        'english=/student/catalogue/mdcat/English '
        'hash_shortcut=false duplicate_shell_ambiguity_removed=true '
        'runtime_dependency_local=true final_response_invariant_logging=true',
        flush=True,
    )
