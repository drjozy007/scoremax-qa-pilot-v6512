from __future__ import annotations

import re
from pathlib import Path


def apply_preimport_hardening(root: Path) -> None:
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')

    # 1) Never auto-seed learner questions into an empty governed bank.
    pattern=re.compile(r"\n    if c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\]==0:\n.*?\n    migrate_v5\(c\)",re.S)
    matches=list(pattern.finditer(text))
    if len(matches)>1:
        raise SystemExit(f'PREIMPORT_DEMO_QUESTION_SEED_BLOCK_MISMATCH:{len(matches)}')
    if len(matches)==1:
        replacement="\n    # PRE-IMPORT HARDENING: never synthesize learner questions into an empty governed bank.\n    # Governed questions are admitted only through Power House / approved import controls.\n    migrate_v5(c)"
        text=pattern.sub(replacement,text,count=1)

    # 2) Never print bootstrap credentials.
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
    zero_control=('never synthesize learner questions into an empty governed bank' in rendered) or not any(x in rendered for x in ('BIO001','OSM001'))
    if not zero_control:
        raise SystemExit('PREIMPORT_ZERO_BANK_CONTROL_MISSING')
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_bank=true demo_autoseed_absent_or_removed=true credential_log_hygiene=true governed_import_only=true',flush=True)
