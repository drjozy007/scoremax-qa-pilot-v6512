"""End-to-end disposable ScoreMax login -> UK11 preference -> logout/login replay.

Uses the real assembled native app login, CSRF, session-version and logout.
Never uses real learner records or production DB. Native question/subject
allocation is not part of this test and remains a separate qualification.
"""
import os,sys,json,sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

BASE='/data/scoremax'
os.makedirs(BASE,exist_ok=True)
os.environ.update({
 'SCOREMAX_ENV':'production',
 'SCOREMAX_SECRET':'synthetic-uk11-login-integration-secret-over-32-characters',
 'SCOREMAX_STAGING_SESSION_SECRET':'synthetic-uk11-staging-session-only',
 'SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-UK11-Temporary-Only-2026',
 'SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'synthetic-admin@example.test',
 'SCOREMAX_SMTP_HOST':'smtp.example.test',
 'SCOREMAX_SMTP_FROM':'noreply@example.test',
 'SCOREMAX_PUBLIC_BASE_URL':'https://scoremax.pk',
 'SCOREMAX_SEND_EMAIL_VERIFICATION':'0',
 'SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1',
 'SCOREMAX_PERSISTENT_ROOT':BASE,
 'SCOREMAX_DB':BASE+'/state/scoremax.db',
 'SCOREMAX_BACKUP_DIR':BASE+'/backup',
 'SCOREMAX_CONTENT_INTAKE_DIR':BASE+'/intake',
 'SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/data',
 'SCOREMAX_INSTANCE_COUNT':'1',
 'WEB_CONCURRENCY':'1',
 'SCOREMAX_INVITE_ONLY_PILOT':'0',
 'SCOREMAX_PUBLIC_STUDENT_OPENING':'1',
 'SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW':'0',
 'SCOREMAX_PUBLIC_STUDENT_ACCOUNT_LIMIT':'20',
 'SCOREMAX_PUBLIC_STUDENT_REQUESTS_PER_SECOND':'2',
 'SCOREMAX_INTERNAL_FULL_ACCESS':'0',
 'SCOREMAX_PAID_AI_FEEDBACK':'0',
 'SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD':'0',
 'SCOREMAX_UK11_DISPOSABLE_TEST_MODE':'1'
})
os.environ.pop('DEEPSEEK_API_KEY',None)
sys.path[:0]=['/app','/qualifier','/checks/native_guard']
from uk11_preferences_migration import DDL
from uk11_native_mount import mount_into_disposable_scoremax
from uk11_native_student_home import install_disposable_student_home
import scoremax_persistent_storage_guard as guard
guard.main()
import scoremax_production as runtime
sm=runtime.scoremax
app=runtime.application

def record(key,**data):
 print('UK11_LOGIN_NATIVE '+key+' '+json.dumps(data,sort_keys=True),flush=True)

# Existing app initialise() is called by scoremax_production module.
dbpath=Path(os.environ['SCOREMAX_DB'])
assert dbpath.is_file(), 'EXACT_NATIVE_DB_NOT_INITIALISED'
c=sm.db()
c.execute(DDL)
users=[]
for suffix,role in [(1,'student'),(2,'student'),(3,'parent')]:
 username=f'uk11-native-{suffix}'
 password='Synthetic-only-Strong-Password-2026!'
 c.execute("""INSERT INTO users(system_user_id,role,full_name,username,email,password_hash,account_status)
 VALUES(?,?,?,?,?,?,?)""",(f'UKSYN-{suffix}',role,f'Synthetic UK {suffix}',username,f'uk11native{suffix}@example.test',generate_password_hash(password),'active'))
 users.append(c.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()['id'])
c.commit();c.close()
schools={'synthetic:school:a':{'name':'Alpha'},'synthetic:school:b':{'name':'Beta'},
         'synthetic:school:c':{'name':'Gamma'},'synthetic:school:pending':{'name':'Unmapped'}}
def resolve(keys,year):
 routes=[]
 if any(k in keys for k in ('synthetic:school:a','synthetic:school:b')):
  routes.append({'route_id':'synthetic:shared','name':'Shared Maths route','evidence_status':'SYNTHETIC_ONLY'})
 if 'synthetic:school:c' in keys:
  routes.append({'route_id':'synthetic:english','name':'English route','evidence_status':'SYNTHETIC_ONLY'})
 subjects=[]
 if any(k in keys for k in ('synthetic:school:a','synthetic:school:b')):subjects.append('Maths')
 if 'synthetic:school:c' in keys:subjects.append('English')
 pending=[{'message':'Unmapped admissions route'}] if 'synthetic:school:pending' in keys else []
 return {'schools':[schools[k] for k in keys],
         'routes':routes,'subjects':subjects,
         'pending':pending,'evidence_revision':'synthetic-only'}
