"""ScoreMax V6.5.3 integration-admission behavioral acceptance.

Exercises the V6.5.3 systemic rectification on a disposable database only.
No external network is required or permitted by this suite.
"""
from __future__ import annotations
from release_compatibility import is_compatible_descendant
import copy, hashlib, io, json, os, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib import error as urlerror

ROOT=Path(__file__).resolve().parent
TMP=Path(tempfile.mkdtemp(prefix='scoremax_v653_acceptance_'))
os.environ['SCOREMAX_DB']=str(TMP/'scoremax.db')
os.environ['SCOREMAX_SECRET']='V653-Test-Secret-Only'
os.environ['SCOREMAX_ENV']='test'
os.environ['SCOREMAX_ENFORCE_PAYWALL']='0'
os.environ['SCOREMAX_INTERNAL_FULL_ACCESS']='1'

from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import scoremax_integration_v1 as integ

count=0
def ok(name,condition):
    global count
    if not condition: raise AssertionError(name)
    count+=1; print('PASS:',name)

def load(name):
    return json.loads((ROOT/'integration_examples'/name).read_text(encoding='utf-8'))

def q_checksum(q):
    q['question_checksum_sha256']=integ._object_checksum(q,'question_checksum_sha256')

def stimulus_checksum(st):
    st['stimulus_checksum_sha256']=integ._object_checksum(st,'stimulus_checksum_sha256')

def content_env(tag,questions,stimuli=None,release_id=None,release_version='1.0.0'):
    env=load('PH_SM_APPROVED_CONTENT_V1.example.json')
    p=env['payload']; r=p['release']; stimuli=list(stimuli or [])
    rid=release_id or f'REL::SM653::{tag}'
    r.update({'release_id':rid,'release_version':release_version,'effective_at':(datetime.now(timezone.utc)-timedelta(minutes=1)).replace(microsecond=0).isoformat().replace('+00:00','Z'),
              'question_count':len(questions),'stimulus_count':len(stimuli),'supersedes_release_version':None})
    for q in questions:
        q['curriculum']['market_id']=r['market_id']; q['curriculum']['programme_id']=r['programme_id']; q['curriculum']['subject_id']=r['subject_id']; q['curriculum']['chapter_id']=r['chapter_id']; q_checksum(q)
    for st in stimuli: stimulus_checksum(st)
    p['questions']=questions; p['stimuli']=stimuli
    r['package_checksum_sha256']=hashlib.sha256(f'{rid}|{release_version}|package'.encode()).hexdigest()
    r['manifest_checksum_sha256']=hashlib.sha256(f'{rid}|{release_version}|manifest'.encode()).hexdigest()
    env['idempotency_key']=f'release::{rid}::{release_version}::{r["package_checksum_sha256"]}'
    env['message_id']='msg::PH_SM_APPROVED_CONTENT_V1::'+hashlib.sha256((tag+'|'+release_version).encode()).hexdigest()[:24]
    env['payload_checksum_sha256']=integ.payload_checksum(p)
    return env

def base_q(tag='A'):
    q=copy.deepcopy(load('PH_SM_APPROVED_CONTENT_V1.example.json')['payload']['questions'][0])
    q['question_id']=f'Q::SM653::{tag}'; q['question_version_id']=f'QV::SM653::{tag}::v1'; q['question_version_number']=1; q['supersedes_question_version_id']=None
    q['architecture']['claim_family_id']=f'FAMILY::SM653::{tag}'; q['architecture']['reasoning_seed_id']=f'SEED::SM653::{tag}'
    return q

def recalc_envelope(env,new_message=None):
    env=copy.deepcopy(env)
    for q in env['payload'].get('questions') or []: q_checksum(q)
    for st in env['payload'].get('stimuli') or []: stimulus_checksum(st)
    env['payload_checksum_sha256']=integ.payload_checksum(env['payload'])
    if new_message: env['message_id']=new_message
    return env

