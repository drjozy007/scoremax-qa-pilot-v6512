from __future__ import annotations

"""Build-time rectification for programme-specific learner catalogue routing.

The learner catalogue labels remain sourced from ``ux_catalogue_data``. This overlay
only removes cross-programme fallback in the legacy student UX batch and makes the
active programme, rather than the home academic level, authoritative for browsing.
It also preserves a valid learner programme across redeploy/bootstrap and routes
MDCAT subject cards to the dedicated MDCAT catalogue surface.
"""

import re
from pathlib import Path

from ux_vnext_overlay.ux_catalogue_data import CATALOGUES

ROUTING_MARKER = 'SCOREMAX_PROGRAMME_CATALOGUE_ROUTING_V2'
_VALID_PROGRAMMES = ('FSc Part 1', 'FSc Part 2', 'MDCAT')


def programme_track(programme: str) -> str:
    value = (programme or '').strip().casefold()
    if value == 'mdcat':
        return 'mdcat'
    if 'fsc' in value and ('part 1' in value or 'year 1' in value or value in {'fsc 1', 'fsc1'}):
        return 'year11'
    if 'fsc' in value and ('part 2' in value or 'year 2' in value or value in {'fsc 2', 'fsc2'}):
        return 'year12'
    return ''


def _assert_governed_catalogue_contract() -> None:
    expected = {
        ('year11', 'Biology'): (12, 'Biodiversity and Classification'),
        ('mdcat', 'Biology'): (16, 'Acellular Life'),
        ('mdcat', 'Chemistry'): (20, 'Introduction of Fundamental Concepts of Chemistry'),
        ('mdcat', 'Physics'): (16, 'Vectors and Equilibrium'),
        ('mdcat', 'English'): (3, None),
        ('mdcat', 'Logical Reasoning'): (6, None),
    }
    for (track, subject), (count, first_name) in expected.items():
        items = CATALOGUES[track]['subjects'][subject]
        actual_first = items[0]['name'] if items else ''
        if len(items) != count or (first_name is not None and actual_first != first_name):
            raise SystemExit(
                f'SCOREMAX_CATALOGUE_CONTRACT_MISMATCH:{track}:{subject}:'
                f'count={len(items)} first={actual_first}'
            )

    expected_totals = {'year11': 54, 'year12': 50, 'mdcat': 61}
    for track, expected_total in expected_totals.items():
        actual_total = sum(len(items) for items in CATALOGUES[track]['subjects'].values())
        if actual_total != expected_total:
            raise SystemExit(
                f'SCOREMAX_CATALOGUE_TOTAL_MISMATCH:{track}:'
                f'expected={expected_total} actual={actual_total}'
            )


_RUNTIME_ROUTING_BLOCK = r"""# SCOREMAX_PROGRAMME_CATALOGUE_ROUTING_V2

def _is_fsc1(level: str) -> bool:
    value=(level or '').strip().casefold(); return 'fsc' in value and ('part 1' in value or 'year 1' in value or value in {'fsc 1','fsc1'})


def _programme_track(programme: str) -> str:
    value=(programme or '').strip().casefold()
    if value=='mdcat': return 'mdcat'
    if 'fsc' in value and ('part 1' in value or 'year 1' in value or value in {'fsc 1','fsc1'}): return 'year11'
    if 'fsc' in value and ('part 2' in value or 'year 2' in value or value in {'fsc 2','fsc2'}): return 'year12'
    return ''


def _active_programme_for_student(conn: sqlite3.Connection, student_id: int) -> str:
    row=conn.execute("SELECT COALESCE(active_programme,'') active_programme,COALESCE(academic_level,'') academic_level FROM users WHERE id=?",(student_id,)).fetchone()
    if not row: return ''
    return ((row['active_programme'] or '').strip() or (row['academic_level'] or '').strip())


def _catalogue_subject(track: str, subject: str) -> str:
    cat=CATALOGUES.get(track) or {}
    subjects=cat.get('subjects') or {}
    wanted=(subject or '').strip().casefold()
    return next((name for name in subjects if name.casefold()==wanted),'')


def _catalogue_for_student(conn: sqlite3.Connection, student_id: int, subject: str) -> list[str]:
    programme=_active_programme_for_student(conn,student_id)
    track=_programme_track(programme)
    if track:
        canonical=_catalogue_subject(track,subject)
        if not canonical:
            return []
        return [item['name'] for item in subject_items(track,canonical)]
    # Unknown programmes may use database-backed browsing, but never borrow another
    # programme's chapters merely because the subject name matches.
    if not programme:
        return []
    return [r['chapter'] for r in conn.execute(
        "SELECT chapter,MIN(id) first_id FROM questions WHERE lower(subject)=lower(?) AND lower(COALESCE(programme,''))=lower(?) AND COALESCE(chapter,'')<>'' GROUP BY chapter ORDER BY first_id",
        (subject,programme),
    ).fetchall()]


def _programme_label_for_student(conn: sqlite3.Connection, student_id: int) -> str:
    track=_programme_track(_active_programme_for_student(conn,student_id))
    return {'year11':'FSc YEAR 11','year12':'FSc YEAR 12','mdcat':'MDCAT'}.get(track,'MY STUDIES')
"""


