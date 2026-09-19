#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,sqlite3,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"scoremax_runtime_v669b"
sys.path.insert(0,str(RUNTIME))
import scoremax_integration_v1 as integ

RELEASE_ID="REL::PILOT::BIO12-CH13::SAFE98::20260919"
RELEASE_VERSION="1"
PACKAGE_SHA="60e4c8a25afaa4ed3c88bf3c796f47983c17533a458bfebbbfd223faac9dd2bf"
QUESTION_ID="PH-RS-Q-1E94CCFE2E15F0E679D9FC"
QUESTION_VERSION_ID="QV::PH-RS-Q-1E94CCFE2E15F0E679D9FC::v1"
QUESTION_SHA="088f2a384f6a9ec13d300f8a10a31c382407ef08ce40a1b372fb91a540decbb0"
FEEDBACK_CODE="SAFE98-RETURN-PROBE-20260919"
INCIDENT_ID="SMINC::SAFE98-RETURN-PROBE::"+hashlib.sha256(
    (RELEASE_ID+"|"+RELEASE_VERSION+"|"+QUESTION_VERSION_ID).encode()
).hexdigest()[:24]

def canonical(v):
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def main():
    db_path=Path(os.environ["SCOREMAX_DB"]).resolve()
    c=sqlite3.connect(db_path,timeout=30); c.row_factory=sqlite3.Row
    try:
        rel=c.execute("""SELECT * FROM integration_ph_content_releases
          WHERE release_id=? AND release_version=?""",(RELEASE_ID,RELEASE_VERSION)).fetchone()
        if not rel: raise RuntimeError("SAFE98_RELEASE_NOT_FOUND")
        if str(rel["local_status"] or "").upper()!="STAGED": raise RuntimeError("SAFE98_RELEASE_NOT_STAGED")
        if str(rel["package_checksum_sha256"] or "").lower()!=PACKAGE_SHA: raise RuntimeError("SAFE98_PACKAGE_SHA_MISMATCH")
        if int(rel["question_count"] or 0)!=98: raise RuntimeError("SAFE98_QUESTION_COUNT_MISMATCH")
        auth=c.execute("""SELECT COUNT(*) n FROM integration_ph_product_activation_authorizations
          WHERE release_id=? AND release_version=?""",(RELEASE_ID,RELEASE_VERSION)).fetchone()["n"]
        if int(auth)!=0: raise RuntimeError("SAFE98_ACTIVATION_AUTHORIZATION_PRESENT")
        q=c.execute("""SELECT v.* FROM integration_ph_question_version_store v
          JOIN integration_ph_release_question_membership m
            ON m.question_id=v.question_id AND m.question_version_id=v.question_version_id
          WHERE m.release_id=? AND m.release_version=? AND v.question_id=? AND v.question_version_id=?""",
          (RELEASE_ID,RELEASE_VERSION,QUESTION_ID,QUESTION_VERSION_ID)).fetchone()
        if not q: raise RuntimeError("SAFE98_PROBE_QUESTION_NOT_FOUND")
        if str(q["question_checksum_sha256"] or "").lower()!=QUESTION_SHA: raise RuntimeError("SAFE98_QUESTION_SHA_MISMATCH")
        projection=json.loads(q["scoremax_projection_json"] or "{}")
        rendered=str(projection.get("question") or "").strip()
        if not rendered: raise RuntimeError("SAFE98_RENDERED_QUESTION_MISSING")
        rendered_sha=hashlib.sha256(rendered.encode()).hexdigest()
        question={
          "question_id":QUESTION_ID,
          "question_version_id":QUESTION_VERSION_ID,
          "question_checksum_sha256":QUESTION_SHA,
          "release_id":RELEASE_ID,
          "release_version":RELEASE_VERSION,
          "release_checksum_sha256":PACKAGE_SHA,
          "market_id":str(rel["market_id"] or ""),
          "programme_id":str(rel["programme_id"] or ""),
          "subject_id":str(rel["subject_id"] or ""),
          "chapter_id":str(rel["chapter_id"] or ""),
          "rendered_question_sha256":rendered_sha,
        }
        payload={
          "incident_id":INCIDENT_ID,
          "scoremax_feedback_code":FEEDBACK_CODE,
          "category":"LEARNER_CONTENT_INTEGRITY",
          "severity":"HIGH",
          "description":"Governed SAFE98 staged return-loop qualification. Hold exact Power House question and require requalification before any learner release.",
          "source":"SAFE98_STAGED_RETURN_PROBE",
          "page_path":"/qualification/safe98-return-probe",
          "question":question,
          "reporter_identity_included":False,
          "student_pii_included":False,
          "release_authority_conferred":False,
        }
        idem="safe98-return-probe::"+QUESTION_VERSION_ID
        env=integ._envelope(
          "SM_PH_CONTENT_INCIDENT_V1","POWER_HOUSE",idem,FEEDBACK_CODE,payload,
          "SCOREMAX-SAFE98-RETURN-PROBE-20260919","INTERNAL"
        )
        msg=integ._queue(c,env,FEEDBACK_CODE,"SAFE98_STAGED_RETURN_PROBE",QUESTION_VERSION_ID)
        c.commit()
        before=c.execute("""SELECT status,attempt_count,receipt_json FROM integration_outbox
          WHERE contract_name='SM_PH_CONTENT_INCIDENT_V1' AND idempotency_key=?""",(idem,)).fetchone()
        dispatch=integ.dispatch_due(c,limit=20,timeout=15)
        row=c.execute("""SELECT status,attempt_count,receipt_json,last_error_code FROM integration_outbox
          WHERE contract_name='SM_PH_CONTENT_INCIDENT_V1' AND idempotency_key=?""",(idem,)).fetchone()
        if not row: raise RuntimeError("SAFE98_RETURN_OUTBOX_MISSING")
        receipt=json.loads(row["receipt_json"] or "{}") if row["receipt_json"] else {}
        result={
          "incident_id":INCIDENT_ID,
          "message_id":msg,
          "question_id":QUESTION_ID,
          "question_version_id":QUESTION_VERSION_ID,
          "release_id":RELEASE_ID,
          "release_version":RELEASE_VERSION,
          "release_still_staged":True,
          "activation_authorizations":0,
          "outbox_before":str(before["status"] if before else ""),
          "outbox_after":str(row["status"] or ""),
          "attempt_count":int(row["attempt_count"] or 0),
          "dispatch":dispatch,
          "receipt_status":str(receipt.get("status") or ""),
          "receipt_id":str(receipt.get("receipt_id") or ""),
          "receipt_contract":str(receipt.get("contract_name") or ""),
          "last_error_code":str(row["last_error_code"] or ""),
          "learner_activation":False,
        }
        print("SCOREMAX_SAFE98_RETURN_PROBE_RESULT "+canonical(result),flush=True)
        if str(row["status"] or "")!="DELIVERED": raise RuntimeError("SAFE98_RETURN_NOT_DELIVERED")
        if str(receipt.get("status") or "") not in {"ACCEPTED","DUPLICATE"}: raise RuntimeError("SAFE98_RETURN_RECEIPT_NOT_ACCEPTED")
        if str(receipt.get("contract_name") or "")!="SM_PH_CONTENT_INCIDENT_V1": raise RuntimeError("SAFE98_RETURN_RECEIPT_CONTRACT_MISMATCH")
        print("SCOREMAX_SAFE98_RETURN_PROBE_PASS exact_native_lineage=true staged_only=true incident_delivered=true learner_activation=false",flush=True)
    finally:
        c.close()

if __name__=="__main__":
    raise SystemExit(main())
