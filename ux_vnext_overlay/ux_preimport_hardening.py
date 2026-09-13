from __future__ import annotations

import re
from pathlib import Path

PRIMARY_SEED_CONDITION="if preexisting_question_count==0 and content_seed_policy.demo_seed_allowed(SCOREMAX_ENV):"
SYNTHETIC_POPULATION_CONDITION="if content_seed_policy.demo_seed_allowed(SCOREMAX_ENV):"


def _disable_demo_seed(text: str) -> str:
    if PRIMARY_SEED_CONDITION in text:
        text=text.replace(PRIMARY_SEED_CONDITION,"if False:  # PRE-IMPORT HARDENING: governed question bank starts empty",1)
    anchor="built_in_demo_ids=('BIO001','BIO002','BIO003','BIO004','BIO005')"
    pos=text.find(anchor)
    if pos>=0:
        cond=text.find(SYNTHETIC_POPULATION_CONDITION,pos)
        if cond<0 or cond-pos>3000:
            raise SystemExit('PREIMPORT_SYNTHETIC_POPULATION_CONDITION_MISSING')
        text=text[:cond]+"if False:  # PRE-IMPORT HARDENING: synthetic qualification population disabled"+text[cond+len(SYNTHETIC_POPULATION_CONDITION):]
    historical=re.compile(r"if c\.execute\('SELECT COUNT\(\*\) n FROM questions'\)\.fetchone\(\)\['n'\]==0:")
    if PRIMARY_SEED_CONDITION not in text and 'PRE-IMPORT HARDENING: governed question bank starts empty' not in text and historical.search(text):
        text=historical.sub("if False:  # PRE-IMPORT HARDENING: governed question bank starts empty",text,count=1)
    return text


def _disable_staging_academic_reviewer_overlay(text: str) -> str:
    text=text.replace("install_content_reviewer(app)","# PRE-IMPORT HARDENING: ScoreMax academic reviewer overlay disabled; Power House is authoritative")
    text=text.replace("ensure_reviewer_accounts()","# PRE-IMPORT HARDENING: staging reviewer accounts disabled")
    return text


def _remove_inactive_reviewer_runtime_templates(root: Path) -> None:
    for name in ('ux_content_review.html','ux_content_review_question.html'):
        path=root/'templates'/name
        if path.exists():
            path.unlink()


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
    text=_disable_staging_academic_reviewer_overlay(text)
    text=_scrub_credential_logging(text)
    app_path.write_text(text,encoding='utf-8')
    _remove_inactive_reviewer_runtime_templates(root)

    rendered=app_path.read_text(encoding='utf-8')
    if PRIMARY_SEED_CONDITION in rendered:
        raise SystemExit('PREIMPORT_DEMO_SEED_EXECUTABLE_CONDITION_SURVIVED')
    if 'PRE-IMPORT HARDENING: governed question bank starts empty' not in rendered:
        raise SystemExit('PREIMPORT_DEMO_SEED_DISABLE_CONTROL_MISSING')
    anchor="built_in_demo_ids=('BIO001','BIO002','BIO003','BIO004','BIO005')"
    if anchor in rendered:
        pos=rendered.find(anchor); nearby=rendered[pos:pos+3500]
        if SYNTHETIC_POPULATION_CONDITION in nearby:
            raise SystemExit('PREIMPORT_SYNTHETIC_POPULATION_EXECUTABLE_CONDITION_SURVIVED')
        if 'synthetic qualification population disabled' not in nearby:
            raise SystemExit('PREIMPORT_SYNTHETIC_POPULATION_DISABLE_CONTROL_MISSING')
    if 'install_content_reviewer(app)' in rendered or 'ensure_reviewer_accounts()' in rendered:
        raise SystemExit('PREIMPORT_STAGING_REVIEWER_INSTALLER_SURVIVED')
    for name in ('ux_content_review.html','ux_content_review_question.html'):
        if (root/'templates'/name).exists():
            raise SystemExit('PREIMPORT_INACTIVE_REVIEWER_TEMPLATE_SURVIVED:'+name)
    for forbidden in ('One-time bootstrap admin created: admin /','New one-time local password: admin /'):
        if forbidden in rendered:
            raise SystemExit('PREIMPORT_CREDENTIAL_LOGGING_SURVIVED:'+forbidden)
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_seed_disabled=true synthetic_population_disabled=true staging_reviewer_overlay_disabled=true inactive_reviewer_templates_removed=true credential_log_hygiene=true governed_import_only=true',flush=True)
