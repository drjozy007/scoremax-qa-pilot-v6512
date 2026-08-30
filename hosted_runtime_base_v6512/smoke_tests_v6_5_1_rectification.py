"""ScoreMax V6.5.3 focused integration rectification acceptance checks."""
from __future__ import annotations
from release_compatibility import is_compatible_descendant
import copy,hashlib,json,os,tempfile,pathlib,threading
from datetime import datetime,timezone,timedelta
ROOT=pathlib.Path(__file__).resolve().parent
TMP=pathlib.Path(tempfile.mkdtemp(prefix='scoremax_v653_rect_'))
os.environ['SCOREMAX_DB']=str(TMP/'scoremax.db'); os.environ['SCOREMAX_SECRET']='Rectification-Test-Secret-Only'; os.environ['SCOREMAX_ENV']='test'; os.environ['SCOREMAX_ENFORCE_PAYWALL']='0'; os.environ['SCOREMAX_INTERNAL_FULL_ACCESS']='1'
from smoke_tests_v5_5 import install_framework_stubs; install_framework_stubs()
import app,scoremax_integration_v1 as integ
N=0
def ok(name,cond):
 global N
 if not cond: raise AssertionError(name)
 N+=1; print('PASS:',name)
def ex(path): return json.loads((ROOT/'integration_examples'/path).read_text())
def recalc(e):
 e=copy.deepcopy(e)
 for q in (e.get('payload') or {}).get('questions') or []: q['question_checksum_sha256']=integ._object_checksum(q,'question_checksum_sha256')
 for s in (e.get('payload') or {}).get('stimuli') or []: s['stimulus_checksum_sha256']=integ._object_checksum(s,'stimulus_checksum_sha256')
 e['payload_checksum_sha256']=integ.payload_checksum(e['payload']); return e
def mutate_release(e,suffix):
 e=copy.deepcopy(e); r=e['payload']['release']; r['release_id']+='::'+suffix; r['release_version']=suffix; r['effective_at']=None
 for i,q in enumerate(e['payload'].get('questions') or []): q['question_id']+=f'::{suffix}::{i}'; q['question_version_id']+=f'::{suffix}::{i}'
 r['question_count']=len(e['payload'].get('questions') or []); r['stimulus_count']=len(e['payload'].get('stimuli') or []); r['package_checksum_sha256']=hashlib.sha256((r['release_id']+'pkg').encode()).hexdigest(); r['manifest_checksum_sha256']=hashlib.sha256((r['release_id']+'man').encode()).hexdigest(); e['idempotency_key']='release::'+r['release_id']+'::'+r['release_version']+'::'+r['package_checksum_sha256']; e['message_id']='msg::v653::'+hashlib.sha256(e['idempotency_key'].encode()).hexdigest()[:24]; return recalc(e)
app.init(); c=app.db(); integ.init_schema(c); c.commit()
# schema/migration foundation
for t in ['integration_ph_question_version_store','integration_ph_release_question_membership','integration_source_change_queue']:
 ok('V6.5.3 schema exists: '+t,bool(c.execute("select 1 from sqlite_master where type='table' and name=?",(t,)).fetchone()))