def product_activate(c,env,reason='V6.5.3 descendant regression'):
    r=env['payload']['release']
    return integ.authorize_product_activation(c,r['release_id'],r['release_version'],r['package_checksum_sha256'],'TEST::V653',reason)

app.init(); c=app.db(); integ.init_schema(c); c.commit()
ok('V6.5.3 integration release identity is active',is_compatible_descendant(integ.SCOREMAX_INTEGRATION_RELEASE,'6.5.3'))

# --- Semantic compiler mutation matrix: every invalid input must have zero release/version/question writes.
def zero_side_effect_reject(name,mutator):
    q=base_q(name); env=content_env(name,[q]); mutator(env)
    env=recalc_envelope(env,'msg::semantic::'+name)
    before=(c.execute('SELECT COUNT(*) n FROM integration_ph_content_releases').fetchone()['n'],
            c.execute('SELECT COUNT(*) n FROM integration_ph_question_version_store').fetchone()['n'],
            c.execute('SELECT COUNT(*) n FROM questions WHERE ph_projection_owner=\'POWER_HOUSE\'').fetchone()['n'])
    rec,status=integ.admit_content_envelope(c,env,env['payload_checksum_sha256'])
    after=(c.execute('SELECT COUNT(*) n FROM integration_ph_content_releases').fetchone()['n'],
           c.execute('SELECT COUNT(*) n FROM integration_ph_question_version_store').fetchone()['n'],
           c.execute('SELECT COUNT(*) n FROM questions WHERE ph_projection_owner=\'POWER_HOUSE\'').fetchone()['n'])
    ok(f'{name} is rejected before any content side effect',status==422 and rec['status']=='REJECTED' and before==after)
    return rec

r=zero_side_effect_reject('BAD_KEY',lambda e:e['payload']['questions'][0]['content']['marking'].__setitem__('key','Z'))
ok('bad option key is rejected with explicit semantic code',any(x['code']=='KEY_NOT_IN_OPTIONS' for x in r['errors']))
r=zero_side_effect_reject('DUP_OPT',lambda e:e['payload']['questions'][0]['content'].__setitem__('options',[{'option_id':'A','text':'x','is_display_only':False},{'option_id':'A','text':'y','is_display_only':False}]))
ok('duplicate option IDs are rejected explicitly',any(x['code']=='DUPLICATE_OPTION_ID' for x in r['errors']))
r=zero_side_effect_reject('BAD_STIM',lambda e:e['payload']['questions'][0]['content'].__setitem__('stimulus_ref','STIM::MISSING'))
ok('unresolved stimulus references are rejected explicitly',any(x['code']=='UNRESOLVED_STIMULUS_REFERENCE' for x in r['errors']))
def make_duplicate_q(e):
    q2=copy.deepcopy(e['payload']['questions'][0]); q2['question_version_id']+='::ALT'; q2['question_version_number']=2; e['payload']['questions'].append(q2); e['payload']['release']['question_count']=2
r=zero_side_effect_reject('MULTI_VERSION',make_duplicate_q)
ok('multiple versions of one question in a snapshot are rejected',any(x['code']=='MULTIPLE_QUESTION_VERSIONS_IN_SNAPSHOT' for x in r['errors']))
def make_bad_numeric(e):
    q=e['payload']['questions'][0]; q['content']['exam_question_type']='NUMERIC_RESPONSE'; q['content']['options']=[]; q['content']['marking'].update({'key_type':'NUMERIC','key':12.0,'numeric_tolerance':-1})
r=zero_side_effect_reject('BAD_NUMERIC',make_bad_numeric)
ok('invalid numerical tolerance is rejected explicitly',any(x['code'] in {'NUMERIC_TOLERANCE','SCHEMA_VALIDATION'} or 'tolerance' in str(x.get('path','')).lower() for x in r['errors']))
def make_rubric(e):
    q=e['payload']['questions'][0]; q['content']['options']=[]; q['content']['marking'].update({'key_type':'RUBRIC_ONLY','key':None,'rubric':{'criterion':'governed'}})
