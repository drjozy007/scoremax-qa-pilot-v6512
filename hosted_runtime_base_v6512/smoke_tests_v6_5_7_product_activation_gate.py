"""Permanent V6.5.7 regression for INT-PHSM-B01-P0-002.

Academic admission must end at immutable STAGED state. Only an exact, durable,
ScoreMax-owned product authorization may project Power House content learner-live.
"""
from __future__ import annotations
import copy, hashlib, json, os, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parent
TMP=Path(tempfile.mkdtemp(prefix='scoremax_v657_activation_'))
os.environ['SCOREMAX_DB']=str(TMP/'scoremax.db')
os.environ['SCOREMAX_SECRET']='V657-Activation-Test-Only'
os.environ['SCOREMAX_ENV']='test'
os.environ['SCOREMAX_ENFORCE_PAYWALL']='0'
os.environ['SCOREMAX_INTERNAL_FULL_ACCESS']='1'

from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import scoremax_integration_v1 as integ

BASE=json.loads((ROOT/'integration_examples'/'PH_SM_APPROVED_CONTENT_V1.example.json').read_text(encoding='utf-8'))
N=0

def ok(name, cond, detail=''):
    global N
    N+=1
    if not cond:
        raise AssertionError(f'{name}: {detail}')
    print('PASS:',name)

def nowz(offset_seconds=-2):
    return (datetime.now(timezone.utc)+timedelta(seconds=offset_seconds)).replace(microsecond=0).isoformat().replace('+00:00','Z')

def q_checksum(q):
    return hashlib.sha256(integ.canonical_json({k:v for k,v in q.items() if k!='question_checksum_sha256'}).encode()).hexdigest()

def make_release(n:int,label:str,effective='NONE'):
    env=copy.deepcopy(BASE)
    rel=env['payload']['release']
    rel['release_id']=f'REL::ACTGATE::{label}::{n}'
    rel['release_version']='1.0.0'
    rel['generated_at']=nowz()
    if effective=='NONE': rel['effective_at']=None
    elif effective=='PAST': rel['effective_at']=nowz(-3600)
    elif effective=='FUTURE': rel['effective_at']=nowz(86400)
    else: rel['effective_at']=effective
    qs=[]
    for i in range(n):
        q=copy.deepcopy(BASE['payload']['questions'][0])
        q['question_id']=f'Q::ACTGATE::{label}::{i:05d}'
        q['question_version_id']=f'QV::ACTGATE::{label}::{i:05d}::v1'
        q['question_version_number']=1
        q['supersedes_question_version_id']=None
        q['effective_from']=nowz()
        q['content']['stem']=f'Activation gate governed question {i} for {label}?'
        q['architecture']['knowledge_node_ids']=[f'NODE::ACT::{i%29:03d}']
        q['architecture']['claim_family_id']=f'FAMILY::ACT::{i%31:03d}'
        q['architecture']['reasoning_seed_id']=f'SEED::ACT::{i%37:03d}'
        q['question_checksum_sha256']=q_checksum(q)
        qs.append(q)
    env['payload']['questions']=qs
    env['payload']['stimuli']=[]
    rel['question_count']=n; rel['stimulus_count']=0
    rel['package_checksum_sha256']=hashlib.sha256((rel['release_id']+'|package').encode()).hexdigest()
    rel['manifest_checksum_sha256']=hashlib.sha256((rel['release_id']+'|manifest').encode()).hexdigest()
    env['idempotency_key']=f"release::{rel['release_id']}::{rel['release_version']}::{rel['package_checksum_sha256']}"
    env['message_id']='msg::PH_SM_APPROVED_CONTENT_V1::'+hashlib.sha256(env['idempotency_key'].encode()).hexdigest()[:24]
    env['occurred_at']=nowz(); env['sent_at']=nowz(); env['correlation_id']='corr::actgate::'+label
    env['payload_checksum_sha256']=integ.payload_checksum(env['payload'])
    return env

