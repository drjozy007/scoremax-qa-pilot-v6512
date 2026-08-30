"""ScoreMax V6.5.3 deep rectification checks: receipt state machine and mixed-version releases."""
from __future__ import annotations
import copy, hashlib, json, os, pathlib, tempfile
ROOT=pathlib.Path(__file__).resolve().parent
TMP=pathlib.Path(tempfile.mkdtemp(prefix='scoremax_v653_deep_'))
os.environ['SCOREMAX_DB']=str(TMP/'scoremax.db')
os.environ['SCOREMAX_SECRET']='V651-Deep-Test-Secret-1234567890'
os.environ['SCOREMAX_ENV']='test'; os.environ['SCOREMAX_ENFORCE_PAYWALL']='0'; os.environ['SCOREMAX_INTERNAL_FULL_ACCESS']='1'
from smoke_tests_v5_5 import install_framework_stubs; install_framework_stubs()
import app, scoremax_integration_v1 as integ
N=0
def ok(name,cond):
 global N
 if not cond: raise AssertionError(name)
 N+=1; print('PASS:',name)
def ex(name='PH_SM_APPROVED_CONTENT_V1.example.json'):
 return json.loads((ROOT/'integration_examples'/name).read_text())
def recalc(e):
 e=copy.deepcopy(e)
 for q in (e.get('payload') or {}).get('questions') or []:
  q['question_checksum_sha256']=integ._object_checksum(q,'question_checksum_sha256')
 for s in (e.get('payload') or {}).get('stimuli') or []:
  s['stimulus_checksum_sha256']=integ._object_checksum(s,'stimulus_checksum_sha256')
 e['payload_checksum_sha256']=integ.payload_checksum(e['payload'])
 return e
def make_release(tag, version, changed_from=None, unchanged_pct=100):
 base=ex(); p=base['payload']; rel=p['release']
 rel['release_id']=f'REL::V651::MIX::{tag}'
 rel['release_version']=version; rel['effective_at']=None
 rel['generated_at']='2026-08-21T15:00:00Z'
 rel['supersedes_release_version']=changed_from
 questions=[]
 unchanged_count=int(round(10*unchanged_pct/100)) if changed_from else 10
 template=p['questions'][0]
 for i in range(10):
  q=copy.deepcopy(template)
  qid=f'Q::V651::{tag}::{i:02d}'
  q['question_id']=qid
  if not changed_from or i<unchanged_count:
   q['question_version_id']=f'QV::V651::{tag}::{i:02d}::v1'
   q['question_version_number']=1
   q['supersedes_question_version_id']=None
  else:
   q['question_version_id']=f'QV::V651::{tag}::{i:02d}::v2'
   q['question_version_number']=2
   q['supersedes_question_version_id']=f'QV::V651::{tag}::{i:02d}::v1'
   q['content']['stem']=q['content']['stem']+f' [governed revision {i}]'
  q['provenance']['lineage']['original_question_id']=qid
  questions.append(q)
 p['questions']=questions; p['stimuli']=[]
 rel['question_count']=10; rel['stimulus_count']=0
 rel['package_checksum_sha256']=hashlib.sha256(f'{tag}:{version}:pkg'.encode()).hexdigest()
 rel['manifest_checksum_sha256']=hashlib.sha256(f'{tag}:{version}:manifest'.encode()).hexdigest()
 base['message_id']=f'msg::v653::{tag}::{version}'
 base['idempotency_key']=f'release::{tag}::{version}::{rel["package_checksum_sha256"]}'
 return recalc(base)

app.init(); c=app.db(); integ.init_schema(c); c.commit()

# Receipt-aware delivery state machine beyond the basic happy/malformed cases.
os.environ['SCOREMAX_GROWTH_ENGINE_BASE_URL']='https://growth.example'
os.environ['SCOREMAX_TO_GROWTH_ENGINE_TOKEN']='T'*32
os.environ['SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET']='S'*48
class Resp:
 def __init__(self,status,body): self.status=status; self._body=body
 def read(self): return self._body.encode()
def mk_event(eid):
 return integ.queue_product_event(c,event_type='FIRST_MEANINGFUL_ACTIVITY',event_id=eid,actor_type='LEARNER',actor_id='PSEUDO',event_data={'completion_status':'DONE'})
