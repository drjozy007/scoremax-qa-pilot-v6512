"""New synthetic AI tests and changed WSGI only. No model or reference-grade benchmark."""
import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from unittest.mock import patch
OUT=Path('/evidence');OUT.mkdir(exist_ok=True)
CG=Path('/sys/fs/cgroup')
def read(name):return dict((k,int(v)) for k,v in (l.split() for l in (CG/name).read_text().splitlines()))
before=read('memory.events');cpu=read('cpu.stat');started=time.monotonic()
p=subprocess.run([sys.executable,'-B','/checks/tests/paid_ai_marking_20261026/test_paid_ai.py','/app'],capture_output=True,text=True,timeout=45)
(OUT/'paid-ai-engineering-tests.log').write_text(p.stdout+p.stderr)
assert p.returncode==0,p.stdout+p.stderr
root=Path('/data/scoremax');root.mkdir()
os.environ.update({'SCOREMAX_ENV':'production','SCOREMAX_SECRET':'synthetic-paid-ai-linux-qualification-secret-over-32-characters','SCOREMAX_STAGING_SESSION_SECRET':'synthetic-staging-session-key-for-ci-only-2026','SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-CI-Only-AI-2026','SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'admin@scoremax.test','SCOREMAX_SMTP_HOST':'smtp.example.test','SCOREMAX_SMTP_FROM':'test@scoremax.test','SCOREMAX_PUBLIC_BASE_URL':'https://scoremax.pk','SCOREMAX_SEND_EMAIL_VERIFICATION':'0','SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1','SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW':'0','SCOREMAX_PERSISTENT_ROOT':str(root),'SCOREMAX_DB':str(root/'state/scoremax.db'),'SCOREMAX_BACKUP_DIR':str(root/'backup'),'SCOREMAX_CONTENT_INTAKE_DIR':str(root/'intake'),'SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/data','SCOREMAX_INSTANCE_COUNT':'1','WEB_CONCURRENCY':'1','SCOREMAX_INVITE_ONLY_PILOT':'0','SCOREMAX_PUBLIC_STUDENT_OPENING':'1','SCOREMAX_PUBLIC_STUDENT_ACCOUNT_LIMIT':'20','SCOREMAX_PUBLIC_STUDENT_REQUESTS_PER_SECOND':'2','SCOREMAX_INTERNAL_FULL_ACCESS':'0','SCOREMAX_PAID_AI_FEEDBACK':'0','SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD':'0'})
os.environ.pop('DEEPSEEK_API_KEY',None)
sys.path.insert(0,'/checks/native_guard')
import scoremax_persistent_storage_guard as guard
assert hashlib.sha256(Path(guard.__file__).read_bytes()).hexdigest()=='c1bff2fcbe000a05aeab4401b9267dd1e460425c485aa6efc683c642fed47195'
guard.main()
sys.path.insert(0,'/app')
import scoremax_production as hosted
app=hosted.application
assert not app.jinja_env.globals['paid_ai_feedback_enabled']()
app.jinja_env.get_template('result.html');app.jinja_env.get_template('_written_marking_run.html');app.jinja_env.get_template('written_result.html')
c=hosted.scoremax.db()
assert c.execute("SELECT 1 FROM sqlite_master WHERE name='paid_ai_feedback_requests'").fetchone() is None
cur=c.execute("""INSERT INTO users(role,system_user_id,full_name,email,username,password_hash,account_status,email_verified,is_demo_account)
 VALUES('student','STU-999801','Synthetic AI entitlement','ai-entitlement@example.test','synthetic-ai-entitlement','not-a-real-password-hash','active',1,0)""")
uid=cur.lastrowid;c.commit();version=c.execute('SELECT session_version FROM users WHERE id=?',(uid,)).fetchone()[0];c.close()
with app.test_client() as client:
 assert client.get('/healthz',base_url='https://scoremax.pk').status_code==200
 assert client.get('/test/result/999/question/1/ai-feedback',base_url='https://scoremax.pk').status_code==405
 assert client.post('/test/result/999/question/1/ai-feedback',base_url='https://scoremax.pk').status_code==400
 client.get('/login',base_url='https://scoremax.pk')
 with client.session_transaction(base_url='https://scoremax.pk') as state:
  state.update(user_id=uid,role='student',full_name='Synthetic AI entitlement',session_version=version,_csrf_token='synthetic-csrf')
 assert client.post('/test/result/999/question/1/ai-feedback',data={'_csrf_token':'synthetic-csrf'},base_url='https://scoremax.pk').status_code==403
 paid={'access_rank':1,'source':'provider','subscription':{'status':'active','price_minor':999}}
 with patch.object(hosted.scoremax,'get_access_profile',return_value=paid):
  assert client.post('/test/result/999/question/1/ai-feedback',data={'_csrf_token':'synthetic-csrf'},base_url='https://scoremax.pk').status_code==303

# Surrounding affected legacy caller, before and after the compatible extension.
sm=hosted.scoremax
import written_ai_adapter as ai
import written_response_engine as engine
c=sm.db()
payload={'version':'SM-RUBRIC-CLAUSES-1','maximum_marks':2,'question_id':'SYN-WR-1',
 'question_family_id':'SYN-WR-F1','question_type':'SHORT_RESPONSE',
 'question_text':'[SYNTHETIC] State the two symbols.','command_verb':'state','rubric_version':'SYN-1',
 'required_mark_points':[{'id':'P1','description':'First point','marks':1,'accepted_phrases':['x'],'acceptable_paraphrases':[]},
                         {'id':'P2','description':'Second point','marks':1,'accepted_phrases':['y'],'acceptable_paraphrases':[]}],
 'contradictions':[{'phrase':'not x','point_ids':['P1']}]}
package={'assessment_package_id':'SYN-WR-PACK','assessment_package_version':'1','framework_id':'SYN-FW',
 'framework_version_id':'SYN-FWV','subject_id':'Chemistry','chapter_id':'Synthetic','academic_approval_status':'APPROVED','questions':[payload]}
pid=c.execute("""INSERT INTO written_assessment_packages(assessment_package_id,assessment_package_version,
 framework_id,framework_version_id,subject_id,chapter_id,academic_approval_status,local_status,export_checksum,immutable_payload_json)
 VALUES('SYN-WR-PACK','1','SYN-FW','SYN-FWV','Chemistry','Synthetic','APPROVED','ACTIVE',?,?)""",
 (engine.package_checksum(package),json.dumps(package))).lastrowid
qid=c.execute("""INSERT INTO written_questions(package_id,question_source_id,question_family_id,question_type,
 question_text,command_verb,maximum_marks,question_json,active) VALUES(?,?,?,?,?,?,?,?,1)""",
 (pid,'SYN-WR-1','SYN-WR-F1','SHORT_RESPONSE',payload['question_text'],'state',2,json.dumps(payload))).lastrowid
def legacy_attempt(answer,index):
 aid=c.execute("""INSERT INTO written_attempts(student_id,written_question_id,package_id,attempt_mode,
 entry_method,evidence_type,support_level,novelty_status,status,maximum_mark,package_version,rubric_version)
 VALUES(?,?,?,'practice','typed','independent_production','independent','seen_family','SUBMITTED',2,'1','SYN-1')""",(uid,qid,pid)).lastrowid
 vid=c.execute("""INSERT INTO written_answer_versions(attempt_id,version_no,version_type,answer_text,word_count,is_frozen)
 VALUES(?,1,'ORIGINAL_TYPED',?,?,0)""",(aid,answer,len(answer.split()))).lastrowid
 c.commit();return aid,vid
aid,vid=legacy_attempt('x; y',0)
first=sm.written_evaluate_attempt(c,aid,vid);c.commit()
assert first[0]['proposed_mark']==2
before={t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in
 ('written_marking_runs','written_mark_point_results','written_processing_jobs','written_usage_ledger')}
assert sm.written_evaluate_attempt(c,aid,vid)==first;c.commit()
assert before=={t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in before}
ai.schema(c)
assert sm.written_evaluate_attempt(c,aid,vid)==first;c.commit()
for answer,expected in (('x',1),('x; not x; y',1)):
 aid2,vid2=legacy_attempt(answer,1)
 result,run_id=sm.written_evaluate_attempt(c,aid2,vid2);c.commit()
 assert result['proposed_mark']==expected
 row=c.execute('SELECT attempt_id,native_attempt_id,source_kind FROM written_marking_runs WHERE id=?',(run_id,)).fetchone()
 assert tuple(row)==(aid2,None,'WRITTEN')
aid3,vid3=legacy_attempt('A novel unauthored paraphrase.',2)
unscored,run=sm.written_evaluate_attempt(c,aid3,vid3);c.commit()
assert run is None and unscored['proposed_mark'] is None
assert c.execute('SELECT current_mark FROM written_attempts WHERE id=?',(aid3,)).fetchone()[0] is None
assert c.execute('SELECT count(*) FROM attempts').fetchone()[0]==0
with app.test_request_context('/'):
 from flask import render_template
 legacy_view=sm.written_attempt_view(c,aid,uid)
 legacy_html=render_template('_written_marking_run.html',run=legacy_view['runs'][0])
 assert '2.0 / 2.0' in legacy_html and 'PROVISIONAL PRACTICE FEEDBACK' not in legacy_html
legacy_counts={t:c.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in before}
job=c.execute("""INSERT INTO written_processing_jobs
 (attempt_id,native_attempt_id,native_question_id,source_kind,job_type,state,provider,idempotency_key)
 VALUES(NULL,1,1,'NATIVE_PROVISIONAL','SEMANTIC_FEEDBACK','FAILED_PROVIDER','synthetic','no-billable-retry')""").lastrowid
c.commit()
admin=c.execute("SELECT id,session_version FROM users WHERE role='admin' LIMIT 1").fetchone()
with app.test_client() as client:
 with client.session_transaction(base_url='https://scoremax.pk') as state:
  state.update(user_id=admin['id'],role='admin',session_version=admin['session_version'],_csrf_token='synthetic-csrf')
 reply=client.post('/admin/pilot-readiness/job/'+str(job)+'/retry',data={'_csrf_token':'synthetic-csrf'},base_url='https://scoremax.pk')
 assert reply.status_code==302
 assert c.execute('SELECT state,retry_count FROM written_processing_jobs WHERE id=?',(job,)).fetchone()['state']=='FAILED_PROVIDER'
 assert c.execute('SELECT retry_count FROM written_processing_jobs WHERE id=?',(job,)).fetchone()[0]==0
assert list(c.execute('PRAGMA integrity_check'))[0][0]=='ok'
assert not c.execute("SELECT 1 FROM sqlite_master WHERE name='paid_ai_feedback_requests'").fetchone()
c.close()

after=read('memory.events');delta={k:after[k]-before[k] for k in before}
assert all(delta[k]==0 for k in ('high','max','oom','oom_kill')),delta
result={'status':'CONSOLIDATED_WRITTEN_AI_ENGINEERING_PASS','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime_sha256':'ec1a17eb734df0657147f76800034807c53b9c31fa0236d0c56854827b7560a4','new_synthetic_engineering_tests':28,'independently_approved_reference_mark_tests':0,'independent_reference_mark_approval':'PENDING','model_benchmark_calls':0,'provider_spend_usd':0,'free_member_denied':True,'native_CSRF_required':True,'paid_member_without_configuration_denied':True,'separate_feedback_page_removed':True,'new_parallel_tables':0,'affected_legacy_written_regressions':6,'legacy_written_rows_and_replay_preserved':True,'native_and_written_identities_separate':True,'billable_admin_retry_rejected':True,'old_runtime_insert_shape_compatible':True,'AI_disabled_by_default':True,'AI_table_not_created_when_disabled':True,'official_score_or_mastery_writes':0,'existing_public_registration_tests_replayed':0,'historical_workloads_replayed':0,'native_startup_guard_unchanged':True,'healthz':200,'memory_event_delta':delta,'memory_peak_bytes':int((CG/'memory.peak').read_text()),'memory_limit_bytes':int((CG/'memory.max').read_text()),'cpu_stat_delta':{k:v-cpu.get(k,0) for k,v in read('cpu.stat').items()},'elapsed_seconds':time.monotonic()-started,'production_database_or_question_or_student_data_used':False,'existing_marking_fixtures_claimed_independent':False}
(OUT/'PAID_AI_ENGINEERING_LINUX_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
