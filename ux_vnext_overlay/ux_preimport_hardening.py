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


def _fence_historical_admin_reviewer_workspace(text: str) -> str:
    anchor="def admin_reviewer_workspace():\n    if not require('admin'): return redirect(url_for('login'))"
    replacement="def admin_reviewer_workspace():\n    if not require('admin'): return redirect(url_for('login'))\n    # PRE-IMPORT HARDENING: academic review is owned by Power House.\n    return redirect(url_for('admin_integration_health'))"
    if anchor in text:
        text=text.replace(anchor,replacement,1)
    elif 'PRE-IMPORT HARDENING: academic review is owned by Power House.' not in text:
        raise SystemExit('PREIMPORT_ADMIN_REVIEWER_WORKSPACE_ANCHOR_MISSING')
    return text


def _disable_demo_progress_default(text: str) -> str:
    anchor="def load_demo_progress():\n    if not require('student'): return redirect(url_for('login'))\n    if SCOREMAX_ENV=='production':"
    replacement="def load_demo_progress():\n    if not require('student'): return redirect(url_for('login'))\n    if os.environ.get('SCOREMAX_ALLOW_DEMO_PROGRESS','0').strip()!='1':\n        flash('Demo progress is disabled.','error'); return redirect(url_for('student_dashboard'))\n    if SCOREMAX_ENV=='production':"
    if anchor in text:
        text=text.replace(anchor,replacement,1)
    elif "SCOREMAX_ALLOW_DEMO_PROGRESS" not in text:
        raise SystemExit('PREIMPORT_DEMO_PROGRESS_ANCHOR_MISSING')
    return text


def _harden_admin_payment_plan_validation(text: str) -> str:
    old="plan=c.execute('SELECT * FROM plans WHERE id=?',(plan_id,)).fetchone(); raw=request.form.get('amount','').strip(); gross=int(round(float(raw)*100)) if raw else int(plan['price_minor'] or 0)"
    new="plan=c.execute('SELECT * FROM plans WHERE id=?',(plan_id,)).fetchone(); raw=request.form.get('amount','').strip()\n            if not plan:\n                c.close(); flash('Choose a valid access plan before recording a payment.','error'); return redirect(url_for('admin_payments'))\n            try:\n                gross=int(round(float(raw)*100)) if raw else int(plan['price_minor'] or 0)\n            except (TypeError,ValueError):\n                c.close(); flash('Enter a valid payment amount.','error'); return redirect(url_for('admin_payments'))"
    if old in text:
        text=text.replace(old,new,1)
    elif 'Choose a valid access plan before recording a payment.' not in text:
        raise SystemExit('PREIMPORT_PAYMENT_VALIDATION_ANCHOR_MISSING')
    return text


def _repair_digital_coach_mock_state(root: Path) -> None:
    path=root/'digital_coach_engine.py'
    if not path.exists():
        raise SystemExit('PREIMPORT_DIGITAL_COACH_ENGINE_MISSING')
    text=path.read_text(encoding='utf-8')
    old="""def _mock_state(c,student_id):
    if not _table(c,'student_mock_forms'): return {'count':0,'avg':0.0,'last_score':None}
    if not _table(c,'attempts'): return {'count':0,'avg':0.0,'last_score':None}
    row=c.execute('''SELECT COUNT(*) n,COALESCE(ROUND(AVG(a.score),1),0) avg FROM student_mock_forms smf LEFT JOIN attempts a ON a.id=smf.attempt_id WHERE smf.student_id=?''',(student_id,)).fetchone()
    last=c.execute('''SELECT a.score FROM student_mock_forms smf JOIN attempts a ON a.id=smf.attempt_id WHERE smf.student_id=? ORDER BY smf.id DESC LIMIT 1''',(student_id,)).fetchone()
    return {'count':int(row['n'] or 0),'avg':float(row['avg'] or 0),'last_score':float(last['score']) if last and last['score'] is not None else None}
"""
    new="""def _mock_state(c,student_id):
    if not _table(c,'student_mock_forms'): return {'count':0,'avg':0.0,'last_score':None}
    form_cols=_cols(c,'student_mock_forms')
    count_row=c.execute('SELECT COUNT(*) n FROM student_mock_forms WHERE student_id=?',(student_id,)).fetchone()
    form_count=int(count_row['n'] or 0)
    if not _table(c,'attempts'):
        return {'count':form_count,'avg':0.0,'last_score':None}
    attempt_cols=_cols(c,'attempts')
    if not {'paper_id','student_id'}.issubset(form_cols) or not {'exam_paper_id','student_id','score'}.issubset(attempt_cols):
        return {'count':form_count,'avg':0.0,'last_score':None}
    scored=c.execute('''SELECT COALESCE(ROUND(AVG(a.score),1),0) avg
      FROM attempts a WHERE a.student_id=? AND a.exam_paper_id IN
      (SELECT smf.paper_id FROM student_mock_forms smf WHERE smf.student_id=? AND smf.paper_id IS NOT NULL)
      AND a.score IS NOT NULL''',(student_id,student_id)).fetchone()
    last=c.execute('''SELECT a.score FROM attempts a WHERE a.student_id=? AND a.exam_paper_id IN
      (SELECT smf.paper_id FROM student_mock_forms smf WHERE smf.student_id=? AND smf.paper_id IS NOT NULL)
      AND a.score IS NOT NULL ORDER BY a.id DESC LIMIT 1''',(student_id,student_id)).fetchone()
    return {'count':form_count,'avg':float(scored['avg'] or 0),'last_score':float(last['score']) if last and last['score'] is not None else None}
"""
    if old in text:
        text=text.replace(old,new,1)
    elif "form_cols=_cols(c,'student_mock_forms')" not in text:
        raise SystemExit('PREIMPORT_DIGITAL_COACH_MOCK_STATE_ANCHOR_MISSING')
    path.write_text(text,encoding='utf-8')


