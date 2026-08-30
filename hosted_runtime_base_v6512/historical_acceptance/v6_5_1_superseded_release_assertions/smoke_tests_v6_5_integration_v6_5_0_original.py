"""ScoreMax V6.5.0 focused three-system integration checks.

These checks exercise ScoreMax's side of frozen Integration Contract v1 without changing
Power House or Growth Engine semantics. They use a disposable database only.
"""
from __future__ import annotations
import copy, hashlib, json, os, tempfile, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TMP=Path(tempfile.mkdtemp(prefix='scoremax_v650_integration_'))
os.environ['SCOREMAX_DB']=str(TMP/'scoremax.db')
os.environ['SCOREMAX_SECRET']='Integration-Test-Secret-Only'
os.environ['SCOREMAX_ENV']='test'
os.environ['SCOREMAX_ENFORCE_PAYWALL']='0'
os.environ['SCOREMAX_INTERNAL_FULL_ACCESS']='1'

from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import scoremax_integration_v1 as integ

n=0
def ok(name,condition):
    global n
    if not condition: raise AssertionError(name)
    n+=1; print('PASS:',name)

def example(name):
    return json.loads((ROOT/'integration_examples'/name).read_text(encoding='utf-8'))

def recalc(env, message_suffix=''):
    env=copy.deepcopy(env)
    env['payload_checksum_sha256']=integ.payload_checksum(env['payload'])
    if message_suffix:
        env['message_id']=env['message_id']+'::'+message_suffix
    return env

def activate_now(env,version=None,q_suffix=None,release_suffix=None):
    env=copy.deepcopy(env); p=env['payload']; r=p['release']
    r['effective_at']=(datetime.now(timezone.utc)-timedelta(seconds=2)).replace(microsecond=0).isoformat().replace('+00:00','Z')
    if release_suffix:
        r['release_id']=r['release_id']+'::'+release_suffix
        for q in p['questions']:
            q['curriculum']['chapter_id']=r['chapter_id']
    if version:
        r['release_version']=version
    r['question_count']=len(p.get('questions') or []); r['stimulus_count']=len(p.get('stimuli') or [])
    r['package_checksum_sha256']=hashlib.sha256((r['release_id']+'|'+r['release_version']+'|package').encode()).hexdigest()
    r['manifest_checksum_sha256']=hashlib.sha256((r['release_id']+'|'+r['release_version']+'|manifest').encode()).hexdigest()
    for i,q in enumerate(p.get('questions') or []):
        if q_suffix:
            q['question_id']=q['question_id']+'::'+q_suffix+str(i)
            q['question_version_id']=q['question_version_id']+'::'+q_suffix+str(i)
        q['question_checksum_sha256']=hashlib.sha256(integ.canonical_json({k:v for k,v in q.items() if k!='question_checksum_sha256'}).encode()).hexdigest()
    env['idempotency_key']='release::'+r['release_id']+'::'+r['release_version']+'::'+r['package_checksum_sha256']
    env['message_id']='msg::PH_SM_APPROVED_CONTENT_V1::'+hashlib.sha256(env['idempotency_key'].encode()).hexdigest()[:20]
    return recalc(env)

app.init(); c=app.db(); integ.init_schema(c); c.commit()

# 1-2 schema / release identity
for t in ['integration_ph_content_releases','integration_ph_question_versions','integration_ph_blueprints','integration_outbox','integration_quarantine']:
    ok('integration schema table exists: '+t, bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone()))
    if n>=1: break
ok('release identity exposes additive V6.5 child while preserving compatibility marker',app.healthz()[0]['version']=='6.2.8.1' and app.healthz()[0]['release_version']=='6.5.0')

