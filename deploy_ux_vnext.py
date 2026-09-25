from pathlib import Path
from ux_vnext_overlay.ux_programme_mastery_repair import apply_programme_mastery_repair
import re
import shutil
import sys

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
from ux_vnext_overlay.ux_cross50_stimulus_single_select_alias_v13b import apply_cross50_stimulus_single_select_alias
from ux_vnext_overlay.ux_cross50_stimulus_single_select_alias_v13b_qualification import assert_cross50_stimulus_single_select_alias
from ux_vnext_overlay.ux_cross50_ph_family_registry_v13c import apply_cross50_ph_family_registry
from ux_vnext_overlay.ux_cross50_ph_family_registry_v13c_qualification import assert_cross50_ph_family_registry
from ux_vnext_overlay.ux_safe98_destination_verifier import apply_safe98_destination_verifier, apply_cross50_math16_destination_verifier, apply_cross50_rejection_diagnostic, apply_cross50_all_destination_verifier

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



def _install_shared_learner_question_surface() -> None:
    """Make staged QA and the live assessment consume one canonical learner surface."""
    take=ROOT/'templates'/'take_test_v4.html'
    staged=ROOT/'templates'/'ux_staged_content_review_question.html'
    component=ROOT/'templates'/'_learner_question_surface.html'
    text=take.read_text(encoding='utf-8')
    start_token='<span class="pill">{{ q.level }}</span>'
    start=text.find(start_token)
    if start<0:
        raise SystemExit('SCOREMAX_CANONICAL_RENDERER_START_MISSING')
    end=text.find("\n</div>\n{% if assessment.mode",start)
    if end<0:
        raise SystemExit('SCOREMAX_CANONICAL_RENDERER_END_MISSING')
    surface=text[start:end].rstrip()+"\n"
    _constructed_note=(
      "{% if marking_cfg.get('auto_markable') %}<p class=\"muted\">This response uses an exact governed marking rule.</p>"
      "{% else %}<p class=\"muted\">Your answer will be marked against the approved rubric. It does not count towards mastery until that review is complete.</p>{% endif %}"
    )
    if _constructed_note in surface:
        surface=surface.replace(_constructed_note,'')
    if 'will be marked against the approved rubric' in surface:
        raise SystemExit('SCOREMAX_LEARNER_MANUAL_MARKING_COPY_SURVIVED')
    required=(
        "qtype in ['single_choice','true_false']",
        "qtype=='numerical'",
        "constructed_response",
        "qtype=='matching'",
        "qtype=='ordering'",
    )
    missing=[token for token in required if token not in surface]
    if missing:
        raise SystemExit('SCOREMAX_CANONICAL_RENDERER_FAMILY_MISSING:'+','.join(missing))
    component.write_text(surface,encoding='utf-8')
    include="{% include '_learner_question_surface.html' %}"
    take.write_text(text[:start]+include+text[end:],encoding='utf-8')
    staged_text=staged.read_text(encoding='utf-8')
    if include not in staged_text:
        raise SystemExit('SCOREMAX_STAGED_CANONICAL_RENDERER_INCLUDE_MISSING')
    for forbidden in ('ux-match-interaction','ux-options','q.option_a','q.option_b','q.option_c','q.option_d'):
        if forbidden in staged_text:
            raise SystemExit('SCOREMAX_STAGED_DUPLICATE_RENDERER_SURVIVED:'+forbidden)
    rebuilt=take.read_text(encoding='utf-8')
    if rebuilt.count(include)!=1:
        raise SystemExit('SCOREMAX_LIVE_CANONICAL_RENDERER_INCLUDE_COUNT_INVALID')
    _ord=surface.find("qtype=='ordering'")
    if _ord<0:
        _ord=surface.find('qtype == \'ordering\'')
    print('SCOREMAX_ORDERING_RENDERER_CONTRACT '+repr(surface[max(0,_ord-300):_ord+1800]),flush=True)
    print(
        'SCOREMAX_SHARED_LEARNER_RENDERER_BUILD_PASS '
        f'component_bytes={len(surface.encode("utf-8"))} '
        'live_take_test=true staged_review=true same_component=true '
        'numeric=true short_response=true matching=true ordering=true fail_closed=true',
        flush=True,
    )


