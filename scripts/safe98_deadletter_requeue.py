#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,sqlite3,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"scoremax_runtime_v669b"
sys.path.insert(0,str(RUNTIME))
import scoremax_integration_v1 as integ

MESSAGE_ID="msg::SM_PH_CONTENT_INCIDENT_V1::2213befab989befa85221119d55d"
INCIDENT_ID="SMINC::SAFE98-RETURN-PROBE::49505a32ebb5805864c533aa"
IDEM="safe98-return-probe::QV::PH-RS-Q-1E94CCFE2E15F0E679D9FC::v1"
ENVELOPE_SHA="0882c65f1b6849b875f7b51a7e83a56e730a4730f711bd3491ce86e357d5b4fa"
RELEASE_ID="REL::PILOT::BIO12-CH13::SAFE98::20260919"
RELEASE_VERSION="1"
QUESTION_ID="PH-RS-Q-1E94CCFE2E15F0E679D9FC"
QUESTION_VERSION_ID="QV::PH-RS-Q-1E94CCFE2E15F0E679D9FC::v1"
QUESTION_SHA="088f2a384f6a9ec13d300f8a10a31c382407ef08ce40a1b372fb91a540decbb0"

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)
def h(s): return hashlib.sha256(str(s).encode()).hexdigest()

def backup_db(c, db_path:Path, target:Path):
    target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_suffix(".tmp"); tmp.unlink(missing_ok=True)
    d=sqlite3.connect(tmp)
    try: c.backup(d); d.commit()
    finally: d.close()
    os.replace(tmp,target)
    raw=target.read_bytes()
    cc=sqlite3.connect(target)
    try:
        qc=cc.execute("PRAGMA quick_check").fetchone()[0]
        fk=len(cc.execute("PRAGMA foreign_key_check").fetchall())
    finally: cc.close()
    if qc!="ok" or fk: raise RuntimeError("ROLLBACK_BACKUP_INVALID")
    return hashlib.sha256(raw).hexdigest(),len(raw)

