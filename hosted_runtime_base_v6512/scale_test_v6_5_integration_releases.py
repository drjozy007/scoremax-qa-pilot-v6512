"""ScoreMax V6.5.0 integration release scale gate.

Synthetic canonical-contract load test only. It proves ScoreMax-side admission/projection scale,
not the real cross-system Power House qualification gate.
"""
from __future__ import annotations
import copy, hashlib, json, os, tempfile, time
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TMP=Path(tempfile.mkdtemp(prefix='scoremax_v650_scale_'))
os.environ['SCOREMAX_DB']=str(TMP/'scoremax.db')
os.environ['SCOREMAX_SECRET']='Scale-Test-Only'
os.environ['SCOREMAX_ENV']='test'
os.environ['SCOREMAX_ENFORCE_PAYWALL']='0'
os.environ['SCOREMAX_INTERNAL_FULL_ACCESS']='1'

from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import scoremax_integration_v1 as integ

BASE=json.loads((ROOT/'integration_examples'/'PH_SM_APPROVED_CONTENT_V1.example.json').read_text(encoding='utf-8'))

def nowz():
    return (datetime.now(timezone.utc)-timedelta(seconds=2)).replace(microsecond=0).isoformat().replace('+00:00','Z')

def q_checksum(q):
    return hashlib.sha256(integ.canonical_json({k:v for k,v in q.items() if k!='question_checksum_sha256'}).encode()).hexdigest()

def make_release(n:int,label:str):
    env=copy.deepcopy(BASE)
    rel=env['payload']['release']
    rel['release_id']=f'REL::SCALE::{label}::{n}'
    rel['release_version']='1.0.0'
    rel['effective_at']=nowz(); rel['generated_at']=nowz(); rel['question_count']=n
    qs=[]; stimuli=[]
    for i in range(n):
        q=copy.deepcopy(BASE['payload']['questions'][0])
        q['question_id']=f'Q::SCALE::{label}::{i:05d}'
        q['question_version_id']=f'QV::SCALE::{label}::{i:05d}::v1'
        q['question_version_number']=1; q['supersedes_question_version_id']=None
        q['effective_from']=nowz()
        q['content']['stem']=f'Scale integration question {i} for {label}?'
        q['content']['marking']['key']='A' if i%2==0 else 'B'
        q['architecture']['knowledge_node_ids']=[f'NODE::SCALE::{i%73:03d}']
        q['architecture']['claim_family_id']=f'FAMILY::SCALE::{i%41:03d}'
        q['architecture']['reasoning_seed_id']=f'SEED::SCALE::{i%97:03d}'
        q['architecture']['misconception_ids']=[]
        # Heterogeneous dependent/recovery records remain zero-weight.
        if i%11==0:
            q['architecture'].update({'evidence_role':'RECOVERY','dependency_type':'RECOVERY','dependency_group_id':f'DEP::SCALE::{i//11:04d}','independent_mastery_eligible':False,'independent_mastery_weight':0})
        else:
            q['architecture'].update({'evidence_role':'INDEPENDENT','dependency_type':None,'dependency_group_id':None,'independent_mastery_eligible':True,'independent_mastery_weight':1})
        # Heterogeneous live-markable structures: numerical and multiple-select routes.
        # Rubric-only content is deliberately covered by the V6.5.3 capability-rejection suite
        # rather than smuggled into a live scale release.
        if i%37==0:
            q['content']['question_family_type']='NUMERICAL'; q['content']['exam_question_type']='NUMERIC_RESPONSE'; q['content']['options']=[]
            q['content']['marking'].update({'key_type':'NUMERIC','key':float(i%100)+0.5,'accepted_answers':[],'numeric_tolerance':0.1,'marks':2,'negative_marks':-0.25,'rubric':None})
        elif i%79==0:
            q['content']['question_family_type']='MCQ'; q['content']['exam_question_type']='MULTIPLE_SELECT'
            q['content']['options']=[{'option_id':'A','text':'Option A','is_display_only':False},{'option_id':'B','text':'Option B','is_display_only':False},{'option_id':'C','text':'Option C','is_display_only':False},{'option_id':'D','text':'Option D','is_display_only':False}]
            q['content']['marking'].update({'key_type':'MULTIPLE_OPTIONS','key':['A','C'],'accepted_answers':[],'numeric_tolerance':None,'marks':2,'negative_marks':-0.25,'rubric':None})
        # Shared stimulus references.
        if i%53==0:
            sid=f'STIM::SCALE::{label}::{i//53:04d}'
            st={'stimulus_id':sid,'stimulus_version_id':sid+'::v1','stimulus_checksum_sha256':'0'*64,'stimulus_type':'TEXT','content':{'text':f'Governed scale stimulus {i//53}.'},'provenance':{'source_id':'fixture::scale','source_type':'TEST_FIXTURE','rights_status':'OWNED'}}; st['stimulus_checksum_sha256']=integ._object_checksum(st,'stimulus_checksum_sha256'); stimuli.append(st)
            q['content']['stimulus_ref']=sid
        q['question_checksum_sha256']=q_checksum(q)
        qs.append(q)
    env['payload']['questions']=qs; env['payload']['stimuli']=stimuli
    rel['stimulus_count']=len(stimuli)
    rel['package_checksum_sha256']=hashlib.sha256((rel['release_id']+'|pkg').encode()).hexdigest()
    rel['manifest_checksum_sha256']=hashlib.sha256((rel['release_id']+'|manifest').encode()).hexdigest()
    env['idempotency_key']=f"release::{rel['release_id']}::{rel['release_version']}::{rel['package_checksum_sha256']}"
    env['message_id']='msg::PH_SM_APPROVED_CONTENT_V1::'+hashlib.sha256(env['idempotency_key'].encode()).hexdigest()[:24]
    env['occurred_at']=nowz(); env['sent_at']=nowz(); env['correlation_id']='corr::scale::'+label
    env['payload_checksum_sha256']=integ.payload_checksum(env['payload'])
    return env

