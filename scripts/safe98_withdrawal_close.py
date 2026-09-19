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
ACK_ENDPOINT="/api/integration/v1/scoremax/question-withdrawal-acks"

def _ensure_ack_endpoint():
    original=getattr(integ,"_dispatch_target",None)
    if original is None or not callable(original):
        raise RuntimeError("ACK_DISPATCH_TARGET_MISSING")
    if getattr(integ,"_SAFE98_ACK_TARGET_PATCHED",False):
        url,path,direction=integ._dispatch_target(ACK)
        if path!=ACK_ENDPOINT or direction!="SCOREMAX_TO_POWER_HOUSE":
            raise RuntimeError("ACK_DISPATCH_TARGET_PATCH_DRIFT")
        return
    def patched(contract):
        if contract==ACK:
            base=os.environ.get("SCOREMAX_POWER_HOUSE_BASE_URL","").rstrip("/")
            return (base+ACK_ENDPOINT if base else ""),ACK_ENDPOINT,"SCOREMAX_TO_POWER_HOUSE"
        return original(contract)
    integ._dispatch_target=patched
    integ._SAFE98_ACK_TARGET_PATCHED=True
    url,path,direction=integ._dispatch_target(ACK)
    if path!=ACK_ENDPOINT or direction!="SCOREMAX_TO_POWER_HOUSE":
        raise RuntimeError("ACK_DISPATCH_TARGET_INSTALL_FAILED")
    print("SCOREMAX_SAFE98_ACK_ENDPOINT_READY "+canon({
      "contract":ACK,"endpoint":ACK_ENDPOINT,"direction":direction,
      "existing_dispatcher_extended":True,"base_configured":bool(url)
    }),flush=True)

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),default=str)