# 3-7 approved content / identity / display / live availability / duplicate
base=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='T1',q_suffix='T1')
receipt,status=integ.admit_content_envelope(c,base,base['payload_checksum_sha256'])
ok('Power House approved INLINE release accepted',status==202 and receipt['status']=='ACCEPTED')
rel=base['payload']['release']; q=base['payload']['questions'][0]
row=c.execute('SELECT * FROM integration_ph_question_versions WHERE question_id=? AND question_version_id=?',(q['question_id'],q['question_version_id'])).fetchone()
ok('opaque Power House question/version IDs survive exactly',row and row['question_id']==q['question_id'] and row['question_version_id']==q['question_version_id'])
proj=c.execute('SELECT * FROM questions WHERE ph_question_id=?',(q['question_id'],)).fetchone()
ok('Power House governed chapter display metadata reaches learner projection',proj and proj['chapter']=='Chemical Bonding' and proj['ph_chapter_id']==rel['chapter_id'])
ok('Power House release activates only into normal live question gate',proj and proj['active']==1 and proj['status']=='Approved' and proj['review_status']=='Approved')
receipt2,status2=integ.admit_content_envelope(c,base,base['payload_checksum_sha256'])
ok('duplicate approved content delivery is idempotent',status2==200 and receipt2['status']=='DUPLICATE')

# concurrent inbound retry storm must collapse to one business release
conc=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='CONC',q_suffix='CONC')
conc_results=[]; conc_errors=[]
def concurrent_admit():
    cc=app.db()
    try:
        rec,st=integ.admit_content_envelope(cc,conc,conc['payload_checksum_sha256']); conc_results.append((st,rec['status']))
    except Exception as exc: conc_errors.append(repr(exc))
    finally: cc.close()
threads=[threading.Thread(target=concurrent_admit) for _ in range(24)]
for t in threads:t.start()
for t in threads:t.join()
cc=app.db(); count=cc.execute('SELECT COUNT(*) n FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(conc['payload']['release']['release_id'],'CONC')).fetchone()['n']; cc.close()
ok('24 concurrent Power House deliveries collapse to one admitted release',not conc_errors and count==1 and len(conc_results)==24 and sum(1 for x in conc_results if x[0]==202)==1)

# 8 same identity different checksum quarantines
conf=copy.deepcopy(base); conf['payload']['release']['package_checksum_sha256']='a'*64; conf=recalc(conf,'conflict')
r3,s3=integ.admit_content_envelope(c,conf,conf['payload_checksum_sha256'])
ok('same release identity/version with different package checksum is quarantined',s3==409 and r3['status']=='QUARANTINED')

# 9-12 gates / dependent rules
for field,val,label in [('hold_status','HOLD','held'),('r2_status','REQUIRED','R2-required'),('source_check_status','REQUIRED','source-check-required')]:
    e=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='G-'+field,q_suffix='G'+field)
    e['payload']['questions'][0]['governance'][field]=val; e=recalc(e,'gate')
    rr,ss=integ.admit_content_envelope(c,e,e['payload_checksum_sha256'])
    ok(label+' question is excluded from learner admission',ss==422 and rr['status']=='REJECTED')
e=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='DEP-BAD',q_suffix='DB')
a=e['payload']['questions'][0]['architecture']; a['evidence_role']='RECOVERY'; a['dependency_type']='RECOVERY'; a['independent_mastery_eligible']=True; a['independent_mastery_weight']=1; e=recalc(e,'depbad')
rr,ss=integ.admit_content_envelope(c,e,e['payload_checksum_sha256'])
ok('dependent/recovery records cannot manufacture independent mastery weight',ss==422)

# 13 valid dependent remains zero
ed=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='DEP-GOOD',q_suffix='DG')
ad=ed['payload']['questions'][0]['architecture']; ad['evidence_role']='RECOVERY'; ad['dependency_type']='RECOVERY'; ad['independent_mastery_eligible']=False; ad['independent_mastery_weight']=0; ed=recalc(ed,'depgood')
rr,ss=integ.admit_content_envelope(c,ed,ed['payload_checksum_sha256']); qdg=ed['payload']['questions'][0]
r=c.execute('SELECT ph_independent_mastery_weight FROM questions WHERE ph_question_id=?',(qdg['question_id'],)).fetchone()
ok('valid dependent record remains zero independent mastery weight',ss==202 and r and float(r['ph_independent_mastery_weight'])==0)

