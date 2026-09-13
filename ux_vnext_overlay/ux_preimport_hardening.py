from __future__ import annotations

import re
from pathlib import Path


def _remove_demo_seed(text: str) -> str:
    # First try the historical exact shape.
    pattern=re.compile(r"\n    if c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\]==0:\n.*?\n    migrate_v5\(c\)",re.S)
    matches=list(pattern.finditer(text))
    if len(matches)>1:
        raise SystemExit(f'PREIMPORT_DEMO_QUESTION_SEED_BLOCK_MISMATCH:{len(matches)}')
    if len(matches)==1:
        return pattern.sub("\n    # PRE-IMPORT HARDENING: never synthesize learner questions into an empty governed bank.\n    # Governed questions are admitted only through Power House / approved import controls.\n    migrate_v5(c)",text,count=1)

    # Current releases may reformat the same seed block. Anchor on the known demo identifiers
    # and remove only the enclosing init() block immediately before migrate_v5(c).
    marker_pos=text.find('BIO001')
    if marker_pos<0:
        return text
    migrate_pos=text.find('\n    migrate_v5(c)',marker_pos)
    if migrate_pos<0:
        raise SystemExit('PREIMPORT_DEMO_SEED_MIGRATION_BOUNDARY_MISSING')
    scan_start=max(0,marker_pos-12000)
    prefix=text[scan_start:marker_pos]
    candidates=[m.start()+scan_start for m in re.finditer(r'\n    if [^\n]*questions[^\n]*:\n',prefix,re.I)]
    if not candidates:
        # Fallback to the nearest init-level conditional and verify the removed region actually contains demo markers.
        candidates=[m.start()+scan_start for m in re.finditer(r'\n    if [^\n]*:\n',prefix)]
    if not candidates:
        raise SystemExit('PREIMPORT_DEMO_SEED_START_BOUNDARY_MISSING')
    start=candidates[-1]
    region=text[start:migrate_pos]
    if 'BIO001' not in region or 'OSM001' not in region:
        raise SystemExit('PREIMPORT_DEMO_SEED_BOUNDARY_UNSAFE')
    replacement="\n    # PRE-IMPORT HARDENING: demo learner seed removed; governed bank remains empty.\n"
    return text[:start]+replacement+text[migrate_pos:]


def apply_preimport_hardening(root: Path) -> None:
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')
    text=_remove_demo_seed(text)

    # Never print bootstrap credentials.
    replacements={
        "print(f'[ScoreMax V6.5.10] One-time bootstrap admin created: admin / {bootstrap}')":"print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')",
        "print(f'[ScoreMax V6.5.10] Legacy demo admin password rotated. New one-time local password: admin / {bootstrap}')":"print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')",
        "print(f'[ScoreMax V6.6.11D] One-time bootstrap admin created: admin / {bootstrap}')":"print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')",
        "print(f'[ScoreMax V6.6.11D] Legacy demo admin password rotated. New one-time local password: admin / {bootstrap}')":"print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')",
    }
    for old,new in replacements.items():
        text=text.replace(old,new)

    app_path.write_text(text,encoding='utf-8')
    rendered=app_path.read_text(encoding='utf-8')
    for marker in ('BIO001','OSM001','A plant cell in concentrated salt solution'):
        if marker in rendered:
            raise SystemExit('PREIMPORT_DEMO_QUESTION_MARKER_SURVIVED:'+marker)
    for forbidden in ('One-time bootstrap admin created: admin /','New one-time local password: admin /'):
        if forbidden in rendered:
            raise SystemExit('PREIMPORT_CREDENTIAL_LOGGING_SURVIVED:'+forbidden)
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_bank=true demo_autoseed_absent_or_removed=true credential_log_hygiene=true governed_import_only=true',flush=True)