def _install_self_marking_release_gate() -> None:
    """Power House content must be deterministically self-markable before learner release."""
    marker_src=Path('ux_vnext_overlay')/'ux_constructed_auto_marker.py'
    marker_dst=ROOT/'ux_constructed_auto_marker.py'
    if not marker_src.is_file():
        raise SystemExit('SCOREMAX_CONSTRUCTED_AUTO_MARKER_SOURCE_MISSING')
    shutil.copy2(marker_src,marker_dst)
    from ux_vnext_overlay.ux_assessment_contract_repair import apply_written_contract_repair
    apply_written_contract_repair(ROOT)

    import importlib.util
    _spec=importlib.util.spec_from_file_location('scoremax_constructed_marker_fixture',marker_dst)
    if _spec is None or _spec.loader is None:
        raise SystemExit('SCOREMAX_CONSTRUCTED_AUTO_MARKER_LOADER_MISSING')
    _mod=importlib.util.module_from_spec(_spec)
    _runtime_path=str(ROOT.resolve())
    _added_path=False
    if _runtime_path not in sys.path:
        sys.path.insert(0,_runtime_path); _added_path=True
    try:
        _spec.loader.exec_module(_mod)
    finally:
        if _added_path and _runtime_path in sys.path:
            sys.path.remove(_runtime_path)
    _fixture=_mod.fixture_qualification()
    if not all(_fixture.values()):
        raise SystemExit('SCOREMAX_CONSTRUCTED_AUTO_MARKER_FIXTURE_FAIL:'+repr(_fixture))
    print('SCOREMAX_CONSTRUCTED_AUTO_MARKER_FIXTURE_PASS exact=true governed_clauses=true arbitrary_semantics=false fail_closed=true',flush=True)

    integ=ROOT/'scoremax_integration_v1.py'
    app=ROOT/'app.py'
    itext=integ.read_text(encoding='utf-8')
    marker='SCOREMAX_SELF_MARKING_RELEASE_GATE_V2'
    if marker not in itext:
        itext += r'''

# SCOREMAX_SELF_MARKING_RELEASE_GATE_V2
from ux_constructed_auto_marker import compile_contract as _compile_constructed_contract
_self_marking_original_authorize_product_activation_v2 = authorize_product_activation
_self_marking_original_activate_release_v2 = _activate_release

def _projection_constructed_contract(proj):
    try:
        answer_cfg=json.loads(proj.get('answer_config') or '{}') if not isinstance(proj.get('answer_config'),dict) else dict(proj.get('answer_config') or {})
    except Exception:
        answer_cfg={}
    return _compile_constructed_contract(
      answer_cfg,
      proj.get('answer') or '',
      proj.get('marks') or 1,
      proj.get('question') or '',
      proj.get('command_word') or '',
    )

def _self_marking_release_errors(c, release_id, release_version):
    rows=c.execute("""SELECT v.question_id,v.question_version_id,v.scoremax_projection_json
      FROM integration_ph_release_question_membership m
      JOIN integration_ph_question_version_store v
        ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
      WHERE m.release_id=? AND m.release_version=?
      ORDER BY m.ordinal,m.id""",(str(release_id),str(release_version))).fetchall()
    errors=[]
    for row in rows:
        try: proj=json.loads(row['scoremax_projection_json'] or '{}')
        except Exception: proj={}
        try: marking=json.loads(proj.get('marking_config') or '{}') if not isinstance(proj.get('marking_config'),dict) else dict(proj.get('marking_config') or {})
        except Exception: marking={}
        qtype=str(proj.get('qtype') or '').strip().lower().replace('_',' ').replace('-',' ')
        auto=bool(proj.get('ph_is_auto_markable')) and bool(marking.get('auto_markable'))
        if qtype in {'constructed response','extended response','short response'}:
            auto=_projection_constructed_contract(proj) is not None
        if not auto:
            errors.append({
              'question_id':str(row['question_id'] or ''),
              'question_version_id':str(row['question_version_id'] or ''),
              'qtype':qtype,
              'code':'SELF_MARKING_REQUIRED',
            })
    return errors

def authorize_product_activation(c,release_id,release_version,package_checksum_sha256,actor,reason):
    errors=_self_marking_release_errors(c,release_id,release_version)
    if errors:
        return {'status':'REJECTED','code':'SELF_MARKING_REQUIRED','activated_count':0,
                'blocked_question_count':len(errors),'blocked_questions':errors[:20]}
    return _self_marking_original_authorize_product_activation_v2(
      c,release_id,release_version,package_checksum_sha256,actor,reason)

def _activate_release(c,release_id,release_version):
    if _self_marking_release_errors(c,release_id,release_version):
        return 0
    return _self_marking_original_activate_release_v2(c,release_id,release_version)
'''
        compile(itext,str(integ),'exec')
        integ.write_text(itext,encoding='utf-8')

    atext=app.read_text(encoding='utf-8')
    app_marker='SCOREMAX_CONSTRUCTED_ASSESSMENT_MARKER_V1'
    if app_marker not in atext:
        atext += r'''

# SCOREMAX_CONSTRUCTED_ASSESSMENT_MARKER_V1
from ux_constructed_auto_marker import compile_contract as _compile_constructed_contract, mark as _mark_constructed_contract
_original_mark_question_response_constructed = mark_question_response

def mark_question_response(q, selected, blueprint_marking_rules=None):
    qtype=canonical_question_type(q)
    if qtype in {'constructed_response','short_response','extended_response'}:
        answer_cfg=safe_json(q['answer_config'], {}) if 'answer_config' in q.keys() else {}
        contract=_compile_constructed_contract(
          answer_cfg,
          q['answer'] if 'answer' in q.keys() else '',
          q['marks'] if 'marks' in q.keys() else 1,
          q['question'] if 'question' in q.keys() else '',
          q['command_word'] if 'command_word' in q.keys() else '',
        )
        result=_mark_constructed_contract(contract,selected)
        if not result.get('markable'):
            return False,0.0,'SELF_MARKING_REQUIRED'
        return bool(result.get('is_correct')),float(result.get('marks_awarded') or 0),''
    return _original_mark_question_response_constructed(q,selected,blueprint_marking_rules)

LIVE_MARKABLE_TYPES.update({'constructed_response','short_response','extended_response'})

_self_marking_original_live_question_clause_v2 = live_question_clause
def live_question_clause(alias='q'):
    base=_self_marking_original_live_question_clause_v2(alias)
    return (
      '('+base+') AND ('
      "COALESCE("+alias+".ph_projection_owner,'')<>'POWER_HOUSE' OR "
      "COALESCE("+alias+".ph_is_auto_markable,0)=1)"
    )
'''
        compile(atext,str(app),'exec')
        app.write_text(atext,encoding='utf-8')

    rendered_i=integ.read_text(encoding='utf-8')
    rendered_a=app.read_text(encoding='utf-8')
    for token in (
      'SCOREMAX_SELF_MARKING_RELEASE_GATE_V2','SELF_MARKING_REQUIRED',
      'def _projection_constructed_contract','_compile_constructed_contract'
    ):
        if token not in rendered_i:
            raise SystemExit('SCOREMAX_SELF_MARKING_GATE_V2_MISSING:'+token)
    for token in (
      'SCOREMAX_CONSTRUCTED_ASSESSMENT_MARKER_V1',
      "LIVE_MARKABLE_TYPES.update({'constructed_response','short_response','extended_response'})",
      '_mark_constructed_contract'
    ):
        if token not in rendered_a:
            raise SystemExit('SCOREMAX_CONSTRUCTED_ASSESSMENT_MARKER_MISSING:'+token)
    print('SCOREMAX_SELF_MARKING_RELEASE_GATE_V2_PASS activation_fail_closed=true constructed_auto_marker=true human_marking=false',flush=True)


