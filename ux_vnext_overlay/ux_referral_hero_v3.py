from __future__ import annotations

from pathlib import Path


STYLE = r'''<style id="ux-referral-hero-v3-style">
.ux-teacher-referrals-brand .referral-hero{
  display:grid;grid-template-columns:minmax(0,1.42fr) minmax(270px,.78fr);grid-auto-rows:min-content;
  column-gap:34px;row-gap:10px;align-items:start;padding:clamp(26px,4vw,42px);
  border:1px solid #b8d9d6;border-top:6px solid #2f7f7d;border-radius:22px;
  background:linear-gradient(135deg,#e8f7f5 0%,#f8fcfb 58%,#fff8e9 100%);
  box-shadow:0 16px 36px rgba(32,89,86,.11)
}
.ux-teacher-referrals-brand .referral-hero>*:not(.ux-referral-hero-actions){grid-column:1;position:relative;z-index:1;min-width:0}
.ux-teacher-referrals-brand .referral-hero .eyebrow{margin:0 0 3px;color:#2f7f7d;font-size:.72rem;font-weight:950;letter-spacing:.12em}
.ux-teacher-referrals-brand .referral-hero h1.ux-referral-hero-title{margin:.1rem 0 .55rem;max-width:720px;font-size:clamp(2rem,4vw,3.35rem);line-height:.99;letter-spacing:-.045em;color:#173f3d;text-wrap:balance}
.ux-teacher-referrals-brand .referral-hero h1.ux-referral-hero-title span{display:block;margin-top:.14em;color:#2f7f7d}
.ux-teacher-referrals-brand .referral-hero p{max-width:720px;line-height:1.58}
.ux-teacher-referrals-brand .referral-hero .muted{max-width:720px;color:#536966}
.ux-teacher-referrals-brand .ux-referral-hero-actions{
  grid-column:2;grid-row:1 / span 12;align-self:center;position:relative;z-index:2;
  display:flex;flex-direction:column;align-items:stretch;gap:10px;margin:0;padding:22px;
  border:1px solid rgba(47,127,125,.2);border-top:4px solid #d6a74d;border-radius:18px;
  background:rgba(255,255,255,.94);box-shadow:0 14px 30px rgba(32,89,86,.12);backdrop-filter:blur(8px)
}
.ux-referral-action-label{font-size:.68rem;font-weight:950;letter-spacing:.09em;text-transform:uppercase;color:#687875}
.ux-referral-code-value{display:block;padding:13px 14px;border:1px solid #d8e8e6;border-radius:13px;background:#f5fbfa;color:#205f5c;font-size:1.24rem;line-height:1.1;letter-spacing:.075em;text-align:center;word-break:break-word}
.ux-referral-copy-code,.ux-referral-share-link{display:flex;align-items:center;justify-content:center;min-height:42px;padding:10px 14px;border-radius:12px;font:inherit;font-size:.76rem;font-weight:900;text-decoration:none;cursor:pointer;transition:transform .14s ease,background .14s ease,border-color .14s ease}
.ux-referral-copy-code{border:1px solid #2f7f7d;background:#2f7f7d;color:#fff}.ux-referral-copy-code:hover{background:#286f6d;border-color:#286f6d;transform:translateY(-1px)}
.ux-referral-share-link{border:1px solid #bcdedb;background:#edf8f7;color:#236765!important}.ux-referral-share-link:hover{background:#dff2f0;border-color:#9ecfcb;transform:translateY(-1px)}
.ux-referral-action-note,.ux-referral-copy-status{margin:0;color:#71807d;font-size:.67rem;line-height:1.45;text-align:center}
.ux-referral-copy-status{min-height:1em;color:#2f7f7d;font-weight:800}
@media(max-width:880px){
  .ux-teacher-referrals-brand .referral-hero{grid-template-columns:1fr;gap:18px;padding:26px}
  .ux-teacher-referrals-brand .referral-hero>*:not(.ux-referral-hero-actions){grid-column:1}
  .ux-teacher-referrals-brand .ux-referral-hero-actions{grid-column:1;grid-row:auto;align-self:stretch;max-width:none}
}
@media(max-width:520px){
  .ux-teacher-referrals-brand .referral-hero{padding:21px 18px;border-radius:18px}
  .ux-teacher-referrals-brand .referral-hero h1.ux-referral-hero-title{font-size:clamp(1.85rem,10vw,2.5rem)}
  .ux-teacher-referrals-brand .ux-referral-hero-actions{padding:17px;border-radius:15px}
}
</style>'''

SCRIPT = r'''<script id="ux-referral-hero-v3-script">
(function(){
  const button=document.getElementById('uxReferralCopyCode');
  const status=document.getElementById('uxReferralCopyStatus');
  if(!button)return;
  button.addEventListener('click',async function(){
    const value=(button.getAttribute('data-referral-code')||'').trim();
    if(!value)return;
    let copied=false;
    try{await navigator.clipboard.writeText(value);copied=true;}catch(_e){
      try{const area=document.createElement('textarea');area.value=value;area.setAttribute('readonly','');area.style.position='fixed';area.style.opacity='0';document.body.appendChild(area);area.select();copied=document.execCommand('copy');area.remove();}catch(_fallback){}
    }
    if(status){status.textContent=copied?'Referral code copied':'Select the code above to copy it';}
    if(copied){const original=button.textContent;button.textContent='Copied';setTimeout(()=>{button.textContent=original;if(status)status.textContent='';},1800);}
  });
})();
</script>'''