_RUNTIME_SUBJECTS_BLOCK = r"""def _subjects_for_student(conn, student_id: int) -> list[str]:
    row=conn.execute("SELECT COALESCE(subjects,'') subjects FROM users WHERE id=?",(student_id,)).fetchone()
    declared=[x.strip() for x in ((row['subjects'] if row else '') or '').split(',') if x.strip()]
    track=_programme_track(_active_programme_for_student(conn,student_id))
    if track=='mdcat':
        return list(CATALOGUES['mdcat']['subjects'].keys())
    if track in {'year11','year12'}:
        catalogue_subjects=list(CATALOGUES[track]['subjects'].keys())
        if not declared:
            return catalogue_subjects
        declared_keys={x.casefold() for x in declared}
        return [name for name in catalogue_subjects if name.casefold() in declared_keys]
    return declared or ['Biology','Chemistry','Physics']
"""


_RUNTIME_LEARN_CONTEXT_BLOCK = r"""def _learn_context(conn, student_id: int):
    track=_programme_track(_active_programme_for_student(conn,student_id))
    subjects=[]
    for name in _subjects_for_student(conn,student_id):
        snap=_subject_snapshot(conn,student_id,name)
        if track=='mdcat':
            target=url_for('ux_catalogue_subject',track='mdcat',subject=name)
        else:
            target=url_for('subject_detail',subject=name)
        snap.update({'name':name,'url':target}); subjects.append(snap)
    future=[] if track=='mdcat' else [
      {'name':'MDCAT','badge':'Route','copy':'Medical admission preparation alongside your FSc journey.','url':url_for('ux_catalogue_track',track='mdcat')},
      {'name':'Logical Reasoning','badge':'MDCAT','copy':'Reasoning practice for your MDCAT route.','url':url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning')},
      {'name':'English','badge':'MDCAT','copy':'English preparation for your MDCAT route.','url':url_for('ux_catalogue_subject',track='mdcat',subject='English')},
    ]
    return subjects,future
"""


def _replace_one(text: str, pattern: str, replacement: str, failure: str) -> str:
    rendered, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(failure + f':matches={count}')
    return rendered


def _preserve_existing_programme_on_preview_bootstrap(text: str) -> str:
    old = "account_status='active',active_programme='FSc Part 1' WHERE id=?"
    new = (
        "account_status='active',active_programme=CASE "
        "WHEN COALESCE(active_programme,'') IN ('FSc Part 1','FSc Part 2','MDCAT') "
        "THEN active_programme ELSE 'FSc Part 1' END WHERE id=?"
    )
    count = text.count(old)
    if count != 1:
        # An already rectified generated runtime is acceptable.
        if new in text and old not in text:
            return text
        raise SystemExit(f'SCOREMAX_PROGRAMME_BOOTSTRAP_PATCH_MISMATCH:matches={count}')
    return text.replace(old, new, 1)