ok('release identity is V6.5.3',is_compatible_descendant(app.healthz()[0]['release_version'],'6.5.3'))
# v1 compatibility and readiness semantics
v1=mutate_release(ex('PH_SM_APPROVED_CONTENT_V1.example.json'),'COMPAT'); v1['payload']['questions'][0]['governance']['source_check_status']='NOT_REQUIRED'; v1['payload']['questions'][0]['governance'].pop('generated_clearance_status',None); v1=recalc(v1); rr,ss=integ.admit_content_envelope(c,v1,v1['payload_checksum_sha256']); ok('v1 INLINE accepts NOT_REQUIRED and optional generated clearance',ss==202 and rr['status']=='ACCEPTED')
ok('null effective_at remains staged pending ScoreMax product activation',c.execute('select local_status from integration_ph_content_releases where release_id=?',(v1['payload']['release']['release_id'],)).fetchone()['local_status']=='STAGED')
# strict invalid creates no academic release/version/projection
bad=mutate_release(ex('PH_SM_APPROVED_CONTENT_V1.example.json'),'BADSTEM'); bad['payload']['questions'][0]['content'].pop('stem'); bad=recalc(bad); before=c.execute('select count(*) n from integration_ph_content_releases').fetchone()['n']; rr,ss=integ.admit_content_envelope(c,bad,bad['payload_checksum_sha256']); after=c.execute('select count(*) n from integration_ph_content_releases').fetchone()['n']; ok('missing stem rejected before release side effect',ss==422 and before==after)
bad2=mutate_release(ex('PH_SM_APPROVED_CONTENT_V1.example.json'),'BADRIGHT'); bad2['payload']['questions'][0]['governance']['rights_status']='DENIED'; bad2=recalc(bad2); rr,ss=integ.admit_content_envelope(c,bad2,bad2['payload_checksum_sha256']); ok('ineligible rights rejected',ss==422 and not c.execute('select 1 from questions where ph_question_id=?',(bad2['payload']['questions'][0]['question_id'],)).fetchone())
# v1.1 INLINE
iv=ex('v1_1_0/PH_SM_APPROVED_CONTENT_V1_1_INLINE.example.json'); iv['payload']['release']['release_id']+='::TEST'; iv['payload']['release']['release_version']='1.1-test'; iv['payload']['release']['effective_at']=None; q=iv['payload']['questions'][0]; q['question_id']+='::TEST'; q['question_version_id']+='::TEST'; iv['payload']['release']['package_checksum_sha256']=hashlib.sha256(b'inline-test').hexdigest(); iv['payload']['release']['manifest_checksum_sha256']=hashlib.sha256(b'inline-man').hexdigest(); iv['idempotency_key']='release::v11::inline'; iv['message_id']='msg::v11::inline'; iv=recalc(iv); rr,ss=integ.admit_content_envelope(c,iv,iv['payload_checksum_sha256']); ok('schema 1.1 INLINE accepted',ss==202 and rr['accepted_schema_version']=='1.1.0')
# manifest pull with exact archive/manifest/member hashes
me=ex('v1_1_0/PH_SM_APPROVED_CONTENT_V1_1_MANIFEST_PULL.example.json'); me['payload']['release']['effective_at']=None; me=recalc(me); archive=ROOT/'integration_examples'/'v1_1_0'/'PH_SM_APPROVED_CONTENT_MANIFEST_DEMO_v1_1_0.zip'; ok('sealed MANIFEST_PULL fixture is packaged',archive.exists())
blob=archive.read_bytes(); olddl=integ._download_manifest_package; integ._download_manifest_package=lambda url,timeout=20:blob
rr,ss=integ.admit_content_envelope(c,me,me['payload_checksum_sha256']); ok('schema 1.1 MANIFEST_PULL validates archive/manifest/content and stages',ss==202 and c.execute('select 1 from integration_ph_release_question_membership where release_id=? and release_version=?',(me['payload']['release']['release_id'],me['payload']['release']['release_version'])).fetchone())
mebad=copy.deepcopy(me); mebad['payload']['release']['release_version']='bad-package'; mebad['payload']['release']['package_checksum_sha256']='f'*64; mebad['idempotency_key']='manifest-bad'; mebad['message_id']='msg::manifest-bad'; mebad=recalc(mebad); rr,ss=integ.admit_content_envelope(c,mebad,mebad['payload_checksum_sha256']); ok('manifest archive checksum mismatch cannot stage release',ss in {409,422} and not c.execute('select 1 from integration_ph_content_releases where release_version=?',('bad-package',)).fetchone())
integ._download_manifest_package=olddl
# immutable version/release membership reuse (100%)
r1=mutate_release(ex('PH_SM_APPROVED_CONTENT_V1.example.json'),'REUSEBASE'); rr,ss=integ.admit_content_envelope(c,r1,r1['payload_checksum_sha256']); r2=copy.deepcopy(r1); rel=r2['payload']['release']; rel['release_version']='REUSE2'; rel['package_checksum_sha256']=hashlib.sha256(b'reuse2').hexdigest(); rel['manifest_checksum_sha256']=hashlib.sha256(b'reuse2m').hexdigest(); rel['supersedes_release_version']='REUSEBASE'; r2['idempotency_key']='release::reuse2'; r2['message_id']='msg::reuse2'; r2=recalc(r2); rr,ss=integ.admit_content_envelope(c,r2,r2['payload_checksum_sha256']); ok('unchanged question version can be member of later full release',ss==202 and c.execute('select count(*) n from integration_ph_release_question_membership where question_id=?',(r1['payload']['questions'][0]['question_id'],)).fetchone()['n']==2)
integ.authorize_product_activation(c,r2['payload']['release']['release_id'],r2['payload']['release']['release_version'],r2['payload']['release']['package_checksum_sha256'],'TEST::V651','withdrawal regression precondition'); c.commit()
# collision safe
legacy_id='OPAQUE-COLLISION-V651'; legacy=c.execute("insert into questions(question_id,family_id,variant,programme,subject,chapter,topic,subtopic,qtype,level,question,option_a,option_b,option_c,option_d,answer,explanation,status,review_status,active,family_key) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(legacy_id,'L','INDEPENDENT','Legacy','Legacy','Legacy','','','MCQ','Foundation','KEEP ME','A','B','C','D','A','','Approved','Approved',1,'LKEY')).lastrowid; c.execute("insert or ignore into question_families(family_key,family_id,programme,subject,review_status,active,source_type) values('LKEY','L','Legacy','Legacy','Approved',1,'Legacy')"); c.commit(); col=mutate_release(ex('PH_SM_APPROVED_CONTENT_V1.example.json'),'COLL'); col['payload']['questions'][0]['question_id']=legacy_id; col=recalc(col); rr,ss=integ.admit_content_envelope(c,col,col['payload_checksum_sha256']); row=c.execute('select question,ph_question_id from questions where id=?',(legacy,)).fetchone(); ok('opaque PH ID collision never overwrites legacy row',row['question']=='KEEP ME' and row['ph_question_id']=='')
# withdrawal future-only
wid=ex('v1_1_0/PH_SM_APPROVED_CONTENT_V1_1_WITHDRAW.example.json'); wr=wid['payload']['release']; wr['release_id']=r2['payload']['release']['release_id']; wr['release_version']='WITHDRAW'; wr['supersedes_release_version']='REUSE2'; wr['market_id']=r2['payload']['release']['market_id']; wr['programme_id']=r2['payload']['release']['programme_id']; wr['subject_id']=r2['payload']['release']['subject_id']; wr['chapter_id']=r2['payload']['release']['chapter_id']; wid['message_id']='msg::with'; wid['idempotency_key']='withdraw::reuse2'; wid=recalc(wid); rr,ss=integ.admit_content_envelope(c,wid,wid['payload_checksum_sha256']); ok('v1.1 WITHDRAW removes target from future inventory',ss==202 and not c.execute("select 1 from questions where ph_release_id=? and ph_release_version='REUSE2' and active=1",(wr['release_id'],)).fetchone())
# blueprint strict
bp=ex('PH_SM_ASSESSMENT_BLUEPRINT_V1.example.json'); bp['payload']['sections']=[]; bp=recalc(bp); rr,ss=integ.admit_blueprint_envelope(c,bp,bp['payload_checksum_sha256']); ok('invalid blueprint rejected by strict schema',ss==422)
# outbound strict and UTC timestamps
mid=integ.queue_product_event(c,event_type='FIRST_MEANINGFUL_ACTIVITY',event_id='V651-E1',actor_type='LEARNER',actor_id='PSEUDO',event_data={'completion_status':'DONE'},occurred_at='2026-08-21 12:00:00'); env=json.loads(c.execute('select envelope_json from integration_outbox where message_id=?',(mid,)).fetchone()['envelope_json']); ok('generated product event strictly validates',not integ._schema_errors(env,'SM_GE_PRODUCT_EVENT_V1','1.0.0')); ok('generated event timestamp normalized to UTC Z',env['payload']['occurred_at'].endswith('Z') and 'T' in env['payload']['occurred_at'])
# receipt-aware dispatch states
os.environ['SCOREMAX_GROWTH_ENGINE_BASE_URL']='https://growth.example'; os.environ['SCOREMAX_TO_GROWTH_ENGINE_TOKEN']='T'*32; os.environ['SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET']='S'*48
class Resp:
 def __init__(self,status,body): self.status=status; self._body=body
 def read(self): return self._body.encode()
row=c.execute('select * from integration_outbox where message_id=?',(mid,)).fetchone(); env=json.loads(row['envelope_json'])
def receipt(status='ACCEPTED',msg=None,chk=None,errors=None): return {'receipt_id':'RCPT::peer::1','message_id':msg or env['message_id'],'contract_name':env['contract_name'],'receiver_system':'GROWTH_ENGINE','received_at':integ.utcnow(),'status':status,'duplicate_of_receipt_id':None,'accepted_schema_version':'1.0.0' if status in {'ACCEPTED','DUPLICATE'} else None,'payload_checksum_sha256':chk or env['payload_checksum_sha256'],'errors':errors or []}
oldopen=integ.urlrequest.urlopen; integ.urlrequest.urlopen=lambda req,timeout=8:Resp(202,json.dumps(receipt())); res=integ.dispatch_due(c); ok('matched ACCEPTED receipt alone marks delivery',res['delivered']==1 and c.execute('select status from integration_outbox where message_id=?',(mid,)).fetchone()['status']=='DELIVERED')
# malformed 202 retries
m2=integ.queue_product_event(c,event_type='FIRST_MEANINGFUL_ACTIVITY',event_id='V651-E2',actor_type='LEARNER',actor_id='PSEUDO',event_data={'completion_status':'DONE'}); integ.urlrequest.urlopen=lambda req,timeout=8:Resp(202,'{}'); res=integ.dispatch_due(c); ok('malformed HTTP 202 receipt remains durable retry',c.execute('select status from integration_outbox where message_id=?',(m2,)).fetchone()['status']=='RETRY')
integ.urlrequest.urlopen=oldopen
# strict preflight rejects HTTP/weak secrets
os.environ['POWER_HOUSE_TO_SCOREMAX_TOKEN']='x'; os.environ['POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET']='y'; os.environ['SCOREMAX_POWER_HOUSE_BASE_URL']='http://ph.example'; os.environ['SCOREMAX_TO_POWER_HOUSE_TOKEN']='x'; os.environ['SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET']='y'; os.environ['SCOREMAX_GROWTH_ENGINE_BASE_URL']='http://ge.example'; os.environ['SCOREMAX_TO_GROWTH_ENGINE_TOKEN']='x'; os.environ['SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET']='y'; pf=integ.production_preflight(strict=True); ok('strict preflight rejects HTTP peers and weak secrets',not pf['ready'] and pf['status']=='BLOCKED' and pf['issues'])
# learner request path contains only activation, no growth/content scans
src=(ROOT/'app.py').read_text(); seg=src[src.find('def _integration_housekeeping_tick'):src.find('def rate_limit')]; ok('learner request housekeeping has no Growth/requirement history projection','sync_growth_outbox' not in seg and 'sync_content_requirements' not in seg)
ok('database integrity remains OK',c.execute('pragma integrity_check').fetchone()[0]=='ok')
c.close(); print(f'\nSCOREMAX V6.5.3 RECTIFICATION CHECKS PASSED: {N}'); print('Disposable database:',TMP/'scoremax.db')