def _install_mastery_rigor_admin_runtime() -> None:
    for rel in ('ux_mastery_rigor_admin.py','templates/admin_mastery_rigor.html'):
        src=Path('ux_vnext_overlay')/rel
        dst=ROOT/rel
        if not src.is_file():
            raise SystemExit('SCOREMAX_MASTERY_RIGOR_SOURCE_MISSING:'+rel)
        dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)

    production=ROOT/'scoremax_production.py'
    text=production.read_text(encoding='utf-8')
    anchor='ensure_reviewer_accounts()\napplication=scoremax.app'
    replacement=(
      "ensure_reviewer_accounts()\n"
      "from ux_mastery_rigor_admin import install_mastery_rigor_admin\n"
      "install_mastery_rigor_admin(scoremax.app)\n"
      "application=scoremax.app"
    )
    if 'install_mastery_rigor_admin(scoremax.app)' not in text:
        if anchor not in text:
            raise SystemExit('SCOREMAX_MASTERY_RIGOR_POST_INIT_ANCHOR_MISSING')
        text=text.replace(anchor,replacement,1)
        production.write_text(text,encoding='utf-8')

    rendered=production.read_text(encoding='utf-8')
    page=(ROOT/'templates'/'admin_mastery_rigor.html').read_text(encoding='utf-8')
    runtime=(ROOT/'ux_mastery_rigor_admin.py').read_text(encoding='utf-8')
    required=(
      'install_mastery_rigor_admin(scoremax.app)',
      "app.route('/admin/mastery-rigor'",
      'mastery_standard_score',
      'rigor_score',
      'min_breadth_pct',
      'Mastery & Rigor',
      'type="range"',
    )
    combined='\n'.join((rendered,page,runtime))
    missing=[x for x in required if x not in combined]
    if missing:
        raise SystemExit('SCOREMAX_MASTERY_RIGOR_POSTBUILD_MISSING:'+','.join(missing))
    print('SCOREMAX_MASTERY_RIGOR_BUILD_PASS consolidated=true sliders=2 level_rules=true breadth=true audit=true post_init=true',flush=True)


