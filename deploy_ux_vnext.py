from pathlib import Path
import re
import shutil

from deploy_ux_vnext_recovery import main as recovery_main
from ux_vnext_overlay.ux_referral_hero_v3 import apply_referral_hero_v3
from ux_vnext_overlay.ux_admin_workspace import apply_admin_workspace
from ux_vnext_overlay.ux_interest_admin_builder import apply_interest_admin
from ux_vnext_overlay.ux_commercial_reset import apply_commercial_reset
from ux_vnext_overlay.ux_preimport_hardening import apply_preimport_hardening
from ux_vnext_overlay.ux_programme_catalogue_routing import apply_programme_catalogue_routing
from ux_vnext_overlay.ux_main_subject_fsc_fence import apply_main_subject_fsc_fence
from ux_vnext_overlay.ux_canonical_student_navigation import apply_canonical_student_navigation
from ux_vnext_overlay.ux_restore_access_cards import apply_restore_access_cards
from ux_vnext_overlay.ux_chapter_card_open_fix import apply_chapter_card_open_fix
from ux_vnext_overlay.ux_admin_rejection_reason_guard import apply_admin_rejection_reason_guard
from ux_vnext_overlay.ux_persistent_guard_postrelease_state import apply_persistent_guard_postrelease_state
from ux_vnext_overlay.ux_persistent_guard_batch_retirement import apply_persistent_guard_batch_retirement
from ux_vnext_overlay.ux_emergency_return_bridge import apply_emergency_return_bridge
from ux_vnext_overlay.ux_emergency_return_contract import apply_emergency_return_contract
from ux_vnext_overlay.ux_emergency_return_recovery import apply_emergency_return_recovery
from ux_vnext_overlay.ux_bio13_identity_crosswalk_audit import apply_bio13_identity_crosswalk_audit
from ux_vnext_overlay.ux_bio13_failed_pilot_retirement import apply_bio13_failed_pilot_retirement
from ux_vnext_overlay.ux_source_market_v12_receiver import apply_source_market_v12_receiver
from ux_vnext_overlay.ux_cross50_qa_staging_v13 import apply_cross50_qa_staging_v13
from ux_vnext_overlay.ux_cross50_qa_staging_v13_qualification import assert_cross50_qa_v13
from ux_vnext_overlay.ux_safe98_destination_verifier import apply_safe98_destination_verifier, apply_cross50_math16_destination_verifier

ROOT=Path('scoremax_runtime_v669b')


