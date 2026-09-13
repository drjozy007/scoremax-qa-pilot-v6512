from __future__ import annotations

import re
from pathlib import Path

SEED_CONDITION="if preexisting_question_count==0 and content_seed_policy.demo_seed_allowed(SCOREMAX_ENV):"


def _disable_demo_seed(text: str) -> str:
    if SEED_CONDITION in text:
        text=text.replace(SEED_CONDITION,"if False:  # PRE-IMPORT HARDENING: governed question bank starts empty",1)
    historical=re.compile(r"if c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\]==0:")
    if SEED_CONDITION not in text and 'PRE-IMPORT HARDENING: governed question bank starts empty' not in text and historical.search(text):
        text=historical.sub("if False:  # PRE-IMPORT HARDENING: governed question bank starts empty",text,count=1)
    return text


def _scrub_credential_logging(text: str) -> str:
    patterns=(
        (r"print\(f'\[ScoreMax V\{SCOREMAX_RELEASE_VERSION\}\] One-time bootstrap admin created: admin / \{bootstrap\}'\)","print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V\{SCOREMAX_RELEASE_VERSION\}\] Legacy demo admin password rotated\. New one-time local password: admin / \{bootstrap\}'\)","print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V[^']+\] One-time bootstrap admin created: admin / \{bootstrap\}'\)","print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V[^']+\] Legacy demo admin password rotated\. New one-time local password: admin / \{bootstrap\}'\)","print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')"),
    )
    for pattern,replacement in patterns:
        text=re.sub(pattern,replacement,text)
    return text


def apply_preimport_hardening(root: Path) -> None:
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')
    text=_disable_demo_seed(text)
    text=_scrub_credential_logging(text)
    app_path.write_text(text,encoding='utf-8')

    rendered=app_path.read_text(encoding='utf-8')
    if SEED_CONDITION in rendered:
        raise SystemExit('PREIMPORT_DEMO_SEED_EXECUTABLE_CONDITION_SURVIVED')
    if 'PRE-IMPORT HARDENING: governed question bank starts empty' not in rendered:
        raise SystemExit('PREIMPORT_DEMO_SEED_DISABLE_CONTROL_MISSING')
    for forbidden in ('One-time bootstrap admin created: admin /','New one-time local password: admin /'):
        if forbidden in rendered:
            raise SystemExit('PREIMPORT_CREDENTIAL_LOGGING_SURVIVED:'+forbidden)
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_seed_disabled=true credential_log_hygiene=true governed_import_only=true',flush=True)