def counts(c,rel):
    rid,ver=rel['release_id'],rel['release_version']
    row=c.execute('SELECT local_status FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(rid,ver)).fetchone()
    members=c.execute('SELECT COUNT(*) n FROM integration_ph_release_question_membership WHERE release_id=? AND release_version=?',(rid,ver)).fetchone()['n']
    live=c.execute("SELECT COUNT(*) n FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND ph_release_id=? AND ph_release_version=? AND COALESCE(active,0)=1",(rid,ver)).fetchone()['n']
    return (row['local_status'] if row else None),members,live

def admit(c,env):
    rec,status=integ.admit_content_envelope(c,env,env['payload_checksum_sha256'])
    c.commit(); return rec,status

def main():
    app.init(); c=app.db(); integ.init_schema(c); c.commit()

    # Real Batch-01 shape requirement: 300 staged memberships, zero learner projections.
    env=make_release(300,'BATCH01','NONE'); rel=env['payload']['release']
    rec,status=admit(c,env)
    st,members,live=counts(c,rel)
    ok('valid PH 300 event accepted',status==202 and rec['status']=='ACCEPTED')
    ok('300 release remains STAGED',st=='STAGED',st)
    ok('300 exact staged memberships retained',members==300,members)
    ok('300 admission creates zero active learner projections',live==0,live)

    # Exact replay must return the original receipt without duplicate state.
    rec2,status2=admit(c,env); st2,members2,live2=counts(c,rel)
    ok('identical event replay is durable/idempotent',status2==200 and rec2==rec)
    ok('replay creates no duplicate membership/projection',members2==300 and live2==0)

    # effective_at is source metadata, never product authority.
    for label,effective in [('NULL','NONE'),('PAST','PAST'),('FUTURE','FUTURE')]:
        e=make_release(2,'EFF'+label,effective); r=e['payload']['release']; admit(c,e)
        activated=integ.activate_due_releases(c); c.commit(); stx,mx,lx=counts(c,r)
        ok(f'effective_at {label} cannot independently activate',activated==0 and stx=='STAGED' and mx==2 and lx==0,(activated,stx,mx,lx))

    # Wrong identities/checksum cannot authorize activation.
    wrong=integ.authorize_product_activation(c,rel['release_id'],rel['release_version'],'0'*64,'ADM-TEST','central qualification passed')
    c.commit(); st,members,live=counts(c,rel)
    ok('wrong checksum cannot activate',wrong['status']=='REJECTED' and wrong['code']=='RELEASE_CHECKSUM_MISMATCH' and st=='STAGED' and live==0,wrong)
    wrong2=integ.authorize_product_activation(c,rel['release_id'],'missing-version',rel['package_checksum_sha256'],'ADM-TEST','central qualification passed')
    c.commit(); ok('wrong release version cannot activate',wrong2['status']=='REJECTED' and wrong2['code']=='RELEASE_NOT_FOUND',wrong2)
    wrong3=integ.authorize_product_activation(c,'missing-release',rel['release_version'],rel['package_checksum_sha256'],'ADM-TEST','central qualification passed')
    c.commit(); ok('wrong release id cannot activate',wrong3['status']=='REJECTED' and wrong3['code']=='RELEASE_NOT_FOUND',wrong3)
    missing_evidence=integ.authorize_product_activation(c,rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],'','')
    c.commit(); ok('activation actor/reason evidence is mandatory',missing_evidence['status']=='REJECTED' and missing_evidence['code']=='ACTIVATION_EVIDENCE_REQUIRED',missing_evidence)

    # Exact ScoreMax-owned authorization activates once.
    result=integ.authorize_product_activation(c,rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],'ADM-000001','Independent connected qualification passed')
    c.commit(); st,members,live=counts(c,rel)
    ok('explicit exact ScoreMax activation succeeds',result['status']=='ACTIVE' and result['activated_count']==300,result)
    ok('explicit activation projects exact 300 once',st=='ACTIVE' and members==300 and live==300,(st,members,live))
    auth=c.execute('SELECT * FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?',(rel['release_id'],rel['release_version'])).fetchall()
    ok('activation evidence is durable actor/time/reason/checksum',len(auth)==1 and auth[0]['authorized_by']=='ADM-000001' and auth[0]['reason']=='Independent connected qualification passed' and auth[0]['authorized_at'] and auth[0]['activated_at'] and auth[0]['package_checksum_sha256']==rel['package_checksum_sha256'])

    replay=integ.authorize_product_activation(c,rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],'ADM-OTHER','should not overwrite first authorization')
    c.commit(); st,members,live=counts(c,rel)
    auth2=c.execute('SELECT * FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?',(rel['release_id'],rel['release_version'])).fetchall()
    ok('repeated activation is idempotent',replay['status']=='ACTIVE' and replay['code']=='IDEMPOTENT_REPLAY' and replay['activated_count']==0 and live==300,replay)
    ok('replay does not overwrite first authorization evidence',len(auth2)==1 and auth2[0]['authorized_by']=='ADM-000001' and auth2[0]['reason']=='Independent connected qualification passed')

    # Direct internal activation has a structural fence when no authorization exists.
    e=make_release(3,'DIRECTFENCE','PAST'); r=e['payload']['release']; admit(c,e)
    direct=integ._activate_release(c,r['release_id'],r['release_version']); c.commit(); stx,mx,lx=counts(c,r)
    ok('internal _activate_release cannot bypass product authorization',direct==0 and stx=='STAGED' and lx==0,(direct,stx,lx))

    # Authorization of future-source-effective release is a ScoreMax decision and can activate it.
    e=make_release(4,'EXPLICITFUTURE','FUTURE'); r=e['payload']['release']; admit(c,e)
    res=integ.authorize_product_activation(c,r['release_id'],r['release_version'],r['package_checksum_sha256'],'ADM-000001','Product launch authorization')
    c.commit(); stx,mx,lx=counts(c,r)
    ok('explicit ScoreMax authorization, not PH schedule, controls learner activation',res['status']=='ACTIVE' and stx=='ACTIVE' and lx==4,(res,stx,lx))

    # Existing Integration Health admin surface executes the same governed activation path.
    e=make_release(1,'ADMINCONTROL','NONE'); r=e['payload']['release']; admit(c,e)
    admin=c.execute("SELECT id,system_user_id FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone()
    app.session.clear(); app.session.update({'user_id':admin['id'],'role':'admin'})
    app.request.form={'release_id':r['release_id'],'release_version':r['release_version'],'package_checksum_sha256':r['package_checksum_sha256'],'reason':'Central connected qualification passed'}
    response=app.admin_activate_power_house_release()
    c2=app.db(); stadmin,madmin,ladmin=counts(c2,r); aadmin=c2.execute('SELECT * FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?',(r['release_id'],r['release_version'])).fetchone(); c2.close()
    ok('existing Integration Health admin control activates the exact staged release',stadmin=='ACTIVE' and ladmin==1 and bool(response),(stadmin,ladmin,response))
    ok('admin activation records governed actor and reason evidence',aadmin and aadmin['authorized_by']==admin['system_user_id'] and aadmin['reason']=='Central connected qualification passed')

    # Withdrawal of a staged release prevents later activation.
    e=make_release(2,'WITHDRAW-STAGED','NONE'); r=e['payload']['release']; admit(c,e)
    c.execute("UPDATE integration_ph_content_releases SET local_status='WITHDRAWN',withdrawn_at=?,withdrawal_reason='test withdrawal' WHERE release_id=? AND release_version=?",(nowz(),r['release_id'],r['release_version']))
    blocked=integ.authorize_product_activation(c,r['release_id'],r['release_version'],r['package_checksum_sha256'],'ADM-000001','should be blocked'); c.commit(); stx,mx,lx=counts(c,r)
    ok('withdrawn staged release cannot activate',blocked['status']=='REJECTED' and blocked['code']=='RELEASE_NOT_ACTIVATABLE' and stx=='WITHDRAWN' and lx==0,blocked)

    integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    fks=c.execute('PRAGMA foreign_key_check').fetchall()
    ok('SQLite integrity ok',integrity=='ok',integrity)
    ok('foreign key violations zero',len(fks)==0,len(fks))
    print(f'PASS: V6.5.7 product activation gate {N}/{N}')
    c.close()

if __name__=='__main__': main()