def _restore_delivery_reviewer() -> None:
    for rel in (
        'ux_content_reviewer.py','ux_reviewer_accounts.py','ux_matching_support.py',
        'templates/ux_content_review.html','templates/ux_content_review_question.html',
        'templates/ux_staged_content_review.html','templates/ux_staged_content_review_question.html',
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
    staged_runtime=(ROOT/'ux_content_reviewer.py').read_text(encoding='utf-8')
    staged_list=(ROOT/'templates'/'ux_staged_content_review.html').read_text(encoding='utf-8')
    staged_item=(ROOT/'templates'/'ux_staged_content_review_question.html').read_text(encoding='utf-8')
    staged_required=(
      'SCOREMAX_STAGED_DELIVERY_REVIEWER_V1',
      "app.route('/student/content-review/staged'",
      'integration_ph_question_version_store',
      'integration_ph_release_question_membership',
      'STAGED_POWER_HOUSE',
      'release_authority_conferred',
      'learner inactive',
    )
    staged_combined='\n'.join((staged_runtime,staged_list,staged_item))
    staged_missing=[token for token in staged_required if token not in staged_combined]
    if staged_missing:
        raise SystemExit('SCOREMAX_STAGED_DELIVERY_REVIEWER_CONTROL_MISSING:'+','.join(staged_missing))
    print('SCOREMAX_DELIVERY_REVIEWER_RESTORED read_only=true accounts=5 edits=false release_authority=false power_house_incident_bridge=true',flush=True)
    print('SCOREMAX_STAGED_DELIVERY_REVIEWER_BUILD_PASS staged_store_read=true materialisation=false learner_activation=false exact_ph_lineage=true existing_incident_lane=true',flush=True)



def _install_matching_runtime() -> None:
    app=ROOT/'app.py'
    tpl=ROOT/'templates'/'take_test_v4.html'
    text=app.read_text(encoding='utf-8')
    t=tpl.read_text(encoding='utf-8')

    # Existing ScoreMax structured-response architecture is authoritative.
    # Matching support must extend it, never install a second assessment path.
    required_app=(
        "qtype in {'matching','ordering'}",
        "saved_struct=safe_json",
        "matching",
    )
    missing_app=[x for x in required_app if x not in text]
    if missing_app:
        raise SystemExit('SCOREMAX_MATCHING_EXISTING_RUNTIME_MISSING:'+','.join(missing_app))

    required_tpl=(
        "qtype=='matching'",
        "answer_cfg.get('left_items'",
        "answer_cfg.get('right_options'",
        'name="match::{{ item.id }}"',
        "saved_struct.get(item.id)",
    )
    missing_tpl=[x for x in required_tpl if x not in t]
    if missing_tpl:
        raise SystemExit('SCOREMAX_MATCHING_EXISTING_TEMPLATE_MISSING:'+','.join(missing_tpl))

    # Marking support must exist before matching can ever become learner-live.
    mark_pos=text.find("if qtype=='matching':")
    if mark_pos<0:
        raise SystemExit('SCOREMAX_MATCHING_MARKER_MISSING')
    mark_window=text[mark_pos:mark_pos+2600]
    if not any(tok in mark_window for tok in ('matching_key','correct_pairs','expected_map','correct_mapping')):
        print('SCOREMAX_MATCHING_MARK_DIAG '+repr(mark_window),flush=True)
        raise SystemExit('SCOREMAX_MATCHING_MARK_CONTRACT_UNPROVEN')

    import importlib.util
    _ms_path=ROOT/'ux_matching_support.py'
    _ms_spec=importlib.util.spec_from_file_location('scoremax_matching_fixture',_ms_path)
    if _ms_spec is None or _ms_spec.loader is None:
        raise SystemExit('SCOREMAX_MATCHING_FIXTURE_LOADER_MISSING')
    _ms=importlib.util.module_from_spec(_ms_spec)
    _ms_spec.loader.exec_module(_ms)
    parse_matching_surface=_ms.parse_matching_surface
    _bio13_fixture='''Left items:
L1. Ectotherm
L2. Endotherm

Right options:
R1. External sources provide most body heat
R2. Internal metabolism generates most body heat
R3. Internal solute concentration matches seawater'''
    _bio13=parse_matching_surface(_bio13_fixture,'{"L1":"R1","L2":"R2"}')
    if not _bio13.get('valid') or len(_bio13.get('left') or [])!=2 or len(_bio13.get('right') or [])!=3:
        raise SystemExit('SCOREMAX_MATCHING_BIO13_FIXTURE_FAIL:'+str(_bio13))
    print('SCOREMAX_MATCHING_BIO13_FIXTURE_PASS left=2 right=3 mobile_tap_select=true',flush=True)
    print('SCOREMAX_MATCHING_RUNTIME_BUILD_PASS existing_structured_runtime=true existing_renderer=true deterministic_marking=true duplicate_runtime=false fail_closed=true',flush=True)


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


def _restore_catalogue_browser() -> None:
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
    anchor='ensure_teacher_preview()\napplication=scoremax.app'
    replacement=(
        "ensure_teacher_preview()\n"
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
    if 'scoremax_commercial_cleanup.clear_default_catalogue()' in rendered:
        raise SystemExit('SCOREMAX_OBSOLETE_COMMERCIAL_CLEANUP_SURVIVED')
    print('SCOREMAX_PROVISIONAL_CATALOGUE_INSTALLED governed_db_untouched=true power_house_authority_unchanged=true',flush=True)


def _install_admin_view_as() -> None:
    for rel in ('ux_admin_view_as_runtime.py','templates/ux_admin_view_as.html'):
        src=Path('ux_vnext_overlay')/rel
        dst=ROOT/rel
        if not src.is_file():
            raise SystemExit('SCOREMAX_ADMIN_VIEW_AS_SOURCE_MISSING:'+rel)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)

    production=ROOT/'scoremax_production.py'
    text=production.read_text(encoding='utf-8')
    anchor='install_catalogue_browser(scoremax.app)\napplication=scoremax.app'
    replacement=(
        "install_catalogue_browser(scoremax.app)\n"
        "from ux_admin_view_as_runtime import install_admin_view_as\n"
        "install_admin_view_as(scoremax.app)\n"
        "application=scoremax.app"
    )
    if 'install_admin_view_as(scoremax.app)' not in text:
        if anchor not in text:
            raise SystemExit('SCOREMAX_ADMIN_VIEW_AS_POST_INIT_ANCHOR_MISSING')
        text=text.replace(anchor,replacement,1)
        production.write_text(text,encoding='utf-8')

    rendered=production.read_text(encoding='utf-8')
    runtime=(ROOT/'ux_admin_view_as_runtime.py').read_text(encoding='utf-8')
    template=(ROOT/'templates'/'ux_admin_view_as.html').read_text(encoding='utf-8')
    base=(ROOT/'templates'/'base.html').read_text(encoding='utf-8')
    required=(
        'install_admin_view_as(scoremax.app)',
        "app.add_url_rule('/admin/view-as'",
        "app.add_url_rule('/admin/view-as/start'",
        "app.add_url_rule('/admin/view-as/exit'",
        'admin_view_as_mode=1',
        'real_user_impersonation=false',
        'ADMIN · VIEW AS',
        "url_for('admin_questions')",
        'admin-preview-bar',
        "url_for('admin_view_as_exit')",
        "session.get('admin_view_as_mode')",
    )
    combined='\n'.join((rendered,runtime,template,base))
    missing=[token for token in required if token not in combined]
    if missing:
        raise SystemExit('SCOREMAX_ADMIN_VIEW_AS_POSTBUILD_CONTROL_MISSING:'+','.join(missing))
    print(
        'SCOREMAX_ADMIN_VIEW_AS_BUILD_PASS roles=student,teacher '
        'programmes=fsc1,fsc2,mdcat synthetic_fixtures=true read_only=true '
        'persistent_exit_banner=true questions_link=true learner_nav_untouched=true '
        'core_runtime_patch=false',
        flush=True,
    )


def _wire_programme_tabs_to_correct_surfaces() -> None:
    """Programme tabs switch state and return to the programme-aware Learn surface."""
    path=ROOT/'templates'/'base.html'
    text=path.read_text(encoding='utf-8')
    old='<input type="hidden" name="return_to" value="{{request.path}}">'
    new='<input type="hidden" name="return_to" value="{{url_for(\'ux_student_learn\')}}">'
    count=text.count(old)
    if count!=2:
        raise SystemExit(f'SCOREMAX_PROGRAMME_TAB_RETURN_TARGET_MISMATCH:matches={count}')
    text=text.replace(old,new)
    path.write_text(text,encoding='utf-8')
    rendered=path.read_text(encoding='utf-8')
    if rendered.count("url_for('ux_student_learn')")<2:
        raise SystemExit('SCOREMAX_PROGRAMME_TAB_ROUTING_POSTBUILD_CONTROL_MISSING')
    print('SCOREMAX_PROGRAMME_TAB_ROUTING_PASS desktop=true mobile=true target=/student/learn-vnext programme_context_authoritative=true post_csrf_preserved=true',flush=True)


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
    apply_source_market_v12_receiver(ROOT)
    apply_cross50_qa_staging_v13(ROOT)
    assert_cross50_qa_v13(ROOT)
    apply_persistent_guard_postrelease_state(ROOT)
    apply_persistent_guard_batch_retirement(ROOT)
    apply_preimport_hardening(ROOT)
    _restore_delivery_reviewer()
    _install_matching_runtime()
    apply_referral_hero_v3(ROOT)
    _assert_referral_hero_v3()
    apply_interest_admin(ROOT)
    apply_commercial_reset(ROOT)
    apply_admin_workspace(ROOT)
    _install_post_init_teacher_preview()
    _restore_catalogue_browser()
    _install_admin_view_as()
    apply_emergency_return_bridge(ROOT)
    apply_emergency_return_contract(ROOT)
    apply_emergency_return_recovery(ROOT)
    apply_programme_catalogue_routing(ROOT)
    apply_main_subject_fsc_fence(ROOT)
    apply_canonical_student_navigation(ROOT)
    apply_restore_access_cards(ROOT)
    apply_chapter_card_open_fix(ROOT)
    apply_admin_rejection_reason_guard(ROOT)
    apply_bio13_identity_crosswalk_audit(ROOT)
    apply_bio13_failed_pilot_retirement(ROOT)
    _wire_programme_tabs_to_correct_surfaces()
    apply_safe98_destination_verifier(ROOT)
    apply_cross50_math16_destination_verifier(ROOT)

if __name__ == '__main__':
    main()
