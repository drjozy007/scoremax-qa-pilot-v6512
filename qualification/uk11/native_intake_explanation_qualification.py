"""UK11 native signed Power House -> ScoreMax -> scored attempt -> explanation replay.

Synthetic software qualification only: this creates NO academically approved UK item.
It runs inside the exact assembled ScoreMax runtime with offline /data tmpfs,
provider disabled, and ScoreMax's existing production auth, intake, scoring,
source-pinning, and release-activation code. No direct question/attempt inserts.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT=Path('/app')
EVIDENCE=Path('/evidence')
EVIDENCE.mkdir(parents=True,exist_ok=True)
DBROOT='/data/scoremax'
Path(DBROOT).mkdir(parents=True,exist_ok=True)
BASE_URL='https://scoremax.pk'
TOKEN='synthetic-uk11-ph-token'
SIGNING='synthetic-uk11-ph-signing-secret'

os.environ.update({
    'SCOREMAX_ENV':'production',
    'SCOREMAX_SECRET':'synthetic-uk11-native-intake-secret-over-32-characters',
    'SCOREMAX_STAGING_SESSION_SECRET':'synthetic-uk11-staging-session-secret-only',
    'SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-UK11-Temporary-Only-2026',
    'SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'synthetic-uk11-admin@example.test',
    'SCOREMAX_SMTP_HOST':'smtp.example.test',
    'SCOREMAX_SMTP_FROM':'noreply@example.test',
    'SCOREMAX_PUBLIC_BASE_URL':BASE_URL,
    'SCOREMAX_SEND_EMAIL_VERIFICATION':'0',
    'SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1',
    'SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW':'0',
    'SCOREMAX_PERSISTENT_ROOT':DBROOT,
    'SCOREMAX_DB':DBROOT+'/state/scoremax.db',
    'SCOREMAX_BACKUP_DIR':DBROOT+'/backup',
    'SCOREMAX_CONTENT_INTAKE_DIR':DBROOT+'/intake',
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
    'POWER_HOUSE_TO_SCOREMAX_TOKEN':TOKEN,
    'POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET':SIGNING,
})
os.environ.pop('DEEPSEEK_API_KEY',None)
sys.path.insert(0,str(ROOT))
sys.path.insert(0,'/checks/native_guard')

OUTPUT={'policy':'UK11-PH-TO-SM-NATIVE-INTAKE-EXPLANATION-SYNTHETIC-20261123',
        'synthetic_only':True,'real_uk_academic_approval':False,
        'provider_calls':0,'production_database_used':False,
        'official_mark_or_mastery_modified_by_explanation':False,
        'runtime_qualified':False,'status':'FAILED'}


def record(name,**values):
    OUTPUT[name]=values
    print('UK11_NATIVE_INTAKE '+name+' '+json.dumps(values,sort_keys=True),flush=True)


def must(test,reason):
    if not test:raise AssertionError(reason)


def package(intake):
    """Clone the repository's accepted-format software *example*; never invent IDs/approvals."""
    src=ROOT/'integration_examples/PH_SM_APPROVED_CONTENT_V1.example.json'
    obj=json.loads(src.read_text(encoding='utf8'))
    rel=obj['payload']['release']
    q=obj['payload']['questions'][0]
    now=intake.utcnow()
    rel.update({
        'release_id':'SOFTWARE-UK11-EXPLANATION-RELEASE',
        'release_version':'1',
        'market_id':'UK','programme_id':'UK11','subject_id':'MATHEMATICS',
        'chapter_id':'UK11-NUMBER',
        'release_status':'ACADEMICALLY_READY',  # synthetic protocol value only
        'generated_at':now,'effective_at':now,
        'question_count':1,'stimulus_count':0,
        'package_checksum_sha256':hashlib.sha256(b'SOFTWARE-UK11-RELEASE-1').hexdigest(),
        'manifest_checksum_sha256':hashlib.sha256(b'SOFTWARE-UK11-MANIFEST-1').hexdigest(),
        'supersedes_release_version':None,
    })
    q.update({
        'question_id':'SOFTWARE-UK11-Q-001',
        'question_version_id':'SOFTWARE-UK11-Q-001-V1',
        'question_version_number':1,
        'supersedes_question_version_id':None,
        'effective_from':now,
    })
    curr=q['curriculum']
    curr.update({'market_id':'UK','qualification_id':'UK11','board_exam_id':'SOFTWARE_FIXTURE',
                 'programme_id':'UK11','subject_id':'MATHEMATICS',
                 'chapter_id':'UK11-NUMBER','topic_id':'UK11-DIVISION',
                 'grade_year_id':None,'learning_outcome_ids':[],
                 'teaching_learning_outcome_ids':[],
                 'display':{'programme':'UK 11+','subject':'Mathematics',
                            'chapter':'Number','chapter_number':'1','section':'Arithmetic',
                            'topic':'Division','subtopic':None,'outcome_text':'Division of whole numbers'}})
    content=q['content']
    content.update({'language':'en','question_family_type':'MCQ',
                    'pedagogical_type':'COMPUTATION','exam_question_type':'SINGLE_BEST_ANSWER',
                    'stem':'What is 12 divided by 3?',
                    'stimulus_ref':None,'inline_stimulus':None,
                    'options':[{'option_id':id,'text':text,'is_display_only':False}
                               for id,text in [('A','2'),('B','4'),('C','6'),('D','9')]],
                    'statements':[],
                    'marking':{'key_type':'SINGLE_OPTION','key':'B','accepted_answers':[],
                               'numeric_tolerance':None,'marks':1,'negative_marks':0,
                               'rubric':None,'explanation':'12 divided into three equal groups gives 4 in each group.'},
                    'estimated_time_seconds':40,'command_word':'What'})
    arch=q['architecture']
    arch.update({'claim_family_id':'SOFTWARE-UK11-FAMILY-001',
                 'reasoning_seed_id':'SOFTWARE-UK11-SEED-001',
                 'knowledge_node_ids':['SOFTWARE-UK11-NODE-001'],
                 'dependency_group_id':None,'dependency_type':None,
                 'evidence_role':'INDEPENDENT','independent_mastery_eligible':True,
                 'independent_mastery_weight':1,'mastery_level':'FOUNDATION'})
    gov=q['governance']
    gov.update({'academic_review_state':'APPROVED',
                'r2_status':'NOT_REQUIRED','hold_status':'CLEAR',
                'source_check_status':'CLEAR','release_readiness':'READY',
                'rights_status':'OWNED','generated_clearance_status':'CLEARED',
                'review_evidence_refs':['SOFTWARE-FIXTURE-NOT-ACADEMIC-APPROVAL']})
    provenance=q['provenance']
    provenance['primary_source'].update({'source_id':'SOFTWARE-FIXTURE-NOT-REAL-ACADEMIC-SOURCE',
                                         'source_type':'ORIGINAL',
                                         'source_version':'synthetic-qualification-only',
                                         'source_title':'Synthetic software test',
                                         'locator':'Disposable native replay',
                                         'rights_status':'OWNED'})
    provenance['lineage']={'original_question_id':q['question_id'],
                           'amendment_reason':'synthetic_native_qualification'}
    q['question_checksum_sha256']=intake._object_checksum(q,'question_checksum_sha256')
    obj['payload'].update(questions=[q],stimuli=[],delivery_mode='INLINE')
    obj.update({'message_id':'SOFTWARE-UK11-CONTENT-MESSAGE-1',
                'correlation_id':'SOFTWARE-UK11-CORRELATION',
                'idempotency_key':'SOFTWARE-UK11-IDEMPOTENCY-1',
                'producer_version':'SOFTWARE-QUALIFICATION-ONLY',
                'occurred_at':now,'sent_at':now,
                'payload_checksum_sha256':intake.payload_checksum(obj['payload'])})
    return obj