def run_one(c,n,label):
    env=make_release(n,label)
    t=time.perf_counter(); receipt,status=integ.admit_content_envelope(c,env,env['payload_checksum_sha256']); c.commit(); elapsed=time.perf_counter()-t
    rel=env['payload']['release']
    admitted=c.execute('SELECT COUNT(*) n FROM integration_ph_release_question_membership WHERE release_id=? AND release_version=?',(rel['release_id'],rel['release_version'])).fetchone()['n']
    state=c.execute('SELECT local_status FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(rel['release_id'],rel['release_version'])).fetchone()['local_status']
    live=c.execute('SELECT COUNT(*) n FROM questions WHERE ph_release_id=? AND ph_release_version=? AND active=1 AND status="Approved"',(rel['release_id'],rel['release_version'])).fetchone()['n']
    if status!=202 or receipt['status']!='ACCEPTED' or admitted!=n or state!='STAGED' or live!=0:
        raise AssertionError({'n':n,'status':status,'receipt':receipt,'admitted':admitted,'state':state,'live_before_activation':live})
    # Duplicate replay must be cheap and idempotent while remaining staged.
    t2=time.perf_counter(); rec2,st2=integ.admit_content_envelope(c,env,env['payload_checksum_sha256']); c.commit(); dup=time.perf_counter()-t2
    if st2!=200 or rec2!=receipt: raise AssertionError('exact scale replay did not return original durable receipt')
    act=integ.authorize_product_activation(c,rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],'SCALE-GATE','Canonical integration scale activation gate'); c.commit()
    live=c.execute('SELECT COUNT(*) n FROM questions WHERE ph_release_id=? AND ph_release_version=? AND active=1 AND status="Approved"',(rel['release_id'],rel['release_version'])).fetchone()['n']
    zero=c.execute('SELECT COUNT(*) n FROM questions WHERE ph_release_id=? AND ph_release_version=? AND ph_dependency_type<>"" AND ph_independent_mastery_weight<>0',(rel['release_id'],rel['release_version'])).fetchone()['n']
    if act.get('status')!='ACTIVE' or live!=n or zero!=0:
        raise AssertionError({'n':n,'activation':act,'live_after_activation':live,'bad_dependent_weight':zero})
    print(f'PASS: {n}-question canonical PH release admission={elapsed:.3f}s duplicate={dup:.3f}s staged={admitted} live_after_authorization={live} stimuli={rel["stimulus_count"]}')
    return elapsed,dup

def main():
    app.init(); c=app.db(); integ.init_schema(c); c.commit()
    timings={}
    for n,label in [(300,'CHAPTER300'),(1500,'CHAPTER1500')]: timings[n]=run_one(c,n,label)
    integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    if integrity!='ok': raise AssertionError(integrity)
    print('PASS: SQLite integrity ok after 300/1500 integration release admissions')
    print('NOTE: synthetic canonical-contract scale evidence only; a real governed Power House 300/1,500 release remains a cross-system qualification gate.')
    c.close()

if __name__=='__main__': main()
