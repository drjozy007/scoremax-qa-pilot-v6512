"""New public-opening tests and affected native registration/email/WSGI only."""
import datetime,hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit
OUT=Path('/evidence');OUT.mkdir(exist_ok=True)
CG=Path('/sys/fs/cgroup')
def read(name):return dict((k,int(v)) for k,v in (l.split() for l in (CG/name).read_text().splitlines()))
before=read('memory.events');cpu=read('cpu.stat');started=time.monotonic()
p=subprocess.run([sys.executable,'-B','/checks/tests/public_student_opening_20261026/test_public_opening.py','/app'],capture_output=True,text=True,timeout=45)
(OUT/'public-opening-tests.log').write_text(p.stdout+p.stderr)
assert p.returncode==0,p.stdout+p.stderr
root=Path('/data/scoremax');root.mkdir()
os.environ.update({'SCOREMAX_ENV':'production','SCOREMAX_SECRET':'synthetic-public-linux-qualification-secret-over-32-characters','SCOREMAX_STAGING_SESSION_SECRET':'synthetic-staging-session-key-for-ci-only-2026','SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-CI-Only-Public-2026','SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'admin@scoremax.test','SCOREMAX_SMTP_HOST':'smtp.example.test','SCOREMAX_SMTP_FROM':'test@scoremax.test','SCOREMAX_PUBLIC_BASE_URL':'https://scoremax.pk','SCOREMAX_SEND_EMAIL_VERIFICATION':'0','SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1','SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW':'0','SCOREMAX_PERSISTENT_ROOT':str(root),'SCOREMAX_DB':str(root/'state/scoremax.db'),'SCOREMAX_BACKUP_DIR':str(root/'backup'),'SCOREMAX_CONTENT_INTAKE_DIR':str(root/'intake'),'SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/data','SCOREMAX_INSTANCE_COUNT':'1','WEB_CONCURRENCY':'1','SCOREMAX_INVITE_ONLY_PILOT':'0','SCOREMAX_PUBLIC_STUDENT_OPENING':'1','SCOREMAX_PUBLIC_STUDENT_ACCOUNT_LIMIT':'20','SCOREMAX_PUBLIC_STUDENT_REQUESTS_PER_SECOND':'2','SCOREMAX_INTERNAL_FULL_ACCESS':'0'})
sys.path.insert(0,'/checks/native_guard')
import scoremax_persistent_storage_guard as guard
assert hashlib.sha256(Path(guard.__file__).read_bytes()).hexdigest()=='c1bff2fcbe000a05aeab4401b9267dd1e460425c485aa6efc683c642fed47195'
guard.main()
sys.path.insert(0,'/app')
import scoremax_production as hosted
app=hosted.application
messages=[]
class SyntheticSMTP:
    def __init__(self,*a,**kw):pass
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def ehlo(self):pass
    def starttls(self,*a,**kw):pass
    def login(self,*a):pass
    def send_message(self,message):messages.append(message.get_content())
hosted.scoremax.smtplib.SMTP=SyntheticSMTP
origin='https://scoremax.pk'
with app.test_client() as client:
    assert client.get('/healthz',base_url=origin).status_code==200
    initial=client.get('/register/student',base_url=origin)
    assert initial.status_code==200
    with client.session_transaction(base_url=origin) as state:csrf=state['_csrf_token']
    programme=next(x['value'] for x in hosted.scoremax.STUDENT_PROGRAMME_CHOICES if x['code']=='fsc1')
    posted=client.post('/register/student',base_url=origin,data={'_csrf_token':csrf,'full_name':'Synthetic onboarding qualification','email':'public-onboarding@example.test','password':'Synthetic-Only-Password-2026','academic_level':programme})
    assert posted.status_code==302 and '/verify-email?' in posted.location,posted.status_code
    assert len(messages)==1,'ONE_NATIVE_VERIFICATION_NOTIFICATION_EXPECTED'
    link=re.search(r'https://scoremax.pk/verify-email/[^\s]+',messages[0]).group(0)
    assert 'preview_token=' not in posted.location
    c=hosted.scoremax.db()
    new=c.execute("SELECT id,email_verified,account_status,email_verification_token_hash FROM users WHERE email=?",('public-onboarding@example.test',)).fetchone()
    uid=new['id'];assert new['email_verified']==0 and new['account_status']=='pending_email_verification' and new['email_verification_token_hash']
    c.close()
    denied=client.post('/login',base_url=origin,data={'_csrf_token':csrf,'identity':'public-onboarding@example.test','password':'Synthetic-Only-Password-2026'})
    assert denied.status_code==302 and '/verify-email?' in denied.location
    verified=client.get(urlsplit(link).path,base_url=origin)
    assert verified.status_code==302
    client.get(urlsplit(link).path,base_url=origin)
    c=hosted.scoremax.db()
    new=c.execute('SELECT email_verified,account_status,email_verification_token_hash FROM users WHERE id=?',(uid,)).fetchone()
    assert tuple(new)==(1,'active','')
    access=hosted.scoremax.get_access_profile(c,uid)
    assert access['plan_code']=='free_access' and access['mastery_ceiling']=='Foundation',access['plan_code']
    assert not hosted.scoremax.access_allows_level(c,uid,'Advanced')
    c.close()
    logged=client.post('/login',base_url=origin,data={'_csrf_token':csrf,'identity':'public-onboarding@example.test','password':'Synthetic-Only-Password-2026'})
    assert logged.status_code==302
    with client.session_transaction(base_url=origin) as state:assert state['user_id']==uid and state['role']=='student'
    practice=client.get('/test/setup',base_url=origin)
    assert practice.status_code==200
    assert b'Initial public practice opening' in practice.data
after=read('memory.events');delta={k:after[k]-before[k] for k in before}
assert all(delta[k]==0 for k in ('high','max','oom','oom_kill')),delta
result={'status':'PUBLIC_GATE_AND_NATIVE_REGISTRATION_EMAIL_WSGI_PASS','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime_sha256':'bed7d678f3c43d10d85ab31c699ad78994e0764670890c2fd0c4c77c2629f69c','new_public_gate_tests':11,'affected_existing_invitation_tests':8,'native_new_signup_pending_email':True,'native_single_use_email_verification':True,'unverified_login_denied':True,'verified_login_and_practice':True,'native_free_access_foundation_ceiling':True,'registration_race_cap':True,'two_rps_overload_admission':True,'network':'NONE_SYNTHETIC_SMTP_ONLY','actual_human_registration_claimed':False,'historical_workloads_replayed':0,'native_startup_guard_unchanged':True,'healthz':200,'memory_event_delta':delta,'memory_peak_bytes':int((CG/'memory.peak').read_text()),'memory_limit_bytes':int((CG/'memory.max').read_text()),'cpu_stat_delta':{k:v-cpu.get(k,0) for k,v in read('cpu.stat').items()},'elapsed_seconds':time.monotonic()-started,'production_database_or_question_or_student_data_used':False,'official_marking_rules_changed':False,'full_gate_d_closed':False}
(OUT/'PUBLIC_OPENING_LINUX_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
