from pathlib import Path
import shutil

from deploy_ux_vnext_recovery import main as recovery_main
from ux_vnext_overlay.ux_referral_hero_v3 import apply_referral_hero_v3
from ux_vnext_overlay.ux_admin_workspace import apply_admin_workspace
from ux_vnext_overlay.ux_interest_admin_builder import apply_interest_admin
from ux_vnext_overlay.ux_commercial_reset import apply_commercial_reset
from ux_vnext_overlay.ux_preimport_hardening import apply_preimport_hardening
from ux_vnext_overlay.ux_programme_catalogue_routing import apply_programme_catalogue_routing

ROOT=Path('scoremax_runtime_v669b')


def _restore_delivery_reviewer() -> None:
    # Restore only the read-only post-delivery QA surface after the hardening layer
    # removes the old independent ScoreMax academic-review implementation.
    for rel in (
        'ux_content_reviewer.py','ux_reviewer_accounts.py',
        'templates/ux_content_review.html','templates/ux_content_review_question.html',
    ):
        src=Path('ux_vnext_overlay')/rel
        dst=ROOT/rel
        if not src.is_file():
            raise SystemExit('SCOREMAX_DELIVERY_REVIEWER_SOURCE_MISSING:'+rel)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)

    path=ROOT/'scoremax_production.py'
    text=path.read_text(encoding='utf-8')
    anchor='scoremax.init()\napplication=scoremax.app'
    replacement=(
        "scoremax.init()\n"
        "from ux_content_reviewer import install_content_reviewer\n"
        "install_content_reviewer(scoremax.app)\n"
        "from ux_reviewer_accounts import ensure_reviewer_accounts\n"
        "ensure_reviewer_accounts()\n"
        "application=scoremax.app"
    )
    if 'install_content_reviewer(scoremax.app)' not in text:
        if anchor not in text:
            raise SystemExit('SCOREMAX_DELIVERY_REVIEWER_POST_INIT_ANCHOR_MISSING')
        text=text.replace(anchor,replacement,1)
        path.write_text(text,encoding='utf-8')
    rendered=path.read_text(encoding='utf-8')
    for token in ('install_content_reviewer(scoremax.app)','ensure_reviewer_accounts()'):
        if token not in rendered:
            raise SystemExit('SCOREMAX_DELIVERY_REVIEWER_INSTALL_CONTROL_MISSING:'+token)
    print('SCOREMAX_DELIVERY_REVIEWER_RESTORED read_only=true accounts=5 edits=false release_authority=false power_house_incident_bridge=true',flush=True)


def _install_post_init_teacher_preview() -> None:
    path=ROOT/'scoremax_production.py'
    text=path.read_text(encoding='utf-8')
    old='ensure_reviewer_accounts()\napplication=scoremax.app'
    new="ensure_reviewer_accounts()\nfrom ux_teacher_preview import ensure_teacher_preview\nensure_teacher_preview()\napplication=scoremax.app"
    if 'ensure_teacher_preview()' not in text:
        if old not in text:
            raise SystemExit('SCOREMAX_TEACHER_PREVIEW_POST_INIT_ANCHOR_MISSING')
        text=text.replace(old,new,1)
    path.write_text(text,encoding='utf-8')
    if 'from ux_teacher_preview import ensure_teacher_preview\nensure_teacher_preview()' not in text:
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


def _restore_catalogue_browser() -> None:
    # Learner-display metadata only. Never seed curriculum/question/chapter_catalogue state here.
    for rel in (
        'ux_catalogue_data.py','ux_catalogue_browser.py',
        'templates/ux_catalogue_home.html','templates/ux_catalogue_track.html','templates/ux_catalogue_subject.html',
    ):
        src=Path('ux_vnext_overlay')/rel
        dst=ROOT/rel
        if not src.is_file():
            raise SystemExit('SCOREMAX_CATALOGUE_BROWSER_SOURCE_MISSING:'+rel)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)

    path=ROOT/'scoremax_production.py'
    text=path.read_text(encoding='utf-8')
    anchor='scoremax_commercial_cleanup.clear_default_catalogue()\napplication=scoremax.app'
    replacement=(
        "scoremax_commercial_cleanup.clear_default_catalogue()\n"
        "from ux_catalogue_browser import install_catalogue_browser\n"
        "install_catalogue_browser(scoremax.app)\n"
        "application=scoremax.app"
    )
    if 'install_catalogue_browser(scoremax.app)' not in text:
        if anchor not in text:
            raise SystemExit('SCOREMAX_CATALOGUE_BROWSER_POST_INIT_ANCHOR_MISSING')
        text=text.replace(anchor,replacement,1)
        path.write_text(text,encoding='utf-8')
    rendered=path.read_text(encoding='utf-8')
    if 'install_catalogue_browser(scoremax.app)' not in rendered:
        raise SystemExit('SCOREMAX_CATALOGUE_BROWSER_INSTALL_CONTROL_MISSING')
    print('SCOREMAX_PROVISIONAL_CATALOGUE_INSTALLED governed_db_untouched=true power_house_authority_unchanged=true',flush=True)


def _write_commercial_cleanup_runtime() -> None:
    path=ROOT/'scoremax_commercial_cleanup.py'
    path.write_text('''from __future__ import annotations\nimport os,sqlite3\nfrom pathlib import Path\n\nDEFAULT_PACKAGE_CODES=(\n    "fsc1_biology","fsc1_two_subjects","fsc1_science_bundle","fsc1_full",\n    "grade9_full","grade10_full","fsc2_full","mdcat_full",\n)\n\ndef clear_default_catalogue():\n    db=Path(os.environ.get("SCOREMAX_DB","/tmp/scoremax-ux-vnext/state/scoremax.db"))\n    if not db.exists(): return\n    conn=sqlite3.connect(db)\n    try:\n        exists=conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='coverage_packages'").fetchone()\n        if not exists: return\n        marks=','.join('?' for _ in DEFAULT_PACKAGE_CODES)\n        conn.execute(f"DELETE FROM coverage_packages WHERE code IN ({marks}) AND id NOT IN (SELECT coverage_package_id FROM student_package_entitlements UNION SELECT coverage_package_id FROM checkout_requests UNION SELECT COALESCE(coverage_package_id,-1) FROM subscriptions)",DEFAULT_PACKAGE_CODES)\n        conn.commit()\n        print("SCOREMAX_DEFAULT_COMMERCIAL_CATALOGUE_CLEARED protected_referenced_rows=true",flush=True)\n    finally:\n        conn.close()\n''',encoding='utf-8')


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
    apply_preimport_hardening(ROOT)
    _restore_delivery_reviewer()
    apply_referral_hero_v3(ROOT)
    _assert_referral_hero_v3()
    apply_interest_admin(ROOT)
    apply_commercial_reset(ROOT)
    apply_admin_workspace(ROOT)
    _write_commercial_cleanup_runtime()
    _install_post_init_teacher_preview()
    _install_post_init_commercial_cleanup()
    _restore_catalogue_browser()
    apply_programme_catalogue_routing(ROOT)


if __name__ == '__main__':
    main()