def signed_intake(client,intake,envelope):
    url='/api/integration/v1/power-house/content-releases'
    timestamp=intake.utcnow()
    headers={'Authorization':'Bearer '+TOKEN,
             'X-Message-Id':envelope['message_id'],
             'X-Sent-At':timestamp,
             'X-Content-SHA256':envelope['payload_checksum_sha256'],
             'X-Signature':'hmac-sha256='+intake.signature('POST',url,envelope['message_id'],
                       timestamp,envelope['payload_checksum_sha256'],SIGNING)}
    return client.post(url,data=intake.canonical_json(envelope),headers=headers,
                       content_type='application/json',base_url=BASE_URL)


def make_learner(c):
    cursor=c.execute('''INSERT INTO users(role,system_user_id,full_name,email,username,
        password_hash,account_status,email_verified,is_demo_account,academic_level,active_programme)
        VALUES('student','STU-UK11-999902','Synthetic UK11 QA Learner',
        'software-uk11-only@example.test','software-uk11-native',
        'synthetic-not-a-real-password','active',1,0,'UK 11+','UK 11+')''')
    c.commit()
    return cursor.lastrowid


def counts(c):
    tables=('attempts','attempt_answers','written_marking_runs','written_usage_ledger')
    return {k:c.execute('SELECT COUNT(*) FROM '+k).fetchone()[0] for k in tables}


