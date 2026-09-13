from __future__ import annotations

import re
from pathlib import Path


def _remove_demo_seed(text: str) -> str:
    # Current governed runtime: keep the preexisting count because migrations use it,
    # but remove the entire optional demonstration-question insertion block.
    current=re.compile(
        r"(\n    preexisting_question_count=int\(c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\] or 0\)\n)"
        r"    if preexisting_question_count==0 and content_seed_policy\.demo_seed_allowed\(SCOREMAX_ENV\):\n"
        r".*?"
        r"(?=    # V6\.6\.0 upgrade safety:)",
        re.S,
    )
    matches=list(current.finditer(text))
    if len(matches)>1:
        raise SystemExit(f'PREIMPORT_CURRENT_DEMO_SEED_BLOCK_MISMATCH:{len(matches)}')
    if len(matches)==1:
        return current.sub(r"\1    # PRE-IMPORT HARDENING: demonstration learner questions are never auto-seeded.\n",text,count=1)

    # Historical fallback.
    historical=re.compile(r"\n    if c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\]==0:\n.*?\n    migrate_v5\(c\)",re.S)
    h=list(historical.finditer(text))
    if len(h)>1:
        raise SystemExit(f'PREIMPORT_HISTORICAL_DEMO_SEED_BLOCK_MISMATCH:{len(h)}')
    if len(h)==1:
        return historical.sub("\n    # PRE-IMPORT HARDENING: demonstration learner questions are never auto-seeded.\n    migrate_v5(c)",text,count=1)
    return text


def _scrub_credential_logging(text: str) -> str:
    # Match any release-version formatting so future release labels cannot reintroduce secret logging.
    text=re.sub(
        r"print\(f'\[ScoreMax V\{SCOREMAX_RELEASE_VERSION\}\] One-time bootstrap admin created: admin / \{bootstrap\}'\)",
        "print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')",
        text,
    )
    text=re.sub(
        r"print\(f'\[ScoreMax V\{SCOREMAX_RELEASE_VERSION\}\] Legacy demo admin password rotated\. New one-time local password: admin / \{bootstrap\}'\)",
        "print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')",
        text,
    )
    # Historical literal-version fallbacks.
    text=re.sub(
        r"print\(f'\[ScoreMax V[^']+\] One-time bootstrap admin created: admin / \{bootstrap\}'\)",
        "print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')",
        text,
    )
    text=re.sub(
        r"print\(f'\[ScoreMax V[^']+\] Legacy demo admin password rotated\. New one-time local password: admin / \{bootstrap\}'\)",
        "print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')",
        text,
    )
    return text


def apply_preimport_hardening(root: Path) -> None:
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')
    text=_remove_demo_seed(text)
    text=_scrub_credential_logging(text)
    app_path.write_text(text,encoding='utf-8')

    rendered=app_path.read_text(encoding='utf-8')
    for marker in ('BIO001','BIO002','BIO003','BIO004','BIO005','OSM001','ACT001','A plant cell in concentrated salt solution'):
        if marker in rendered:
            raise SystemExit('PREIMPORT_DEMO_QUESTION_MARKER_SURVIVED:'+marker)
    for forbidden in ('One-time bootstrap admin created: admin /','New one-time local password: admin /'):
        if forbidden in rendered:
            raise SystemExit('PREIMPORT_CREDENTIAL_LOGGING_SURVIVED:'+forbidden)
    if 'content_seed_policy.demo_seed_allowed(SCOREMAX_ENV)' in rendered:
        raise SystemExit('PREIMPORT_DEMO_SEED_POLICY_CALL_SURVIVED')
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_bank=true demo_autoseed_removed=true credential_log_hygiene=true governed_import_only=true',flush=True)
