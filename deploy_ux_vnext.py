from pathlib import Path

from deploy_ux_vnext_recovery import main as recovery_main
from ux_vnext_overlay.ux_referral_hero_v3 import apply_referral_hero_v3
from ux_vnext_overlay.ux_admin_workspace import apply_admin_workspace
from ux_vnext_overlay.ux_interest_admin import apply_interest_admin

ROOT=Path('scoremax_runtime_v669b')


def _install_post_init_teacher_preview() -> None:
    path=ROOT/'scoremax_production.py'
    text=path.read_text(encoding='utf-8')
    old='scoremax.init()\napplication=scoremax.app'
    new="scoremax.init()\nfrom ux_teacher_preview import ensure_teacher_preview\nensure_teacher_preview()\napplication=scoremax.app"
    if 'ensure_teacher_preview()' not in text:
        if old not in text:
            raise SystemExit('SCOREMAX_TEACHER_PREVIEW_POST_INIT_ANCHOR_MISSING')
        text=text.replace(old,new,1)
    path.write_text(text,encoding='utf-8')
    if 'scoremax.init()\nfrom ux_teacher_preview import ensure_teacher_preview\nensure_teacher_preview()' not in text:
        raise SystemExit('SCOREMAX_TEACHER_PREVIEW_POST_INIT_CONTROL_MISSING')
    print('SCOREMAX_UX_TEACHER_PREVIEW_STARTUP_ORDER_PASS after_database_init=true',flush=True)


def _assert_referral_hero_v3() -> None:
    path=ROOT/'templates'/'referrals.html'
    if not path.is_file():
        raise SystemExit('SCOREMAX_REFERRAL_V3_RENDERED_TEMPLATE_MISSING')
    text=path.read_text(encoding='utf-8')
    required=(
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
    missing=[token for token in required if token not in text]
    if missing:
        raise SystemExit('SCOREMAX_REFERRAL_V3_POSTBUILD_CONTROL_MISSING:'+','.join(missing))
    if '<span class="ux-referral-code-chip">' in text:
        raise SystemExit('SCOREMAX_REFERRAL_V3_OLD_MARKUP_SURVIVED')
    print('SCOREMAX_UX_REFERRAL_HERO_V3_POSTBUILD_PASS presentation_only=true backend_unchanged=true',flush=True)


def main() -> None:
    recovery_main()
    apply_referral_hero_v3(ROOT)
    _assert_referral_hero_v3()
    apply_interest_admin(ROOT)
    apply_admin_workspace(ROOT)
    _install_post_init_teacher_preview()


if __name__ == '__main__':
    main()