r=zero_side_effect_reject('RUBRIC_ONLY',make_rubric)
ok('unsupported rubric-only delivery is explicitly capability-rejected',any(x['code']=='UNSUPPORTED_RUBRIC_ONLY_DELIVERY' for x in r['errors']))

# --- Learner-safe stimulus projection while retaining immutable source object.
st= {'stimulus_id':'STIM::SM653::SAFE','stimulus_version_id':'STIMV::SM653::SAFE::1','stimulus_checksum_sha256':'0'*64,'stimulus_type':'TEXT',
     'content':{'text':'Learner-visible passage.','review_note':'INTERNAL REVIEW MUST NEVER LEAK','data':[1,2,3]},
     'provenance':{'source_id':'SRC::SAFE','source_type':'TEXTBOOK','rights_status':'LICENSED_COMMERCIAL','metadata':{'internal_ticket':'SECRET-77'}}}
qs=base_q('SAFE_STIM'); qs['content']['stimulus_ref']=st['stimulus_id']; env=content_env('SAFE_STIM',[qs],[st])
rec,status=integ.admit_content_envelope(c,env,env['payload_checksum_sha256']); product_activate(c,env)
qrow=c.execute('SELECT * FROM questions WHERE ph_question_id=?',(qs['question_id'],)).fetchone(); srow=c.execute('SELECT immutable_payload_json FROM integration_ph_stimulus_version_store WHERE stimulus_id=?',(st['stimulus_id'],)).fetchone()
ok('valid governed stimulus content is admitted',status==202 and rec['status']=='ACCEPTED' and qrow is not None)
ok('learner stimulus projection excludes provenance and internal review metadata','Learner-visible passage.' in (qrow['stimulus_data'] or '') and 'INTERNAL REVIEW' not in (qrow['stimulus_data'] or '') and 'SECRET-77' not in (qrow['stimulus_data'] or ''))
ok('complete governed stimulus remains immutable internally','INTERNAL REVIEW MUST NEVER LEAK' in srow['immutable_payload_json'] and 'SECRET-77' in srow['immutable_payload_json'])

# --- Marking fidelity for numeric, multiple-select partial/negative, text and boolean.
mark_questions=[]
qn=base_q('NUMERIC'); qn['content']['exam_question_type']='NUMERIC_RESPONSE'; qn['content']['options']=[]; qn['content']['marking'].update({'key_type':'NUMERIC','key':12.5,'numeric_tolerance':0.2,'marks':2,'negative_marks':-0.5,'rubric':None}); mark_questions.append(qn)
qm=base_q('MULTI'); qm['content']['exam_question_type']='MULTIPLE_SELECT'; qm['content']['options']=[{'option_id':'A','text':'A','is_display_only':False},{'option_id':'B','text':'B','is_display_only':False},{'option_id':'C','text':'C','is_display_only':False}]; qm['content']['marking'].update({'key_type':'MULTIPLE_OPTIONS','key':['A','C'],'numeric_tolerance':None,'marks':2,'negative_marks':-0.25,'rubric':None}); mark_questions.append(qm)
qt=base_q('TEXT'); qt['content']['exam_question_type']='TEXT'; qt['content']['options']=[]; qt['content']['marking'].update({'key_type':'TEXT','key':'ionic','accepted_answers':['ionic bond'],'numeric_tolerance':None,'marks':1,'negative_marks':0,'rubric':None}); mark_questions.append(qt)
qb=base_q('BOOL'); qb['content']['exam_question_type']='TRUE_FALSE'; qb['content']['options']=[]; qb['content']['marking'].update({'key_type':'BOOLEAN','key':True,'accepted_answers':[],'numeric_tolerance':None,'marks':1,'negative_marks':-0.25,'rubric':None}); mark_questions.append(qb)
env=content_env('MARKING',mark_questions); rec,status=integ.admit_content_envelope(c,env,env['payload_checksum_sha256']); product_activate(c,env); ok('auto-markable governed key types are admitted',status==202 and rec['status']=='ACCEPTED')
rows={r['ph_question_id']:r for r in c.execute("SELECT * FROM questions WHERE ph_release_id=?",(env['payload']['release']['release_id'],)).fetchall()}
num=rows[qn['question_id']]; ok('numeric value and tolerance are preserved and executed',app.mark_question_response(num,'12.65')[0] and app.mark_question_response(num,'13.0')[1]==-0.5)
mul=rows[qm['question_id']]; ok('multiple-select exact key and governed negative mark are executed',app.mark_question_response(mul,'A,C')[0] and app.mark_question_response(mul,'B')[1]==-0.25)
ok('multiple-select partial credit obeys immutable blueprint marking rule',app.mark_question_response(mul,'A',{'correct_marks':2,'incorrect_marks':-0.25,'unanswered_marks':0,'partial_credit_allowed':True})[1]==1.0)
text=rows[qt['question_id']]; ok('text accepted-answer marking is preserved',app.mark_question_response(text,'IONIC BOND')[0])
boolq=rows[qb['question_id']]; ok('boolean marking is preserved',app.mark_question_response(boolq,'TRUE')[0] and app.mark_question_response(boolq,'FALSE')[1]==-0.25)

