from __future__ import annotations

import re
from pathlib import Path

DEFAULT_PACKAGE_CODES=(
    'fsc1_biology','fsc1_two_subjects','fsc1_science_bundle','fsc1_full',
    'grade9_full','grade10_full','fsc2_full','mdcat_full',
)


def _disable_seeded_coverage_packages(root: Path) -> None:
    path=root/'commercial_access_engine.py'
    text=path.read_text(encoding='utf-8')
    rx=re.compile(r"\n    seeds=\[\n.*?\n    \]\n    for row in seeds:",re.S)
    matches=list(rx.finditer(text))
    if len(matches)!=1:
        raise SystemExit(f'UX_COMMERCIAL_PACKAGE_SEED_BLOCK_MISMATCH:{len(matches)}')
    replacement="\n    # ScoreMax commercial package catalogue is intentionally empty until configured by Admin.\n    seeds=[]\n    for row in seeds:"
    text=rx.sub(replacement,text,count=1)
    path.write_text(text,encoding='utf-8')
    rendered=path.read_text(encoding='utf-8')
    for code in DEFAULT_PACKAGE_CODES:
        if f"('{code}'" in rendered:
            raise SystemExit('UX_COMMERCIAL_DEFAULT_PACKAGE_SURVIVED:'+code)
    if 'seeds=[]' not in rendered:
        raise SystemExit('UX_COMMERCIAL_EMPTY_SEED_CONTROL_MISSING')


def _remove_legacy_plan_pricing_from_admin(root: Path) -> None:
    path=root/'templates'/'admin_payments.html'
    text=path.read_text(encoding='utf-8')
    # Keep the access-tier architecture, but remove the old generic plan-pricing editor.
    rx=re.compile(r"<div class='card'><p class='eyebrow'>PLAN CONFIGURATION</p><h3>Prices</h3>.*?</div>\n</div>",re.S)
    matches=list(rx.finditer(text))
    if len(matches)==1:
        text=rx.sub("<div class='card'><p class='eyebrow'>ACCESS LEVELS</p><h3>Configured through subject packages</h3><p class='muted'>Create the commercial package and price above. Access levels remain technical entitlement controls and do not carry a separate public price here.</p></div>\n</div>",text,count=1)
    elif len(matches)>1:
        raise SystemExit(f'UX_COMMERCIAL_PLAN_PRICE_BLOCK_MISMATCH:{len(matches)}')
    path.write_text(text,encoding='utf-8')


def apply_commercial_reset(root: Path) -> None:
    _disable_seeded_coverage_packages(root)
    _remove_legacy_plan_pricing_from_admin(root)
    print('SCOREMAX_UX_COMMERCIAL_RESET_PASS seeded_packages=0 admin_defined_only=true entitlement_architecture_preserved=true',flush=True)
