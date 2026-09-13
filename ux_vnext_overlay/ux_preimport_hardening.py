from __future__ import annotations

import re
from pathlib import Path


def apply_preimport_hardening(root: Path) -> None:
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')
    # The historical bootstrap inserted five demonstration Biology questions whenever the bank was empty.
    # A governed production bank must begin genuinely empty; content arrives only through the governed import path.
    pattern=re.compile(r"\n    if c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\]==0:\n.*?\n    migrate_v5\(c\)",re.S)
    matches=list(pattern.finditer(text))
    if len(matches)!=1:
        raise SystemExit(f'PREIMPORT_DEMO_QUESTION_SEED_BLOCK_MISMATCH:{len(matches)}')
    replacement="\n    # PRE-IMPORT HARDENING: never synthesize learner questions into an empty governed bank.\n    # Governed questions are admitted only through Power House / approved import controls.\n    migrate_v5(c)"
    text=pattern.sub(replacement,text,count=1)
    app_path.write_text(text,encoding='utf-8')
    rendered=app_path.read_text(encoding='utf-8')
    for marker in ('BIO001','OSM001','A plant cell in concentrated salt solution'):
        if marker in rendered:
            raise SystemExit('PREIMPORT_DEMO_QUESTION_MARKER_SURVIVED:'+marker)
    if 'never synthesize learner questions into an empty governed bank' not in rendered:
        raise SystemExit('PREIMPORT_ZERO_BANK_CONTROL_MISSING')
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_bank=true demo_autoseed_removed=true governed_import_only=true',flush=True)