# --- Canonical semantic identity and durable exact-replay receipt.
ident_q=base_q('IDENT'); ident=content_env('IDENT',[ident_q],release_id='REL::SM653::IDENT')
rec1,st1=integ.admit_content_envelope(c,ident,ident['payload_checksum_sha256']); rec2,st2=integ.admit_content_envelope(c,ident,ident['payload_checksum_sha256'])
ok('exact content replay returns original durable receipt',st1==202 and st2==200 and rec2==rec1)
conf=copy.deepcopy(ident); conf['message_id']='msg::IDENT::semantic-conflict'; conf['idempotency_key']='different-caller-idempotency'; conf['payload']['questions'][0]['content']['stem']='Semantically changed under same release identity/version'; conf=recalc_envelope(conf)
# deliberately retain the same caller package checksum; ScoreMax must own semantic identity.
rec3,st3=integ.admit_content_envelope(c,conf,conf['payload_checksum_sha256'])
ok('same release identity/version with semantic change is quarantined despite unchanged caller package checksum',st3==409 and rec3['status']=='QUARANTINED')

# --- Immutable evidence scope cannot be moved by changing current question projection.
qev=base_q('EVIDENCE'); evenv=content_env('EVIDENCE',[qev],release_id='REL::SM653::EVIDENCE'); integ.admit_content_envelope(c,evenv,evenv['payload_checksum_sha256']); product_activate(c,evenv)
qdb=c.execute('SELECT * FROM questions WHERE ph_question_id=?',(qev['question_id'],)).fetchone()
uid=c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,academic_level,subjects,login_provider) VALUES(?,?,?,?,?,?,?,?,?,?)",('STU-SM653','student','V653 Student','v653@student.test','v653student',app.generate_password_hash('Pass123!'),'active','FSc Part I','Chemistry','local')).lastrowid
sid=app.create_assessment_session(c,uid,'practice',None,[qdb['id']],{'programme':'FSc Part I','subject':'Chemistry','chapters':'Chemical Bonding','scope':'chapter'})
session=c.execute('SELECT * FROM assessment_sessions WHERE id=?',(sid,)).fetchone(); pin=integ.answer_pin(session,qdb['id'])
aid=c.execute("INSERT INTO attempts(student_id,scope,programme,subject,chapters,score,correct_count,total_count,assessment_kind,ph_release_pins_json,ph_question_pins_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(uid,'chapter','FSc Part I','Chemistry','Chemical Bonding',100,1,1,'standard',session['ph_release_pins_json'],session['ph_question_pins_json'])).lastrowid
snapshot=copy.deepcopy(pin.get('projection') or {}); snapshot.update({'ph_market_id':pin['market_id'],'ph_programme_id':pin['programme_id'],'ph_subject_id':pin['subject_id'],'ph_chapter_id':pin['chapter_id']})
c.execute("INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,marks_awarded,question_version,ph_question_id,ph_question_version_id,ph_question_checksum_sha256,ph_release_id,ph_release_version,ph_release_checksum_sha256,ph_question_snapshot_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(aid,qdb['id'],'B',1,1,1,pin['question_id'],pin['question_version_id'],pin['question_checksum_sha256'],pin['release_id'],pin['release_version'],pin['release_checksum_sha256'],integ.canonical_json(snapshot)))
c.commit(); old_scope=(pin['market_id'],pin['programme_id'],pin['subject_id'],pin['chapter_id']); c.execute("UPDATE questions SET ph_chapter_id='CHAPTER::MOVED' WHERE id=?",(qdb['id'],)); c.commit()
start=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat().replace('+00:00','Z'); end=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat().replace('+00:00','Z')
old_mid=integ.queue_delivery_evidence(c,market_id=old_scope[0],programme_id=old_scope[1],subject_id=old_scope[2],chapter_id=old_scope[3],period_start=start,period_end=end,minimum_n=1)
new_mid=integ.queue_delivery_evidence(c,market_id=old_scope[0],programme_id=old_scope[1],subject_id=old_scope[2],chapter_id='CHAPTER::MOVED',period_start=start,period_end=end,minimum_n=1)
ok('historical delivery evidence remains in immutable delivered scope after current projection moves',bool(old_mid) and not new_mid)

# --- Blueprint runtime: released blueprint controls inventory, distributions, timing and session pin.
runtime_questions=[]
levels=[('FOUNDATION','RECALL')]*3+[('EXAM_READY','APPLY')]*5+[('ADVANCED','ANALYSE')]*2
for i,(level,cog) in enumerate(levels,1):
    q=base_q(f'RUNTIME-{i}'); q['architecture']['mastery_level']=level; q['architecture']['mastery_ceiling']='ADVANCED'; q['architecture']['cognitive_demand']=cog; q['architecture']['claim_family_id']=f'FAMILY::SM653::RUNTIME::{i}'; runtime_questions.append(q)
runtime_release='REL::PK::FSC1::CHEM::CH03'; renv=content_env('RUNTIME',runtime_questions,release_id=runtime_release,release_version='SM653.RUNTIME.1'); rr,rs=integ.admit_content_envelope(c,renv,renv['payload_checksum_sha256']); product_activate(c,renv); ok('governed runtime inventory release is admitted',rs==202 and rr['status']=='ACCEPTED')
bp=load('PH_SM_ASSESSMENT_BLUEPRINT_V1.example.json'); bp['payload']['blueprint_id']='BP::SM653::RUNTIME'; bp['payload']['blueprint_version']='1.0.0'; bp['payload']['permitted_release_ids']=[runtime_release]; bp['payload']['effective_from']=datetime.now(timezone.utc).date().isoformat(); bp['payload']['marking_rules'].update({'correct_marks':1,'incorrect_marks':-0.25,'unanswered_marks':0,'partial_credit_allowed':False}); bp['payload']['blueprint_checksum_sha256']='a'*64; bp['idempotency_key']='blueprint::BP::SM653::RUNTIME::1.0.0'; bp['message_id']='msg::BP::SM653::RUNTIME'; bp['payload_checksum_sha256']=integ.payload_checksum(bp['payload'])
br,bs=integ.admit_blueprint_envelope(c,bp,bp['payload_checksum_sha256']); bpi=c.execute('SELECT * FROM integration_ph_blueprints WHERE blueprint_id=?',(bp['payload']['blueprint_id'],)).fetchone(); ok('RELEASED Power House blueprint is activated into existing ScoreMax runtime',bs==202 and br['status']=='ACCEPTED' and bpi['projection_status']=='ACTIVE_RUNTIME' and bpi['projected_blueprint_id'])
br2,bs2=integ.admit_blueprint_envelope(c,bp,bp['payload_checksum_sha256']); ok('exact blueprint replay returns original durable receipt',bs2==200 and br2==br)
bpconf=copy.deepcopy(bp); bpconf['message_id']='msg::BP::SM653::RUNTIME::conflict'; bpconf['idempotency_key']='different-blueprint-idem'; bpconf['payload']['total_duration_seconds']=601; bpconf['payload_checksum_sha256']=integ.payload_checksum(bpconf['payload']); bc,bcs=integ.admit_blueprint_envelope(c,bpconf,bpconf['payload_checksum_sha256']); ok('same blueprint ID/version semantic change is quarantined despite unchanged caller blueprint checksum',bcs==409 and bc['status']=='QUARANTINED')
assembled=app.assemble_blueprint_mock(c,int(bpi['projected_blueprint_id']),student_id=None,seed='SM653')
ok('governed blueprint assembles exactly its permitted 10-question inventory',assembled['ready'] and assembled['selected_total']==10 and all(c.execute('SELECT ph_release_id FROM questions WHERE id=?',(x['question_id'],)).fetchone()['ph_release_id']==runtime_release for x in assembled['selected']))
report=assembled['sections'][0]; ok('governed blueprint mastery and cognitive distributions are executed exactly',report['mastery_counts']==report['mastery_quotas']=={'FOUNDATION':3,'EXAM_READY':5,'ADVANCED':2} and report['cognitive_counts']==report['cognitive_quotas']=={'RECALL':3,'APPLY':5,'ANALYSE':2})
qids=[x['question_id'] for x in assembled['selected']]; sess_id=app.create_assessment_session(c,uid,'mock',10,qids,{'programme':'FSc Part I','subject':'Chemistry','scope':'blueprint','assessment_blueprint_id':int(bpi['projected_blueprint_id']),'blueprint_version':'1.0.0','blueprint_source_id':bp['payload']['blueprint_id'],'blueprint_snapshot':assembled['blueprint_snapshot'],'assembly_policy_version':'PH_GOVERNED'})
sess=c.execute('SELECT * FROM assessment_sessions WHERE id=?',(sess_id,)).fetchone()
ok('governed blueprint session immutably pins blueprint identity and all question scope',sess['blueprint_source_id']==bp['payload']['blueprint_id'] and sess['blueprint_version']=='1.0.0' and len(json.loads(sess['ph_question_pins_json']))==10)
ok('governed blueprint timing is enforced on future session',bool(sess['expires_at']))
# blueprint-level incorrect marking must override otherwise-zero question negative mark.
firstq=c.execute('SELECT * FROM questions WHERE id=?',(qids[0],)).fetchone(); ok('blueprint marking rules execute governed negative mark',app.mark_question_response(firstq,'A' if firstq['answer']!='A' else 'B',bp['payload']['marking_rules'])[1]==-0.25)

# --- Dispatch security, receipt matrix, claim lease, fairness, worker health, audited requeue.
# isolate outbound state created above so each transport case is deterministic.
c.execute("DELETE FROM integration_outbox"); c.execute("DELETE FROM integration_dispatch_attempts"); c.commit()
os.environ['SCOREMAX_TO_GROWTH_ENGINE_TOKEN']='T'*32; os.environ['SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET']='S'*48
orig_urlopen=integ.urlrequest.urlopen; orig_creds=integ._credentials
try:
    mid=integ.queue_product_event(c,event_type='ASSESSMENT_STARTED',event_id='HTTP-LEAK-TEST',event_data={}); c.commit(); os.environ['SCOREMAX_GROWTH_ENGINE_BASE_URL']='http://insecure.example'
    touched={'credentials':0,'network':0}
    def forbidden_creds(direction): touched['credentials']+=1; raise AssertionError('credentials read before HTTPS gate')
    def forbidden_network(*a,**k): touched['network']+=1; raise AssertionError('network call attempted for HTTP peer')
    integ._credentials=forbidden_creds; integ.urlrequest.urlopen=forbidden_network; dr=integ.dispatch_due(c,limit=1)
    row=c.execute('SELECT status,last_error_code FROM integration_outbox WHERE message_id=?',(mid,)).fetchone(); ok('HTTP peer is quarantined before credential read or any network call',row['status']=='QUARANTINED' and row['last_error_code']=='INSECURE_PEER_URL' and touched=={'credentials':0,'network':0})
finally:
    integ._credentials=orig_creds; integ.urlrequest.urlopen=orig_urlopen

# clean and matrix helper
c.execute("DELETE FROM integration_outbox"); c.execute("DELETE FROM integration_dispatch_attempts"); c.commit(); os.environ['SCOREMAX_GROWTH_ENGINE_BASE_URL']='https://growth.example'
def dispatch_case(label,http_status,receipt_status,retryable=False,receiver='GROWTH_ENGINE'):
    mid=integ.queue_product_event(c,event_type='ASSESSMENT_STARTED',event_id='CASE-'+label,event_data={}); c.commit(); row=c.execute('SELECT * FROM integration_outbox WHERE message_id=?',(mid,)).fetchone(); env=json.loads(row['envelope_json'])
    receipt={'receipt_id':'RECEIPT::'+label,'message_id':env['message_id'],'contract_name':env['contract_name'],'receiver_system':receiver,'received_at':integ.utcnow(),'status':receipt_status,'duplicate_of_receipt_id':None,'accepted_schema_version':'1.0.0','payload_checksum_sha256':env['payload_checksum_sha256'],'errors':([{'code':'TEMP','path':'','message':'temporary','retryable':retryable}] if receipt_status=='REJECTED' else [])}
    body=integ.canonical_json(receipt).encode()
    class Resp:
        def __init__(self,status,data): self.status=status; self.data=data
        def read(self): return self.data
    def fake(req,timeout=8):
        if http_status>=400: raise urlerror.HTTPError(req.full_url,http_status,'fixture',{},io.BytesIO(body))
        return Resp(http_status,body)
    old=integ.urlrequest.urlopen; integ.urlrequest.urlopen=fake
    try: result=integ.dispatch_due(c,limit=1)
    finally: integ.urlrequest.urlopen=old
    return c.execute('SELECT * FROM integration_outbox WHERE message_id=?',(mid,)).fetchone(),result

for code in (200,202):
    row,_=dispatch_case(str(code),code,'ACCEPTED'); ok(f'valid ACCEPTED receipt over HTTP {code} closes delivery',row['status']=='DELIVERED' and bool(row['receipt_json']))
row,_=dispatch_case('409',409,'QUARANTINED'); ok('valid QUARANTINED receipt over HTTP 409 is preserved as quarantine',row['status']=='QUARANTINED' and bool(row['receipt_json']))
row,_=dispatch_case('422',422,'REJECTED',False); ok('valid non-retryable REJECTED receipt over HTTP 422 dead-letters with receipt',row['status']=='DEAD_LETTER' and bool(row['receipt_json']))
row,_=dispatch_case('429',429,'REJECTED',True); ok('valid retryable REJECTED receipt over HTTP 429 schedules retry with receipt',row['status']=='RETRY' and bool(row['receipt_json']))
row,_=dispatch_case('503',503,'REJECTED',True); ok('valid retryable REJECTED receipt over HTTP 503 schedules retry with receipt',row['status']=='RETRY' and bool(row['receipt_json']))
row,_=dispatch_case('WRONG_RECEIVER',200,'ACCEPTED',False,'SCOREMAX'); ok('receipt receiver is bound to the exact dispatched destination',row['status']=='RETRY' and row['last_error_code']=='INVALID_OR_MISMATCHED_INTEGRATION_RECEIPT_V1')

# Atomic claim: two connections cannot claim same row simultaneously.
c.execute("DELETE FROM integration_outbox"); c.commit(); m1=integ.queue_product_event(c,event_type='ASSESSMENT_STARTED',event_id='LEASE-1',event_data={}); c.commit(); first=integ._claim_due(c,1,lease_seconds=120); c2=app.db(); integ.init_schema(c2); c2.commit(); second=integ._claim_due(c2,1,lease_seconds=120); ok('atomic claim lease prevents concurrent workers claiming the same row',len(first)==1 and len(second)==0); c.execute("UPDATE integration_outbox SET status='PENDING',claim_token='',claim_expires_at='' WHERE message_id=?",(m1,)); c.commit(); c2.close()

# Fair scheduling: one content requirement and one growth event are both claimed before a second item from either contract.
c.execute("DELETE FROM integration_outbox"); c.commit()
req=load('SM_PH_CONTENT_REQUIREMENT_V1.example.json')['payload']; integ.queue_content_requirement(c,req,'6.5.3'); integ.queue_content_requirement(c,copy.deepcopy(req)|{'request_batch_id':'REQB::SECOND'},'6.5.3')
integ.queue_product_event(c,event_type='ASSESSMENT_STARTED',event_id='FAIR-GROWTH-1',event_data={}); integ.queue_product_event(c,event_type='ASSESSMENT_STARTED',event_id='FAIR-GROWTH-2',event_data={}); c.commit(); claimed=integ._claim_due(c,2,lease_seconds=120); ok('bounded dispatcher fairly interleaves outbound contracts',len(claimed)==2 and {r['contract_name'] for r in claimed}=={'SM_PH_CONTENT_REQUIREMENT_V1','SM_GE_PRODUCT_EVENT_V1'})
# Turn one claimed row into a terminal exception then exercise audited recovery.
term=claimed[0]; c.execute("UPDATE integration_outbox SET status='QUARANTINED',claim_token='',claim_expires_at='' WHERE id=?",(term['id'],)); c.commit(); ok('audited requeue restores a terminal integration exception',integ.requeue_outbox(c,term['id'],actor='TEST_OPERATOR',reason='governed acceptance') and c.execute('SELECT COUNT(*) n FROM integration_requeue_audit WHERE outbox_id=?',(term['id'],)).fetchone()['n']==1)
integ.worker_heartbeat(c,result={'acceptance':'ok'},process_id='test'); c.commit(); health=integ.integration_health(c); ok('integration health exposes worker heartbeat and backlog age/source counts without secrets',health['worker'] and health['worker']['process_id']=='test' and any('oldest_backlog_at' in d and 'source_counts' in d for d in health['directions']) and 'TOKEN' not in integ.canonical_json(health))

# Missing endpoint preserves committed work without a network call.
for k in ('SCOREMAX_GROWTH_ENGINE_BASE_URL','SCOREMAX_TO_GROWTH_ENGINE_TOKEN','SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET'): os.environ.pop(k,None)
c.execute("DELETE FROM integration_outbox"); c.commit(); mid=integ.queue_product_event(c,event_type='ASSESSMENT_STARTED',event_id='NOT-CONFIGURED',event_data={}); c.commit(); d=integ.dispatch_due(c,limit=1); state=c.execute('SELECT status FROM integration_outbox WHERE message_id=?',(mid,)).fetchone()['status']; ok('missing peer configuration preserves committed work as pending',d['not_configured']==1 and state=='PENDING')

c.commit(); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; fk=len(c.execute('PRAGMA foreign_key_check').fetchall()); ok('V6.5.3 behavioral acceptance database integrity remains clean',integrity=='ok' and fk==0)
print(f'\nSCOREMAX V6.5.3 INTEGRATION ADMISSION ACCEPTANCE PASSED: {count}')
print('Disposable database:',TMP/'scoremax.db')
