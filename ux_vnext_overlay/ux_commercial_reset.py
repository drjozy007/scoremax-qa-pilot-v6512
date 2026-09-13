from __future__ import annotations

import re
from pathlib import Path

DEFAULT_PACKAGE_CODES=(
    'fsc1_biology','fsc1_two_subjects','fsc1_science_bundle','fsc1_full',
    'grade9_full','grade10_full','fsc2_full','mdcat_full',
)

# Recovered from the previously accepted commercial_access_engine baseline.
# Prices are minor PKR units. FSc Part 2 and MDCAT remain explicitly unpriced/COMING_SOON.
APPROVED_PACKAGE_TOKENS=(
    "('fsc1_biology','Biology only','FSc Part 1','Full access to Biology within the selected access level.','SUBJECTS',['Biology'],79900,'PKR','monthly','ACTIVE',10)",
    "('fsc1_two_subjects','Choose two FSc Part 1 subjects','FSc Part 1','A flexible two-subject package.','SELECT_N',[],129900,'PKR','monthly','ACTIVE',20)",
    "('fsc1_science_bundle','Biology, Chemistry and Physics','FSc Part 1','The core science bundle.','SUBJECTS',['Biology','Chemistry','Physics'],169900,'PKR','monthly','ACTIVE',30)",
    "('fsc1_full','All currently available FSc Part 1 subjects','FSc Part 1','Every subject released for this programme.','ALL_AVAILABLE',[],199900,'PKR','monthly','ACTIVE',40)",
    "('grade9_full','Grade 9 — all available subjects','Grade 9','All Grade 9 subjects as they become available.','ALL_AVAILABLE',[],None,'PKR','monthly','COMING_SOON',50)",
    "('grade10_full','Grade 10 — all available subjects','Grade 10','All Grade 10 subjects as they become available.','ALL_AVAILABLE',[],None,'PKR','monthly','COMING_SOON',60)",
    "('fsc2_full','FSc Part 2 — all available subjects','FSc Part 2','All FSc Part 2 subjects as they become available.','ALL_AVAILABLE',[],None,'PKR','monthly','COMING_SOON',70)",
    "('mdcat_full','MDCAT — complete curriculum','MDCAT','Complete released MDCAT curriculum.','ALL_AVAILABLE',[],None,'PKR','monthly','COMING_SOON',80)",
)

PUBLIC_ACCESS_NAMES={
    'free_access':'Free',
    'level_1_access':'Silver',
    'level_2_access':'Gold',
    'full_access':'Platinum',
}


def _preserve_approved_coverage_packages(root: Path) -> None:
    path=root/'commercial_access_engine.py'
    text=path.read_text(encoding='utf-8')
    if 'seeds=[]' in text:
        raise SystemExit('SCOREMAX_APPROVED_COMMERCIAL_CATALOGUE_WAS_EMPTIED')
    missing=[token for token in APPROVED_PACKAGE_TOKENS if token not in text]
    if missing:
        raise SystemExit('SCOREMAX_APPROVED_COMMERCIAL_PACKAGE_SOURCE_MISMATCH:'+str(len(missing)))
    for code in DEFAULT_PACKAGE_CODES:
        if f"('{code}'" not in text:
            raise SystemExit('SCOREMAX_APPROVED_COMMERCIAL_PACKAGE_MISSING:'+code)


def _remove_legacy_plan_pricing_from_admin(root: Path) -> None:
    path=root/'templates'/'admin_payments.html'
    text=path.read_text(encoding='utf-8')
    # Access tiers remain technical entitlement controls. The recovered approved
    # catalogue carries prices on subject coverage packages, not on the tier rows.
    rx=re.compile(r"<div class='card'><p class='eyebrow'>PLAN CONFIGURATION</p><h3>Prices</h3>.*?</div>\n</div>",re.S)
    matches=list(rx.finditer(text))
    if len(matches)==1:
        text=rx.sub("<div class='card'><p class='eyebrow'>ACCESS LEVELS</p><h3>Free · Silver · Gold · Platinum</h3><p class='muted'>Public access names map onto the existing governed entitlement levels. Subject-package prices remain controlled by the package catalogue above.</p></div>\n</div>",text,count=1)
    elif len(matches)>1:
        raise SystemExit(f'UX_COMMERCIAL_PLAN_PRICE_BLOCK_MISMATCH:{len(matches)}')
    path.write_text(text,encoding='utf-8')


