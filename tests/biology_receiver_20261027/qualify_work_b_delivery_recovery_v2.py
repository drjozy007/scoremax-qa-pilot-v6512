"""Actual signed Flask/native SQLite race and recovery controls; software only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import hashlib,json,sys,tempfile,threading
from unittest.mock import patch
from native_delivery_fixture import NativeDeliveryFixture
ROOT=Path(__file__).resolve().parents[2]


def ack(f,stop):
    c=f.native.db()
    try:return json.loads(c.execute('SELECT envelope_json FROM integration_outbox WHERE contract_name=? AND business_identity=?',
        ('SM_PH_QUESTION_WITHDRAWAL_ACK_V1',stop['payload']['export_public_id'])).fetchone()[0])['payload']['items'][0]
    finally:c.close()


def placement(f,envelope,label,programme):
    e=deepcopy(envelope);e.update(message_id='software-content::'+label,idempotency_key='software-content::'+label)
    r=e['payload']['release'];r.update(release_id='software-release::'+label,programme_id=programme,
        package_checksum_sha256=hashlib.sha256(label.encode()).hexdigest())
    return f.seal(e)


def attempt(f,sid):
    c=f.native.db()
    try:
        row=c.execute('SELECT * FROM attempts WHERE assessment_session_id=?',(sid,)).fetchone()
        return dict(row) if row else None
    finally:c.close()


def current_evidence(f,uid,programme):
    c=f.native.db()
    try:return len(f.native.learner_answer_evidence(c,uid,programme))
    finally:c.close()


def run(runtime=None):
    observations=[]
    with tempfile.TemporaryDirectory(prefix='native-delivery-recovery-') as directory:
        f=NativeDeliveryFixture(runtime or ROOT/'scoremax_runtime_v669b',directory);i=f.integration;n=f.native
        # One global local q row, two actual independently authorized release placements.
        e=f.content('shared-scope');q=e['payload']['questions'][0]
        md=placement(f,e,'shared-scope-mdcat','MDCAT')
        f.send_content(e);f.activate(e);f.send_content(md);f.activate(md)
        u=f.learner('shared-fsc');sid,qdb,programme=f.session_for(u,e)
        um=f.learner('shared-mdcat','MDCAT');sidm,_,_=f.session_for(um,md)
        stop=f.withdrawal('only-fsc',q,target=f.exact_target(e));f.send_stop(stop)
        assert f.active(q)['active']==1
        c=n.db()
        try:
            assert not i._eligible_release_question_versions(c,e['payload']['release']['release_id'],'1')
            assert len(i._eligible_release_question_versions(c,md['payload']['release']['release_id'],'1'))==1
        finally:c.close()
        f.submit(u,sid,expected_statuses=(409,));f.submit(um,sidm)
        assert attempt(f,sid) is None
        assert attempt(f,sidm)['mastery_evidence_eligible']==1
        assert current_evidence(f,u,programme)==0 and current_evidence(f,um,'MDCAT')==1
        observations.append({'case':'FSc-stop-preserves-independent-MDCAT-placement-and-fences-formal-evidence','passed':True})
        # All targets in an item validate before any stop. A real known-membership
        # mismatch may not mutate even its valid sibling target or poison retries.
        bad=f.exact_target(md);bad['question_checksum_sha256']='7'*64
        mixed=f.withdrawal('mixed-bad',q,target=[f.exact_target(md),bad])
        f.signed_post('/api/integration/v1/power-house/question-withdrawals',mixed,expected_statuses=(422,))
        assert f.active(q)['active']==1
        bad=f.exact_target(md);bad['question_version_id']='opaque::not-member'
        mixed=f.withdrawal('mixed-known-bad',q,target=[f.exact_target(md),bad]);f.send_stop(mixed)
        assert ack(f,mixed)['state']=='RETRY' and f.active(q)['active']==1
        c=n.db()
        try:assert c.execute('SELECT count(*) FROM ph_bridge_staged_withdrawal_exclusions_v6611e WHERE release_id=?',(md['payload']['release']['release_id'],)).fetchone()[0]==0
        finally:c.close()
        # The failed identity request is retained for audit but confers no stop.
        repeated=deepcopy(md);repeated.update(message_id='software-mdcat-duplicate-after-retry',idempotency_key='software-mdcat-duplicate-after-retry')
        f.send_content(repeated)
        both=f.withdrawal('all-exact',q,target=[f.exact_target(e),f.exact_target(md)]);f.send_stop(both)
        assert ack(f,both)['state'] in ('WITHDRAWN_AND_STAGED_EXCLUDED','STAGED_EXCLUDED') and f.active(q)['active']==0
        assert current_evidence(f,um,'MDCAT')==0
        observations.append({'case':'all-exact-targets-one-ACK-and-one-bad-tuple-no-partial-stop','passed':True})
        # Inject a crash at the real native signed HTTP queue boundary after
        # exclusions were inserted. Connection closure must roll back everything.
        e=f.content('crash-stop');q=e['payload']['questions'][0];f.send_content(e);f.activate(e)
        stop=f.withdrawal('crash-stop',q,target=f.exact_target(e))
        original=i._queue
        def crash(c,env,*args,**kwargs):
            if env['contract_name']=='SM_PH_QUESTION_WITHDRAWAL_ACK_V1':
                assert c.in_transaction
                assert c.execute('SELECT count(*) FROM ph_bridge_staged_withdrawal_exclusions_v6611e WHERE question_id=?',(q['question_id'],)).fetchone()[0]==1
                raise RuntimeError('SOFTWARE_CRASH_BEFORE_ACK_LEDGER_COMMIT')
            return original(c,env,*args,**kwargs)
        with patch.object(i,'_queue',side_effect=crash):
            try:f.send_stop(stop)
            except RuntimeError as error:assert str(error)=='SOFTWARE_CRASH_BEFORE_ACK_LEDGER_COMMIT'
            else:raise AssertionError('Injected crash not reached')
        c=n.db()
        try:
            assert f.active(q)['active']==1
            assert c.execute('SELECT count(*) FROM ph_bridge_staged_withdrawal_exclusions_v6611e WHERE question_id=?',(q['question_id'],)).fetchone()[0]==0
            assert c.execute('SELECT count(*) FROM ph_bridge_withdrawal_receipts_v6611d WHERE export_public_id=?',(stop['payload']['export_public_id'],)).fetchone()[0]==0
            c.execute('BEGIN IMMEDIATE');c.execute("UPDATE questions SET question='SOFTWARE_UNCOMMITTED_SENTINEL' WHERE ph_question_id=?",(q['question_id'],))
            try:i.init_schema(c)
            except RuntimeError as error:assert str(error)=='INTEGRATION_SCHEMA_REQUIRES_IDLE_CONNECTION'
            else:raise AssertionError('Implicit business transaction commit possible')
            c.rollback()
        finally:c.close()
        f.send_stop(stop);f.send_stop(stop)
        assert f.active(q)['active']==0
        observations.append({'case':'actual-Flask-stop-crash-rolls-back-targets-ledger-and-ACK-then-recovers-once','passed':True})
        # Concurrent duplicate submissions share the existing writer claim.
        e=f.content('duplicate-submit');f.send_content(e);f.activate(e);u=f.learner('duplicate-submit');sid,_,p=f.session_for(u,e)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:f.submit(u,sid),range(2)))
        c=n.db()
        try:assert c.execute('SELECT count(*) FROM attempts WHERE assessment_session_id=?',(sid,)).fetchone()[0]==1
        finally:c.close()
        observations.append({'case':'actual-concurrent-native-submit-writers-one-attempt','passed':True})
        # Grade writer wins: score/flags are the original historical result;
        # after the stop, fresh current evidence is excluded.
        for first in ('grade','stop'):
            e=f.content('race-'+first);q=e['payload']['questions'][0];f.send_content(e);f.activate(e)
            u=f.learner('race-'+first);sid,_,p=f.session_for(u,e);stop=f.withdrawal('race-'+first,q,target=f.exact_target(e))
            entered=threading.Event();release=threading.Event()
            bridge=n.ph_bridge_v6611d
            original_mark=n.mark_question_result;original_stop=bridge._withdraw_one
            def hold_mark(*args,**kwargs):
                entered.set();assert release.wait(10);return original_mark(*args,**kwargs)
            def hold_stop(*args,**kwargs):
                result=original_stop(*args,**kwargs);entered.set();assert release.wait(10);return result
            with patch.object(n,'mark_question_result',side_effect=hold_mark) if first=='grade' else patch.object(bridge,'_withdraw_one',side_effect=hold_stop):
                with ThreadPoolExecutor(max_workers=2) as pool:
                    leader=pool.submit(f.submit,u,sid) if first=='grade' else pool.submit(f.send_stop,stop)
                    assert entered.wait(10)
                    follower=pool.submit(f.send_stop,stop) if first=='grade' else pool.submit(f.submit,u,sid,expected_statuses=(409,))
                    release.set();leader.result(timeout=20);follower.result(timeout=20)
            result=attempt(f,sid)
            assert (result and result['score']==100 and result['mastery_evidence_eligible']==1) if first=='grade' else result is None,result
            assert current_evidence(f,u,p)==0 and f.active(q)['active']==0
            observations.append({'case':'native-concurrent-'+first+'-first-linearization-history-preserved-current-evidence-stopped','passed':True})
        c=n.db()
        try:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()
        finally:c.close()
    return {'status':'PASSED','observations':observations,'native_signed_HTTP_SQLite_and_submit':True,
        'academic_authority':'SOFTWARE_FIXTURES_ONLY','production_mutated':False}

if __name__=='__main__':
    result=run(Path(sys.argv[2]) if len(sys.argv)>2 else None);out=Path(sys.argv[1]);assert not out.exists();out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