def main():
    db_path=Path(os.environ["SCOREMAX_DB"]).resolve()
    backup_dir=Path(os.environ.get("SCOREMAX_BACKUP_DIR",str(db_path.parent))).resolve()
    rollback=backup_dir/"safe98_return_requeue_preapply_20260919.sqlite3"
    c=sqlite3.connect(db_path,timeout=30); c.row_factory=sqlite3.Row
    try:
        row=c.execute("SELECT * FROM integration_outbox WHERE message_id=?",(MESSAGE_ID,)).fetchone()
        if not row: raise RuntimeError("TARGET_MESSAGE_MISSING")
        d=dict(row); outbox_id=int(d["id"])
        env=str(d.get("envelope_json") or "")
        if h(env)!=ENVELOPE_SHA: raise RuntimeError("ENVELOPE_SHA_MISMATCH")
        if str(d.get("idempotency_key") or "")!=IDEM: raise RuntimeError("IDEMPOTENCY_MISMATCH")
        rel=c.execute("SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",(RELEASE_ID,RELEASE_VERSION)).fetchone()
        if not rel or str(rel["local_status"] or "").upper()!="STAGED": raise RuntimeError("SAFE98_RELEASE_NOT_STAGED")
        if int(rel["question_count"] or 0)!=98: raise RuntimeError("SAFE98_COUNT_NOT_98")
        auth=c.execute("SELECT COUNT(*) FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?",(RELEASE_ID,RELEASE_VERSION)).fetchone()[0]
        if int(auth)!=0: raise RuntimeError("ACTIVATION_AUTH_PRESENT")
        q=c.execute("""SELECT v.* FROM integration_ph_question_version_store v
          JOIN integration_ph_release_question_membership m
          ON m.question_id=v.question_id AND m.question_version_id=v.question_version_id
          WHERE m.release_id=? AND m.release_version=? AND v.question_id=? AND v.question_version_id=?""",
          (RELEASE_ID,RELEASE_VERSION,QUESTION_ID,QUESTION_VERSION_ID)).fetchone()
        if not q or str(q["question_checksum_sha256"] or "").lower()!=QUESTION_SHA: raise RuntimeError("PROBE_QUESTION_IDENTITY_MISMATCH")

        # Idempotent post-pass observation path.
        if str(d.get("status") or "")=="DELIVERED":
            receipt=json.loads(d.get("receipt_json") or "{}") if d.get("receipt_json") else {}
            print("SCOREMAX_SAFE98_DEADLETTER_REQUEUE_ALREADY_PASS "+canon({
              "message_id":MESSAGE_ID,"incident_id":INCIDENT_ID,"status":"DELIVERED",
              "receipt_status":receipt.get("status"),"receipt_id":receipt.get("receipt_id"),
              "retry_cycle":d.get("retry_cycle"),"attempt_count":d.get("attempt_count"),
              "envelope_sha256":h(env),"release_still_staged":True,"activation_authorizations":0,
              "quick_check":c.execute("PRAGMA quick_check").fetchone()[0],
              "fk":len(c.execute("PRAGMA foreign_key_check").fetchall())
            }),flush=True)
            return 0

        if str(d.get("status") or "")!="DEAD_LETTER": raise RuntimeError("TARGET_NOT_DEAD_LETTER")
        if int(d.get("attempt_count") or 0)!=1: raise RuntimeError("UNEXPECTED_PRIOR_ATTEMPT_COUNT")
        if int(d.get("retry_cycle") or 0)!=0: raise RuntimeError("UNEXPECTED_PRIOR_RETRY_CYCLE")
        attempts_before=int(c.execute("SELECT COUNT(*) FROM integration_dispatch_attempts WHERE outbox_id=?",(outbox_id,)).fetchone()[0])
        audit_before=int(c.execute("SELECT COUNT(*) FROM integration_requeue_audit WHERE outbox_id=?",(outbox_id,)).fetchone()[0])
        if attempts_before!=1 or audit_before!=0: raise RuntimeError("PRIOR_HISTORY_UNEXPECTED")

        rollback_sha,rollback_bytes=backup_db(c,db_path,rollback)

        ok=integ.requeue_outbox(c,outbox_id,actor="SAFE98_GOVERNED_RECOVERY",
              reason="Peer-side exact delivered-lineage resolver repaired and qualified 98/98; replay same immutable incident.")
        if not ok: raise RuntimeError("REQUEUE_PRIMITIVE_REFUSED")
        rq=c.execute("SELECT * FROM integration_outbox WHERE id=?",(outbox_id,)).fetchone(); rqd=dict(rq)
        if str(rqd.get("status") or "")!="PENDING": raise RuntimeError("REQUEUE_NOT_PENDING")
        if int(rqd.get("attempt_count") or 0)!=0 or int(rqd.get("retry_cycle") or 0)!=1: raise RuntimeError("REQUEUE_CYCLE_STATE_BAD")
        if str(rqd.get("message_id") or "")!=MESSAGE_ID or str(rqd.get("idempotency_key") or "")!=IDEM: raise RuntimeError("IDENTITY_CHANGED_ON_REQUEUE")
        if h(rqd.get("envelope_json") or "")!=ENVELOPE_SHA: raise RuntimeError("ENVELOPE_CHANGED_ON_REQUEUE")
        audit_mid=int(c.execute("SELECT COUNT(*) FROM integration_requeue_audit WHERE outbox_id=?",(outbox_id,)).fetchone()[0])
        if audit_mid!=1: raise RuntimeError("REQUEUE_AUDIT_MISSING")

        dispatch=integ.dispatch_due(c,limit=20,timeout=15)
        fin=c.execute("SELECT * FROM integration_outbox WHERE id=?",(outbox_id,)).fetchone(); fd=dict(fin)
        receipt=json.loads(fd.get("receipt_json") or "{}") if fd.get("receipt_json") else {}
        attempts_after=int(c.execute("SELECT COUNT(*) FROM integration_dispatch_attempts WHERE outbox_id=?",(outbox_id,)).fetchone()[0])
        audit_after=int(c.execute("SELECT COUNT(*) FROM integration_requeue_audit WHERE outbox_id=?",(outbox_id,)).fetchone()[0])
        qc=c.execute("PRAGMA quick_check").fetchone()[0]; fk=len(c.execute("PRAGMA foreign_key_check").fetchall())
        result={
          "message_id":MESSAGE_ID,"incident_id":INCIDENT_ID,"outbox_id":outbox_id,
          "status":str(fd.get("status") or ""),"retry_cycle":int(fd.get("retry_cycle") or 0),
          "attempt_count":int(fd.get("attempt_count") or 0),"attempt_history_before":attempts_before,
          "attempt_history_after":attempts_after,"requeue_audit_before":audit_before,
          "requeue_audit_after":audit_after,"envelope_sha256":h(fd.get("envelope_json") or ""),
          "idempotency_key":str(fd.get("idempotency_key") or ""),"dispatch":dispatch,
          "receipt_status":str(receipt.get("status") or ""),"receipt_id":str(receipt.get("receipt_id") or ""),
          "receipt_contract":str(receipt.get("contract_name") or ""),"last_error_code":str(fd.get("last_error_code") or ""),
          "rollback_path":str(rollback),"rollback_sha256":rollback_sha,"rollback_bytes":rollback_bytes,
          "release_still_staged":True,"activation_authorizations":0,"quick_check":qc,"fk":fk
        }
        print("SCOREMAX_SAFE98_DEADLETTER_REQUEUE_RESULT "+canon(result),flush=True)
        if result["status"]!="DELIVERED": raise RuntimeError("REQUEUE_NOT_DELIVERED")
        if result["receipt_status"] not in {"ACCEPTED","DUPLICATE"}: raise RuntimeError("PH_RECEIPT_NOT_ACCEPTED")
        if result["receipt_contract"]!="SM_PH_CONTENT_INCIDENT_V1": raise RuntimeError("PH_RECEIPT_CONTRACT_BAD")
        if result["retry_cycle"]!=1 or attempts_after!=2 or audit_after!=1: raise RuntimeError("RECOVERY_HISTORY_BAD")
        if result["envelope_sha256"]!=ENVELOPE_SHA or result["idempotency_key"]!=IDEM: raise RuntimeError("IMMUTABLE_IDENTITY_CHANGED")
        if qc!="ok" or fk: raise RuntimeError("DB_INTEGRITY_BAD")
        print("SCOREMAX_SAFE98_DEADLETTER_REQUEUE_PASS same_message=true same_incident=true same_payload=true retry_cycle=1 prior_attempt_preserved=true learner_activation=false",flush=True)
        return 0
    finally:
        c.close()

if __name__=="__main__": raise SystemExit(main())
