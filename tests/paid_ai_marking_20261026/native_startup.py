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
app.jinja_env.get_template('result.html');app.jinja_env.get_template('paid_ai_feedback.html')
c=hosted.scoremax.db()
assert c.execute("SELECT 1 FROM sqlite_master WHERE name='paid_ai_feedback_requests'").fetchone() is None
cur=c.execute("""INSERT INTO users(role,system_user_id,full_name,email,username,password_hash,account_status,email_verified,is_demo_account)
 VALUES('student','STU-999801','Synthetic AI entitlement','ai-entitlement@example.test','synthetic-ai-entitlement','not-a-real-password-hash','active',1,0)""")
uid=cur.lastrowid;c.commit();version=c.execute('SELECT session_version FROM users WHERE id=?',(uid,)).fetchone()[0];c.close()
with app.test_client() as client:
 assert client.get('/healthz',base_url='https://scoremax.pk').status_code==200
 assert client.post('/test/result/999/question/1/ai-feedback',base_url='https://scoremax.pk').status_code==400
 client.get('/login',base_url='https://scoremax.pk')
 with client.session_transaction(base_url='https://scoremax.pk') as state:
  state.update(user_id=uid,role='student',full_name='Synthetic AI entitlement',session_version=version)
 assert client.get('/test/result/999/question/1/ai-feedback',base_url='https://scoremax.pk').status_code==403
 paid={'access_rank':1,'source':'provider','subscription':{'status':'active','price_minor':999}}
 with patch.object(hosted.scoremax,'get_access_profile',return_value=paid):
  assert client.get('/test/result/999/question/1/ai-feedback',base_url='https://scoremax.pk').status_code==503
after=read('memory.events');delta={k:after[k]-before[k] for k in before}
assert all(delta[k]==0 for k in ('high','max','oom','oom_kill')),delta
result={'status':'PAID_AI_ENGINEERING_AND_DISABLED_NATIVE_WSGI_PASS','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime_sha256':'3c416aa54f3c81004be6ac2e1247df225eda8b775b617df7554fef6852f36f39','new_synthetic_engineering_tests':18,'independently_approved_reference_mark_tests':0,'independent_reference_mark_approval':'PENDING','model_benchmark_calls':0,'provider_spend_usd':0,'free_member_denied':True,'native_CSRF_required':True,'paid_member_without_configuration_denied':True,'AI_disabled_by_default':True,'AI_table_not_created_when_disabled':True,'official_score_or_mastery_writes':0,'existing_public_registration_tests_replayed':0,'historical_workloads_replayed':0,'native_startup_guard_unchanged':True,'healthz':200,'memory_event_delta':delta,'memory_peak_bytes':int((CG/'memory.peak').read_text()),'memory_limit_bytes':int((CG/'memory.max').read_text()),'cpu_stat_delta':{k:v-cpu.get(k,0) for k,v in read('cpu.stat').items()},'elapsed_seconds':time.monotonic()-started,'production_database_or_question_or_student_data_used':False,'existing_marking_fixtures_claimed_independent':False}
(OUT/'PAID_AI_ENGINEERING_LINUX_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
