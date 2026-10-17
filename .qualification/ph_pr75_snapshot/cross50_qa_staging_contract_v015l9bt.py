from __future__ import annotations
import copy, hashlib, json, os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION="1.3.0"
POLICY="PH-CROSS50-QA-STAGING-V015L9BT-1"
APP=Path(os.environ.get("PH_APP_DIR","/opt/powerhouse/app")).resolve()

def _canon(v:Any)->str:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)

def _sha(v:Any)->str:
    raw=v if isinstance(v,(bytes,bytearray)) else _canon(v).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _iso_now()->str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00","Z")

def build_schema_v13(app:Path=APP)->Path:
    out=app/"integration_contracts_v1_3"
    path=out/"PH_SM_APPROVED_CONTENT_V1.schema.json"
    # Runtime containers execute as the unprivileged powerhouse user. The schema is
    # generated and sealed at image-build time; runtime validation must consume it
    # read-only rather than attempting to rewrite application bytes.
    if path.is_file():
        existing=json.loads(path.read_text(encoding="utf-8"))
        if str(((existing.get("properties") or {}).get("schema_version") or {}).get("const") or "")!="1.3.0":
            raise RuntimeError("PH_QA13_EXISTING_SCHEMA_VERSION_INVALID")
        arch=(((existing.get("$defs") or {}).get("question") or {}).get("properties") or {}).get("architecture") or {}
        if "mastery_status" not in (arch.get("properties") or {}):
            raise RuntimeError("PH_QA13_EXISTING_SCHEMA_MASTERY_FENCE_MISSING")
        return path
    src=app/"integration_contracts_v1_2"/"PH_SM_APPROVED_CONTENT_V1.schema.json"
    if not src.is_file():
        raise RuntimeError("PH_QA13_PARENT_SCHEMA_MISSING")
    schema=json.loads(src.read_text(encoding="utf-8"))
    schema["$id"]="https://contracts.scoremax.internal/v1.3/PH_SM_APPROVED_CONTENT_V1.schema.json"
    schema["title"]="Power House to ScoreMax delivery-QA staging — schema 1.3.0"
    schema["description"]="QA-only staging contract. Immutable review-store admission only; no learner materialisation, activation or mastery authority."
    schema["properties"]["schema_version"]={"const":SCHEMA_VERSION}
    payload=schema["properties"]["payload"]
    payload["properties"]["delivery_mode"]={"const":"INLINE"}
    payload["properties"]["package_download_url"]={"type":"null"}
    payload["properties"]["release_operation"]={"const":"STAGE_FOR_DELIVERY_QA"}
    payload["allOf"]=[{
      "if":{"properties":{"release_operation":{"const":"STAGE_FOR_DELIVERY_QA"}},"required":["release_operation"]},
      "then":{"properties":{
        "questions":{"type":"array","minItems":1,"items":{"$ref":"#/$defs/question"}},
        "release":{"allOf":[{"$ref":"#/$defs/release"},{"properties":{
          "release_status":{"const":"DELIVERY_QA_ONLY"},
          "question_count":{"type":"integer","minimum":1}
        }}]}
      }}
    }]
    schema["$defs"]["release"]["properties"]["release_status"]={"const":"DELIVERY_QA_ONLY"}
    arch=schema["$defs"]["question"]["properties"]["architecture"]
    arch["properties"]={
      "knowledge_node_ids":{"type":"array","items":{"type":"string","minLength":1,"maxLength":255},"uniqueItems":True},
      "claim_family_id":{"type":["string","null"],"maxLength":255},
      "reasoning_seed_id":{"type":["string","null"],"maxLength":255},
      "parent_question_id":{"type":["string","null"],"maxLength":255},
      "dependency_group_id":{"type":["string","null"],"maxLength":255},
      "dependency_type":{"type":["string","null"],"maxLength":255},
      "evidence_role":{"enum":[None,"INDEPENDENT","DEPENDENT","RECOVERY","RECONFIRMATION","SHARED_STIMULUS_DEPENDENT"]},
      "independent_mastery_eligible":{"const":False},
      "independent_mastery_weight":{"const":0},
      "transfer_level":{"type":["string","null"],"maxLength":255},
      "common_cr":{"type":["string","null"],"maxLength":255},
      "mastery_status":{"const":"PENDING_CONTRACT"},
      "mastery_level":{"enum":[None,"FOUNDATION","EXAM_READY","ADVANCED","DISTINCTION"]},
      "mastery_ceiling":{"enum":[None,"FOUNDATION","EXAM_READY","ADVANCED","DISTINCTION"]},
      "cognitive_demand":{"type":["string","null"],"maxLength":255},
      "misconception_ids":{"type":"array","items":{"type":"string","minLength":1,"maxLength":255},"uniqueItems":True}
    }
    arch["required"]=["knowledge_node_ids","independent_mastery_eligible","independent_mastery_weight","mastery_status"]
    arch["allOf"]=[]
    gov=schema["$defs"]["question"]["properties"]["governance"]
    gov["properties"]={
      "academic_review_state":{"const":"QA_CANDIDATE"},
      "r2_status":{"enum":["NOT_REQUIRED","AMENDMENT_PENDING_R2","R2_CLEARED"]},
      "hold_status":{"const":"QA_ONLY"},
      "source_check_status":{"enum":["QA_ONLY","CLEAR","NOT_REQUIRED"]},
      "release_readiness":{"const":"NOT_AUTHORIZED"},
      "rights_status":{"enum":["OWNED","COMMISSIONED_IP_ASSIGNED","LICENSED_COMMERCIAL","OPEN_COMMERCIAL","PUBLIC_DOMAIN"]},
      "generated_clearance_status":{"enum":[None,"NOT_APPLICABLE"]},
      "readiness_policy_version":{"type":"string","minLength":1,"maxLength":255},
      "review_evidence_refs":{"type":"array","items":{"type":"string","minLength":1,"maxLength":255},"uniqueItems":True},
      "release_authority_conferred":{"const":False},
      "mastery_authority_conferred":{"const":False}
    }
    gov["required"]=[
      "academic_review_state","r2_status","hold_status","source_check_status",
      "release_readiness","rights_status","readiness_policy_version",
      "release_authority_conferred","mastery_authority_conferred"
    ]
    out.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(schema,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return path

def _source_value(source_row:dict[str,Any],*names:str):
    import re
    for n in names:
        if source_row.get(n) not in (None,""):
            return source_row.get(n)
    def norm(v): return re.sub(r"[^a-z0-9]+","",str(v or "").lower())
    idx={norm(k):v for k,v in source_row.items()}
    for n in names:
        v=idx.get(norm(n))
        if v not in (None,""): return v
    return None

def _num(v, default:float)->float:
    if v in (None,""): return float(default)
    try:return float(v)
    except Exception:return float(default)

def _qa_source_evidence(*,qid:int,source_question_id:str,source_row:dict[str,Any],spec:dict[str,Any])->dict[str,Any]:
    original_sha=str(spec["sha256"]).lower()
    source_row_no=int(source_row.get("_PH_Original_Source_Row") or next(
        int(x["source_row"]) for x in spec["selected"] if str(x["source_question_id"])==source_question_id
    ))
    identity={
      "source_question_id":source_question_id,
      "source_file_sha256":original_sha,
      "worksheet":str(spec["sheet_name"]),
      "row":source_row_no,
    }
    evid_public="PH-QA13-EVID-"+_sha(identity)[:24].upper()
    source_public="SHA256::"+original_sha
    set_id="PH-QA13-SET-"+original_sha[:24].upper()
    body={
      "public_id":evid_public,"evidence_set_id":set_id,
      "source_public_id":source_public,"source_type":"SCOREMAX_CREATED",
      "source_version":original_sha,"source_title":str(spec["filename"]),
      "locator":f"{spec['sheet_name']}!row {source_row_no}",
      "source_file_sha256":original_sha,"worksheet":str(spec["sheet_name"]),
      "source_row":source_row_no,"rights_status":"OWNED",
      "source_chapter_public_id":None,"evidence_role":"PRIMARY",
    }
    body["evidence_checksum_sha256"]=_sha(body)
    return body

def _effective_projection(integration, material_snapshot, row:dict[str,Any], stored_options:list[dict[str,Any]],
                          review:dict[str,Any]|None, assignment_snapshot:dict[str,Any]|None):
    qid=int(row["id"])
    eff=dict(material_snapshot(qid))
    projected=dict(row)
    for field in (
      "stem","stimulus_context","statements","assumptions","correct_answer","explanation",
      "answer_rubric_json","question_format","stimulus_type","mastery_level","cognitive_demand"
    ):
        if field in eff and eff.get(field) is not None:
            projected[field]=eff.get(field)
    opts=[dict(x) for x in stored_options]
    by_label={str(o.get("option_label") or "").strip().upper():o for o in opts}
    for raw in (eff.get("options") or []):
        if not isinstance(raw,dict): continue
        lab=str(raw.get("option_label") or raw.get("label") or "").strip().upper()
        if lab and lab in by_label:
            if raw.get("option_text") is not None or raw.get("text") is not None:
                by_label[lab]["option_text"]=str(raw.get("option_text") if raw.get("option_text") is not None else raw.get("text"))
            if "is_correct" in raw:
                by_label[lab]["is_correct"]=int(bool(raw.get("is_correct")))
    snap=copy.deepcopy((review or {}).get("snapshot") or assignment_snapshot or {})
    if not isinstance(snap,dict): snap={}
    q=snap.setdefault("question",{})
    for field in ("stem","stimulus_context","statements","assumptions","correct_answer","explanation","question_format","stimulus_type"):
        if projected.get(field) is not None:
            q[field]=projected.get(field)
    if projected.get("correct_answer") not in (None,""):
        q["proposed_answer"]=projected.get("correct_answer")
    if review:
        snap.setdefault("_power_house_governance",{})["canonical_snapshot"]=True
    projected,opts2=integration._reviewed_delivery_projection(projected,opts,snap)
    return projected,opts2,snap,eff

def _scope_context(conn,row:dict[str,Any],source_row:dict[str,Any],spec:dict[str,Any],marks:float)->dict[str,Any]:
    qid=int(row["id"])
    assignment=conn.execute("""SELECT a.market_id,a.subject,a.chapter_label
      FROM academic_review_assignment_items_v011 ai
      JOIN academic_review_assignments_v011 a ON a.id=ai.assignment_id
      WHERE ai.question_id=? ORDER BY ai.id DESC LIMIT 1""",(qid,)).fetchone()
    if not assignment or not str(assignment["market_id"] or "").strip():
        raise RuntimeError(f"{qid}: governed QA market scope missing")
    framework=conn.execute("""SELECT af.qualification_or_exam_name,af.subject_domain,fv.part_or_year
      FROM questions q JOIN framework_versions fv ON fv.id=q.framework_version_id
      JOIN assessment_frameworks af ON af.id=fv.framework_id WHERE q.id=?""",(qid,)).fetchone()
    if not framework:
        raise RuntimeError(f"{qid}: governed framework scope missing")
    programme=str(framework["qualification_or_exam_name"] or "").strip()
    subject=str(framework["subject_domain"] or "").strip()
    if not programme or not subject:
        raise RuntimeError(f"{qid}: governed programme/subject scope missing")
    grade=str(_source_value(source_row,"Grade","Grade_Year","Year") or framework["part_or_year"] or "").strip()
    chapter_num=str(_source_value(source_row,"Chapter","Chapter_Number") or spec["chapter"]).strip()
    chapter_title=str(_source_value(source_row,"Chapter_Title","Chapter Title") or spec["chapter_label"]).strip()
    scope={
      "market_id":str(assignment["market_id"]).strip(),
      "programme_id":programme,
      "subject_id":subject,
      "chapter_id":chapter_num,
      "grade_year_id":grade or None,
      "board_exam_id":None,"qualification_id":None,
      "section_id":None,"topic_id":None,"subtopic_id":None,
      "display":{
        "programme":programme,"grade_year":grade or None,"subject":subject,
        "chapter_number":chapter_num,"chapter":chapter_title,
        "section":None,"topic":None,"subtopic":None
      },
      "default_marks":marks,"negative_marks":0,
      "language":"en","learner_hygiene_version":"1",
      "require_exam_profile":False,"exam_profile_name":"",
    }
    profile_material={k:scope[k] for k in ("market_id","programme_id","subject_id","chapter_id","grade_year_id")}
    scope["release_profile_id"]="PH-QA13-SCOPE-"+_sha(profile_material)[:24].upper()
    scope["release_profile_version"]="1"
    scope["release_profile_checksum_sha256"]=_sha(profile_material)
    return scope

def build_subject_envelope(*,subject:str,spec:dict[str,Any],question_ids:list[int],manifest_sha256:str,
                           producer_version:str="V015L9BT")->dict[str,Any]:
    import db, integration_v1 as integration
    from integrity_contract_v014 import material_snapshot
    ids=[int(x) for x in question_ids]
    if not ids or len(ids)!=len(set(ids)):
        raise RuntimeError(f"{subject}: invalid QA staging population")
    fw_rows=db.query(f"SELECT DISTINCT framework_version_id FROM questions WHERE id IN ({','.join('?' for _ in ids)})",ids)
    fwids={int(r["framework_version_id"]) for r in fw_rows}
    if len(fwids)!=1: raise RuntimeError(f"{subject}: framework scope ambiguous {sorted(fwids)}")
    rows,options=integration._question_snapshot_rows(next(iter(fwids)),ids)
    rows_by={int(r["id"]):dict(r) for r in rows}
    stimuli_by={}; questions=[]
    with db.connect() as conn:
        reviews=integration._review_decisions_conn(conn,ids)
        assignments=integration._review_snapshots_conn(conn,ids)
        for qid in sorted(ids):
            row=rows_by[qid]
            f=conn.execute("""SELECT source_question_id,source_row_json FROM question_source_fidelity_v015l1
                              WHERE question_id=?""",(qid,)).fetchall()
            if len(f)!=1: raise RuntimeError(f"{subject}:{qid}: exact one source fidelity row required")
            source_question_id=str(f[0]["source_question_id"])
            source_row=json.loads(str(f[0]["source_row_json"] or "{}"))
            expected=next((x for x in spec["selected"] if str(x["source_question_id"])==source_question_id),None)
            if not expected: raise RuntimeError(f"{subject}:{source_question_id}: outside frozen selection")
            if int(source_row.get("_PH_Original_Source_Row") or 0)!=int(expected["source_row"]):
                raise RuntimeError(f"{subject}:{source_question_id}: source-row commitment mismatch")
            if str(source_row.get("_PH_Original_Master_SHA256") or "").lower()!=str(spec["sha256"]).lower():
                raise RuntimeError(f"{subject}:{source_question_id}: master-SHA commitment mismatch")
            projected,opts,snapshot,eff=_effective_projection(
                integration,material_snapshot,row,options.get(qid,[]),reviews.get(qid),assignments.get(qid)
            )
            evidence=_qa_source_evidence(qid=qid,source_question_id=source_question_id,source_row=source_row,spec=spec)
            projected["_source_evidence"]=[evidence]
            projected["source_public_id"]=evidence["source_public_id"]
            projected["source_type"]=evidence["source_type"]
            projected["source_rights"]="OWNED"
            projected["source_file_sha256"]=evidence["source_file_sha256"]
            projected["source_title"]=evidence["source_title"]
            projected["effective_rights"]="OWNED"
            dep=_source_value(source_row,"Dependency_Group_ID","Dependency Group ID")
            dep_type=_source_value(source_row,"Dependency_Type","Dependency Type")
            # Non-authoritative native-builder compatibility values. These are overwritten
            # and asserted absent from the final QA-staging contract before hashing.
            native_role="SHARED_STIMULUS_DEPENDENT" if dep not in (None,"") else "DEPENDENT"
            ep={"evidence_role":native_role,"reasoning_seed_id":None,
                "dependency_group_id":str(dep).strip() if dep not in (None,"") else None,
                "dependency_type":str(dep_type).strip() if dep_type not in (None,"") else None,
                "independent_mastery_eligible":False,"independent_mastery_weight":0.0,
                "mastery_weight":0.0,"transfer_level":None,"common_cr":None,"_source_market_direct":True}
            mp={"destination_node_id":None,"destination_mastery":"FOUNDATION",
                "assessment_ceiling":"FOUNDATION","_source_market_direct":True}
            marks=_num(projected.get("maximum_marks") or _source_value(source_row,"Maximum_Marks","Maximum Marks","Marks"),1)
            context=_scope_context(conn,projected,source_row,spec,marks)
            cognitive=_source_value(source_row,"Cognitive_Demand","Cognitive Demand")
            snapshot.setdefault("source_record_metadata",{})
            if eff.get("stimulus_data") is not None:
                snapshot["source_record_metadata"]["stimulus_data"]=eff.get("stimulus_data")
            try:
                stimulus=integration._canonical_stimulus_from_snapshot(projected,ep,snapshot,canonical_evidence=evidence)
            except TypeError:
                stimulus=integration._canonical_stimulus_from_snapshot(projected,ep,snapshot)
            if stimulus:
                stimuli_by[str(stimulus["stimulus_version_id"])]=stimulus
            review=reviews.get(qid) or {}
            state=str(review.get("state") or "").strip().upper()
            review_item_id=review.get("origin_assignment_item_id")
            material=integration._build_question_material(
                projected,opts,mp,ep,[],context,state or None,stimulus,review_item_id
            )
            a=material["architecture"]
            a.update({
              "knowledge_node_ids":[],"claim_family_id":None,"reasoning_seed_id":None,
              "parent_question_id":None,
              "dependency_group_id":str(dep).strip() if dep not in (None,"") else None,
              "dependency_type":str(dep_type).strip() if dep_type not in (None,"") else None,
              "evidence_role":None,"independent_mastery_eligible":False,
              "independent_mastery_weight":0,"transfer_level":None,"common_cr":None,
              "mastery_status":"PENDING_CONTRACT","mastery_level":None,"mastery_ceiling":None,
              "cognitive_demand":str(cognitive).strip() if cognitive not in (None,"") else None,
              "misconception_ids":[],
            })
            r2=("AMENDMENT_PENDING_R2" if state=="AMENDMENT_PENDING_R2" else
                ("R2_CLEARED" if state=="R2_CLEARED" else "NOT_REQUIRED"))
            material["governance"]={
              "academic_review_state":"QA_CANDIDATE","r2_status":r2,
              "hold_status":"QA_ONLY","source_check_status":"QA_ONLY",
              "release_readiness":"NOT_AUTHORIZED","rights_status":"OWNED",
              "generated_clearance_status":"NOT_APPLICABLE",
              "readiness_policy_version":POLICY,
              "review_evidence_refs":[f"assignment_item::{int(review_item_id)}"] if review_item_id else [],
              "release_authority_conferred":False,"mastery_authority_conferred":False,
            }
            # Native compatibility placeholders must not survive into outbound material.
            if a.get("mastery_level") is not None or a.get("mastery_ceiling") is not None or a.get("evidence_role") is not None:
                raise RuntimeError(f"{subject}:{source_question_id}: non-authoritative mastery placeholder escaped")
            _,item=integration._question_version_v013c(conn,qid,str(projected["public_id"]),material)
            questions.append(item)
        conn.commit()
    stimuli=list(stimuli_by.values())
    scope=questions[0]["curriculum"]
    for q in questions:
        cur=q["curriculum"]
        if any(str(cur.get(k))!=str(scope.get(k)) for k in ("market_id","programme_id","subject_id","chapter_id")):
            raise RuntimeError(f"{subject}: QA release scope divergence")
    membership={
      "manifest_sha256":manifest_sha256,
      "questions":[{"id":q["question_version_id"],"sha":q["question_checksum_sha256"]} for q in questions],
      "stimuli":[{"id":s["stimulus_version_id"],"sha":s["stimulus_checksum_sha256"]} for s in stimuli],
    }
    manifest_checksum=_sha(membership)
    release_id=f"REL::CROSS50-QA13::{subject.upper()}::CH{spec['chapter']}"
    release_version="QA13-"+manifest_checksum[:16].upper()
    package_checksum=_sha({"delivery_mode":"INLINE","manifest_checksum_sha256":manifest_checksum,"release_id":release_id,"release_version":release_version})
    stamp=_iso_now()
    release={
      "release_id":release_id,"release_version":release_version,
      "release_status":"DELIVERY_QA_ONLY","generated_at":stamp,
      "effective_at":None,
      "market_id":scope["market_id"],"programme_id":scope["programme_id"],
      "subject_id":scope["subject_id"],"chapter_id":scope["chapter_id"],
      "readiness_policy_version":POLICY,
      "question_count":len(questions),"stimulus_count":len(stimuli),
      "package_checksum_sha256":package_checksum,"manifest_checksum_sha256":manifest_checksum,
      "supersedes_release_version":None,"withdrawn_at":None,"withdrawal_reason":None,
    }
    payload={"delivery_mode":"INLINE","package_download_url":None,"release_operation":"STAGE_FOR_DELIVERY_QA",
             "release":release,"stimuli":stimuli,"questions":questions}
    payload_sha=_sha(payload)
    envelope={
      "message_id":"msg::PH_SM_APPROVED_CONTENT_V1::"+payload_sha[:32],
      "contract_name":"PH_SM_APPROVED_CONTENT_V1","contract_version":"1","schema_version":SCHEMA_VERSION,
      "source_system":"POWER_HOUSE","destination_system":"SCOREMAX",
      "occurred_at":stamp,"sent_at":stamp,
      "correlation_id":"CROSS50-QA13::"+subject.upper(),
      "idempotency_key":"CROSS50-QA13::"+payload_sha,
      "producer_version":producer_version,"retry_of_message_id":None,
      "payload_checksum_sha256":payload_sha,"data_classification":"INTERNAL","payload":payload,
    }
    return envelope

def validate_envelope(envelope:dict[str,Any], app:Path=APP)->None:
    from jsonschema import Draft202012Validator, FormatChecker
    path=build_schema_v13(app)
    schema=json.loads(path.read_text(encoding="utf-8"))
    errs=sorted(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(envelope),key=lambda e:list(e.path))
    if errs:
        detail="; ".join(f"{'.'.join(map(str,e.path))}: {e.message}" for e in errs[:20])
        raise RuntimeError("PH_QA13_SCHEMA_INVALID "+detail)
    payload=envelope["payload"]
    if _sha(payload)!=str(envelope["payload_checksum_sha256"]):
        raise RuntimeError("PH_QA13_PAYLOAD_CHECKSUM_INVALID")
    for q in payload["questions"]:
        a=q["architecture"];g=q["governance"]
        if a.get("mastery_status")!="PENDING_CONTRACT" or bool(a.get("independent_mastery_eligible")) or float(a.get("independent_mastery_weight") or 0)!=0:
            raise RuntimeError("PH_QA13_MASTERY_FENCE_INVALID")
        if g.get("release_readiness")!="NOT_AUTHORIZED" or g.get("release_authority_conferred") is not False or g.get("mastery_authority_conferred") is not False:
            raise RuntimeError("PH_QA13_RELEASE_FENCE_INVALID")