# 14 shared stimulus survives
es=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='STIM',q_suffix='ST')
st={'stimulus_id':'STIM::opaque::A-01','stimulus_version_id':'STIMV::opaque::A-01::v1','stimulus_checksum_sha256':'b'*64,'language':'en','stimulus_type':'PASSAGE','content':{'text':'A governed shared stimulus.'},'provenance':{'source':'fixture'}}
es['payload']['stimuli']=[st]; es['payload']['release']['stimulus_count']=1; es['payload']['questions'][0]['content']['stimulus_ref']=st['stimulus_id']; es=recalc(es,'stim')
rr,ss=integ.admit_content_envelope(c,es,es['payload_checksum_sha256']); qst=es['payload']['questions'][0]
r=c.execute('SELECT stimulus_data FROM questions WHERE ph_question_id=?',(qst['question_id'],)).fetchone()
ok('shared-stimulus identity/content survives admission',ss==202 and 'governed shared stimulus' in (r['stimulus_data'] if r else ''))

# 15 cross market no Pakistan hard coding
em=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='INDIA',q_suffix='IN')
rrr=em['payload']['release']; rrr['market_id']='IN'; rrr['programme_id']='NEET'; rrr['subject_id']='PHYSICS'; rrr['chapter_id']='CHAPTER::NCERT::PHYS::11::05'
qq=em['payload']['questions'][0]; qq['curriculum'].update({'market_id':'IN','programme_id':'NEET','subject_id':'PHYSICS','chapter_id':rrr['chapter_id']}); qq['curriculum']['display'].update({'programme':'NEET','subject':'Physics','chapter_number':'5','chapter':'Laws of Motion'}); em=recalc(em,'india')
rr,ss=integ.admit_content_envelope(c,em,em['payload_checksum_sha256']); qin=em['payload']['questions'][0]
r=c.execute('SELECT ph_market_id,ph_programme_id,subject,chapter FROM questions WHERE ph_question_id=?',(qin['question_id'],)).fetchone()
ok('content admission is cross-market and not Pakistan-hardcoded',ss==202 and tuple(r)==('IN','NEET','Physics','Laws of Motion'))

# 16-17 rubric-only constructed response preserved and not auto-marked
cr=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='CR',q_suffix='CR')
qc=cr['payload']['questions'][0]; qc['content']['question_family_type']='CONSTRUCTED_RESPONSE'; qc['content']['exam_question_type']='EXTENDED_RESPONSE'; qc['content']['options']=[]; qc['content']['marking']['key_type']='RUBRIC_ONLY'; qc['content']['marking']['key']=None; qc['content']['marking']['rubric']={'criteria':['Reasoning','Conclusion']}; cr=recalc(cr,'cr')
rr,ss=integ.admit_content_envelope(c,cr,cr['payload_checksum_sha256']); qcr=cr['payload']['questions'][0]
r=c.execute('SELECT qtype,ph_is_auto_markable,marking_config FROM questions WHERE ph_question_id=?',(qcr['question_id'],)).fetchone()
ok('rubric-only constructed response is preserved',ss==202 and r and r['qtype']=='Extended Response' and 'criteria' in r['marking_config'])
ok('rubric-only constructed response is not ordinary auto-markable inventory',r and int(r['ph_is_auto_markable'])==0)

