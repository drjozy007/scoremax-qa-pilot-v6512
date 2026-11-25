"""End-to-end disposable ScoreMax login -> UK11 preference -> logout/login replay.

Uses the real assembled native app login, CSRF, session-version and logout.
Never uses real learner records or production DB. Native question/subject
allocation is not part of this test and remains a separate qualification.
"""
import os,sys,json,sqlite3,re,hashlib
from urllib.parse import urlsplit
from datetime import datetime, timedelta, timezone
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
 'SCOREMAX_SMTP_PORT':'587',
 'SCOREMAX_SMTP_SSL':'0',
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
 'SCOREMAX_UK11_DISPOSABLE_TEST_MODE':'1',
 'SCOREMAX_UK11_TEST_REGISTRATION':'1'
})
os.environ.pop('DEEPSEEK_API_KEY',None)
sys.path[:0]=['/app','/qualifier','/checks/native_guard']
from uk11_preferences_migration import DDL, UK_MARKET_DDL, GUARDIAN_DDL
from uk11_native_mount import mount_into_disposable_scoremax
from uk11_native_student_home import install_disposable_student_home
from uk11_native_market_boundary import install_uk11_market_boundary
import scoremax_persistent_storage_guard as guard
guard.main()
import scoremax_production as runtime
sm=runtime.scoremax
app=runtime.application

class CapturedSMTP:
 """Network-free SMTP stand-in that captures actual native EmailMessage objects."""
 messages=[]
 def __init__(self,*args,**kwargs):pass
 def __enter__(self):return self
 def __exit__(self,*args):return False
 def ehlo(self,*args):return (250,b'local test')
 def starttls(self,*args,**kwargs):return (220,b'local test tls')
 def login(self,*args,**kwargs):return (235,b'local test')
 def send_message(self,message):
  type(self).messages.append(message)

# Native ScoreMax still builds its real verification token and sends an actual
# EmailMessage through its own mailer. Only the transport is replaced in this
# disposable no-network runner.
sm.smtplib.SMTP=CapturedSMTP

def record(key,**data):
 print('UK11_LOGIN_NATIVE '+key+' '+json.dumps(data,sort_keys=True),flush=True)

# Existing app initialise() is called by scoremax_production module.
dbpath=Path(os.environ['SCOREMAX_DB'])
assert dbpath.is_file(), 'EXACT_NATIVE_DB_NOT_INITIALISED'
c=sm.db()
c.execute(DDL)
c.execute(UK_MARKET_DDL)
c.executescript(GUARDIAN_DDL)
users=[]
for suffix,role in [(1,'student'),(2,'student'),(3,'parent'),(4,'parent')]:
 username=f'uk11-native-{suffix}'
 password='Synthetic-only-Strong-Password-2026!'
 c.execute("""INSERT INTO users(system_user_id,role,full_name,username,email,password_hash,account_status)
 VALUES(?,?,?,?,?,?,?)""",(f'UKSYN-{suffix}',role,f'Synthetic UK {suffix}',username,f'uk11native{suffix}@example.test',generate_password_hash(password),'active'))
 users.append(c.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()['id'])