def mk_receipt(env,status='ACCEPTED',message_id=None,checksum=None,errors=None):
 return {'receipt_id':'RCPT::GE::'+hashlib.sha256((env['message_id']+status).encode()).hexdigest()[:12],
         'message_id':message_id or env['message_id'],'contract_name':env['contract_name'],
         'receiver_system':'GROWTH_ENGINE','received_at':'2026-08-21T15:00:00Z','status':status,
         'duplicate_of_receipt_id':None,'accepted_schema_version':'1.0.0' if status in {'ACCEPTED','DUPLICATE'} else None,
         'payload_checksum_sha256':checksum or env['payload_checksum_sha256'],'errors':errors or []}
oldopen=integ.urlrequest.urlopen
# QUARANTINED
m=mk_event('V651-DEEP-Q'); env=json.loads(c.execute('select envelope_json from integration_outbox where message_id=?',(m,)).fetchone()['envelope_json'])
integ.urlrequest.urlopen=lambda req,timeout=8:Resp(202,json.dumps(mk_receipt(env,'QUARANTINED',errors=[{'code':'PEER_POLICY','path':'payload','message':'quarantined','retryable':False}])))
integ.dispatch_due(c); ok('peer QUARANTINED receipt persists quarantined state',c.execute('select status from integration_outbox where message_id=?',(m,)).fetchone()['status']=='QUARANTINED')
# non-retryable REJECTED
m=mk_event('V651-DEEP-R'); env=json.loads(c.execute('select envelope_json from integration_outbox where message_id=?',(m,)).fetchone()['envelope_json'])
integ.urlrequest.urlopen=lambda req,timeout=8:Resp(422,json.dumps(mk_receipt(env,'REJECTED',errors=[{'code':'BAD_PAYLOAD','path':'payload','message':'rejected','retryable':False}])))
integ.dispatch_due(c); ok('peer non-retryable REJECTED receipt dead-letters',c.execute('select status from integration_outbox where message_id=?',(m,)).fetchone()['status']=='DEAD_LETTER')
# wrong-message receipt
m=mk_event('V651-DEEP-MISMATCH'); env=json.loads(c.execute('select envelope_json from integration_outbox where message_id=?',(m,)).fetchone()['envelope_json'])
integ.urlrequest.urlopen=lambda req,timeout=8:Resp(202,json.dumps(mk_receipt(env,'ACCEPTED',message_id='msg::wrong')))
integ.dispatch_due(c); ok('wrong-message ACCEPTED receipt cannot mark delivery',c.execute('select status from integration_outbox where message_id=?',(m,)).fetchone()['status']=='RETRY')
integ.urlrequest.urlopen=oldopen

# Mixed-version release membership: prove version identity is independent of release membership.
for pct in (0,50,90,100):
 tag=f'P{pct}'
 r1=make_release(tag,'BASE')
 rr,ss=integ.admit_content_envelope(c,r1,r1['payload_checksum_sha256']); ok(f'{pct}% pattern base release admitted',ss==202)
 r2=make_release(tag,'NEXT',changed_from='BASE',unchanged_pct=pct)
 rr,ss=integ.admit_content_envelope(c,r2,r2['payload_checksum_sha256']); ok(f'{pct}% unchanged successor release admitted',ss==202)
 integ.authorize_product_activation(c,r2['payload']['release']['release_id'],r2['payload']['release']['release_version'],r2['payload']['release']['package_checksum_sha256'],'TEST::V651-DEEP','successor projection regression'); c.commit()
 version_count=c.execute('select count(*) n from integration_ph_question_version_store where question_id like ?',(f'Q::V651::{tag}::%',)).fetchone()['n']
 expected_versions=20-int(round(10*pct/100))
 ok(f'{pct}% unchanged stores only genuinely new immutable versions',version_count==expected_versions)
 memberships=c.execute('select count(*) n from integration_ph_release_question_membership where release_id=?',(f'REL::V651::MIX::{tag}',)).fetchone()['n']
 ok(f'{pct}% unchanged preserves both full release memberships',memberships==20)
 current=c.execute('select count(*) n from questions where ph_release_id=? and ph_release_version=? and active=1',(f'REL::V651::MIX::{tag}','NEXT')).fetchone()['n']
 ok(f'{pct}% unchanged projects exactly the successor snapshot',current==10)

ok('deep-suite database integrity remains OK',c.execute('pragma integrity_check').fetchone()[0]=='ok')
c.close(); print(f'\nSCOREMAX V6.5.3 DEEP RECTIFICATION CHECKS PASSED: {N}'); print('Disposable database:',TMP/'scoremax.db')