def main():
    mode=os.environ.get("SCOREMAX_SAFE98_WITHDRAWAL_CLOSE","OFF").strip().upper()
    if mode not in {"CHECK","FLUSH_ACK"}: raise RuntimeError("MODE_MUST_BE_CHECK_OR_FLUSH_ACK")
    if os.environ.get("SCOREMAX_SAFE98_ACK_DISPATCH_DIAG","OFF").strip().upper()=="RUN":
        import inspect
        dicts=[]
        for name,value in sorted(vars(integ).items()):
            if not isinstance(value,dict): continue
            sample=[]
            for k,v in value.items():
                ks=str(k); vs=str(v)
                if ("POWER_HOUSE" in ks or "POWER_HOUSE" in vs or "SM_PH" in ks or "SM_PH" in vs or "/api/integration/" in vs):
                    sample.append([ks,vs])
            if sample:
                dicts.append({"name":name,"sample":sample[:30],"size":len(value)})
        try: src=inspect.getsource(integ.dispatch_due)
        except Exception as exc: src=f"<unavailable:{type(exc).__name__}>"
        selected=[line for line in src.splitlines() if any(tok in line.lower() for tok in ("endpoint","url","contract","power_house","outbound","destination"))]
        helpers={}
        for hn in ("_dispatch_target","_credentials"):
            hf=getattr(integ,hn,None)
            if hf is None:
                helpers[hn]="<missing>"
            else:
                try: helpers[hn]=inspect.getsource(hf)
                except Exception as exc: helpers[hn]=f"<unavailable:{type(exc).__name__}>"
        print("SCOREMAX_SAFE98_ACK_DISPATCH_DIAG "+canon({
          "dispatch_module":getattr(integ.dispatch_due,"__module__",""),
          "dispatch_names":sorted(set(str(x) for x in getattr(getattr(integ.dispatch_due,"__code__",None),"co_names",()) or ())),
          "selected_source":selected[:120],
          "routing_dicts":dicts,
          "helpers":helpers
        }),flush=True)
    if mode=="FLUSH_ACK":
        _ensure_ack_endpoint()
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
          "item_state":str(target_result[0].get("state") or ""),
          "last_http_status":ackrow.get("last_http_status"),
          "last_error_code":ackrow.get("last_error_code"),
          "last_error_redacted":ackrow.get("last_error_redacted"),
          "next_attempt_at":ackrow.get("next_attempt_at"),
          "delivered_at":ackrow.get("delivered_at"),
          "business_receipt_id":ackrow.get("business_receipt_id"),
          "retry_cycle":ackrow.get("retry_cycle"),
          "cycle_attempt_count":ackrow.get("cycle_attempt_count")
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
                if before["status"] not in {"PENDING","RETRY","DEAD_LETTER"}: raise RuntimeError("ACK_NOT_DISPATCHABLE:"+before["status"])
                force_due=os.environ.get("SCOREMAX_SAFE98_WITHDRAWAL_ACK_FORCE_DUE","OFF").strip().upper()
                expected_message="msg::SM_PH_QUESTION_WITHDRAWAL_ACK_V1::e944e4da37a37a69ce77ddadef67"
                expected_export="PH-SMWD15L1-7E5BF1D67C0B6D677AEA6E15"
                if force_due=="RUN" and before["status"] in {"RETRY","DEAD_LETTER"}:
                    if int(before["outbox_id"])!=6: raise RuntimeError("ACK_FORCE_DUE_WRONG_OUTBOX")
                    if before["message_id"]!=expected_message: raise RuntimeError("ACK_FORCE_DUE_MESSAGE_MISMATCH")
                    if before["export_public_id"]!=expected_export: raise RuntimeError("ACK_FORCE_DUE_EXPORT_MISMATCH")
                    if before["item_state"]!="STAGED_EXCLUDED": raise RuntimeError("ACK_FORCE_DUE_STATE_MISMATCH")
                    expected_attempt=8 if before["status"]=="DEAD_LETTER" else int(before["attempt_count"] or 0)
                    if int(before["attempt_count"] or 0)!=expected_attempt: raise RuntimeError(f"ACK_FORCE_DUE_ATTEMPT_MISMATCH:{before['attempt_count']}")
                    expected_prior_error="HTTP_502" if before["status"]=="DEAD_LETTER" and expected_attempt==8 else "INVALID_OR_MISMATCHED_INTEGRATION_RECEIPT_V1"
                    if str(before.get("last_error_code") or "")!=expected_prior_error:
                        raise RuntimeError("ACK_FORCE_DUE_UNEXPECTED_PRIOR_ERROR:"+str(before.get("last_error_code")))
                    if before["status"]=="DEAD_LETTER":
                        # Governed recovery of the same terminal message: preserve attempt_count,
                        # increment retry_cycle, clear terminal claim state, and make due now.
                        cols={str(r[1]) for r in c.execute("PRAGMA table_info(integration_outbox)").fetchall()}
                        required={"status","retry_cycle","next_attempt_at","claim_token","claim_expires_at","attempt_count","message_id","id"}
                        missing=sorted(required-cols)
                        if missing: raise RuntimeError("ACK_REQUEUE_SCHEMA_MISSING:"+",".join(missing))
                        c.execute("""UPDATE integration_outbox
                                     SET status='RETRY',
                                         retry_cycle=COALESCE(retry_cycle,0)+1,
                                         next_attempt_at=CURRENT_TIMESTAMP,
                                         claim_token='',claim_expires_at=''
                                     WHERE id=? AND status='DEAD_LETTER' AND message_id=?""",
                                  (6,expected_message))
                        event="DEAD_LETTER_REQUEUE_PASS"
                    else:
                        c.execute("""UPDATE integration_outbox
                                     SET next_attempt_at=CURRENT_TIMESTAMP
                                     WHERE id=? AND status='RETRY' AND message_id=?""",
                                  (6,expected_message))
                        event="FORCE_DUE_PASS"
                    c.commit()
                    refreshed=dict(c.execute("SELECT * FROM integration_outbox WHERE id=6").fetchone())
                    if str(refreshed.get("status") or "")!="RETRY" or str(refreshed.get("message_id") or "")!=expected_message:
                        raise RuntimeError("ACK_FORCE_DUE_POSTSTATE_BAD")
                    if int(refreshed.get("attempt_count") or 0)!=int(before["attempt_count"] or 0):
                        raise RuntimeError("ACK_REQUEUE_ATTEMPT_COUNT_CHANGED")
                    print("SCOREMAX_SAFE98_ACK_GOVERNED_FORCE_DUE "+canon({
                      "event":event,"outbox_id":6,"message_id":expected_message,
                      "export_public_id":expected_export,"attempt_count_preserved":int(refreshed.get("attempt_count") or 0),
                      "retry_cycle":int(refreshed.get("retry_cycle") or 0),
                      "status":refreshed.get("status"),"next_attempt_at":refreshed.get("next_attempt_at"),
                      "prior_error_code":before.get("last_error_code")
                    }),flush=True)
                due_total=int(c.execute("""SELECT COUNT(*) FROM integration_outbox
                  WHERE status IN ('PENDING','RETRY')
                    AND (next_attempt_at IS NULL OR next_attempt_at<=CURRENT_TIMESTAMP)""").fetchone()[0])
                if due_total!=1: raise RuntimeError(f"UNRELATED_DUE_OUTBOX_PRESENT:{due_total}")
                dispatch=integ.dispatch_due(c,limit=1,timeout=15)
                post=dict(c.execute("SELECT * FROM integration_outbox WHERE id=?",(int(ackrow["id"]),)).fetchone())
                if str(post.get("status") or "")!="DELIVERED": raise RuntimeError("ACK_NOT_DELIVERED:"+canon({"dispatch":dispatch,"post":post}))
                result.update({"event":"FLUSH_ACK_PASS","dispatch":dispatch,"ack_post_status":"DELIVERED",
                               "ack_post_attempt_count":int(post.get("attempt_count") or 0)})
            qc2=c.execute("PRAGMA quick_check").fetchone()[0]; fk2=len(c.execute("PRAGMA foreign_key_check").fetchall())
            if qc2!="ok" or fk2: raise RuntimeError("POST_DISPATCH_DB_INTEGRITY_BAD")
            result.update({"quick_check":qc2,"fk":fk2})
        print("SCOREMAX_SAFE98_WITHDRAWAL_CLOSE "+canon(result),flush=True)
        return 0
    finally:c.close()

if __name__=="__main__": raise SystemExit(main())