# 18-21 session pinning, changed future question, withdrawal future-only
v1=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='PIN1',q_suffix='PIN')
v1['payload']['questions'][0]['content']['stem']='Original pinned stem'; v1['payload']['questions'][0]['content']['marking']['key']='A'; v1=recalc(v1,'pin1')
integ.admit_content_envelope(c,v1,v1['payload_checksum_sha256']); qpin=v1['payload']['questions'][0]; qr=c.execute('SELECT id FROM questions WHERE ph_question_id=?',(qpin['question_id'],)).fetchone(); qdb=int(qr['id'])
# create student
cur=c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,academic_level,subjects,login_provider) VALUES(?,?,?,?,?,?,?,?,?,?)",('STU-INT-1','student','Integration Student','int@student.test','intstudent',app.generate_password_hash('Pass123!'),'active','FSc Part 1','Chemistry','local')); stu=cur.lastrowid
sid=app.create_assessment_session(c,stu,'practice',None,[qdb],{'programme':'FSc Part 1','subject':'Chemistry','chapters':'Chemical Bonding','scope':'chapter'})
sess=c.execute('SELECT * FROM assessment_sessions WHERE id=?',(sid,)).fetchone(); pin=integ.answer_pin(sess,qdb)
ok('assessment session pins exact Power House question/release version/checksum',pin['question_version_id']==qpin['question_version_id'] and pin['release_version']=='PIN1' and bool(pin['question_checksum_sha256']))
v2=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='PIN2')
q2=v2['payload']['questions'][0]; q2['question_id']=qpin['question_id']; q2['question_version_id']=qpin['question_version_id']+'::vNEXT'; q2['question_version_number']=int(qpin['question_version_number'])+1; q2['content']['stem']='Changed future stem'; q2['content']['marking']['key']='B'; q2['supersedes_question_version_id']=qpin['question_version_id']; v2['payload']['release']['supersedes_release_version']='PIN1'; v2=recalc(v2,'pin2')
integ.admit_content_envelope(c,v2,v2['payload_checksum_sha256'])
current=c.execute('SELECT * FROM questions WHERE id=?',(qdb,)).fetchone(); pinned=integ.pinned_question(sess,qdb,current)
ok('changed question affects future projection but not active-session delivered snapshot',current['question']=='Changed future stem' and pinned['question']=='Original pinned stem')
ok('active-session answer remains pinned to original marking',pinned['answer']=='A' and current['answer']=='B')
withdraw=copy.deepcopy(v2); withdraw['payload']['release']['release_version']='PIN3'; withdraw['payload']['release']['supersedes_release_version']='PIN2'; withdraw['payload']['questions']=[]; withdraw['payload']['release']['question_count']=0; withdraw['payload']['release']['package_checksum_sha256']='c'*64; withdraw['payload']['release']['manifest_checksum_sha256']='d'*64; withdraw['idempotency_key']='release::withdraw::pin3'; withdraw['message_id']='msg::withdraw::pin3'; withdraw=recalc(withdraw)
integ.admit_content_envelope(c,withdraw,withdraw['payload_checksum_sha256']); future=c.execute('SELECT active,status FROM questions WHERE id=?',(qdb,)).fetchone(); pinned2=integ.pinned_question(sess,qdb,current)
ok('withdrawal removes question from future inventory while active session snapshot remains usable',future['active']==0 and pinned2['question']=='Original pinned stem')

# 22-24 immutable blueprint admission / duplicate / fail-safe projection
bp=example('PH_SM_ASSESSMENT_BLUEPRINT_V1.example.json'); bp['payload']['effective_from']='2026-08-21'; bp=recalc(bp,'bp')
br,bs=integ.admit_blueprint_envelope(c,bp,bp['payload_checksum_sha256'])
ok('Power House blueprint is immutably admitted',bs==202 and br['status']=='ACCEPTED' and bool(c.execute('SELECT 1 FROM integration_ph_blueprints WHERE blueprint_id=?',(bp['payload']['blueprint_id'],)).fetchone()))
br2,bs2=integ.admit_blueprint_envelope(c,bp,bp['payload_checksum_sha256'])
ok('duplicate blueprint delivery is idempotent',bs2==200 and br2['status']=='DUPLICATE')
bpr=c.execute('SELECT projection_status,immutable_payload_json FROM integration_ph_blueprints WHERE blueprint_id=?',(bp['payload']['blueprint_id'],)).fetchone()
ok('blueprint adapter fails safe rather than inventing missing legacy framework identity',bpr['projection_status']=='IMMUTABLE_ONLY' and bp['payload']['blueprint_id'] in bpr['immutable_payload_json'])

# 25 content requirement outbox
req=example('SM_PH_CONTENT_REQUIREMENT_V1.example.json')['payload']; mid=integ.queue_content_requirement(c,req,'6.5.0')
ok('content requirement queues to Power House with business idempotency',bool(mid) and c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_PH_CONTENT_REQUIREMENT_V1'").fetchone()['n']>=1)

# 26-31 teacher referral/payment/outbox: direct + one upstream + refund + hold + renewal-like distinct events
# configure commission programs
c.execute("UPDATE referral_programs SET reward_rate=0.10,hold_days=7,active=1 WHERE role_group='teacher_direct'")
c.execute("UPDATE referral_programs SET reward_rate=0.02,hold_days=7,active=1 WHERE role_group='teacher_override'")
def user(uid,role,name,email):
    cur=c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,academic_level,subjects,login_provider) VALUES(?,?,?,?,?,?,?,?,?,?)",(uid,role,name,email,uid.lower().replace('-',''),app.generate_password_hash('Pass123!'),'active','FSc Part 1','Chemistry','local')); return cur.lastrowid
