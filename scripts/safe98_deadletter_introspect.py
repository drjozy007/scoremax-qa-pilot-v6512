#!/usr/bin/env python3
from __future__ import annotations
import hashlib, inspect, json, os, sqlite3, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"scoremax_runtime_v669b"
sys.path.insert(0,str(RUNTIME))
import scoremax_integration_v1 as integ

MESSAGE_ID="msg::SM_PH_CONTENT_INCIDENT_V1::2213befab989befa85221119d55d"
INCIDENT_ID="SMINC::SAFE98-RETURN-PROBE::49505a32ebb5805864c533aa"

def canon(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)

def main():
    db=Path(os.environ["SCOREMAX_DB"]).resolve()
    c=sqlite3.connect(db,timeout=30); c.row_factory=sqlite3.Row
    try:
        row=c.execute("SELECT * FROM integration_outbox WHERE message_id=?",(MESSAGE_ID,)).fetchone()
        if not row: raise RuntimeError("SAFE98_TARGET_MESSAGE_NOT_FOUND")
        d=dict(row)
        env=str(d.get("envelope_json") or "")
        payload_sha=hashlib.sha256(env.encode()).hexdigest()
        fn=getattr(integ,"requeue_outbox",None)
        if fn is None: raise RuntimeError("REQUEUE_OUTBOX_PRIMITIVE_MISSING")
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%outbox%' OR name LIKE '%attempt%' OR name LIKE '%retry%' OR name LIKE '%incident%' OR name LIKE '%audit%') ORDER BY name").fetchall()]
        related={}
        outbox_id=d.get("id")
        for t in tables:
            cols=[r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
            keys=[k for k in ("outbox_id","message_id","incident_id","idempotency_key") if k in cols]
            if not keys: continue
            clauses=[]; args=[]
            for k in keys:
                if k=="outbox_id" and outbox_id is not None: clauses.append("outbox_id=?"); args.append(outbox_id)
                elif k=="message_id": clauses.append("message_id=?"); args.append(MESSAGE_ID)
                elif k=="incident_id": clauses.append("incident_id=?"); args.append(INCIDENT_ID)
                elif k=="idempotency_key": clauses.append("idempotency_key=?"); args.append(str(d.get("idempotency_key") or ""))
            if clauses:
                try:
                    n=c.execute(f"SELECT COUNT(*) FROM {t} WHERE "+" OR ".join(clauses),args).fetchone()[0]
                    related[t]={"count":int(n),"match_columns":keys}
                except Exception as exc:
                    related[t]={"error":type(exc).__name__,"match_columns":keys}
        result={
            "marker":"SCOREMAX_SAFE98_DEADLETTER_INTROSPECT_V1",
            "message_id":MESSAGE_ID,
            "incident_id":INCIDENT_ID,
            "status":str(d.get("status") or ""),
            "attempt_count":int(d.get("attempt_count") or 0),
            "retry_cycle":int(d.get("retry_cycle") or 0) if "retry_cycle" in d else None,
            "cycle_attempt_count":int(d.get("cycle_attempt_count") or 0) if "cycle_attempt_count" in d else None,
            "last_error_code":str(d.get("last_error_code") or ""),
            "idempotency_key":str(d.get("idempotency_key") or ""),
            "envelope_sha256":payload_sha,
            "requeue_signature":str(inspect.signature(fn)),
            "requeue_source":inspect.getsource(fn),
            "related_tables":related,
            "quick_check":c.execute("PRAGMA quick_check").fetchone()[0],
            "fk":len(c.execute("PRAGMA foreign_key_check").fetchall()),
            "mutated":False,
        }
        print("SCOREMAX_SAFE98_DEADLETTER_INTROSPECT "+canon(result),flush=True)
    finally:
        c.close()

if __name__=="__main__":
    raise SystemExit(main())