# Student 1 belongs to UK regardless of selected school count; student 2
# remains Pakistan/legacy and must never access UK school routes.
c.execute("INSERT INTO uk11_learner_markets(student_user_id,market_id,programme_id) VALUES(?,?,?)",(users[0],"UK","UK11"))
c.execute("UPDATE users SET parent_link_code=? WHERE id=?",("P-SYNTHETIC-UK11-ONLY", users[0]))
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
# Do not overlay Pakistan's old /student presentation in the market-gated
# UK test. Explicit UK market is resolved before Pakistan student analytics.
market_gate=install_uk11_market_boundary(app,sm.db,app.view_functions["uk11_account.get_schools"])
record('native_uk_market_guard_installed',**market_gate)
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
 empty_market_home=paced_get(client,'/student',base_url=BASEURL)
 assert empty_market_home.status_code==200
 empty_html=empty_market_home.get_data(as_text=True)
 assert 'UK 11+' in empty_html and 'Not Yet Established' in empty_html and 'No target schools selected' in empty_html
 forbidden_tokens=('FSc','MDCAT','Pakistan','Biology','Chemistry')
 found_tokens=[token for token in forbidden_tokens if token in empty_html]
 record('uk_market_html_diagnostic',forbidden_tokens_found=found_tokens,
        snippet=empty_html[:350],length=len(empty_html))
 assert not found_tokens, ('CROSS_MARKET_UI_LEAK',found_tokens)
 record('explicit_uk_market_no_selection',status=200,no_pakistan_content=True)
 initial_guardian=paced_get(client,'/uk11/api/me/guardian-status',base_url=BASEURL)
 assert initial_guardian.status_code==200 and initial_guardian.json['status']=='PENDING_GUARDIAN'
 assert initial_guardian.json['learning_unlocked'] is False
 record('guardian_pending_on_first_login',status=initial_guardian.status_code)
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
 assert all(token not in native_html for token in ('FSc','MDCAT','Pakistan','Biology','Chemistry'))
 assert 'Shared Maths route' in native_html and native_html.count('Shared Maths route')==1
 assert 'English route' not in native_html and '<li>English</li>' not in native_html
 assert 'Not Yet Established' in native_html and 'Elite' in native_html
 assert 'MY SUBJECTS' not in native_html and 'COMING UP' not in native_html
 record('native_student_home_two_schools',status=native_home.status_code,maths_only=True)
 # UK account must not use Pakistan's unqualified native learning engines.
 for path in ('/test/setup','/subjects','/exam-centre','/study-plan'):
  blocked=paced_get(client,path,base_url=BASEURL)
  assert blocked.status_code==403,('UK_NATIVE_UNQUALIFIED_ROUTE_NOT_BLOCKED',path,blocked.status_code)
 record('uk_native_learning_fail_closed',count=4,status=403)


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
 assert isolated.status_code==403,('PAKISTAN_LEGACY_UK_API_DENIED',isolated.status_code)
 record('pakistan_uk_api_denied',status=isolated.status_code)
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
 # Native parent link must require BOTH existing child address and access code.
 # A parent account alone confers no UK guardian acknowledgement.
 uk_links=paced_get(client,'/uk11/api/guardian/students',base_url=BASEURL)
 assert uk_links.status_code==200 and uk_links.json['students']==[]
 missing_link=paced_post(client,f'/uk11/api/guardian/students/{users[0]}/decision',
   base_url=BASEURL,json={'decision':'APPROVED','text_version':'UK11-ONBOARDING-CANDIDATE-20261125'},
   headers={'X-CSRF-Token':csrf(client)})
 assert missing_link.status_code==403,('UNLINKED_PARENT_APPROVED',missing_link.status_code)
 native_link=paced_post(client,'/parent/link-student',base_url=BASEURL,data={
   '_csrf_token':csrf(client),'student_email':'uk11native1@example.test',
   'link_code':'P-SYNTHETIC-UK11-ONLY','relationship':'Guardian'},follow_redirects=False)
 assert native_link.status_code==302,('NATIVE_PARENT_LINK',native_link.status_code)
 linked=paced_get(client,'/uk11/api/guardian/students',base_url=BASEURL)
 assert linked.status_code==200 and len(linked.json['students'])==1
 assert linked.json['students'][0]['student_id']==users[0]
 assert linked.json['students'][0]['status']=='PENDING_GUARDIAN'
 wrong_version=paced_post(client,f'/uk11/api/guardian/students/{users[0]}/decision',base_url=BASEURL,
   json={'decision':'APPROVED','text_version':'UNKNOWN'},headers={'X-CSRF-Token':csrf(client)})
 assert wrong_version.status_code==400
 accepted=paced_post(client,f'/uk11/api/guardian/students/{users[0]}/decision',base_url=BASEURL,
   json={'decision':'APPROVED','text_version':'UK11-ONBOARDING-CANDIDATE-20261125'},
   headers={'X-CSRF-Token':csrf(client)})
 assert accepted.status_code==200 and accepted.json['status']=='ACKNOWLEDGED'
 assert accepted.json['learning_unlocked'] is False and accepted.json['legal_guardianship_verified'] is False
 record('linked_parent_acknowledged_no_learning_unlock',status=accepted.status_code)
 guardian_withdrawn=paced_post(client,f'/uk11/api/guardian/students/{users[0]}/decision',base_url=BASEURL,
   json={'decision':'REVOKED','text_version':'UK11-ONBOARDING-CANDIDATE-20261125'},
   headers={'X-CSRF-Token':csrf(client)})
 assert guardian_withdrawn.status_code==200 and guardian_withdrawn.json['status']=='PENDING_GUARDIAN'
 acknowledged_again=paced_post(client,f'/uk11/api/guardian/students/{users[0]}/decision',base_url=BASEURL,
   json={'decision':'APPROVED','text_version':'UK11-ONBOARDING-CANDIDATE-20261125'},
   headers={'X-CSRF-Token':csrf(client)})
 assert acknowledged_again.status_code==200 and acknowledged_again.json['status']=='ACKNOWLEDGED'
 record('guardian_explicit_withdrawal_and_reapproval',status=acknowledged_again.status_code,withdrawal_effective=True)
 paced_get(client,'/logout',base_url=BASEURL)
 # Separate parent cannot read the first parent's children or approve them.
 login(client,4)
 other=paced_get(client,'/uk11/api/guardian/students',base_url=BASEURL)
 assert other.status_code==200 and other.json['students']==[]
 other_decision=paced_post(client,f'/uk11/api/guardian/students/{users[0]}/decision',
   base_url=BASEURL,json={'decision':'APPROVED','text_version':'UK11-ONBOARDING-CANDIDATE-20261125'},
   headers={'X-CSRF-Token':csrf(client)})
 assert other_decision.status_code==403,('OTHER_PARENT_APPROVAL',other_decision.status_code)
 record('cross_family_guardian_access_denied',status=other_decision.status_code)
 paced_get(client,'/logout',base_url=BASEURL)
 login(client,1)
 approved_status=paced_get(client,'/uk11/api/me/guardian-status',base_url=BASEURL)
 assert approved_status.status_code==200 and approved_status.json['status']=='ACKNOWLEDGED'
 with sm.db() as c:
  link_id=c.execute("SELECT id FROM parent_student_links WHERE student_user_id=? AND parent_user_id=?",
    (users[0],users[2])).fetchone()['id']
 revoked_link=paced_post(client,f'/student/parent-link/{link_id}/revoke',
   base_url=BASEURL,data={'_csrf_token':csrf(client)},follow_redirects=False)
 assert revoked_link.status_code==302,('NATIVE_PARENT_LINK_REVOKE',revoked_link.status_code)
 pending_again=paced_get(client,'/uk11/api/me/guardian-status',base_url=BASEURL)
 assert pending_again.status_code==200 and pending_again.json['status']=='PENDING_GUARDIAN'
 record('native_link_revocation_removes_guardian_acknowledgement',status=pending_again.status_code)
 paced_get(client,'/logout',base_url=BASEURL)
 login(client,3)
 linked_again=paced_get(client,'/uk11/api/guardian/students',base_url=BASEURL)
 assert linked_again.status_code==200 and linked_again.json['students']==[]
 record('guardian_revoke_removes_parent_access',status=linked_again.status_code)