def main():
    import scoremax_persistent_storage_guard as persistent_guard
    persistent_guard.main()
    import scoremax_production as hosted
    sm=hosted.scoremax
    app=hosted.application
    intake=sm.integration_v1
    must(app.extensions.get('scoremax_uk11_explain') is not None,'EXPLAIN_OVERLAY_NOT_INSTALLED')
    must(callable(app.extensions.get('scoremax_written_ai_owned_material')),'NATIVE_AI_OWNER_MISSING')
    must(not app.jinja_env.globals['paid_ai_feedback_enabled'](),'PAID_AI_MUST_BE_DISABLED')
    must(os.environ['SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD']=='0','AI_BUDGET_MUST_BE_ZERO')
    for template in ('result.html','uk11_explain_mistake.html'):
        app.jinja_env.get_template(template)
    record('runtime',app_routes=len(list(app.url_map.iter_rules())),
           ai_provider_enabled=False,templates_compiled=True)

    envelope=package(intake)
    rel=envelope['payload']['release']
    source_q=envelope['payload']['questions'][0]
    with app.test_client() as client:
        delivery=signed_intake(client,intake,envelope)
        record('signed_content',status_code=delivery.status_code,
               receipt_status=(delivery.get_json() or {}).get('status'))
        must(delivery.status_code==202,('SIGNED_CONTENT_REJECTED',delivery.status_code,delivery.get_json()))
        replay=signed_intake(client,intake,envelope)
        must(replay.status_code==200,('IDEMPOTENT_REPLAY_FAILED',replay.status_code,replay.get_json()))
        record('idempotent_delivery',status_code=replay.status_code)

        c=sm.db()
        try:
            before=c.execute('SELECT local_status FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',
                   (rel['release_id'],rel['release_version'])).fetchone()
            must(before and before['local_status']=='STAGED','PH_ACCEPTED_RECEIPT_CONFLATED_WITH_ACTIVATION')
            must(c.execute('SELECT COUNT(*) FROM questions WHERE ph_question_id=?',(source_q['question_id'],)).fetchone()[0]==0,
                 'QUESTION_PUBLIC_BEFORE_ACTIVATION')
            record('source_staging',status='STAGED',learner_rows=0)
            decision=intake.authorize_product_activation(c,rel['release_id'],rel['release_version'],
                                 rel['package_checksum_sha256'],'SOFTWARE_FIXTURE_ONLY',
                                 'Synthetic staging and activation in disposable qualification database')
            c.commit()
            must(decision.get('status')=='ACTIVE',('NATIVE_ACTIVATION_FAILED',decision))
            qrow=c.execute('SELECT * FROM questions WHERE ph_question_id=?',(source_q['question_id'],)).fetchone()
            must(qrow and qrow['active']==1 and qrow['ph_projection_owner']=='POWER_HOUSE',
                 'NATIVE_QUESTION_MATERIALIZATION_FAILED')
            qid=qrow['id']
            must(qrow['ph_question_checksum_sha256']==source_q['question_checksum_sha256'],
                 'NATIVE_SOURCE_CHECKSUM_DRIFT')
            record('product_activation',status=decision.get('status'),question_id_pinned=True)
            uid=make_learner(c)
            programme=intake.question_contracts.programme_for_release(rel['programme_id'],
                                               intake.canonical_json(source_q['curriculum']))
            must(programme=='UK 11+',('UK_PROGRAMME_MAPPING_REQUIRED',programme))
            sid=sm.create_assessment_session(c,uid,'practice',None,[qid],{
                'programme':programme,'subject':'Mathematics',
                'chapters':'Number','scope':'chapter','level':'Foundation',
                'assessment_kind':'standard'})
            assessment=c.execute('SELECT * FROM assessment_sessions WHERE id=?',(sid,)).fetchone()
            pins=json.loads(assessment['ph_question_pins_json'])
            pin=pins[str(qid)]
            must(pin['question_id']==source_q['question_id'] and
                 pin['question_checksum_sha256']==source_q['question_checksum_sha256'],
                 'NATIVE_SESSION_PIN_INCONSISTENT_WITH_INTAKE')
            must(pin['projection']['ph_question_checksum_sha256']==source_q['question_checksum_sha256'],
                 'NATIVE_PROJECTION_CHECKSUM_NOT_BOUND')
            must(pin['market_id']=='UK','UK_PIN_SCOPE_LOST')
            sm.save_assessment(c,sid,answers={str(qid):'A'})
            c.commit()
            record('native_session',source_pins_verified=True,canonical_programme=programme)
        finally:c.close()

        with client.session_transaction(base_url=BASE_URL) as sess:
            u=sm.db()
            try: ver=u.execute('SELECT session_version FROM users WHERE id=?',(uid,)).fetchone()[0]
            finally:u.close()
            sess.update(user_id=uid,role='student',session_version=ver,
                        full_name='Synthetic UK11 QA Learner',_csrf_token='synthetic-uk11-csrf')
        submitted=client.post('/test/session/'+str(sid)+'/submit',
                        data={'_csrf_token':'synthetic-uk11-csrf'},base_url=BASE_URL)
        must(submitted.status_code==302,('NATIVE_SUBMISSION_REJECTED',submitted.status_code,submitted.data[:600]))
        c=sm.db()
        try:
            attempt=c.execute('SELECT * FROM attempts WHERE student_id=? AND assessment_session_id=?',
                              (uid,sid)).fetchone()
            must(attempt and attempt['correct_count']==0 and attempt['total_count']==1,
                 'INCORRECT_RESPONSE_NOT_NATIVELY_MARKED')
            aid=attempt['id']
            item=c.execute('SELECT * FROM attempt_answers WHERE attempt_id=? AND question_db_id=?',
                           (aid,qid)).fetchone()
            must(item and item['is_correct']==0 and item['selected_answer']=='A' and item['marks_awarded']==0,
                 'INCORRECT_MARK_NOT_NATIVE_ZERO')
            before=counts(c)
            record('native_marking',scored_incorrect=True,score=attempt['score'],
                   selected_response_correct=False)
        finally:c.close()
        explained=client.get(f'/uk11/result/{aid}/question/{qid}/explain',base_url=BASE_URL)
        page=explained.get_data(as_text=True)
        must(explained.status_code==200,('EXPLANATION_NOT_READY',explained.status_code,page[:500]))
        must('12 divided into three equal groups gives 4' in page,
             'CANONICAL_EXPLANATION_MISSING')
        must('SOFTWARE-UK11' not in page,'INTERNAL_SOURCE_ID_LEAKED')
        c=sm.db()
        try:
            must(counts(c)==before,'EXPLANATION_CHANGED_MARKS_OR_AI_REQUESTS')
        finally:c.close()
        record('wrong_answer_explanation',status_code=200,canonical_source_used=True,
               explanation_read_only=True)

        replay_submit=client.post('/test/session/'+str(sid)+'/submit',
                      data={'_csrf_token':'synthetic-uk11-csrf'},base_url=BASE_URL)
        must(replay_submit.status_code==302,'REPLAY_SUBMISSION_CHANGED_IDENTITY')
        c=sm.db()
        try:
            must(c.execute('SELECT COUNT(*) FROM attempts WHERE student_id=? AND assessment_session_id=?',
                           (uid,sid)).fetchone()[0]==1,'DOUBLE_ATTEMPT_ON_RETRY')
            record('submit_idempotency',single_attempt=True)
        finally:c.close()

        # Native source membership withdrawal must block all future explanation delivery.
        c=sm.db()
        try:
            c.execute("UPDATE integration_ph_content_releases SET local_status='WITHDRAWN' WHERE release_id=?",
                      (rel['release_id'],))
            c.commit()
        finally:c.close()
        response=client.get(f'/uk11/result/{aid}/question/{qid}/explain',base_url=BASE_URL)
        must(response.status_code==404,('WITHDRAWAL_EXPLANATION_NOT_BLOCKED',response.status_code))
        record('withdrawn_source_denied',status_code=404)

    OUTPUT.update(status='PASSED',runtime_qualified=True)

try:
    main()
except Exception as e:
    OUTPUT.update(status='FAILED',runtime_qualified=False,error=str(e),
                  error_type=type(e).__name__,trace=traceback.format_exc()[-9000:])
    print('UK11_NATIVE_INTAKE_FAILED',type(e).__name__,str(e),flush=True)
finally:
    (EVIDENCE/'UK11_NATIVE_INTAKE_EXPLANATION.json').write_text(
         json.dumps(OUTPUT,sort_keys=True,indent=2)+'\n',encoding='utf8')
    print('UK11_NATIVE_INTAKE_RESULT '+json.dumps({k:v for k,v in OUTPUT.items() if k!='trace'},sort_keys=True),flush=True)
if OUTPUT['status']!='PASSED':sys.exit(1)