def apply_referral_hero_v3(root: Path) -> None:
    path = root / 'templates' / 'referrals.html'
    if not path.is_file():
        raise SystemExit('UX_REFERRAL_V3_TEMPLATE_MISSING')
    text = path.read_text(encoding='utf-8')

    required = (
        'ux-teacher-referrals-brand',
        'ux-referral-code-chip',
        'ux-referral-share-link',
        'id="ux-referral-links"',
        '{{user.own_referral_code}}',
        'eligible cleared payments',
        'Registration alone never creates commission.',
    )
    missing = [token for token in required if token not in text]
    if missing:
        raise SystemExit('UX_REFERRAL_V3_BASELINE_MISSING:' + ','.join(missing))

    # Replace only the teacher-only action treatment created by Workspace v2.
    old_actions = '''<div class="ux-referral-hero-actions"><span class="ux-referral-code-chip">Your code <strong>{{user.own_referral_code}}</strong></span><a class="ux-referral-share-link" href="#ux-referral-links">Share now ↓</a></div>'''
    if text.count(old_actions) != 1:
        raise SystemExit('UX_REFERRAL_V3_ACTION_BASELINE_MISMATCH:' + str(text.count(old_actions)))
    new_actions = '''<aside class="ux-referral-hero-actions" aria-label="Referral sharing actions">
        <span class="ux-referral-action-label">Your referral code</span>
        <strong class="ux-referral-code-value">{{user.own_referral_code}}</strong>
        <button class="ux-referral-copy-code" id="uxReferralCopyCode" type="button" data-referral-code="{{user.own_referral_code}}">Copy code</button>
        <a class="ux-referral-share-link" href="#ux-referral-links">Share now</a>
        <small class="ux-referral-action-note">Use the sharing links below for the right referral route.</small>
        <small class="ux-referral-copy-status" id="uxReferralCopyStatus" aria-live="polite"></small>
      </aside>'''
    text = text.replace(old_actions, new_actions, 1)

    # Keep all governed supporting copy; only make the existing hero headline cleaner and more accurate.
    hero_pos = text.find('referral-hero')
    links_pos = text.find('id="ux-referral-links"')
    if hero_pos < 0 or links_pos < 0 or hero_pos >= links_pos:
        raise SystemExit('UX_REFERRAL_V3_HERO_BOUNDS_MISSING')
    h1_open = text.find('<h1', hero_pos, links_pos)
    h1_gt = text.find('>', h1_open, links_pos) if h1_open >= 0 else -1
    h1_close = text.find('</h1>', h1_gt, links_pos) if h1_gt >= 0 else -1
    if min(h1_open, h1_gt, h1_close) < 0:
        raise SystemExit('UX_REFERRAL_V3_HEADLINE_MISSING')
    headline = '<h1 class="ux-referral-hero-title">Share ScoreMax.<span>Earn when eligible students subscribe.</span></h1>'
    text = text[:h1_open] + headline + text[h1_close + len('</h1>'):]

    # Load after Workspace v2 styles so this bounded refinement is authoritative.
    root_anchor = '<section class="page-shell referral-page-v640'
    if text.count(root_anchor) != 1:
        raise SystemExit('UX_REFERRAL_V3_ROOT_ANCHOR_MISMATCH:' + str(text.count(root_anchor)))
    conditional_style = "{% if user.role=='teacher' %}\n" + STYLE + "\n{% endif %}\n"
    text = text.replace(root_anchor, conditional_style + root_anchor, 1)

    endblock = text.rfind('{% endblock %}')
    if endblock < 0:
        raise SystemExit('UX_REFERRAL_V3_ENDBLOCK_MISSING')
    conditional_script = "{% if user.role=='teacher' %}\n" + SCRIPT + "\n{% endif %}\n"
    text = text[:endblock] + conditional_script + text[endblock:]

    post_checks = (
        'ux-referral-hero-v3-style',
        'ux-referral-hero-title',
        'ux-referral-code-value',
        'id="uxReferralCopyCode"',
        'id="uxReferralCopyStatus"',
        '>Share now</a>',
        'id="ux-referral-links"',
        'eligible cleared payments',
        'Registration alone never creates commission.',
    )
    missing = [token for token in post_checks if token not in text]
    if missing:
        raise SystemExit('UX_REFERRAL_V3_POSTCHECK_MISSING:' + ','.join(missing))
    if 'ux-referral-code-chip' in text:
        raise SystemExit('UX_REFERRAL_V3_OLD_PATCH_SURVIVED')

    path.write_text(text, encoding='utf-8')
    print('SCOREMAX_UX_REFERRAL_HERO_V3_PASS layout=two_zone copy_code=true share_links_reused=true economics_unchanged=true backend_unchanged=true', flush=True)
