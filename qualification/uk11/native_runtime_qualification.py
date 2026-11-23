"""UK11 read-only explanation qualification in the exact assembled ScoreMax Docker runtime.

No real learner, school, source, or deployment data. Synthetic input is written only
inside a disposable /data tmpfs. No provider calls, emails, marks, or mastery writes.
This harness is meaningful only after the repository's exact Render build script has
replayed its authenticated, checksum-pinned runtime tree.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sqlite3
import sys
import traceback
from contextlib import contextmanager

RUNTIME=pathlib.Path('/app')
EVIDENCE=pathlib.Path('/evidence')
EVIDENCE.mkdir(parents=True,exist_ok=True)

# Match the synthetic configurations of ScoreMax's accepted paid-AI native startup.
# All environment values are disposable fixture values, not production credentials.
BASE='/data/scoremax'
pathlib.Path(BASE).mkdir(parents=True,exist_ok=True)
os.environ.update({
 'SCOREMAX_ENV':'production',
 'SCOREMAX_SECRET':'synthetic-uk11-qualification-secret-over-32-characters',
 'SCOREMAX_STAGING_SESSION_SECRET':'synthetic-uk11-staging-session-secret-only',
 'SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-UK11-Temporary-Only-2026',
 'SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'synthetic-uk11-admin@example.test',
 'SCOREMAX_SMTP_HOST':'smtp.example.test',
 'SCOREMAX_SMTP_FROM':'noreply@example.test',
 'SCOREMAX_PUBLIC_BASE_URL':'https://scoremax.pk',
 'SCOREMAX_SEND_EMAIL_VERIFICATION':'0',
 'SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1',
 'SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW':'0',
 'SCOREMAX_PERSISTENT_ROOT':BASE,
 'SCOREMAX_DB':BASE+'/state/scoremax.db',
 'SCOREMAX_BACKUP_DIR':BASE+'/backup',
 'SCOREMAX_CONTENT_INTAKE_DIR':BASE+'/intake',
 'SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/data',
 'SCOREMAX_INSTANCE_COUNT':'1',
 'WEB_CONCURRENCY':'1',
 'SCOREMAX_INVITE_ONLY_PILOT':'0',
 'SCOREMAX_PUBLIC_STUDENT_OPENING':'1',
 'SCOREMAX_PUBLIC_STUDENT_ACCOUNT_LIMIT':'20',
 'SCOREMAX_PUBLIC_STUDENT_REQUESTS_PER_SECOND':'2',
 'SCOREMAX_INTERNAL_FULL_ACCESS':'0',
 'SCOREMAX_PAID_AI_FEEDBACK':'0',
 'SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD':'0',
 'SCOREMAX_UK11_EXPLAIN_ENABLED_TEST_ONLY':'1',
})
os.environ.pop('DEEPSEEK_API_KEY',None)
sys.path.insert(0,str(RUNTIME))
sys.path.insert(0,'/checks/native_guard')

EVIDENCE_NAME='UK11_EXPLAIN_EXACT_NATIVE_RUNTIME.json'
result={'runtime_root':'/app','provider_calls':0,'production_database_access':False,
        'official_score_or_mastery_changed':False,'synthetic_only':True,'qualification_scope':'EXACT_ASSEMBLED_BASELINE_DISPOSABLE_OVERLAY'}

def record(stage,**data):
    result[stage]=data
    print('UK11_NATIVE '+stage+' '+json.dumps(data,sort_keys=True),flush=True)


def snapshot(c):
    return {t:(c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] if c.execute('SELECT 1 FROM sqlite_master WHERE name=?',(t,)).fetchone() else None) for t in ['attempts','attempt_answers','written_marking_runs','written_usage_ledger']}


def add(c,table,values):
    """Construct isolated synthetic fixtures using actual native SQLite constraints."""
    fields=[]
    for info in c.execute('PRAGMA table_info('+table+')').fetchall():
        name=info[1]; type_=str(info[2]).upper(); notnull=bool(info[3]);default=info[4];pk=bool(info[5]);
        if name in values: fields.append((name,values[name])); continue
        if notnull and default is None and not pk:
            fields.append((name,0 if any(t in type_ for t in ['INT','REAL','NUM','FLOAT','DEC']) else '{}'
                            if name.endswith('_json') else ''))
    cols=','.join(k for k,_ in fields)
    placeholders=','.join('?' for _ in fields)
    cursor=c.execute('INSERT INTO '+table+'('+cols+') VALUES ('+placeholders+')',[v for _,v in fields])
    return cursor.lastrowid


try:
    import scoremax_persistent_storage_guard as guard
    guard.main()
    import scoremax_production as hosted
    import uk11_result_explanation as explanation
    from flask import render_template

    app=hosted.application
    sm=hosted.scoremax
    assert callable(app.extensions.get('scoremax_written_ai_owned_material')),'WRITTEN_AI_NATIVE_OWNER_EXTENSION_MISSING'
    assert app.extensions['scoremax_uk11_explain']['official_score_changes'] is False
    assert app.extensions['scoremax_uk11_explain']['mastery_changes'] is False
    assert explanation.enabled() and not app.jinja_env.globals['paid_ai_feedback_enabled']()
    assert app.jinja_env.globals['uk11_explanation_available']()
    assert len([x for x in app.url_map.iter_rules() if x.endpoint=='uk11_explain_mistake'])==1
    for template in ['result.html','uk11_explain_mistake.html','learning_capsule.html']:
        app.jinja_env.get_template(template)
    record('native_boot',app_routes=len(list(app.url_map.iter_rules())),templates_compiled=3,
           paid_ai_disabled=True,uk11_explanation_guard=True,native_ownership_hook=True)

    c=sm.db()
    try:
        before=snapshot(c)
        with app.test_client() as client:
            # Without a session, the actual native auth is authoritative.
            response=client.get('/uk11/result/999/question/999/explain',base_url='https://scoremax.pk')
            assert response.status_code in (302,401,403),('unauthenticated',response.status_code)
            record('unauthenticated_rejected',status_code=response.status_code)

            # Create a synthetic student, preserving the actual native schema.
            uid=add(c,'users',dict(role='student',system_user_id='STU-999876',full_name='Synthetic UK learner',
                                  email='synthetic-uk11@example.test',username='uk11-qualification',
                                  password_hash='synthetic-not-a-password',account_status='active',
                                  email_verified=1,is_demo_account=0))
            c.commit()
            user=c.execute('SELECT session_version FROM users WHERE id=?',(uid,)).fetchone()
            with client.session_transaction(base_url='https://scoremax.pk') as state:
                state.update(user_id=uid,role='student',session_version=user['session_version'],
                             full_name='Synthetic UK learner',_csrf_token='synthetic-ci-csrf')
            response=client.get('/uk11/result/999/question/999/explain',base_url='https://scoremax.pk')
            assert response.status_code==404,('missing attempt',response.status_code)
            record('unknown_question_fails_closed',status_code=response.status_code)

            q_id=add(c,'questions',dict(question_id='UK11-SYN-QUESTION',family_id='UK11-SYN-FAMILY',family_key='UK11-SYN-FAMILY-KEY',
                question='What is 12 divided by 3?',answer='4',explanation='12 split into three equal groups gives 4 in each group.',
                level='Foundation',country='UK',programme='UK 11+',subject='Mathematics',chapter='Number',topic='Division',
                qtype='Numerical',status='Approved',review_status='Approved',active=1,scoremax_ready=1,
                guided=0,is_demo=0,content_environment='PRODUCTION',rights_status='OWNED',
                ph_question_id='UK11-SYN-QUESTION',ph_question_version_id='UK11-SYN-V1',
                ph_question_checksum_sha256='SYNTHETIC-CHECKSUM-1',ph_market_id='UK',ph_is_auto_markable=1,
                ph_release_id='UK11-SYN-RELEASE',ph_release_version='1',ph_release_checksum_sha256='SYNTHETIC-RELEASE-CHECKSUM-1'))
            # Reuse native publication's family gate: question approval alone is insufficient.
            add(c,'question_families',dict(family_key='UK11-SYN-FAMILY-KEY',family_id='UK11-SYN-FAMILY',
                review_status='Approved',active=1,country='UK',programme='UK 11+',subject='Mathematics'))
            assert c.execute('SELECT 1 FROM questions q WHERE q.id=? AND '+sm.live_question_clause('q'),
                             (q_id,)).fetchone(), 'SYNTHETIC_FAMILY_PUBLICATION_GATE_UNSATISFIED'
            pin={'question_db_id':q_id,'question_id':'UK11-SYN-QUESTION','question_version_id':'UK11-SYN-V1',
                 'question_checksum_sha256':'SYNTHETIC-CHECKSUM-1','release_id':'UK11-SYN-RELEASE',
                 'release_version':'1','release_checksum_sha256':'SYNTHETIC-RELEASE-CHECKSUM-1','market_id':'UK',
                 'projection':{'ph_market_id':'UK','ph_is_auto_markable':1}}
            sid=add(c,'assessment_sessions',dict(student_id=uid,mode='practice',status='submitted',
                  question_ids=str(q_id),saved_answers=json.dumps({str(q_id):'6'}),meta_json='{}',
                  ph_question_pins_json=json.dumps({str(q_id):pin}),ph_release_pins_json='{}'))
            aid=add(c,'attempts',dict(student_id=uid,assessment_session_id=sid,scope='subject',
                  programme='UK 11+',subject='Mathematics',chapters='Number',topic='Division',
                  score=0.0,correct_count=0,total_count=1,assessment_kind='standard'))
            answer_id=add(c,'attempt_answers',dict(attempt_id=aid,question_db_id=q_id,selected_answer='6',
                is_correct=0,marks_awarded=0.0,question_version=1,ph_question_id=pin['question_id'],
                ph_question_version_id=pin['question_version_id'],ph_question_checksum_sha256=pin['question_checksum_sha256'],
                ph_release_id=pin['release_id'],ph_release_version=pin['release_version'],
                ph_release_checksum_sha256=pin['release_checksum_sha256'],
                ph_question_snapshot_json=json.dumps(pin['projection'])))
            add(c,'integration_ph_question_version_store',dict(question_id=pin['question_id'],question_version_id=pin['question_version_id'],
                question_version_number=1,question_checksum_sha256=pin['question_checksum_sha256'],
                curriculum_json=json.dumps({'market_id':'UK'}),
                content_json=json.dumps({'stem':'What is 12 divided by 3?',
                   'marking':{'key_type':'NUMERIC','key':'4','explanation':'Three groups of 4 give 12; divide 12 by 3 to get 4.'}}),
                architecture_json=json.dumps({'evidence_role':'INDEPENDENT','independent_mastery_eligible':True,'independent_mastery_weight':1}),
                governance_json=json.dumps({'academic_review_state':'APPROVED','hold_status':'CLEAR','release_readiness':'READY',
                    'source_check_status':'CLEAR','r2_status':'NOT_REQUIRED','rights_status':'OWNED'}),
                provenance_json='{}',scoremax_projection_json='{}',first_admitted_at='2026-11-23T18:00:00Z'))
            add(c,'integration_ph_release_question_membership',dict(release_id=pin['release_id'],release_version='1',
                question_id=pin['question_id'],question_version_id=pin['question_version_id'],ordinal=1,
                admitted_at='2026-11-23T18:00:00Z'))
            add(c,'integration_ph_content_releases',dict(release_id=pin['release_id'],release_version='1',
                package_checksum_sha256=pin['release_checksum_sha256'],local_status='ACTIVE',
                market_id='UK',programme_id='UK11',subject_id='MATHEMATICS',chapter_id='SYNTHETIC'))
            add(c,'integration_ph_product_activation_authorizations',dict(release_id=pin['release_id'],release_version='1',
                package_checksum_sha256=pin['release_checksum_sha256'],activation_status='ACTIVATED'))
            c.commit()
            pre=snapshot(c)

            try:
                explanation.read_explanation(c,sm,attempt_id=aid,question_id=q_id,student_id=uid,
                    owned=app.extensions['scoremax_written_ai_owned_material'])
                record('native_authority_diagnostic',status='APPROVED')
            except Exception as err:
                record('native_authority_diagnostic',status='REJECTED',code=str(getattr(err,'code',type(err).__name__)))
                raise
            response=client.get(f'/uk11/result/{aid}/question/{q_id}/explain',base_url='https://scoremax.pk')
            assert response.status_code==200,('explained',response.status_code,response.data[:900])
            page=response.get_data(as_text=True)
            assert 'divide 12 by 3 to get 4' in page
            assert 'UK11-SYN-RELEASE' not in page and 'UK11-SYN-QUESTION' not in page
            assert 'Synthetic UK learner' not in page or 'Your' in page  # base navigation may show synthetic test name
            assert snapshot(c)==pre,'EXPLANATION_MUTATED_ATTEMPT_OR_AI_TABLES'
            record('submitted_wrong_answer_explained',status_code=200,
                   no_new_marks_or_ai_requests=True,approved_canonical_solution_in_page=True)

            c.execute('UPDATE attempt_answers SET is_correct=1 WHERE attempt_id=? AND question_db_id=?',(aid,q_id));c.commit()
            response=client.get(f'/uk11/result/{aid}/question/{q_id}/explain',base_url='https://scoremax.pk')
            assert response.status_code==404,('correct attempt',response.status_code)
            c.execute('UPDATE attempt_answers SET is_correct=0 WHERE attempt_id=? AND question_db_id=?',(aid,q_id));c.commit()
            record('correct_answers_denied',status_code=404)

            c.execute("UPDATE integration_ph_content_releases SET local_status='WITHDRAWN' WHERE release_id=?",(pin['release_id'],));c.commit()
            response=client.get(f'/uk11/result/{aid}/question/{q_id}/explain',base_url='https://scoremax.pk')
            assert response.status_code==404,('withdrawn',response.status_code)
            record('withdrawn_release_denied',status_code=404)

    finally:
        c.close()
    result.update(status='PASSED',runtime_qualified=True)
except Exception as exc:
    result.update(status='FAILED',runtime_qualified=False,error_type=type(exc).__name__,error=str(exc),trace=traceback.format_exc()[-7500:])
    print('UK11_NATIVE_FAILED',type(exc).__name__,exc,flush=True)
finally:
    (EVIDENCE/EVIDENCE_NAME).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print('UK11_NATIVE_RESULT '+json.dumps({k:v for k,v in result.items() if k!='trace'},sort_keys=True),flush=True)
if result['status']!='PASSED':sys.exit(1)