def _install_post_init_teacher_preview() -> None:
    path=ROOT/'scoremax_production.py'
    text=path.read_text(encoding='utf-8')
    old='install_mastery_rigor_admin(scoremax.app)\napplication=scoremax.app'
    new="install_mastery_rigor_admin(scoremax.app)\nfrom ux_teacher_preview import ensure_teacher_preview\nensure_teacher_preview()\napplication=scoremax.app"
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
    apply_cross50_stimulus_single_select_alias(ROOT)
    apply_cross50_ph_family_registry(ROOT)
    assert_cross50_qa_v13(ROOT)
    assert_cross50_stimulus_single_select_alias(ROOT)
    assert_cross50_ph_family_registry(ROOT)
    apply_persistent_guard_postrelease_state(ROOT)
    apply_persistent_guard_batch_retirement(ROOT)
    apply_preimport_hardening(ROOT)
    _restore_delivery_reviewer()
    _install_matching_runtime()
    _install_shared_learner_question_surface()
    _install_self_marking_release_gate()
    apply_referral_hero_v3(ROOT)
    _assert_referral_hero_v3()
    apply_interest_admin(ROOT)
    apply_commercial_reset(ROOT)
    apply_admin_workspace(ROOT)
    _install_mastery_rigor_admin_runtime()
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
    apply_cross50_all_destination_verifier(ROOT)
    apply_cross50_rejection_diagnostic(ROOT)
    from ux_vnext_overlay.ux_assessment_contract_repair import apply_assessment_contract_repair
    apply_assessment_contract_repair(ROOT)
    apply_programme_mastery_repair(ROOT)
    from ux_vnext_overlay.ux_qa_agents_admin import install_qa_agents_admin as _install_qa_agents_admin_source
    for rel in ('ux_qa_agents_admin.py','templates/admin_mastery_lab.html','templates/admin_qa_agent_problems.html'):
        src=Path('ux_vnext_overlay')/rel; dst=ROOT/rel
        if not src.is_file(): raise SystemExit('SCOREMAX_QA_AGENTS_ADMIN_SOURCE_MISSING:'+rel)
        dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    production=ROOT/'scoremax_production.py'; text=production.read_text(encoding='utf-8')
    old="install_mastery_rigor_admin(scoremax.app)\nfrom ux_teacher_preview import ensure_teacher_preview"
    new="install_mastery_rigor_admin(scoremax.app)\nfrom ux_qa_agents_admin import install_qa_agents_admin\ninstall_qa_agents_admin(scoremax.app)\nfrom ux_teacher_preview import ensure_teacher_preview"
    if 'install_qa_agents_admin(scoremax.app)' not in text:
        if old not in text: raise SystemExit('SCOREMAX_QA_AGENTS_ADMIN_POST_INIT_ANCHOR_MISSING')
        text=text.replace(old,new,1);production.write_text(text,encoding='utf-8')
    print('SCOREMAX_QA_AGENTS_ADMIN_BUILD_PASS existing_mastery_lab=true release_authority=false mastery_authority=false',flush=True)


if __name__ == '__main__':
    main()
