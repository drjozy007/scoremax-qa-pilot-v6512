#!/usr/bin/env python3
"""Portable central-admission attacks added after ScoreMax V6.5.3.

Usage:
  python RUN_NEW_CENTRAL_ATTACKS.py <candidate.zip-or-extracted-root>

The candidate is extracted/copied to a disposable temporary workspace. This script never edits
sealed candidate bytes. Exit code 0 means all three new findings are NOT_CONFIRMED.
"""
from __future__ import annotations
import argparse, json, os, shutil, sys, tempfile, zipfile
from pathlib import Path
from urllib import error as urlerror

REQUIRED_HEALTH={
 'direction','contract','connection_state','last_success_at','last_received_at','last_dispatched_at',
 'queued_count','retrying_count','dead_letter_count','quarantined_count','oldest_queued_at',
 'last_error_code','last_error_at','local_schema_version','peer_schema_version','peer_version',
 'credential_expiry_warning','clock_skew_warning'
}

def find_root(base: Path) -> Path:
    if (base/'app.py').exists() and (base/'scoremax_integration_v1.py').exists(): return base
    hits=list(base.rglob('scoremax_integration_v1.py'))
    for hit in hits:
        root=hit.parent
        if (root/'app.py').exists(): return root
    raise SystemExit('Could not locate candidate root containing app.py and scoremax_integration_v1.py')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('candidate'); ap.add_argument('--json-out',default='')
    args=ap.parse_args(); src=Path(args.candidate).resolve()
    temp=Path(tempfile.mkdtemp(prefix='scoremax_new_central_attacks_'))
    try:
        if src.is_file():
            with zipfile.ZipFile(src) as z: z.extractall(temp/'candidate')
            root=find_root(temp/'candidate')
        else:
            root=find_root(src)
        db=temp/'scoremax.db'
        os.environ.update({
          'SCOREMAX_DB':str(db),'SCOREMAX_SECRET':'Central-Return-Gate-Test-Secret-Only',
          'SCOREMAX_ENV':'test','SCOREMAX_ENFORCE_PAYWALL':'0','SCOREMAX_INTERNAL_FULL_ACCESS':'1',
          'SCOREMAX_GROWTH_ENGINE_BASE_URL':'https://growth.example',
          'SCOREMAX_TO_GROWTH_ENGINE_TOKEN':'central-return-gate-token-long-enough',
          'SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET':'central-return-gate-secret-long-enough-for-hmac'
        })
        sys.path.insert(0,str(root))
        from smoke_tests_v5_5 import install_framework_stubs
        install_framework_stubs()
        import app
        import scoremax_integration_v1 as integ
        app.init(); c=app.db(); integ.init_schema(c); c.commit()
        findings=[]
        def add(fid,severity,title,confirmed,evidence):
            findings.append({'id':fid,'severity':severity,'title':title,'confirmed':bool(confirmed),'evidence':evidence})
            print(('CONFIRMED' if confirmed else 'NOT_CONFIRMED')+':',fid,title)

        # 1. Exhausted cycle -> audited requeue -> one new transient failure must NOT immediately dead-letter.
        mid=integ.queue_product_event(c,event_type='LEARNER_REGISTERED',event_id='RETURN-GATE-REQUEUE-1',event_data={'metadata':{'case':'requeue'}}); c.commit()
        row=c.execute('SELECT * FROM integration_outbox WHERE message_id=?',(mid,)).fetchone(); oid=int(row['id'])
        exhausted=len(integ.RETRY_DELAYS)
        c.execute("UPDATE integration_outbox SET status='DEAD_LETTER',attempt_count=?,last_error_code='TRANSPORT_ERROR',last_error='prior cycle exhausted' WHERE id=?",(exhausted,oid))
        for i in range(exhausted):
            c.execute("INSERT INTO integration_dispatch_attempts(outbox_id,attempted_at,http_status,result_status,error_code,error_text,response_json) VALUES(?,?,?,?,?,?,?)",(oid,integ.utcnow(),503,'RETRY' if i<exhausted-1 else 'DEAD_LETTER','HTTP_503','prior cycle',''))
        c.commit(); prior=c.execute('SELECT COUNT(*) n FROM integration_dispatch_attempts WHERE outbox_id=?',(oid,)).fetchone()['n']
        requeued=integ.requeue_outbox(c,oid,actor='RETURN_GATE',reason='new governed retry cycle')
        after_requeue=dict(c.execute('SELECT status,attempt_count FROM integration_outbox WHERE id=?',(oid,)).fetchone())
        orig=integ.urlrequest.urlopen; integ.urlrequest.urlopen=lambda *a,**k: (_ for _ in ()).throw(urlerror.URLError('simulated outage'))
        try: dispatch=integ.dispatch_due(c,limit=1,timeout=1)
        finally: integ.urlrequest.urlopen=orig
        post=dict(c.execute('SELECT status,attempt_count,next_attempt_at,last_error_code FROM integration_outbox WHERE id=?',(oid,)).fetchone())
        postn=c.execute('SELECT COUNT(*) n FROM integration_dispatch_attempts WHERE outbox_id=?',(oid,)).fetchone()['n']
        # Finding is confirmed if first new transient failure is terminal; corrected behaviour is RETRY.
        confirmed=bool(requeued and post['status']=='DEAD_LETTER')
        add('INT-SM653-P1-001','P1','Dead-letter requeue preserves exhausted cycle',confirmed,{
          'after_requeue':after_requeue,'after_one_new_transient_failure':post,'dispatch_result':dispatch,
          'prior_attempt_rows':prior,'attempt_rows_after':postn,'retry_profile':integ.RETRY_DELAYS})

        # 2. Non-finite input must fail before durable integration side effects.
        before=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
        nan_mid=''; exc=''
        try:
            nan_mid=integ.queue_product_event(c,event_type='LEARNER_REGISTERED',event_id='RETURN-GATE-NAN-1',event_data={'metadata':{'poison':float('nan')}}); c.commit()
        except Exception as e:
            exc=repr(e); c.rollback()
        after=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
        row=c.execute('SELECT envelope_json FROM integration_outbox WHERE message_id=?',(nan_mid,)).fetchone() if nan_mid else None
        invalid_persisted=False
        if row:
            try: json.loads(row['envelope_json'],parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            except Exception: invalid_persisted=True
        confirmed=bool(invalid_persisted or after>before)
        add('INT-SM653-P1-002','P1','Non-finite value persisted as non-standard JSON',confirmed,{
          'outbox_count_before':before,'outbox_count_after':after,'message_id':nan_mid,'exception':exc,'invalid_json_persisted':invalid_persisted})

        # 3. Frozen minimum health fields.
        health=integ.integration_health(c); missing={}
        for d in health.get('directions',[]):
            miss=sorted(REQUIRED_HEALTH-set(d.keys()))
            if miss: missing[d.get('contract')]=miss
        confirmed=bool(missing)
        add('INT-SM653-P1-003','P1','Integration Health omits frozen minimum fields',confirmed,{'missing_by_contract':missing})

        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
        out={'candidate_release':getattr(integ,'SCOREMAX_INTEGRATION_RELEASE','UNKNOWN'),'confirmed_total':sum(f['confirmed'] for f in findings),
             'P0':sum(f['confirmed'] and f['severity']=='P0' for f in findings),'P1':sum(f['confirmed'] and f['severity']=='P1' for f in findings),
             'integrity':integrity,'foreign_key_violations':fk,'findings':findings}
        text=json.dumps(out,indent=2,sort_keys=True,default=str); print(text)
        if args.json_out: Path(args.json_out).write_text(text,encoding='utf-8')
        c.close()
        return 0 if out['confirmed_total']==0 and integrity=='ok' and fk==0 else 1
    finally:
        shutil.rmtree(temp,ignore_errors=True)

if __name__=='__main__':
    raise SystemExit(main())