def _restore_public_access_cards(root: Path) -> None:
    path=root/'templates'/'access.html'
    text=path.read_text(encoding='utf-8')

    # Current access summary should never leak technical Level 1/2/Full names.
    old="<div><span>Access level</span><strong>{{access.name}}</strong></div>"
    new="<div><span>Access level</span><strong>{{ {'free_access':'Free','level_1_access':'Silver','level_2_access':'Gold','full_access':'Platinum'}.get(access.plan_code,access.name) }}</strong></div>"
    if old not in text:
        raise SystemExit('SCOREMAX_PUBLIC_ACCESS_SUMMARY_ANCHOR_MISSING')
    text=text.replace(old,new,1)

    access_rx=re.compile(
        r'<section><div class="section-heading"><div><p class="eyebrow">2\. ACCESS LEVEL</p>.*?</section>\n\n<section class="card paywall-checkout">',
        re.S,
    )
    matches=list(access_rx.finditer(text))
    if len(matches)!=1:
        raise SystemExit(f'SCOREMAX_PUBLIC_ACCESS_SECTION_MISMATCH:matches={len(matches)}')

    replacement='''<section><div class="section-heading"><div><p class="eyebrow">2. SCOREMAX ACCESS</p><h2>Choose Free, Silver, Gold or Platinum.</h2><p class="muted">Your subject package controls what you can study. Your ScoreMax access level controls the depth of diagnostics, recovery, mocks, mastery and premium learning support inside those subjects.</p></div></div><div class="access-grid">{% for p in plans %}{% set public_name={'free_access':'Free','level_1_access':'Silver','level_2_access':'Gold','full_access':'Platinum'}.get(p.code,p.name) %}{% set public_copy={'free_access':'Start with core diagnostic, results and topic practice.','level_1_access':'Build strong foundations and structured progress.','level_2_access':'Go deeper with broader mastery and exam preparation.','full_access':'Use the fullest ScoreMax learning and mastery journey.'}.get(p.code,'') %}<section class="card access-card {% if p.code==access.plan_code %}current{% endif %}"><p class="eyebrow">{% if p.code==access.plan_code %}CURRENT · {% endif %}{{public_name|upper}}</p><h2>{{public_name}}</h2><div class="mastery-mini-ladder">{% for level in levels %}<span class="{% if loop.index0<=({'Foundation':0,'Exam Ready':1,'Advanced':2,'Distinction':3,'Expert':4,'Elite':5}[p.ceiling]) %}on{% endif %}">{{level}}</span>{% endfor %}</div><p><strong>Work toward {{p.ceiling}}</strong></p><p>{{public_copy}}</p>{% if p.code=='level_1_access' %}<p class="muted">Advanced diagnostics · Live study plan</p>{% elif p.code=='level_2_access' %}<p class="muted">Silver features · Recovery engine · All mocks</p>{% elif p.code=='full_access' %}<p class="muted">Gold features · Monthly challenges · Ranking eligibility · Premium reports</p>{% else %}<p class="muted">Core diagnostic · Basic results · Topic practice</p>{% endif %}<label class="form-check"><input class="form-check-input tier-radio" type="radio" name="tier_preview" value="{{p.code}}"><span class="form-check-label">Select {{public_name}}</span></label></section>{% endfor %}</div></section>

<section class="card paywall-checkout">'''
    text=access_rx.sub(replacement,text,count=1)

    old_option='<option value="{{p.code}}">{{p.name}}</option>'
    new_option='<option value="{{p.code}}">{{ {\'free_access\':\'Free\',\'level_1_access\':\'Silver\',\'level_2_access\':\'Gold\',\'full_access\':\'Platinum\'}.get(p.code,p.name) }}</option>'
    if old_option not in text:
        raise SystemExit('SCOREMAX_PUBLIC_ACCESS_CHECKOUT_OPTION_ANCHOR_MISSING')
    text=text.replace(old_option,new_option,1)

    old_price="<strong>{{'%.0f'|format(p.price_minor/100)}} {{p.currency}} / {{p.billing_period}}</strong>"
    new_price="<strong>{{p.currency}} {{'%.0f'|format(p.price_minor/100)}} / {{'month' if p.billing_period=='monthly' else p.billing_period}}</strong>"
    if old_price not in text:
        raise SystemExit('SCOREMAX_PACKAGE_PRICE_PRESENTATION_ANCHOR_MISSING')
    text=text.replace(old_price,new_price,1)

    path.write_text(text,encoding='utf-8')
    rendered=path.read_text(encoding='utf-8')
    for token in ('Choose Free, Silver, Gold or Platinum.','Silver features · Recovery engine · All mocks','Gold features · Monthly challenges','Select {{public_name}}'):
        if token not in rendered:
            raise SystemExit('SCOREMAX_PUBLIC_ACCESS_CARD_CONTROL_MISSING:'+token)
    for technical in ('<h2>{{p.name}}</h2>','<span class="form-check-label">Select level</span>'):
        if technical in rendered:
            raise SystemExit('SCOREMAX_TECHNICAL_ACCESS_LABEL_SURVIVED:'+technical)


def apply_commercial_reset(root: Path) -> None:
    _preserve_approved_coverage_packages(root)
    _remove_legacy_plan_pricing_from_admin(root)
    _restore_public_access_cards(root)
    print(
        'SCOREMAX_COMMERCIAL_CATALOGUE_RESTORED '
        'coverage_packages=8 active_priced=4 coming_soon_unpriced=4 '
        'fsc1_prices_pkr=799,1299,1699,1999 public_access=Free,Silver,Gold,Platinum '
        'backend_plan_codes_unchanged=true payment_gateway_unchanged=true',
        flush=True,
    )