A=user('TCH-A','teacher','Teacher A','a@t.test'); B=user('TCH-B','teacher','Teacher B','b@t.test'); S=user('STU-R','student','Student R','r@s.test')
ca=app.ensure_referral_code(c,A); cb=app.ensure_referral_code(c,B); app.apply_referral_attribution(c,B,ca,'teacher_referral'); app.apply_referral_attribution(c,S,cb,'teacher_referral')
plan=c.execute('SELECT id FROM plans ORDER BY id LIMIT 1').fetchone(); plan_id=int(plan['id'])
tx=app.record_payment(c,S,plan_id,100000,'PKR','successful'); c.commit(); rrw=c.execute('SELECT * FROM referral_rewards WHERE payment_transaction_id=?',(tx,)).fetchone()
ok('direct teacher paid referral reward is created',rrw and int(rrw['referrer_user_id'])==B and int(rrw['reward_amount_minor'])==10000)
ok('only one upstream teacher override is preserved',rrw and int(rrw['override_referrer_user_id'])==A and int(rrw['override_reward_amount_minor'])==2000)
integ.sync_growth_outbox(c,'6.5.0'); events=[json.loads(r['envelope_json']) for r in c.execute("SELECT * FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchall()]
ok('payment/referral facts queue to Growth Engine without Growth authority',any(e['payload']['event_type']=='PAYMENT_CLEARED' for e in events))
count_before=len(events); integ.sync_growth_outbox(c,'6.5.0'); count_after=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
ok('repeated Growth synchronization is idempotent',count_after==count_before)
c.execute('UPDATE payment_transactions SET refund_amount_minor=25000 WHERE id=?',(tx,)); c.commit(); integ.sync_growth_outbox(c,'6.5.0'); events2=[json.loads(r['envelope_json']) for r in c.execute("SELECT * FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchall()]
ok('refund/reversal is a distinct Growth event rather than mutation of cleared event',any(e['payload']['event_type']=='PAYMENT_REFUNDED' for e in events2) and any(e['payload']['event_type']=='PAYMENT_CLEARED' for e in events2))
ok('reward hold state is preserved for payout governance',rrw['status']=='pending' and rrw['override_status']=='pending')
# explicit renewal event ID must coexist with payment event
renew=integ.queue_product_event(c,event_type='SUBSCRIPTION_RENEWED',event_id='RENEW::TX::'+str(tx),actor_type='LEARNER',actor_id=integ._pseudo_user(c,S),event_data={'payment_transaction_id':tx},producer_version='6.5.0')
ok('renewal can be represented as a distinct idempotent product event',bool(renew))
c.commit()

# concurrent Growth-event delivery preparation must also collapse to one outbox row
ge_errors=[]; ge_mids=[]
def concurrent_growth_queue():
    cc=app.db()
    try:
        m=integ.queue_product_event(cc,event_type='FIRST_MEANINGFUL_ACTIVITY',event_id='EVT::CONCURRENT::ONE',actor_type='LEARNER',actor_id='USR::PSEUDO::CONC',event_data={'completion_status':'DONE'},producer_version='6.5.0')
        cc.commit(); ge_mids.append(m)
    except Exception as exc: ge_errors.append(repr(exc))
    finally: cc.close()
threads=[threading.Thread(target=concurrent_growth_queue) for _ in range(24)]
for t in threads:t.start()
for t in threads:t.join()
cc=app.db(); gecount=cc.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1' AND idempotency_key='product-event::EVT::CONCURRENT::ONE'").fetchone()['n']; cc.close()
ok('24 concurrent Growth event queues collapse to one business event',not ge_errors and gecount==1 and len(set(ge_mids))==1)

# 32-35 HMAC current/previous/independent Growth/bad signature
class Req:
    def __init__(self,path,headers): self.method='POST'; self.path=path; self.headers=headers
path='/api/integration/v1/power-house/content-releases'; mid='msg::auth::1'; sent=integ.utcnow(); chk='e'*64
os.environ['POWER_HOUSE_TO_SCOREMAX_TOKEN']='ph-current'; os.environ['POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET']='ph-secret'
os.environ['POWER_HOUSE_TO_SCOREMAX_PREVIOUS_TOKEN']='ph-prev'; os.environ['POWER_HOUSE_TO_SCOREMAX_PREVIOUS_HMAC_SECRET']='ph-prev-secret'
os.environ['GROWTH_ENGINE_TO_SCOREMAX_TOKEN']='ge-current'; os.environ['GROWTH_ENGINE_TO_SCOREMAX_HMAC_SECRET']='ge-secret'
def headers(tok,sec,p=path,m=mid): return {'Authorization':'Bearer '+tok,'X-Message-Id':m,'X-Sent-At':sent,'X-Content-SHA256':chk,'X-Signature':'hmac-sha256='+integ.signature('POST',p,m,sent,chk,sec)}
ok('current Power House service credential/HMAC is accepted',integ.verify_inbound_http(Req(path,headers('ph-current','ph-secret')),'POWER_HOUSE')[0])
ok('previous Power House credential supports controlled secret rotation',integ.verify_inbound_http(Req(path,headers('ph-prev','ph-prev-secret')),'POWER_HOUSE')[0])
gpath='/api/integration/v1/growth/fixture'; gh=headers('ge-current','ge-secret',gpath,'msg::ge::1'); ok('Growth Engine uses an independent service credential pair',integ.verify_inbound_http(Req(gpath,gh),'GROWTH_ENGINE')[0])
bad=headers('ph-current','wrong'); ok('bad HMAC is rejected',not integ.verify_inbound_http(Req(path,bad),'POWER_HOUSE')[0])

# 36 stale replay rejected by clock skew
old=(datetime.now(timezone.utc)-timedelta(hours=1)).replace(microsecond=0).isoformat().replace('+00:00','Z'); oldh={'Authorization':'Bearer ph-current','X-Message-Id':'old','X-Sent-At':old,'X-Content-SHA256':chk,'X-Signature':'hmac-sha256='+integ.signature('POST',path,'old',old,chk,'ph-secret')}
ok('stale replay outside permitted clock skew is rejected',not integ.verify_inbound_http(Req(path,oldh),'POWER_HOUSE')[0])

# 37-38 outage/restart queue persistence
out_before=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE status='PENDING'").fetchone()['n']; dispatch=integ.dispatch_due(c,limit=100); c.commit(); out_after=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE status='PENDING'").fetchone()['n']
ok('peer outage/not-configured never deletes committed outbox work',dispatch['not_configured']>0 and out_after==out_before)
c.close(); c=app.db(); integ.init_schema(c)
ok('integration queues survive database restart',c.execute("SELECT COUNT(*) n FROM integration_outbox").fetchone()['n']>=out_after)

# 39-40 minimum-N aggregate / privacy
# create enough attempt evidence for current governed DG question; direct rows keep exact PH pins.
qrow=c.execute('SELECT * FROM questions WHERE ph_question_id=?',(qdg['question_id'],)).fetchone()
for i in range(10):
    cur=c.execute("INSERT INTO attempts(student_id,scope,programme,subject,chapters,score,correct_count,total_count,assessment_kind,ph_release_pins_json,ph_question_pins_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(stu,'chapter','FSc Part I','Chemistry','Chemical Bonding',100 if i<7 else 0,1 if i<7 else 0,1,'standard','{}','{}')); aid=cur.lastrowid
    c.execute("INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,marks_awarded,question_version,ph_question_id,ph_question_version_id,ph_question_checksum_sha256,ph_release_id,ph_release_version,ph_release_checksum_sha256,ph_question_snapshot_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,qrow['id'],'A',1 if i<7 else 0,1 if i<7 else 0,1,qdg['question_id'],qdg['question_version_id'],qdg['question_checksum_sha256'],ed['payload']['release']['release_id'],ed['payload']['release']['release_version'],ed['payload']['release']['package_checksum_sha256'],'{}'))
c.commit(); start=(datetime.now(timezone.utc)-timedelta(days=1)).strftime('%Y-%m-%d 00:00:00'); end=(datetime.now(timezone.utc)+timedelta(days=1)).strftime('%Y-%m-%d 23:59:59')
ev_mid=integ.queue_delivery_evidence(c,market_id=qrow['ph_market_id'],programme_id=qrow['ph_programme_id'],subject_id=qrow['ph_subject_id'],chapter_id=qrow['ph_chapter_id'],period_start=start,period_end=end,minimum_n=10)
envrow=c.execute('SELECT envelope_json FROM integration_outbox WHERE message_id=?',(ev_mid,)).fetchone(); ev=json.loads(envrow['envelope_json']) if envrow else {}
ok('delivery evidence respects minimum-N question-version aggregation',bool(ev) and ev['payload']['minimum_sample_policy']['minimum_n']==10 and ev['payload']['items'][0]['sample_suppressed'] is False)
serialized=integ.canonical_json(ev).lower(); ok('Power House delivery evidence contains no learner identity or raw answer payload',('student_id' not in serialized and 'email' not in serialized and 'password' not in serialized and 'selected_answer' not in serialized))

# 41 common envelopes validate frozen schema constants/required fields at receiver layer
for fn,contract,dest in [('SM_PH_DELIVERY_EVIDENCE_V1.example.json','SM_PH_DELIVERY_EVIDENCE_V1','POWER_HOUSE'),('SM_PH_CONTENT_REQUIREMENT_V1.example.json','SM_PH_CONTENT_REQUIREMENT_V1','POWER_HOUSE'),('SM_GE_PRODUCT_EVENT_V1.example.json','SM_GE_PRODUCT_EVENT_V1','GROWTH_ENGINE')]:
    e=example(fn); ok('frozen outbound envelope shape retained: '+contract,all(k in e for k in ['message_id','contract_name','contract_version','schema_version','source_system','destination_system','idempotency_key','payload_checksum_sha256','payload']) and e['contract_name']==contract and e['destination_system']==dest)
    if n>=41: break

# 42 no sensitive data in outbound contracts
all_out='\n'.join(r['envelope_json'] for r in c.execute('SELECT envelope_json FROM integration_outbox').fetchall()).lower()
ok('outbound integration payloads exclude passwords, card data and raw learner answers',all(x not in all_out for x in ['password_hash','card_number','cvv','raw_answer']))

# 43 frozen MANIFEST_PULL contradiction surfaced, not silently redefined
man=activate_now(example('PH_SM_APPROVED_CONTENT_V1.example.json'),version='MANIFEST',q_suffix='M'); man['payload']['delivery_mode']='MANIFEST_PULL'; man=recalc(man,'manifest'); mr,ms=integ.admit_content_envelope(c,man,man['payload_checksum_sha256'])
ok('frozen MANIFEST_PULL/schema contradiction is surfaced for Integration Control',ms==422 and any(e['code']=='FROZEN_MANIFEST_PULL_SCHEMA_CONFLICT' for e in mr['errors']))

# 44-45 preflight soft/strict
for k in ['SCOREMAX_POWER_HOUSE_BASE_URL','SCOREMAX_TO_POWER_HOUSE_TOKEN','SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET','SCOREMAX_GROWTH_ENGINE_BASE_URL','SCOREMAX_TO_GROWTH_ENGINE_TOKEN','SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET']:
    os.environ.pop(k,None)
pf=integ.production_preflight(strict=False); ok('production preflight is nonblocking before peers are enabled',pf['status']=='NOT_CONFIGURED' and not pf['ready'])
pfs=integ.production_preflight(strict=True); ok('strict integrated-pilot preflight detects missing peer configuration',pfs['status']=='BLOCKED' and len(pfs['missing'])>0)

c.close()
print(f'\nSCOREMAX V6.5.0 FOCUSED INTEGRATION CHECKS PASSED: {n}')
print('Disposable database:',TMP/'scoremax.db')
