from __future__ import annotations

import re
from pathlib import Path


def apply_preimport_hardening(root: Path) -> None:
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')

    # 1) Never auto-seed learner questions into an empty governed bank.
    pattern=re.compile(r"\n    if c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\]==0:\n.*?\n    migrate_v5\(c\)",re.S)
    matches=list(pattern.finditer(text))
    if len(matches)!=1:
        raise SystemExit(f'PREIMPORT_DEMO_QUESTION_SEED_BLOCK_MISMATCH:{len(matches)}')
    replacement="\n    # PRE-IMPORT HARDENING: never synthesize learner questions into an empty governed bank.\n    # Governed questions are admitted only through Power House / approved import controls.\n    migrate_v5(c)"
    text=pattern.sub(replacement,text,count=1)

    # 2) Never print bootstrap credentials. A one-time password may exist operationally,
    # but logs may state only that credential material was created/rotated.
    text=text.replace("print(f'[ScoreMax V6.5.10] One-time bootstrap admin created: admin / {bootstrap}')",
                      "print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')")
    text=text.replace("print(f'[ScoreMax V6.5.10] Legacy demo admin password rotated. New one-time local password: admin / {bootstrap}')",
                      "print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')")

    app_path.write_text(text,encoding='utf-8')
    rendered=app_path.read_text(encoding='utf-8')
    for marker in ('BIO001','OSM001','A plant cell in concentrated salt solution'):
        if marker in rendered:
            raise SystemExit('PREIMPORT_DEMO_QUESTION_MARKER_SURVIVED:'+marker)
    if 'never synthesize learner questions into an empty governed bank' not in rendered:
        raise SystemExit('PREIMPORT_ZERO_BANK_CONTROL_MISSING')
    for forbidden in ('One-time bootstrap admin created: admin /','New one-time local password: admin /'):
        if forbidden in rendered:
            raise SystemExit('PREIMPORT_CREDENTIAL_LOGGING_SURVIVED:'+forbidden)
    if 'credential withheld from logs' not in rendered:
        raise SystemExit('PREIMPORT_CREDENTIAL_LOG_HYGIENE_CONTROL_MISSING')
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_bank=true demo_autoseed_removed=true credential_log_hygiene=true governed_import_only=true',flush=True)
