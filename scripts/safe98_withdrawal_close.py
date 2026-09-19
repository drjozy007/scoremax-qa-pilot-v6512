#!/usr/bin/env python3
from __future__ import annotations
import json,os,sqlite3,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"scoremax_runtime_v669b"
sys.path.insert(0,str(RUNTIME))
import scoremax_integration_v1 as integ

DB=Path(os.environ["SCOREMAX_DB"]).resolve()
RELEASE_ID="REL::PILOT::BIO12-CH13::SAFE98::20260919"
RELEASE_VERSION="1"
TARGET="PH-RS-Q-1E94CCFE2E15F0E679D9FC"
TARGET_VERSION="QV::PH-RS-Q-1E94CCFE2E15F0E679D9FC::v1"
ACK="SM_PH_QUESTION_WITHDRAWAL_ACK_V1"

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),default=str)

def main():
    mode=os.environ.get("SCOREMAX_SAFE98_WITHDRAWAL_CLOSE","OFF").strip().upper()
    if mode not in {"CHECK","FLUSH_ACK"}: raise RuntimeError("MODE_MUST_BE_CHECK_OR_FLUSH_ACK")
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
    try:
        member=int(c.execute("""SELECT COUNT(*) FROM integration_ph_release_question_membership
          WHERE release_id=? AND release_version=?""",(RELEASE_ID,RELEASE_VERSION)).fetchone()[0])
        target_member=int(c.execute("""SELECT COUNT(*) FROM integration_ph_release_question_membership
          WHERE release_id=? AND release_version=? AND question_id=? AND question_version_id=?""",
          (RELEASE_ID,RELEASE_VERSION,TARGET,TARGET_VERSION)).fetchone()[0])
        excl=c.execute("""SELECT * FROM ph_bridge_staged_withdrawal_exclusions_v6611e
          WHERE release_id=? AND release_version=? AND question_id=? AND question_version_id=?""",
          (RELEASE_ID,RELEASE_VERSION,TARGET,TARGET_VERSION)).fetchall()
        all_excl=c.execute("""SELECT * FROM ph_bridge_staged_withdrawal_exclusions_v6611e
          WHERE release_id=? AND release_version=? ORDER BY id""",(RELEASE_ID,RELEASE_VERSION)).fetchall()
        activation=int(c.execute("""SELECT COUNT(*) FROM integration_ph_product_activation_authorizations
          WHERE release_id=? AND release_version=?""",(RELEASE_ID,RELEASE_VERSION)).fetchone()[0])
        target_rows=int(c.execute("""SELECT COUNT(*) FROM questions
          WHERE ph_projection_owner='POWER_HOUSE' AND ph_question_id=?""",(TARGET,)).fetchone()[0])
        learner_active=int(c.execute("""SELECT COUNT(*) FROM questions
          WHERE ph_projection_owner='POWER_HOUSE' AND ph_release_id=? AND ph_release_version=? AND COALESCE(active,0)=1""",
          (RELEASE_ID,RELEASE_VERSION)).fetchone()[0])
        eligible=int(c.execute("""SELECT COUNT(*) FROM integration_ph_release_question_membership m
          WHERE m.release_id=? AND m.release_version=?
            AND NOT EXISTS (
              SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e
              WHERE e.release_id=m.release_id AND e.release_version=m.release_version
                AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id
            )""",(RELEASE_ID,RELEASE_VERSION)).fetchone()[0])
        rel=dict(c.execute("SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",(RELEASE_ID,RELEASE_VERSION)).fetchone())
        acks=c.execute("""SELECT * FROM integration_outbox WHERE contract_name=? ORDER BY id DESC""",(ACK,)).fetchall()
        target_acks=[]
        current_acks=[]
        current_export=str(dict(excl[0]).get("export_public_id") or "") if len(excl)==1 else ""
        if not current_export: raise RuntimeError("CURRENT_EXCLUSION_EXPORT_ID_MISSING")
        for r in acks:
            d=dict(r)
            try: env=json.loads(d.get("envelope_json") or "{}")
            except Exception: env={}
            payload=dict(env.get("payload") or {})
            items=list(payload.get("items") or [])
            if any(str(x.get("question_public_id") or "")==TARGET for x in items):
                target_acks.append((d,env))
                if str(payload.get("export_public_id") or "")==current_export:
                    current_acks.append((d,env))
        qc=c.execute("PRAGMA quick_check").fetchone()[0]; fk=len(c.execute("PRAGMA foreign_key_check").fetchall())
        if member!=98 or target_member!=1: raise RuntimeError(f"MEMBERSHIP_BAD:{member}:{target_member}")
        if len(all_excl)!=1 or len(excl)!=1: raise RuntimeError(f"EXCLUSION_COUNT_BAD:{len(all_excl)}:{len(excl)}")
        if eligible!=97: raise RuntimeError(f"ELIGIBLE_NOT_97:{eligible}")
        if activation!=0 or target_rows!=0 or learner_active!=0: raise RuntimeError(f"ZERO_ACTIVATION_BROKEN:{activation}:{target_rows}:{learner_active}")
        if str(rel.get("local_status") or "")!="STAGED": raise RuntimeError("RELEASE_NOT_STAGED")
        if qc!="ok" or fk: raise RuntimeError("DB_INTEGRITY_BAD")
        if len(current_acks)!=1: raise RuntimeError(f"CURRENT_ACK_COUNT_BAD:{len(current_acks)}:historical_target_acks={len(target_acks)}")
        ackrow,ackenv=current_acks[0]
        ackitems=list(((ackenv.get("payload") or {}).get("items") or []))
        target_result=[x for x in ackitems if str(x.get("question_public_id") or "")==TARGET]
        if len(target_result)!=1 or str(target_result[0].get("state") or "") not in {"STAGED_EXCLUDED","WITHDRAWN_AND_STAGED_EXCLUDED"}:
            raise RuntimeError("ACK_RESULT_NOT_STAGED_EXCLUDED")
        before={
          "outbox_id":int(ackrow["id"]),"status":str(ackrow.get("status") or ""),
          "attempt_count":int(ackrow.get("attempt_count") or 0),
          "message_id":str(ackrow.get("message_id") or ""),
          "export_public_id":str((ackenv.get("payload") or {}).get("export_public_id") or ""),
          "item_state":str(target_result[0].get("state") or "")
        }
        result={"event":"CHECK_PASS","mode":mode,"membership":98,"target_membership":1,"staged_exclusions":1,
                "activation_eligible":97,"activation_authorizations":0,"target_materialised_rows":0,
                "learner_active_rows":0,"local_status":"STAGED","ack":before,
                "historical_target_ack_count":len(target_acks),"current_export_public_id":current_export,
                "current_ack_count":len(current_acks),"quick_check":qc,"fk":fk}
        if mode=="FLUSH_ACK":
            if before["status"]=="DELIVERED":
                result["event"]="ALREADY_DELIVERED"
            else:
                if before["status"] not in {"PENDING","RETRYING"}: raise RuntimeError("ACK_NOT_DISPATCHABLE:"+before["status"])
                due_total=int(c.execute("""SELECT COUNT(*) FROM integration_outbox
                  WHERE status IN ('PENDING','RETRYING')""").fetchone()[0])
                if due_total!=1: raise RuntimeError(f"UNRELATED_DUE_OUTBOX_PRESENT:{due_total}")
                dispatch=integ.dispatch_due(c,limit=5,timeout=15)
                post=dict(c.execute("SELECT * FROM integration_outbox WHERE id=?",(int(ackrow["id"]),)).fetchone())
                if str(post.get("status") or "")!="DELIVERED": raise RuntimeError("ACK_NOT_DELIVERED:"+canon(dispatch))
                result.update({"event":"FLUSH_ACK_PASS","dispatch":dispatch,"ack_post_status":"DELIVERED",
                               "ack_post_attempt_count":int(post.get("attempt_count") or 0)})
            qc2=c.execute("PRAGMA quick_check").fetchone()[0]; fk2=len(c.execute("PRAGMA foreign_key_check").fetchall())
            if qc2!="ok" or fk2: raise RuntimeError("POST_DISPATCH_DB_INTEGRITY_BAD")
            result.update({"quick_check":qc2,"fk":fk2})
        print("SCOREMAX_SAFE98_WITHDRAWAL_CLOSE "+canon(result),flush=True)
        return 0
    finally:c.close()

if __name__=="__main__": raise SystemExit(main())