def apply_programme_catalogue_routing(root: Path) -> None:
    _assert_governed_catalogue_contract()
    path = Path(root) / 'ux_student_batch.py'
    if not path.is_file():
        raise SystemExit('SCOREMAX_PROGRAMME_CATALOGUE_RUNTIME_MISSING')
    text = path.read_text(encoding='utf-8')
    if ROUTING_MARKER in text:
        # Still verify the critical persistence guard before accepting idempotent return.
        forced = "account_status='active',active_programme='FSc Part 1' WHERE id=?"
        if forced in text:
            raise SystemExit('SCOREMAX_PROGRAMME_BOOTSTRAP_FORCE_RESET_SURVIVED')
        return

    import_anchor = 'from werkzeug.security import generate_password_hash\n'
    runtime_import = 'from ux_catalogue_data import CATALOGUES, subject_items\n'
    if runtime_import not in text:
        if import_anchor not in text:
            raise SystemExit('SCOREMAX_PROGRAMME_CATALOGUE_IMPORT_ANCHOR_MISSING')
        text = text.replace(import_anchor, import_anchor + runtime_import, 1)

    text = _replace_one(
        text,
        r"def _is_fsc1\(level: str\) -> bool:\n.*?(?=\ndef _ensure_fixed_test_student\(\) -> None:)",
        _RUNTIME_ROUTING_BLOCK.rstrip() + '\n\n',
        'SCOREMAX_PROGRAMME_CATALOGUE_ROUTING_BLOCK_MISMATCH',
    )
    text = _preserve_existing_programme_on_preview_bootstrap(text)
    text = _replace_one(
        text,
        r"def _subjects_for_student\(conn, student_id: int\) -> list\[str\]:\n.*?(?=\ndef _subject_snapshot\()",
        _RUNTIME_SUBJECTS_BLOCK.rstrip() + '\n\n',
        'SCOREMAX_PROGRAMME_CATALOGUE_SUBJECT_BLOCK_MISMATCH',
    )
    text = _replace_one(
        text,
        r"def _learn_context\(conn, student_id: int\):\n.*?(?=\ndef _progress_context\()",
        _RUNTIME_LEARN_CONTEXT_BLOCK.rstrip() + '\n\n',
        'SCOREMAX_PROGRAMME_CATALOGUE_LEARN_BLOCK_MISMATCH',
    )

    call_pattern = re.compile(
        r"(?P<indent>^[ \t]*)try: subjects,future=_learn_context\(conn,session\['user_id'\]\)\n"
        r"(?P=indent)finally: conn\.close\(\)",
        re.M,
    )

    def _label_repl(match: re.Match) -> str:
        indent = match.group('indent')
        inner = indent + '    '
        return (
            f"{indent}try:\n"
            f"{inner}subjects,future=_learn_context(conn,session['user_id'])\n"
            f"{inner}programme_label=_programme_label_for_student(conn,session['user_id'])\n"
            f"{indent}finally: conn.close()"
        )

    text, label_calls = call_pattern.subn(_label_repl, text)
    if label_calls != 2:
        # Existing V1-generated runtime may already have these callsites.
        if text.count("programme_label=_programme_label_for_student(conn,session['user_id'])") != 2:
            raise SystemExit(f'SCOREMAX_PROGRAMME_LABEL_CALLSITE_MISMATCH:matches={label_calls}')
    else:
        text, hardcoded_labels = re.subn("programme_label='FSc PRE-MEDICAL'", 'programme_label=programme_label', text)
        if hardcoded_labels != 2:
            raise SystemExit(f'SCOREMAX_PROGRAMME_LABEL_RENDER_MISMATCH:matches={hardcoded_labels}')

    compile(text, str(path), 'exec')
    required = (
        ROUTING_MARKER,
        "if value=='mdcat': return 'mdcat'",
        "return list(CATALOGUES['mdcat']['subjects'].keys())",
        "programme_label=_programme_label_for_student(conn,session['user_id'])",
        "lower(COALESCE(programme,''))=lower(?)",
        "url_for('ux_catalogue_track',track='mdcat')",
        "url_for('ux_catalogue_subject',track='mdcat',subject='Logical Reasoning')",
        "url_for('ux_catalogue_subject',track='mdcat',subject='English')",
        "target=url_for('ux_catalogue_subject',track='mdcat',subject=name)",
        "THEN active_programme ELSE 'FSc Part 1' END WHERE id=?",
    )
    missing = [token for token in required if token not in text]
    if missing:
        raise SystemExit('SCOREMAX_PROGRAMME_CATALOGUE_POSTBUILD_CONTROL_MISSING:' + ','.join(missing))
    forbidden = (
        "SELECT chapter,MIN(id) first_id FROM questions WHERE lower(subject)=lower(?) "
        "AND COALESCE(chapter,'')<>''"
    )
    if forbidden in text:
        raise SystemExit('SCOREMAX_PROGRAMME_CATALOGUE_UNSCOPED_FALLBACK_SURVIVED')
    if "account_status='active',active_programme='FSc Part 1' WHERE id=?" in text:
        raise SystemExit('SCOREMAX_PROGRAMME_BOOTSTRAP_FORCE_RESET_SURVIVED')

    path.write_text(text, encoding='utf-8')
    print(
        'SCOREMAX_PROGRAMME_CATALOGUE_ROUTING_PASS '
        'year11_total=54 year12_total=50 mdcat_total=61 '
        'mdcat_biology=16 mdcat_chemistry=20 mdcat_physics=16 mdcat_english=3 mdcat_logical_reasoning=6 '
        'active_programme_authoritative=true programme_survives_redeploy=true '
        'cross_programme_fallback=false fail_closed=true mdcat_subject_links_dedicated=true',
        flush=True,
    )
