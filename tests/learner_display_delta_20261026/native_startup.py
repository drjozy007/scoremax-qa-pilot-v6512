"""Only new display tests and the modified WSGI import. Accepted eight/five suites are not replayed."""
import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
OUT=Path('/evidence');OUT.mkdir(exist_ok=True)
CG=Path('/sys/fs/cgroup')
def read(name):return dict((k,int(v)) for k,v in (l.split() for l in (CG/name).read_text().splitlines()))
before=read('memory.events');cpu=read('cpu.stat');started=time.monotonic()
p=subprocess.run([sys.executable,'-B','/checks/tests/learner_display_delta_20261026/test_display.py','/app'],capture_output=True,text=True,timeout=30)
(OUT/'display-tests.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stdout+p.stderr
root=Path('/data/scoremax');root.mkdir()
os.environ.update({'SCOREMAX_ENV':'production','SCOREMAX_SECRET':'synthetic-linux-delta-only-secret-over-32-characters','SCOREMAX_STAGING_SESSION_SECRET':'synthetic-staging-session-key-for-ci-only-2026','SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-CI-Only-Delta-2026','SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'admin@scoremax.test','SCOREMAX_SMTP_HOST':'localhost','SCOREMAX_SMTP_FROM':'test@scoremax.test','SCOREMAX_PUBLIC_BASE_URL':'https://scoremax.test','SCOREMAX_SEND_EMAIL_VERIFICATION':'0','SCOREMAX_PERSISTENT_ROOT':str(root),'SCOREMAX_DB':str(root/'state/scoremax.db'),'SCOREMAX_BACKUP_DIR':str(root/'backup'),'SCOREMAX_CONTENT_INTAKE_DIR':str(root/'intake'),'SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/data','SCOREMAX_INSTANCE_COUNT':'1','WEB_CONCURRENCY':'1','SCOREMAX_INVITE_ONLY_PILOT':'1','SCOREMAX_PILOT_STUDENT_IDS_JSON':'["STU-999901"]'})

sys.path.insert(0,'/checks/native_guard')
import scoremax_persistent_storage_guard as guard
assert hashlib.sha256(Path(guard.__file__).read_bytes()).hexdigest()=='c1bff2fcbe000a05aeab4401b9267dd1e460425c485aa6efc683c642fed47195'
guard.main()
sys.path.insert(0,'/app')
import scoremax_production as hosted
app=hosted.application
assert app.jinja_env.filters['learner_answer']('A')=='A'
with app.test_client() as client:
 status=client.get('/healthz',base_url='https://scoremax.test').status_code
assert status==200
after=read('memory.events');delta={k:after[k]-before[k] for k in before}
assert all(delta[k]==0 for k in ('high','max','oom','oom_kill')),delta
result={'status':'LEARNER_DISPLAY_AND_MODIFIED_WSGI_PASS','observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime_sha256':'037ee7cf7e2cf4a4400c28104a7a884b6cccfa4669c6a2ec85ee2f57858779ba','new_display_tests':6,'accepted_invitation_tests_replayed':0,'accepted_routing_tests_replayed':0,'historical_workloads_replayed':0,'native_startup_guard_unchanged':True,'healthz':status,'memory_event_delta':delta,'memory_peak_bytes':int((CG/'memory.peak').read_text()),'memory_limit_bytes':int((CG/'memory.max').read_text()),'cpu_stat_delta':{k:v-cpu.get(k,0) for k,v in read('cpu.stat').items()},'elapsed_seconds':time.monotonic()-started,'production_database_or_question_or_student_data_used':False,'official_marking_rules_changed':False,'full_gate_d_closed':False}
(OUT/'LEARNER_DISPLAY_LINUX_RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
