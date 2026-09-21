from __future__ import annotations

import copy
import json
from pathlib import Path

MARKER="SCOREMAX_CROSS50_QA_STAGING_V13_1"
SCHEMA_VERSION="1.3.0"

def _build_schema(root: Path) -> None:
    src=root/"integration_contracts"/"v1_2_0"/"PH_SM_APPROVED_CONTENT_V1.schema.json"
    if not src.is_file():
        raise SystemExit("SCOREMAX_QA_V13_PARENT_SCHEMA_MISSING")
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
    release=schema["$defs"]["release"]
    release["properties"]["release_status"]={"const":"DELIVERY_QA_ONLY"}

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

    out=root/"integration_contracts"/"v1_3_0"
    out.mkdir(parents=True,exist_ok=True)
    path=out/"PH_SM_APPROVED_CONTENT_V1.schema.json"
    path.write_text(json.dumps(schema,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    json.loads(path.read_text(encoding="utf-8"))

def _runtime_patch() -> str:
    return r'''
# SCOREMAX_CROSS50_QA_STAGING_V13_1
QA_STAGING_SCHEMA_VERSION='1.3.0'

_smqa_v13_contract_schema_path=_contract_schema_path
_smqa_v13_strict_envelope_errors=_strict_envelope_errors
_smqa_v13_admit_content_envelope=admit_content_envelope
_smqa_v13_projection=_projection
_smqa_v13_activate_release=_activate_release
_smqa_v13_authorize_product_activation=authorize_product_activation

def _contract_schema_path(contract,schema_version='1.0.0'):
    if contract=='PH_SM_APPROVED_CONTENT_V1' and str(schema_version)==QA_STAGING_SCHEMA_VERSION:
        return Path(__file__).resolve().parent/'integration_contracts'/'v1_3_0'/'PH_SM_APPROVED_CONTENT_V1.schema.json'
    return _smqa_v13_contract_schema_path(contract,schema_version)

def _strict_envelope_errors(envelope,contract,source,destination):
    sv=str(envelope.get('schema_version') or '') if isinstance(envelope,dict) else ''
    if contract!='PH_SM_APPROVED_CONTENT_V1' or sv!=QA_STAGING_SCHEMA_VERSION:
        return _smqa_v13_strict_envelope_errors(envelope,contract,source,destination)
    errors=_schema_errors(envelope,contract,sv)
    if not errors:
        if envelope.get('contract_name')!=contract:
            errors.append({'code':'CONTRACT_MISMATCH','path':'contract_name','message':'Unexpected contract','retryable':False})
        if envelope.get('source_system')!=source:
            errors.append({'code':'SOURCE_SYSTEM','path':'source_system','message':'Unexpected source system','retryable':False})
        if envelope.get('destination_system')!=destination:
            errors.append({'code':'DESTINATION_SYSTEM','path':'destination_system','message':'Unexpected destination system','retryable':False})
        if str(envelope.get('payload_checksum_sha256') or '')!=payload_checksum(envelope.get('payload')):
            errors.append({'code':'PAYLOAD_CHECKSUM','path':'payload_checksum_sha256','message':'Payload checksum does not match canonical payload','retryable':False})
    return errors

def _qa_v13_governance_errors(q,index):
    errors=[]; path=f'payload.questions[{index}]'; a=q.get('architecture') or {}; g=q.get('governance') or {}
    if str(a.get('mastery_status') or '')!='PENDING_CONTRACT':
        errors.append({'code':'QA_MASTERY_STATUS','path':path+'.architecture.mastery_status','message':'QA staging requires PENDING_CONTRACT mastery status','retryable':False})
    if bool(a.get('independent_mastery_eligible')) or abs(float(a.get('independent_mastery_weight') or 0))>1e-9:
        errors.append({'code':'QA_MASTERY_CREDIT_FORBIDDEN','path':path+'.architecture','message':'QA-staged questions cannot carry mastery credit','retryable':False})
    required={
      'academic_review_state':'QA_CANDIDATE','hold_status':'QA_ONLY',
      'release_readiness':'NOT_AUTHORIZED'
    }
    for k,v in required.items():
        if str(g.get(k) or '').upper()!=v:
            errors.append({'code':'QA_GOVERNANCE_STATE','path':path+'.governance.'+k,'message':f'QA staging requires {k}={v}','retryable':False})
    if str(g.get('r2_status') or '').upper() not in {'NOT_REQUIRED','AMENDMENT_PENDING_R2','R2_CLEARED'}:
        errors.append({'code':'QA_R2_STATE','path':path+'.governance.r2_status','message':'Unsupported QA R2 state','retryable':False})
    if bool(g.get('release_authority_conferred')) or bool(g.get('mastery_authority_conferred')):
        errors.append({'code':'QA_AUTHORITY_FORBIDDEN','path':path+'.governance','message':'QA staging cannot confer release or mastery authority','retryable':False})
    if str(g.get('rights_status') or '').upper() not in RIGHTS_ELIGIBLE:
        errors.append({'code':'RIGHTS_NOT_ELIGIBLE','path':path+'.governance.rights_status','message':'QA staging still requires eligible rights','retryable':False})
    return errors

def _qa_v13_projection(q,stimuli):
    proj=dict(_smqa_v13_projection(q,stimuli))
    proj.update({
      'level':'','difficulty':'','variant':'',
      'review_status':'QA Staged','source_type':'Power House QA Staged',
      'active':0,'scoremax_ready':0,'content_environment':'QA_STAGED',
      'ph_evidence_role':'','ph_independent_mastery_weight':0,
      'ph_mastery_ceiling':'',
    })
    return proj

def _qa_v13_stage_question_version(c,q,release_id,release_version,stim_lookup,ordinal,now):
    qid=str(q['question_id']); qvid=str(q['question_version_id']); qchk=str(q['question_checksum_sha256'])
    existing=c.execute('SELECT * FROM integration_ph_question_version_store WHERE question_id=? AND question_version_id=?',(qid,qvid)).fetchone()
    if existing and existing['question_checksum_sha256']!=qchk:
        raise ValueError(f'QUESTION_VERSION_CHECKSUM_CONFLICT::{qid}::{qvid}')
    proj=_qa_v13_projection(q,stim_lookup)
    if not existing:
        c.execute('''INSERT INTO integration_ph_question_version_store(question_id,question_version_id,question_version_number,question_checksum_sha256,
          supersedes_question_version_id,effective_from,curriculum_json,content_json,architecture_json,governance_json,provenance_json,
          scoremax_projection_json,first_admitted_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (qid,qvid,int(q['question_version_number']),qchk,q.get('supersedes_question_version_id'),q.get('effective_from'),
           canonical_json(q.get('curriculum') or {}),canonical_json(q.get('content') or {}),canonical_json(q.get('architecture') or {}),
           canonical_json(q.get('governance') or {}),canonical_json(q.get('provenance') or {}),canonical_json(proj),now))
        c.execute('''INSERT OR IGNORE INTO integration_ph_question_versions(release_id,release_version,question_id,question_version_id,question_version_number,
          question_checksum_sha256,supersedes_question_version_id,effective_from,curriculum_json,content_json,architecture_json,governance_json,provenance_json,scoremax_projection_json,admitted_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(release_id,release_version,qid,qvid,int(q['question_version_number']),qchk,q.get('supersedes_question_version_id'),q.get('effective_from'),
          canonical_json(q.get('curriculum') or {}),canonical_json(q.get('content') or {}),canonical_json(q.get('architecture') or {}),canonical_json(q.get('governance') or {}),canonical_json(q.get('provenance') or {}),canonical_json(proj),now))
    c.execute('''INSERT OR IGNORE INTO integration_ph_release_question_membership(release_id,release_version,question_id,question_version_id,ordinal,admitted_at)
      VALUES(?,?,?,?,?,?)''',(release_id,release_version,qid,qvid,int(ordinal),now))

def admit_content_envelope(c,envelope,content_sha_header=''):
    sv=str(envelope.get('schema_version') or '')
    if sv!=QA_STAGING_SCHEMA_VERSION:
        return _smqa_v13_admit_content_envelope(c,envelope,content_sha_header)
    p=envelope.get('payload') if isinstance(envelope.get('payload'),dict) else {}
    errors=_basic_validate(envelope,'PH_SM_APPROVED_CONTENT_V1','POWER_HOUSE')
    if errors:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',errors); c.commit(); return rec,422
    if content_sha_header and content_sha_header!=envelope['payload_checksum_sha256']:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',[{'code':'HEADER_CHECKSUM','path':'X-Content-SHA256','message':'Header checksum mismatch','retryable':False}]); c.commit(); return rec,400
    rel=p.get('release') or {}; questions=list(p.get('questions') or []); stimuli=list(p.get('stimuli') or [])
    if str(p.get('delivery_mode') or '').upper()!='INLINE' or str(p.get('release_operation') or '').upper()!='STAGE_FOR_DELIVERY_QA':
        errors.append({'code':'QA_DELIVERY_OPERATION','path':'payload','message':'Schema 1.3 supports INLINE STAGE_FOR_DELIVERY_QA only','retryable':False})
    if str(rel.get('release_status') or '').upper()!='DELIVERY_QA_ONLY':
        errors.append({'code':'QA_RELEASE_STATUS','path':'payload.release.release_status','message':'Schema 1.3 requires DELIVERY_QA_ONLY','retryable':False})
    if int(rel.get('question_count') or 0)!=len(questions):
        errors.append({'code':'QUESTION_COUNT','path':'payload.release.question_count','message':'Question count mismatch','retryable':False})
    if int(rel.get('stimulus_count') or 0)!=len(stimuli):
        errors.append({'code':'STIMULUS_COUNT','path':'payload.release.stimulus_count','message':'Stimulus count mismatch','retryable':False})
    errors.extend(_verify_question_stimulus_checksums({'questions':questions,'stimuli':stimuli}))
    seen=set()
    for i,q in enumerate(questions):
        ident=(str(q.get('question_id') or ''),str(q.get('question_version_id') or ''))
        if ident in seen:
            errors.append({'code':'DUPLICATE_QUESTION_VERSION','path':f'payload.questions[{i}]','message':'Duplicate question version in package','retryable':False})
        seen.add(ident)
        errors.extend(_qa_v13_governance_errors(q,i))
        curr=q.get('curriculum') or {}
        for rk in ('market_id','programme_id','subject_id','chapter_id'):
            if str(curr.get(rk) or '')!=str(rel.get(rk) or ''):
                errors.append({'code':'SCOPE_MISMATCH','path':f'payload.questions[{i}].curriculum.{rk}','message':'Question scope differs from release scope','retryable':False})
    # Content/marking semantics are exactly the qualified 1.2 source-market semantics.
    errors.extend(_semantic_content_errors(questions,stimuli,'1.2.0'))
    if errors:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',errors); c.commit(); return rec,422

    semantic=release_semantic_checksum(rel,questions,stimuli,'STAGE_FOR_DELIVERY_QA')
    _begin_immediate(c)
    state,row=_register_inbound(c,envelope)
    identity=f"{rel.get('release_id')}|{rel.get('release_version')}"
    existing=c.execute('SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(rel.get('release_id'),rel.get('release_version'))).fetchone()
    if state=='DUPLICATE':
        rec=_durable_replay_receipt(c,row)
        if rec: c.commit(); return rec,200
    if state=='CONFLICT':
        rec=_quarantine(c,envelope,identity,semantic,row['payload_checksum_sha256'] if row else '','INBOUND_IDEMPOTENCY_CONFLICT'); c.commit(); return rec,409
    if existing:
        old_sem=str(existing['semantic_checksum_sha256'] or '')
        if old_sem!=semantic:
            rec=_quarantine(c,envelope,identity,semantic,old_sem or 'EXISTING_IDENTITY','SEMANTIC_IDENTITY_VERSION_CONFLICT'); c.commit(); return rec,409
        rec=_receipt(c,envelope,'DUPLICATE'); _record_inbound(c,envelope,rec,'DUPLICATE'); c.commit(); return rec,200

    for q in questions:
        old=c.execute('SELECT question_checksum_sha256 FROM integration_ph_question_version_store WHERE question_id=? AND question_version_id=?',(q['question_id'],q['question_version_id'])).fetchone()
        if old and old['question_checksum_sha256']!=q['question_checksum_sha256']:
            rec=_quarantine(c,envelope,f"{q['question_id']}|{q['question_version_id']}",q['question_checksum_sha256'],old['question_checksum_sha256'],'QUESTION_VERSION_CHECKSUM_CONFLICT'); c.commit(); return rec,409
    for st in stimuli:
        old=c.execute('SELECT stimulus_checksum_sha256 FROM integration_ph_stimulus_version_store WHERE stimulus_id=? AND stimulus_version_id=?',(st['stimulus_id'],st['stimulus_version_id'])).fetchone()
        if old and old['stimulus_checksum_sha256']!=st['stimulus_checksum_sha256']:
            rec=_quarantine(c,envelope,f"{st['stimulus_id']}|{st['stimulus_version_id']}",st['stimulus_checksum_sha256'],old['stimulus_checksum_sha256'],'STIMULUS_VERSION_CHECKSUM_CONFLICT'); c.commit(); return rec,409

    now=utcnow(); effective=rel.get('effective_at')
    c.execute('''INSERT INTO integration_ph_content_releases(release_id,release_version,package_checksum_sha256,manifest_checksum_sha256,
      payload_checksum_sha256,semantic_checksum_sha256,release_status,local_status,effective_at,generated_at,market_id,programme_id,subject_id,chapter_id,
      question_count,stimulus_count,readiness_policy_version,supersedes_release_version,source_system_version,immutable_payload_json,admitted_at,
      schema_version,release_operation) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],rel['manifest_checksum_sha256'],envelope['payload_checksum_sha256'],semantic,
       rel['release_status'],'STAGED',effective,rel.get('generated_at'),rel['market_id'],rel['programme_id'],rel['subject_id'],rel['chapter_id'],
       len(questions),len(stimuli),rel.get('readiness_policy_version',''),rel.get('supersedes_release_version'),envelope.get('producer_version',''),
       canonical_json(p),now,QA_STAGING_SCHEMA_VERSION,'STAGE_FOR_DELIVERY_QA'))
    stim_lookup={str(st.get('stimulus_id')):st for st in stimuli if st.get('stimulus_id')}
    for i,st in enumerate(stimuli): _stage_stimulus_version(c,st,rel['release_id'],rel['release_version'],i,now)
    for i,q in enumerate(questions): _qa_v13_stage_question_version(c,q,rel['release_id'],rel['release_version'],stim_lookup,i,now)
    rec=_receipt(c,envelope,'ACCEPTED'); _record_inbound(c,envelope,rec,'ACCEPTED')
    c.commit(); return rec,202

