from pathlib import Path

from deploy_ux_vnext_recovery import main as recovery_main
from ux_vnext_overlay.ux_referral_hero_v3 import apply_referral_hero_v3
from ux_vnext_overlay.ux_admin_workspace import apply_admin_workspace
from ux_vnext_overlay.ux_interest_admin_builder import apply_interest_admin
from ux_vnext_overlay.ux_commercial_reset import apply_commercial_reset

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


def _install_post_init_commercial_cleanup() -> None:
    path=ROOT/'scoremax_production.py'
    text=path.read_text(encoding='utf-8')
    anchor='ensure_teacher_preview()\napplication=scoremax.app'
    replacement="ensure_teacher_preview()\nimport scoremax_commercial_cleanup\nscoremax_commercial_cleanup.clear_default_catalogue()\napplication=scoremax.app"
    if 'scoremax_commercial_cleanup.clear_default_catalogue()' not in text:
        if anchor not in text:
            raise SystemExit('SCOREMAX_COMMERCIAL_CLEANUP_POST_INIT_ANCHOR_MISSING')
        text=text.replace(anchor,replacement,1)
        path.write_text(text,encoding='utf-8')
    rendered=path.read_text(encoding='utf-8')
    if 'scoremax_commercial_cleanup.clear_default_catalogue()' not in rendered:
        raise SystemExit('SCOREMAX_COMMERCIAL_CLEANUP_POST_INIT_CONTROL_MISSING')
    print('SCOREMAX_UX_COMMERCIAL_CLEANUP_STARTUP_PASS after_database_init=true',flush=True)


def _write_commercial_cleanup_runtime() -> None:
    path=ROOT/'scoremax_commercial_cleanup.py'
    path.write_text('''from __future__ import annotations\nimport os,sqlite3\nfrom pathlib import Path\n\nDEFAULT_PACKAGE_CODES=(\n    "fsc1_biology","fsc1_two_subjects","fsc1_science_bundle","fsc1_full",\n    "grade9_full","grade10_full","fsc2_full","mdcat_full",\n)\n\ndef clear_default_catalogue():\n    db=Path(os.environ.get("SCOREMAX_DB","/tmp/scoremax-ux-vnext/state/scoremax.db"))\n    if not db.exists(): return\n    conn=sqlite3.connect(db)\n    try:\n        exists=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='coverage_packages'").fetchone()\n        if not exists: return\n        marks=','.join('?' for _ in DEFAULT_PACKAGE_CODES)\n        # Fresh staging databases have no legitimate assignments yet. Do not delete a package if a governed entitlement or checkout already references it.\n        conn.execute(f"DELETE FROM coverage_packages WHERE code IN ({marks}) AND id NOT IN (SELECT coverage_package_id FROM student_package_entitlements UNION SELECT coverage_package_id FROM checkout_requests UNION SELECT COALESCE(coverage_package_id,-1) FROM subscriptions)",DEFAULT_PACKAGE_CODES)\n        conn.commit()\n        print("SCOREMAX_DEFAULT_COMMERCIAL_CATALOGUE_CLEARED protected_referenced_rows=true",flush=True)\n    finally:\n        conn.close()\n''',encoding='utf-8')


def _assert_referral_hero_v3() -> None:
    path=ROOT/'templates'/'referrals.html'
    if not path.is_file():
        raise SystemExit('SCOREMAX_REFERRAL_V3_RENDERED_TEMPLATE_MISSING')
    text=path.read_text(encoding='utf-8')
    required=(
        'ux-referral-hero-v3-style','ux-referral-hero-title','ux-referral-code-value',
        'id="uxReferralCopyCode"','id="uxReferralCopyStatus"','>Share now</a>',
        'id="ux-referral-links"','eligible cleared payments','Registration alone never creates commission.',
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
    apply_commercial_reset(ROOT)
    apply_admin_workspace(ROOT)
    _write_commercial_cleanup_runtime()
    _install_post_init_teacher_preview()
    _install_post_init_commercial_cleanup()


if __name__ == '__main__':
    main()