out=mount_into_disposable_scoremax(app,'/app',sm.db,schools,resolve)
record('mounted',**out,route_count=len(list(app.url_map.iter_rules())))
home_overlay=install_disposable_student_home('/app',app)
record('native_student_home_installed',**home_overlay)
BASEURL='https://scoremax.pk'

def csrf(client):
 with client.session_transaction(base_url=BASEURL) as s:
  return s['_csrf_token']

def login(client,idx):
 page=paced_get(client,'/login',base_url=BASEURL)
 assert page.status_code==200,('LOGIN_FORM',page.status_code)
 token=csrf(client)
 resp=paced_post(client,'/login',base_url=BASEURL,data={'identity':f'uk11-native-{idx}','password':'Synthetic-only-Strong-Password-2026!','_csrf_token':token},follow_redirects=False)
 assert resp.status_code==302,('NATIVE_LOGIN_REDIRECT',resp.status_code,resp.data[:300])
 with client.session_transaction(base_url=BASEURL) as s:
  assert s.get('user_id')==users[idx-1],('NATIVE_LOGIN_SESSION',dict(s))
 record('native_login',student_index=idx,status=resp.status_code)
 return csrf(client)

import time
def paced_get(client,*args,**kwargs):
 time.sleep(1.3)  # honor existing native request-rate protection
 return getattr(client,'get')(*args,**kwargs)
def paced_post(client,*args,**kwargs):
 time.sleep(1.3)
 return getattr(client,'post')(*args,**kwargs)

