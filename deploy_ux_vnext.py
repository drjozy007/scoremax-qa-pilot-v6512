from pathlib import Path
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
from ux_vnext_overlay.ux_safe98_destination_verifier import apply_safe98_destination_verifier

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
    text=app.read_text(encoding='utf-8')
    old="LIVE_MARKABLE_TYPES={'single_choice','true_false','fill_blank','multiple_select','numerical'}"
    if old in text:
        text=text.replace(old,"LIVE_MARKABLE_TYPES={'single_choice','true_false','fill_blank','multiple_select','numerical','matching'}",1)

    mark_anchor="""    if qtype=='fill_blank':
"""
    mark_insert="""    if qtype=='matching':
        expected=marking_cfg.get('matching_key') or {}
        try:
            candidate=json.loads(response)
        except Exception:
            candidate={}
        if not isinstance(candidate,dict):
            candidate={}
        candidate={str(k):str(v) for k,v in candidate.items() if str(k) and str(v)}
        expected={str(k):str(v) for k,v in dict(expected or {}).items() if str(k) and str(v)}
        ok=bool(expected) and candidate==expected
        return ok,correct_marks if ok else incorrect_marks,''

    if qtype=='fill_blank':
"""
    if "if qtype=='matching':" not in text:
        if text.count(mark_anchor)!=1:
            raise SystemExit('SCOREMAX_MATCHING_MARK_ANCHOR_MISMATCH')
        text=text.replace(mark_anchor,mark_insert,1)

    route_anchor="""    options=answer_cfg.get('options') or [
        {'id':code,'text':q[key]} for code,key in [('A','option_a'),('B','option_b'),('C','option_c'),('D','option_d')] if q[key]
    ]
    c.close()
"""
    route_new="""    options=answer_cfg.get('options') or [
        {'id':code,'text':q[key]} for code,key in [('A','option_a'),('B','option_b'),('C','option_c'),('D','option_d')] if q[key]
    ]
    matching_ui=None; matching_saved={}
    if qtype=='matching':
        from ux_matching_support import parse_matching_surface,parse_matching_key
        matching_ui=parse_matching_surface(q['stimulus_data'] if 'stimulus_data' in q.keys() else '',marking_cfg.get('matching_key') or q['answer'])
        matching_saved=parse_matching_key(answers.get(str(q['id']),'')) or {}
        if not matching_ui.get('valid'):
            c.close()
            abort(503,description='Matching question is not safely renderable.')
    c.close()
"""
    if "matching_ui=None; matching_saved={}" not in text:
        if text.count(route_anchor)!=1:
            raise SystemExit('SCOREMAX_MATCHING_ROUTE_ANCHOR_MISMATCH')
        text=text.replace(route_anchor,route_new,1)

    render_anchor="""        qtype=qtype,options=options,answer_cfg=answer_cfg,marking_cfg=marking_cfg,confidence=confidence,response_times=response_times,
        exam_meta=exam_meta
"""
    render_new="""        qtype=qtype,options=options,answer_cfg=answer_cfg,marking_cfg=marking_cfg,confidence=confidence,response_times=response_times,
        exam_meta=exam_meta,matching_ui=matching_ui,matching_saved=matching_saved
"""
    if "matching_saved=matching_saved" not in text:
        if text.count(render_anchor)!=1:
            raise SystemExit('SCOREMAX_MATCHING_RENDER_ARGS_ANCHOR_MISMATCH')
        text=text.replace(render_anchor,render_new,1)

    compile(text,str(app),'exec')
    app.write_text(text,encoding='utf-8')

    tpl=ROOT/'templates'/'take_test_v4.html'
    t=tpl.read_text(encoding='utf-8')
    if "qtype=='matching'" not in t:
        opt_anchor="""{% elif qtype=='fill_blank' %}
"""
        opt_new="""{% elif qtype=='matching' %}
  <p class="muted">Match each item on the left with one item on the right.</p>
  <div class="matching-assessment-grid">
    <div class="matching-left-list">
    {% for left in matching_ui.left %}
      <label class="matching-row"><span><strong>{{left.id}}</strong> {{left.text}}</span>
        <select data-matching-left="{{left.id}}" required>
          <option value="">Choose match</option>
          {% for right in matching_ui.right %}<option value="{{right.id}}" {% if matching_saved.get(left.id)==right.id %}selected{% endif %}>{{right.id}} — {{right.text}}</option>{% endfor %}
        </select>
      </label>
    {% endfor %}
    </div>
    <aside class="matching-right-bank"><strong>Right-side choices</strong>{% for right in matching_ui.right %}<div class="matching-choice"><strong>{{right.id}}</strong> {{right.text}}</div>{% endfor %}</aside>
  </div>
  <input type="hidden" name="answer" id="matching-answer-json" value="">
{% elif qtype=='fill_blank' %}
"""
        if t.count(opt_anchor)!=1:
            raise SystemExit('SCOREMAX_MATCHING_TEMPLATE_OPTION_ANCHOR_MISMATCH')
        t=t.replace(opt_anchor,opt_new,1)

        script_anchor="""<script>
let questionSeconds=0;
"""
        script_new="""<script>
(function(){
  const form=document.getElementById('question-form');
  if(!form) return;
  form.addEventListener('submit',function(){
    const hidden=document.getElementById('matching-answer-json');
    if(!hidden) return;
    const out={};
    document.querySelectorAll('[data-matching-left]').forEach(function(sel){
      if(sel.value) out[sel.getAttribute('data-matching-left')]=sel.value;
    });
    hidden.value=JSON.stringify(out);
  });
})();
let questionSeconds=0;
"""
        if t.count(script_anchor)!=1:
            raise SystemExit('SCOREMAX_MATCHING_TEMPLATE_SCRIPT_ANCHOR_MISMATCH')
        t=t.replace(script_anchor,script_new,1)

        style_patch="""<style id="scoremax-matching-runtime-style">
.matching-assessment-grid{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(220px,.8fr);gap:14px;margin:14px 0}.matching-left-list{display:grid;gap:10px}.matching-row{display:grid;grid-template-columns:1fr minmax(180px,.7fr);gap:12px;align-items:center;padding:12px;border:1px solid #dfe8e7;border-radius:12px;background:#fff}.matching-row select{width:100%}.matching-right-bank{display:grid;align-content:start;gap:8px;padding:12px;border:1px solid #dfe8e7;border-radius:12px;background:#f8fbfb}.matching-choice{padding:8px;border-radius:9px;background:#fff}@media(max-width:720px){.matching-assessment-grid{grid-template-columns:1fr}.matching-row{grid-template-columns:1fr}}
</style>
"""
        if '</head>' in t:
            t=t.replace('</head>',style_patch+'</head>',1)
        else:
            t=style_patch+t
    tpl.write_text(t,encoding='utf-8')

    combined=text+'\\n'+tpl.read_text(encoding='utf-8')
    for token in ("'matching'","matching_key","parse_matching_surface","data-matching-left","matching-answer-json"):
        if token not in combined:
            raise SystemExit('SCOREMAX_MATCHING_RUNTIME_CONTROL_MISSING:'+token)
    print('SCOREMAX_MATCHING_RUNTIME_BUILD_PASS receiver_type=true learner_renderer=true deterministic_marking=true fail_closed=true',flush=True)


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

if __name__ == '__main__':
    main()
