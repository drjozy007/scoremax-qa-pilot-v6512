"""ScoreMax V6.5.4 governed integration outbox worker.

Runs independently from learner HTTP requests. Source projections are bounded, transport uses
an atomic outbox lease, and failed/quarantined work remains visible for audited operator requeue.
"""
from __future__ import annotations
import argparse, json, os, time, traceback
import app
import scoremax_integration_v1 as integration


def run_cycle(*,evidence=False,limit=100,strict_preflight=False):
    app.init()
    c=app.db()
    try:
        integration.init_schema(c)
        preflight=integration.production_preflight(strict=strict_preflight)
        if strict_preflight and not preflight['ready']:
            out={'release':app.SCOREMAX_RELEASE_VERSION,'status':'BLOCKED','preflight':preflight}
            integration.worker_heartbeat(c,result=out,process_id=str(os.getpid())); c.commit()
            return out,2
        activated=integration.activate_due_releases(c)
        growth=integration.sync_growth_outbox(c,app.SCOREMAX_RELEASE_VERSION,limit=max(1,limit))
        reqs=integration.sync_content_requirements(c,app.SCOREMAX_RELEASE_VERSION,limit=max(1,limit))
        evidence_count=integration.sync_delivery_evidence(c,app.SCOREMAX_RELEASE_VERSION) if evidence else 0
        dispatch=integration.dispatch_due(c,limit=max(1,limit))
        out={'release':app.SCOREMAX_RELEASE_VERSION,'status':'OK','activated_releases':activated,
             'growth_events_queued':growth,'content_requirements_queued':reqs,
             'evidence_batches_queued':evidence_count,'dispatch':dispatch,
             'health':integration.integration_health(c),'preflight':preflight}
        integration.worker_heartbeat(c,result=out,process_id=str(os.getpid())); c.commit()
        return out,0
    except Exception as exc:
        c.rollback()
        try:
            integration.init_schema(c)
            integration.worker_heartbeat(c,result={'status':'ERROR','error':str(exc)[:1000]},process_id=str(os.getpid())); c.commit()
        except Exception:
            pass
        raise
    finally:
        c.close()


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--evidence',action='store_true',help='also aggregate eligible delivery evidence for Power House')
    ap.add_argument('--limit',type=int,default=100)
    ap.add_argument('--strict-preflight',action='store_true')
    ap.add_argument('--worker',action='store_true',help='run a bounded recurring production worker loop')
    ap.add_argument('--interval-seconds',type=int,default=15)
    args=ap.parse_args()
    interval=max(5,int(args.interval_seconds))
    while True:
        try:
            out,code=run_cycle(evidence=args.evidence,limit=args.limit,strict_preflight=args.strict_preflight)
            print(json.dumps(out,indent=2,default=str),flush=True)
            if code:
                raise SystemExit(code)
        except SystemExit:
            raise
        except Exception as exc:
            print(json.dumps({'release':getattr(app,'SCOREMAX_RELEASE_VERSION','6.5.4'),'status':'ERROR','error':str(exc),'traceback':traceback.format_exc(limit=8)},indent=2),flush=True)
            if not args.worker:
                raise
        if not args.worker:
            break
        time.sleep(interval)


if __name__=='__main__':
    main()