with app.test_client() as client:
 anon=paced_get(client,'/uk11/api/me/schools',base_url=BASEURL)
 assert anon.status_code in (302,401,403),('ANON_ACCESS',anon.status_code)
 record('unauthenticated_guard',status=anon.status_code)
 t=login(client,1)
 initial=paced_get(client,'/uk11/api/me/schools',base_url=BASEURL)
 assert initial.status_code==200,('INITIAL_GET',initial.status_code)
 assert initial.json['school_keys']==[]
 no_csrf=paced_post(client,'/uk11/api/me/schools',base_url=BASEURL,json={'entry_year':2028,'revision':0,'school_keys':['synthetic:school:a']})
 assert no_csrf.status_code==400,('CSRF_MISSING',no_csrf.status_code)
 data={'entry_year':2028,'revision':0,'school_keys':['synthetic:school:a','synthetic:school:b']}
 saved=paced_post(client,'/uk11/api/me/schools',base_url=BASEURL,json=data,headers={'X-CSRF-Token':t})
 assert saved.status_code==200,('PREFERENCE_SAVE',saved.status_code,saved.data[:400])
 assert saved.json['subjects']==['Maths'] and len(saved.json['routes'])==1
 assert saved.json['revision']==1
 record('native_save',status=saved.status_code,selected=len(saved.json['school_keys']),route_count=len(saved.json['routes']))
 page=paced_get(client,'/uk11/my-learning',base_url=BASEURL)
 assert page.status_code==200,('NATIVE_DASHBOARD_INITIAL',page.status_code,page.data[:500])
 html=page.get_data(as_text=True)
 assert 'Alpha' in html and 'Beta' in html and 'Maths' in html
 assert 'English route' not in html and '<li>English</li>' not in html
 assert html.count('Shared Maths route')==1,('SHARED_TEST_NOT_DEDUPED',html)
 assert all(x in html for x in ('Foundation','Exam Ready','Advanced','Distinction','Expert','Elite','Not Yet Established'))
 record('dashboard_two_schools',status=page.status_code,shared_test_once=True,maths_only=True)
 native_home=paced_get(client,'/student',base_url=BASEURL)
 assert native_home.status_code==200,('UK_NATIVE_STUDENT_HOME',native_home.status_code,native_home.data[:500])
 native_html=native_home.get_data(as_text=True)
 assert 'uk11-school-context' in native_html and 'Alpha' in native_html and 'Beta' in native_html
 assert 'Shared Maths route' in native_html and native_html.count('Shared Maths route')==1
 assert 'English route' not in native_html and '<li>English</li>' not in native_html
 assert 'Not Yet Established' in native_html and 'Elite' in native_html
 assert 'MY SUBJECTS' not in native_html and 'COMING UP' not in native_html
 record('native_student_home_two_schools',status=native_home.status_code,maths_only=True)


 stale=paced_post(client,'/uk11/api/me/schools',base_url=BASEURL,json=data,headers={'X-CSRF-Token':t})
 assert stale.status_code==409,('STALE_REVISION',stale.status_code)
 logout=paced_get(client,'/logout',base_url=BASEURL,follow_redirects=False)
 assert logout.status_code in (302,303),('NATIVE_LOGOUT',logout.status_code)
 after=paced_get(client,'/uk11/api/me/schools',base_url=BASEURL)
 assert after.status_code in (302,401,403),('AFTER_LOGOUT',after.status_code)
 record('native_logout',status=logout.status_code)
 t=login(client,1)
 persisted=paced_get(client,'/uk11/api/me/schools',base_url=BASEURL)
 assert persisted.status_code==200 and persisted.json['school_keys']==data['school_keys'],('LOGIN_RESTORE',persisted.status_code)
 record('login_restore',status=persisted.status_code,revision=persisted.json['revision'])
 restored_page=paced_get(client,'/uk11/my-learning',base_url=BASEURL)
 assert restored_page.status_code==200 and 'Alpha' in restored_page.get_data(as_text=True)
 assert 'Beta' in restored_page.get_data(as_text=True)
 record('dashboard_after_login',status=restored_page.status_code)
 changed=paced_post(client,'/uk11/api/me/schools',base_url=BASEURL,
    json={'entry_year':2028,'revision':1,'school_keys':['synthetic:school:c','synthetic:school:pending']},
    headers={'X-CSRF-Token':t})
 assert changed.status_code==200,('CHANGE_SCHOOL',changed.status_code,changed.data[:300])
 assert changed.json['subjects']==['English'] and len(changed.json['routes'])==1 and len(changed.json['pending'])==1
 changed_page=paced_get(client,'/uk11/my-learning',base_url=BASEURL)
 changed_html=changed_page.get_data(as_text=True)
 assert changed_page.status_code==200
 assert 'Gamma' in changed_html and 'Unmapped' in changed_html
 assert 'English route' in changed_html and '<li>English</li>' in changed_html
 assert '<li>Maths</li>' not in changed_html and 'Shared Maths route' not in changed_html
 assert 'Unmapped admissions route' in changed_html
 assert 'Not Yet Established' in changed_html
 record('dashboard_changed_schools',status=changed_page.status_code,english_only=True,pending_visible=True)
 changed_home=paced_get(client,'/student',base_url=BASEURL)
 assert changed_home.status_code==200,('CHANGED_NATIVE_HOME',changed_home.status_code)
 changed_native=changed_home.get_data(as_text=True)
 assert 'Gamma' in changed_native and 'Unmapped' in changed_native
 assert 'English route' in changed_native and '<li>English</li>' in changed_native
 assert 'Shared Maths route' not in changed_native and '<li>Maths</li>' not in changed_native
 assert 'Admissions verification pending' in changed_native
 record('native_student_home_changed',status=changed_home.status_code,english_only=True,pending_visible=True)


 paced_get(client,'/logout',base_url=BASEURL)
 t2=login(client,2)
 isolated=paced_get(client,'/uk11/api/me/schools',base_url=BASEURL)
 assert isolated.status_code==200 and isolated.json['school_keys']==[],('SECOND_STUDENT_LEAK',isolated.status_code)
 record('cross_student_isolation',status=isolated.status_code)
 pakistan_home=paced_get(client,'/student',base_url=BASEURL)
 assert pakistan_home.status_code==200,('PAKISTAN_REGRESSION_HOME',pakistan_home.status_code)
 pakistan_html=pakistan_home.get_data(as_text=True)
 assert 'uk11-school-context' not in pakistan_html
 assert 'MY SUBJECTS' in pakistan_html and 'COMING UP' in pakistan_html
 record('pakistan_home_unchanged',status=pakistan_home.status_code,uk_panel_absent=True)

 paced_get(client,'/logout',base_url=BASEURL)
 login(client,3)
 forbidden=paced_get(client,'/uk11/api/me/schools',base_url=BASEURL)
 assert forbidden.status_code==403,('PARENT_ROLE_DENIAL',forbidden.status_code)
 record('parent_role_denial',status=forbidden.status_code)
print('UK11_NATIVE_LOGIN_PREFERENCES_REPLAY_PASSED')
