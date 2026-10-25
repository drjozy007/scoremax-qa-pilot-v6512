"""New invitation delta on the exact production WSGI path; synthetic users only."""
import contextlib,datetime,hashlib,importlib.metadata,io,json,os,resource,socket,sqlite3,subprocess,sys,time
from pathlib import Path
OUT=Path('/evidence');OUT.mkdir(exist_ok=True)
CG=Path('/sys/fs/cgroup')
def counters(name):return dict((k,int(v)) for k,v in (line.split() for line in (CG/name).read_text().splitlines()))
before=counters('memory.events');cpu_before=counters('cpu.stat');started=time.monotonic()
p=subprocess.run([sys.executable,'-B','/checks/tests/test_invite_only_pilot.py','-v'],capture_output=True,text=True,timeout=30)
(OUT/'invitation-boundary-tests.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stdout+p.stderr
root=Path('/tmp/scoremax-launch-delta');root.mkdir()
os.environ.update({'SCOREMAX_ENV':'production','SCOREMAX_SECRET':'synthetic-linux-delta-only-secret-over-32-characters','SCOREMAX_STAGING_SESSION_SECRET':'synthetic-staging-session-key-for-ci-only-2026','SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-CI-Only-Delta-2026','SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'admin@scoremax.test','SCOREMAX_SMTP_HOST':'localhost','SCOREMAX_SMTP_FROM':'test@scoremax.test','SCOREMAX_PUBLIC_BASE_URL':'https://scoremax.test','SCOREMAX_SEND_EMAIL_VERIFICATION':'0','SCOREMAX_PERSISTENT_ROOT':str(root),'SCOREMAX_DB':str(root/'state/scoremax.db'),'SCOREMAX_BACKUP_DIR':str(root/'backup'),'SCOREMAX_CONTENT_INTAKE_DIR':str(root/'intake'),'SCOREMAX_INSTANCE_COUNT':'1','WEB_CONCURRENCY':'1','SCOREMAX_INVITE_ONLY_PILOT':'1','SCOREMAX_PILOT_STUDENT_IDS_JSON':'["STU-999901"]'})
network_calls=[]
def no_network(self,address):network_calls.append('blocked');raise RuntimeError('NO_NETWORK_IN_SYNTHETIC_DELTA')
socket.socket.connect=no_network
sys.path.insert(0,'/app');import scoremax_production as hosted
app=hosted.application;native=hosted.scoremax
assert app.extensions['scoremax_invite_only_pilot']=={'enabled':True,'allowed_count':1}
c=native.db()
try:
 for n in (1,2):
  c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,academic_level,active_programme,subjects,account_status,email_verified,is_demo_account,session_version) VALUES(?,'student',?,?,?,?,?,'FSc Part 1','Biology,Chemistry,Physics,Mathematics','active',1,0,0)",(f'STU-99990{n}',f'Synthetic {n}',f'student{n}@scoremax.test',f'synthetic{n}','not-a-real-password','FSc Part 1'))
 ids=[c.execute('SELECT id FROM users WHERE system_user_id=?',(f'STU-99990{n}',)).fetchone()[0] for n in (1,2)];c.commit()
finally:c.close()
def client(uid,role='student'):
 cl=app.test_client()
 with cl.session_transaction(base_url='https://scoremax.test') as s:s['user_id']=uid;s['role']=role;s['session_version']=0
 return cl
checks={};invited=client(ids[0]);other=client(ids[1]);base='https://scoremax.test'
checks['healthz']=invited.get('/healthz',base_url=base).status_code;assert checks['healthz']==200
checks['invited_native_setup']=invited.get('/test/setup',base_url=base).status_code;assert checks['invited_native_setup']==200
checks['noninvited_native_setup']=other.get('/test/setup',base_url=base).status_code;assert checks['noninvited_native_setup']==403
checks['native_admin_role_fence']=invited.get('/admin',base_url=base).status_code;assert checks['native_admin_role_fence'] in (302,403)
checks['forged_session_role_fence']=client(ids[1],'admin').get('/admin',base_url=base).status_code;assert checks['forged_session_role_fence']==403
checks['formal_mastery_blocked']=invited.get('/student/mastery',base_url=base).status_code;assert checks['formal_mastery_blocked']==403
anonymous=app.test_client();anonymous.get('/login',base_url=base)
with anonymous.session_transaction(base_url=base) as s:token=s['_csrf_token']
checks['native_registration_post_blocked']=anonymous.post('/register/student',base_url=base,data={'_csrf_token':token}).status_code;assert checks['native_registration_post_blocked']==403
c=native.db()
try:
 assert c.execute("SELECT count(*) FROM users WHERE system_user_id IN ('STU-999901','STU-999902')").fetchone()[0]==2
 assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok'
 assert c.execute('SELECT count(*) FROM integration_ph_product_activation_authorizations').fetchone()[0]==0
finally:c.close()
after=counters('memory.events');cpu_after=counters('cpu.stat');delta={k:after[k]-before[k] for k in before};assert all(delta[k]==0 for k in ('high','max','oom','oom_kill')),delta
assert not network_calls
result={'status':'NEW_LINUX_RUNTIME_AND_INVITATION_DELTA_PASS','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime_sha256':'6151aa9c27feea18b36080613350b97230278eac8793f447d4db7e66486e87fe','unit_boundary_tests':8,'native_http_checks':checks,'memory_event_delta':delta,'memory_peak_bytes':int((CG/'memory.peak').read_text()),'memory_limit_bytes':int((CG/'memory.max').read_text()),'cpu_stat_delta':{k:cpu_after[k]-cpu_before[k] for k in cpu_before},'elapsed_seconds':time.monotonic()-started,'python':sys.version,'dependencies':{p:importlib.metadata.version(p) for p in ('Flask','Werkzeug','gunicorn','Pillow','jsonschema','openpyxl')},'external_network_calls':len(network_calls),'student_data_or_question_payloads':0,'production_import_or_activation':False,'historical_workload_repeated':False,'full_gate_d_closed':False}
(OUT/'LINUX_LAUNCH_DELTA_RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