def _remove_inactive_reviewer_runtime_templates(root: Path) -> None:
    for name in ('ux_content_review.html','ux_content_review_question.html'):
        path=root/'templates'/name
        if path.exists(): path.unlink()


def _scrub_credential_logging(text: str) -> str:
    patterns=(
        (r"print\(f'\[ScoreMax V\{SCOREMAX_RELEASE_VERSION\}\] One-time bootstrap admin created: admin / \{bootstrap\}'\)","print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V\{SCOREMAX_RELEASE_VERSION\}\] Legacy demo admin password rotated\. New one-time local password: admin / \{bootstrap\}'\)","print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V[^']+\] One-time bootstrap admin created: admin / \{bootstrap\}'\)","print('[ScoreMax] One-time bootstrap admin created; credential withheld from logs.')"),
        (r"print\(f'\[ScoreMax V[^']+\] Legacy demo admin password rotated\. New one-time local password: admin / \{bootstrap\}'\)","print('[ScoreMax] Legacy bootstrap admin credential rotated; credential withheld from logs.')"),
    )
    for pattern,replacement in patterns: text=re.sub(pattern,replacement,text)
    return text


def apply_preimport_hardening(root: Path) -> None:
    app_path=root/'app.py'
    text=app_path.read_text(encoding='utf-8')
    text=_disable_demo_seed(text)
    text=_disable_staging_academic_reviewer_overlay(text)
    text=_fence_historical_admin_reviewer_workspace(text)
    text=_disable_demo_progress_default(text)
    text=_harden_admin_payment_plan_validation(text)
    text=_scrub_credential_logging(text)
    app_path.write_text(text,encoding='utf-8')
    _repair_digital_coach_mock_state(root)
    _remove_inactive_reviewer_runtime_templates(root)

    rendered=app_path.read_text(encoding='utf-8')
    coach=(root/'digital_coach_engine.py').read_text(encoding='utf-8')
    if PRIMARY_SEED_CONDITION in rendered: raise SystemExit('PREIMPORT_DEMO_SEED_EXECUTABLE_CONDITION_SURVIVED')
    if 'PRE-IMPORT HARDENING: governed question bank starts empty' not in rendered: raise SystemExit('PREIMPORT_DEMO_SEED_DISABLE_CONTROL_MISSING')
    anchor="built_in_demo_ids=('BIO001','BIO002','BIO003','BIO004','BIO005')"
    if anchor in rendered:
        pos=rendered.find(anchor); nearby=rendered[pos:pos+3500]
        if SYNTHETIC_POPULATION_CONDITION in nearby: raise SystemExit('PREIMPORT_SYNTHETIC_POPULATION_EXECUTABLE_CONDITION_SURVIVED')
        if 'synthetic qualification population disabled' not in nearby: raise SystemExit('PREIMPORT_SYNTHETIC_POPULATION_DISABLE_CONTROL_MISSING')
    if 'install_content_reviewer(app)' in rendered or 'ensure_reviewer_accounts()' in rendered: raise SystemExit('PREIMPORT_STAGING_REVIEWER_INSTALLER_SURVIVED')
    if 'PRE-IMPORT HARDENING: academic review is owned by Power House.' not in rendered: raise SystemExit('PREIMPORT_ADMIN_REVIEWER_FENCE_MISSING')
    if 'SCOREMAX_ALLOW_DEMO_PROGRESS' not in rendered: raise SystemExit('PREIMPORT_DEMO_PROGRESS_FENCE_MISSING')
    if 'Choose a valid access plan before recording a payment.' not in rendered: raise SystemExit('PREIMPORT_PAYMENT_VALIDATION_MISSING')
    if "form_cols=_cols(c,'student_mock_forms')" not in coach or 'smf.attempt_id' in coach: raise SystemExit('PREIMPORT_DIGITAL_COACH_SCHEMA_REPAIR_MISSING')
    for name in ('ux_content_review.html','ux_content_review_question.html'):
        if (root/'templates'/name).exists(): raise SystemExit('PREIMPORT_INACTIVE_REVIEWER_TEMPLATE_SURVIVED:'+name)
    for forbidden in ('One-time bootstrap admin created: admin /','New one-time local password: admin /'):
        if forbidden in rendered: raise SystemExit('PREIMPORT_CREDENTIAL_LOGGING_SURVIVED:'+forbidden)
    print('SCOREMAX_PREIMPORT_HARDENING_PASS zero_question_seed_disabled=true synthetic_population_disabled=true staging_reviewer_overlay_disabled=true admin_reviewer_workspace_fenced=true demo_progress_default_off=true payment_input_validation=true digital_coach_mock_schema_compatible=true inactive_reviewer_templates_removed=true credential_log_hygiene=true governed_import_only=true',flush=True)