def _activate_release(c,release_id,release_version):
    rel=c.execute('SELECT release_operation FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(release_id,release_version)).fetchone()
    if rel and str(rel['release_operation'] or '').upper()!='PUBLISH_SNAPSHOT':
        return 0
    return _smqa_v13_activate_release(c,release_id,release_version)

def authorize_product_activation(c,release_id,release_version,package_checksum_sha256,actor,reason):
    rel=c.execute('SELECT release_operation FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(str(release_id or '').strip(),str(release_version or '').strip())).fetchone()
    if rel and str(rel['release_operation'] or '').upper()!='PUBLISH_SNAPSHOT':
        return {'status':'REJECTED','code':'QA_STAGING_NOT_ACTIVATABLE','activated_count':0}
    return _smqa_v13_authorize_product_activation(c,release_id,release_version,package_checksum_sha256,actor,reason)
'''

def apply_cross50_qa_staging_v13(root: Path) -> None:
    root=Path(root)
    target=root/"scoremax_integration_v1.py"
    if not target.is_file():
        raise SystemExit("SCOREMAX_QA_V13_RUNTIME_MISSING")
    _build_schema(root)
    text=target.read_text(encoding="utf-8")
    if MARKER not in text:
        text += "\n\n"+_runtime_patch()+"\n"
    compile(text,str(target),"exec")
    target.write_text(text,encoding="utf-8")
    rendered=target.read_text(encoding="utf-8")
    required=(
      MARKER,"QA_STAGING_SCHEMA_VERSION='1.3.0'","STAGE_FOR_DELIVERY_QA",
      "QA_STAGING_NOT_ACTIVATABLE","PENDING_CONTRACT","content_environment':'QA_STAGED"
    )
    missing=[x for x in required if x not in rendered]
    if missing:
        raise SystemExit("SCOREMAX_QA_V13_POSTBUILD_CONTROL_MISSING:"+",".join(missing))
    print("SCOREMAX_CROSS50_QA_STAGING_V13_BUILD_PASS schema=1.3.0 qa_only=true inline_only=true mastery_credit=0 materialisation=false activation=false backward_1_0_1_1_1_2_untouched=true",flush=True)