# Test native UK student registration without adding a second authentication flow.
# Account and market mapping must commit atomically through the native handler.
 paced_get(client,'/logout',base_url=BASEURL)
 signup=paced_get(client,'/register/student',base_url=BASEURL)
 assert signup.status_code==200,('UK_SIGNUP_FORM',signup.status_code)
 signup_html=signup.get_data(as_text=True)
 assert 'Join ScoreMax UK 11+' in signup_html and 'UK11' in signup_html
 assert all(t not in signup_html for t in ('FSc','MDCAT','Biology','Chemistry'))
 registration=paced_post(client,'/register/student',base_url=BASEURL,data={
   '_csrf_token':csrf(client),
   'full_name':'Synthetic UK Learner',
   'email':'uk11-new-registration@example.test',
   'password':'Synthetic-only-Strong-Password-2026!',
   'academic_level':'UK11'
 },follow_redirects=False)
 record('native_signup_http_result',status=registration.status_code,redirect=registration.headers.get('Location',''))
 assert registration.status_code in (302,303),('NATIVE_UK_REGISTRATION',registration.status_code,registration.data[:250])
 with sm.db() as c:
  person=c.execute("SELECT id,role,active_programme,academic_level,account_status,email_verified FROM users WHERE email=?",('uk11-new-registration@example.test',)).fetchone()
  if person is None:
   with client.session_transaction(base_url=BASEURL) as state:
    messages=state.get('_flashes',[])
   record('native_signup_rejected',flash_categories=[m[0] for m in messages],flash_message_hints=[str(m[1])[:160] for m in messages])
  assert person is not None and person['role']=='student'
  assert person['active_programme']=='UK11'
  market=c.execute("SELECT market_id,programme_id FROM uk11_learner_markets WHERE student_user_id=?",(person['id'],)).fetchone()
  assert market is not None and market['market_id']=='UK' and market['programme_id']=='UK11'
  assert not person['email_verified'],('NEW_STUDENT_MUST_START_EMAIL_UNVERIFIED',person['email_verified'])
  record('native_email_verification_gate_required',account_status=person['account_status'],verified=bool(person['email_verified']))
  issued_hash=person['email_verification_token_hash'] if 'email_verification_token_hash' in person.keys() else c.execute(
   "SELECT email_verification_token_hash FROM users WHERE id=?",(person['id'],)).fetchone()[0]
  assert issued_hash and len(issued_hash)==64,('NATIVE_VERIFICATION_HASH_NOT_ISSUED',)
 record('native_registration_provisioned_uk_market',status=registration.status_code,market='UK',programme='UK11')
 assert len(CapturedSMTP.messages)==1,('NATIVE_SMTP_NOT_CAPTURED',len(CapturedSMTP.messages))
 message=CapturedSMTP.messages[0]
 assert message['To']=='uk11-new-registration@example.test'
 assert 'Verify your ScoreMax email' in message['Subject']
 links=re.findall(r'https://[^\s]+',message.get_content())
 verify_url=next(x for x in links if '/verify-email/' in x)
 parsed=urlsplit(verify_url)
 assert parsed.scheme=='https' and parsed.netloc=='scoremax.pk'
 verification_path=parsed.path
 token=verification_path.rsplit('/',1)[-1]
 assert hashlib.sha256(token.encode()).hexdigest()==issued_hash
 with sm.db() as c:
  user_row=c.execute("SELECT * FROM users WHERE email=?",('uk11-new-registration@example.test',)).fetchone()
  first_expires=user_row['email_verification_expires_at']
  assert token not in str(dict(user_row)),('PLAINTEXT_TOKEN_LEAKED_TO_DB',)
 record('native_verification_token_issued',smtp_captured=1,hashed_at_rest=True,expires_configured=bool(first_expires))
 # Existing ScoreMax login must deny a registered but unverified UK student.
 login_page=paced_get(client,'/login',base_url=BASEURL)
 assert login_page.status_code==200
 unverified_login=paced_post(client,'/login',base_url=BASEURL,data={
  'identity':'uk11-new-registration@example.test',
  'password':'Synthetic-only-Strong-Password-2026!',
  '_csrf_token':csrf(client)
 },follow_redirects=False)
 assert unverified_login.status_code==302 and '/verify-email?' in unverified_login.headers['Location'],(
  'UNVERIFIED_LOGIN_NOT_BLOCKED',unverified_login.status_code,unverified_login.headers.get('Location'))
 with client.session_transaction(base_url=BASEURL) as sess:
  assert 'user_id' not in sess,('UNVERIFIED_LOGIN_CREATED_SESSION',)
 record('native_unverified_login_blocked',status=unverified_login.status_code)
 # A resend within the 60-second cooldown must not generate another token.
 resend_data={'identity':'uk11-new-registration@example.test','_csrf_token':csrf(client)}
 rapid_resend=paced_post(client,'/verify-email/resend',base_url=BASEURL,data=resend_data,follow_redirects=False)
 assert rapid_resend.status_code==302 and len(CapturedSMTP.messages)==1,('RESEND_COOLDOWN_BYPASS',len(CapturedSMTP.messages))
 with sm.db() as c:
  c.execute("UPDATE users SET email_verification_sent_at=? WHERE email=?",
    ((datetime.now(timezone.utc)-timedelta(seconds=65)).isoformat(),
     'uk11-new-registration@example.test'))
  c.commit()
 valid_resend=paced_post(client,'/verify-email/resend',base_url=BASEURL,data=resend_data,follow_redirects=False)
 assert valid_resend.status_code==302 and len(CapturedSMTP.messages)==2,('RESEND_DID_NOT_ROTATE',len(CapturedSMTP.messages))
 new_links=re.findall(r'https://[^\s]+',CapturedSMTP.messages[-1].get_content())
 fresh_path=urlsplit(next(x for x in new_links if '/verify-email/' in x)).path
 assert fresh_path!=verification_path,('VERIFICATION_TOKEN_REUSED',)
 old_response=paced_get(client,verification_path,base_url=BASEURL,follow_redirects=False)
 assert old_response.status_code==302
 with sm.db() as c:
  current=c.execute("SELECT email_verified,email_verification_expires_at FROM users WHERE email=?",
   ('uk11-new-registration@example.test',)).fetchone()
  assert not current['email_verified'],('OLD_TOKEN_CLAIMED_AFTER_ROTATION',)
  fresh_expiry=current['email_verification_expires_at']
  c.execute("UPDATE users SET email_verification_expires_at=? WHERE email=?",
   ((datetime.now(timezone.utc)-timedelta(seconds=10)).isoformat(),
    'uk11-new-registration@example.test'))
  c.commit()
 expired_response=paced_get(client,fresh_path,base_url=BASEURL,follow_redirects=False)
 assert expired_response.status_code==302
 with sm.db() as c:
  current=c.execute("SELECT email_verified FROM users WHERE email=?",
   ('uk11-new-registration@example.test',)).fetchone()
  assert not current['email_verified'],('EXPIRED_TOKEN_CLAIMED',)
  # Restore only the original expiry in this disposable fixture to test valid
  # native redemption without sleeping or generating a parallel token.
  c.execute("UPDATE users SET email_verification_expires_at=? WHERE email=?",
   (fresh_expiry,'uk11-new-registration@example.test'))
  c.commit()
 verified=paced_get(client,fresh_path,base_url=BASEURL,follow_redirects=False)
 assert verified.status_code==302 and verified.headers.get('Location')=='/login'
 with sm.db() as c:
  approved=c.execute("SELECT email_verified,account_status,email_verification_token_hash FROM users WHERE email=?",
   ('uk11-new-registration@example.test',)).fetchone()
  assert approved['email_verified']==1 and approved['account_status']=='active'
  assert not approved['email_verification_token_hash'],('USED_TOKEN_NOT_CLEARED',)
 replay=paced_get(client,fresh_path,base_url=BASEURL,follow_redirects=False)
 assert replay.status_code==302
 record('native_email_verification_pass',smtp_captured=2,unverified_blocked=True,cooldown=True,
        rotation=True,expired_rejected=True,one_time=True,token_hash_cleared=True)

 # Existing authentication path must recognise the same new account.
 login_page=paced_get(client,'/login',base_url=BASEURL)
 assert login_page.status_code==200
 signin=paced_post(client,'/login',base_url=BASEURL,data={
   'identity':'uk11-new-registration@example.test',
   'password':'Synthetic-only-Strong-Password-2026!',
   '_csrf_token':csrf(client)
 },follow_redirects=False)
 assert signin.status_code==302,('NEW_UK_LOGIN',signin.status_code)
 registered_home=paced_get(client,'/student',base_url=BASEURL)
 assert registered_home.status_code==200
 assert 'UK 11+' in registered_home.get_data(as_text=True)
 assert 'No target schools selected' in registered_home.get_data(as_text=True)
 record('registered_uk_first_login',status=registered_home.status_code)
print('UK11_NATIVE_LOGIN_PREFERENCES_REPLAY_PASSED')
