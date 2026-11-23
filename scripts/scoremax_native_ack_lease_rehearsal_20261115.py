"""Actual ScoreMax integration outbox lease concurrency and recovery test.

Runs the accepted integration._claim_due with simultaneous independent SQLite
connections on a disposable file. No network, real ACK receipt, PH signature,
credentials, user data or production database. A claimed row is NOT a sent ACK.
"""
from __future__ import annotations
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import sqlite3
import sys
import tempfile
import threading
from pathlib import Path
from time import perf_counter

def main(root):
    root=Path(root).resolve()
    if root.name!="scoremax_runtime_v669b" or not (root/"scoremax_integration_v1.py").is_file():
        raise RuntimeError("ACCEPTED_INTEGRATION_RUNTIME_REQUIRED")
    sys.path.insert(0,str(root))
    import scoremax_integration_v1 as integration
    contracts=("SM_PH_CONTENT_DELIVERY_ACK_V1",
               "SM_PH_QUESTION_WITHDRAWAL_ACK_V1",
               "SM_GE_PRODUCT_EVENT_V1")
    with tempfile.TemporaryDirectory(prefix="scoremax-ack-lease-") as td:
        path=Path(td)/"outbox.sqlite"
        def connect():
            c=sqlite3.connect(path,timeout=12,isolation_level=None)
            c.row_factory=sqlite3.Row
            c.execute("PRAGMA busy_timeout=12000")
            return c
        with closing(connect()) as c:
            c.executescript("""CREATE TABLE integration_outbox(
              id INTEGER PRIMARY KEY,
              contract_name TEXT NOT NULL,
              status TEXT NOT NULL,
              next_attempt_at TEXT,
              created_at TEXT,
              claim_token TEXT,
              claim_expires_at TEXT);
            """)
            c.executemany("""INSERT INTO integration_outbox
              (id,contract_name,status,next_attempt_at,created_at,claim_token,claim_expires_at)
              VALUES(?,?,'PENDING','','2026-11-15T00:00:00Z','','')""",
              [(i,contracts[(i-1)%len(contracts)]) for i in range(1,61)])
            c.commit()
        gate=threading.Barrier(12)
        def claim(worker):
            with closing(connect()) as c:
                gate.wait(timeout=25)
                got=integration._claim_due(c,limit=5,lease_seconds=40)
                return [(row["id"],row["claim_token"]) for row in got]
        with ThreadPoolExecutor(max_workers=12) as executor:
            groups=list(executor.map(claim,range(12)))
        seen=[qid for group in groups for qid,_ in group]
        counts=Counter(seen)
        if len(seen)!=60 or len(counts)!=60 or max(counts.values())!=1:
            raise RuntimeError("ACK_DOUBLE_CLAIM_OR_MISSING:"+str((len(seen),len(counts))))
        if any(not token.startswith("CLAIM::") for group in groups for _,token in group):
            raise RuntimeError("OUTBOX_CLAIM_TOKEN_NOT_RECORDED")
        with closing(connect()) as c:
            if c.execute("SELECT COUNT(*) FROM integration_outbox WHERE status='IN_FLIGHT'").fetchone()[0]!=60:
                raise RuntimeError("CLAIMED_LEASE_NOT_COMMITTED")
            if integration._claim_due(c,limit=10)!=[]:
                raise RuntimeError("IN_FLIGHT_LEASE_PREMATURE_REDELIVERY")
            # Reclaim only one explicitly expired lease; terminal states never replay.
            c.execute("""UPDATE integration_outbox SET claim_expires_at='2020-01-01T00:00:00Z'
              WHERE id=1""")
            c.execute("""UPDATE integration_outbox SET status='DELIVERED'
              WHERE id=2""")
            c.commit()
        with closing(connect()) as c:
            reissued=integration._claim_due(c,limit=10)
            if [r["id"] for r in reissued]!=[1]:
                raise RuntimeError("EXPIRED_LEASE_RECLAIM_DRIFT:"+repr([x["id"] for x in reissued]))
            c.execute("""UPDATE integration_outbox SET status='DELIVERED',
              claim_token='',claim_expires_at='' WHERE id=1""")
            c.commit()
            if integration._claim_due(c,limit=10):
                raise RuntimeError("COMPLETED_ROW_RECLAIMED")
            if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("OUTBOX_INTEGRITY_FAILURE")
            states=dict(c.execute("SELECT status,COUNT(*) FROM integration_outbox GROUP BY status"))
        print("SCOREMAX_NATIVE_ACK_LEASE_CONCURRENCY_PASS="+json.dumps({
            "simultaneous_claim_workers":12,
            "queued_events":60,
            "unique_first_claims":len(counts),
            "overlapping_claims":0,
            "expired_lease_reclaimed_once":True,
            "terminal_delivery_not_reclaimed":True,
            "final_state_census":states,
            "actual_signed_peer_receipt_tested":False,
            "real_ack_dispatched":False,
            "actual_multi_instance_postgres_claim_qualified":False,
            "production_touched":False
        },sort_keys=True),flush=True)
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("USAGE: script <runtime>")
    main(sys.argv[1])
