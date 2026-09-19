#!/usr/bin/env python3
from __future__ import annotations

import base64, copy, hashlib, io, json, os, sqlite3, sys, zlib, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"hosted_runtime_base_v6512"
FIX=ROOT/"qualification"
sys.path.insert(0,str(RUNTIME))
import scoremax_integration_v1 as sm
import app as scoremax_app

ENV_FIX=FIX/"source_market_v1_2_exact100_envelope.zlib.b64"
PKG_FIX=FIX/"source_market_v1_2_exact100_package_json.zlib.b64"

def load_fixture(path: Path):
    raw=zlib.decompress(base64.b64decode(path.read_text(encoding="ascii").strip()))
    return raw,json.loads(raw.decode("utf-8"))

def conn(path: str):
    p=Path(path); p.unlink(missing_ok=True)
    scoremax_app.DB=p
    scoremax_app.init()
    c=scoremax_app.db()
    return c

def qcounts(c):
    tables=("integration_ph_content_releases","integration_ph_question_version_store",
            "integration_ph_release_question_membership","integration_ph_stimulus_version_store",
            "integration_ph_release_stimulus_membership","integration_receipts","integration_quarantine")
    out={}
    for t in tables:
        out[t]=int(c.execute(f"SELECT COUNT(*) n FROM {t}").fetchone()["n"])
    return out

def canonical_bytes(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")

def set_message_identity(env, suffix):
    env["message_id"]=f"SM-QUAL::{suffix}"
    env["correlation_id"]=f"SM-QUAL::{suffix}"
    env["idempotency_key"]=f"SM-QUAL::{suffix}"
    env["payload_checksum_sha256"]=sm.payload_checksum(env["payload"])
    return env

def build_manifest_zip(package_body, release):
    content_bytes=canonical_bytes(package_body)
    content_sha=hashlib.sha256(content_bytes).hexdigest()
    generated=str(release.get("generated_at") or "2026-09-19T00:00:00Z")
    manifest={
        "manifest_schema_version":"1.2.0",
        "release_id":str(release["release_id"]),
        "release_version":str(release["release_version"]),
        "generated_at":generated,
        "content_file":"content.json",
        "content_file_sha256":content_sha,
        "question_count":len(package_body["questions"]),
        "stimulus_count":len(package_body["stimuli"]),
        "files":[{
            "path":"content.json",
            "sha256":content_sha,
            "size_bytes":len(content_bytes),
        }],
    }
    manifest_bytes=canonical_bytes(manifest)
    bio=io.BytesIO()
    with zipfile.ZipFile(bio,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        # deterministic metadata for repeatable qualification bytes
        zi=zipfile.ZipInfo("manifest.json",(2026,9,19,0,0,0)); zi.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(zi,manifest_bytes)
        zi=zipfile.ZipInfo("content.json",(2026,9,19,0,0,0)); zi.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(zi,content_bytes)
    return bio.getvalue(),manifest_bytes

def assert_db_health(c):
    assert c.execute("PRAGMA quick_check").fetchone()[0]=="ok"
    assert c.execute("PRAGMA foreign_key_check").fetchall()==[]

def main():
    env_raw,env=load_fixture(ENV_FIX)
    pkg_raw,durable=load_fixture(PKG_FIX)
    assert str(env.get("schema_version"))=="1.2.0",env.get("schema_version")
    payload=dict(env["payload"])
    release=dict(payload["release"])
    questions=list(durable.get("questions") or [])
    stimuli=list(durable.get("stimuli") or [])
    assert len(questions)==100,(len(questions),len(stimuli))
    assert hashlib.sha256(pkg_raw).hexdigest(), "fixture hash unavailable"

    # Bounded diagnostic: vocabulary/shape only; no learner question text.
    from collections import Counter
    generated=Counter(str((q.get("governance") or {}).get("generated_clearance_status")) for q in questions)
    text_shapes=Counter()
    for q in questions:
        content=q.get("content") or {}; marking=content.get("marking") or {}
        if str(marking.get("key_type") or "").upper()=="TEXT":
            opts=list(content.get("options") or [])
            display_only=sum(1 for o in opts if isinstance(o,dict) and bool(o.get("is_display_only")))
            text_shapes[(str(content.get("question_family_type") or ""),str(content.get("exam_question_type") or ""),len(opts),display_only)]+=1
    print("SCOREMAX_V12_DIAG_GENERATED "+json.dumps(dict(generated),sort_keys=True),flush=True)
    print("SCOREMAX_V12_DIAG_TEXT_SHAPES "+json.dumps([{"family":k[0],"exam":k[1],"options":k[2],"display_only":k[3],"count":v} for k,v in sorted(text_shapes.items())],sort_keys=True),flush=True)
    unresolved=[]
    for idx,q in enumerate(questions):
        content=q.get("content") or {}; marking=content.get("marking") or {}; opts=list(content.get("options") or [])
        if str(marking.get("key_type") or "").upper()=="TEXT" and opts and not sm._text_option_id(content):
            key=marking.get("key"); accepted=list(marking.get("accepted_answers") or [])
            opt_ids={str(o.get("option_id") or "").strip() for o in opts if isinstance(o,dict)}
            opt_texts={str(o.get("text") or "").strip() for o in opts if isinstance(o,dict)}
            tokens=[]
            if key is not None and not isinstance(key,(dict,list)): tokens.append(str(key).strip())
            tokens.extend(str(x).strip() for x in accepted)
            unresolved.append({
                "index":idx,"question_id":str(q.get("question_id") or ""),
                "family":str(content.get("question_family_type") or ""),
                "exam":str(content.get("exam_question_type") or ""),
                "marking_keys":sorted(marking.keys()),
                "key_python_type":type(key).__name__,
                "key_length":len(str(key)) if key is not None else 0,
                "accepted_count":len(accepted),"option_count":len(opts),
                "token_matches_option_id":sum(1 for x in tokens if x in opt_ids),
                "token_matches_option_text":sum(1 for x in tokens if x in opt_texts),
            })
    print("SCOREMAX_V12_DIAG_UNRESOLVED "+json.dumps(unresolved,sort_keys=True),flush=True)

    # Bounded full-population regression expectation for learner-visible two-tier contracts.
    # Diagnostic only: no question mutation and no receiver relaxation.
    import re
    tiered=[]
    tier_pat=re.compile(r"\b(?:tier\s*1|tier\s*2|both\s+tiers|answer\s+both\s+tiers)\b",re.I)
    composite_pat=re.compile(r"\btier\s*1\s*:\s*[^;]+;\s*tier\s*2\s*:\s*.+$",re.I)
    for idx,q in enumerate(questions):
        content=q.get("content") or {}
        marking=content.get("marking") or {}
        stem=str(content.get("stem") or "")
        key=str(marking.get("key") or "")
        accepted=[str(x) for x in (marking.get("accepted_answers") or [])]
        if not (tier_pat.search(stem) or composite_pat.search(key) or any(composite_pat.search(x) for x in accepted)):
            continue
        opts=[o for o in (content.get("options") or []) if isinstance(o,dict) and not bool(o.get("is_display_only"))]
        statements=[str(x).strip() for x in (content.get("statements") or []) if str(x).strip()]
        # Flat A-D options alone provide only one selectable response surface. A valid two-tier
        # item must expose a second learner-visible response set/structure in the payload.
        option_ids=[str(o.get("option_id") or "").strip() for o in opts]
        has_second_surface=(
            any(re.search(r"^(?:T2|TIER[_ -]?2)[:._ -]",x,re.I) for x in option_ids)
            or any(re.search(r"\btier\s*2\b",x,re.I) for x in statements)
            or isinstance(content.get("tier_2"),dict)
            or isinstance(content.get("tier2"),dict)
            or isinstance(content.get("response_groups"),list) and len(content.get("response_groups") or [])>=2
        )
        tiered.append({
            "index":idx,
            "question_id":str(q.get("question_id") or ""),
            "family":str(content.get("question_family_type") or ""),
            "exam":str(content.get("exam_question_type") or ""),
            "option_count":len(opts),
            "statement_count":len(statements),
            "key_is_composite":bool(composite_pat.search(key)),
            "tier2_surface_present":bool(has_second_surface),
            "expected_firewall_disposition":"CLEAR" if has_second_surface else "CONTENT_HOLD",
        })
    print("SCOREMAX_V12_TIERED_FULL100_SCAN "+json.dumps(tiered,sort_keys=True),flush=True)
    print("SCOREMAX_V12_TIERED_FULL100_SUMMARY "+json.dumps({
        "tiered_count":len(tiered),
        "expected_hold_count":sum(1 for x in tiered if x["expected_firewall_disposition"]=="CONTENT_HOLD"),
        "expected_clear_count":sum(1 for x in tiered if x["expected_firewall_disposition"]=="CLEAR"),
    },sort_keys=True),flush=True)
    # Targeted private diagnostic for the two unresolved governed payloads only.
    # No database mutation and no learner activation.
    unresolved_ids={x["question_id"] for x in unresolved}
    for q in questions:
        if str(q.get("question_id") or "") in unresolved_ids:
            print("SCOREMAX_V12_DIAG_UNRESOLVED_PAYLOAD "+json.dumps({
                "question_id":q.get("question_id"),
                "content":q.get("content"),
                "architecture":q.get("architecture"),
                "governance":q.get("governance"),
                "provenance":q.get("provenance"),
            },sort_keys=True,ensure_ascii=False),flush=True)

    # A. Exact governed question/stimulus objects through 1.2 INLINE admission.
    inline=copy.deepcopy(env)
    inline["payload"]["delivery_mode"]="INLINE"
    inline["payload"]["package_download_url"]=None
    inline["payload"]["questions"]=copy.deepcopy(questions)
    inline["payload"]["stimuli"]=copy.deepcopy(stimuli)
    set_message_identity(inline,"EXACT100-INLINE")

    c=conn("/tmp/scoremax_v12_exact100_inline.db")
    rec,status=sm.admit_content_envelope(c,inline,inline["payload_checksum_sha256"])
    assert status==202,(status,rec)
    row=c.execute("SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",
                  (release["release_id"],release["release_version"])).fetchone()
    assert row and row["local_status"]=="STAGED",dict(row) if row else None
    assert int(row["question_count"])==100
    assert c.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership").fetchone()[0]==100
    assert c.execute("SELECT COUNT(*) FROM integration_ph_question_version_store").fetchone()[0]==100
    # No ScoreMax-owned activation authorization exists: admission must not become learner-live.
    assert c.execute("SELECT COUNT(*) FROM integration_ph_product_activation_authorizations").fetchone()[0]==0

    rec2,status2=sm.admit_content_envelope(c,inline,inline["payload_checksum_sha256"])
    assert status2==200,(status2,rec2)
    assert c.execute("SELECT COUNT(*) FROM integration_ph_content_releases").fetchone()[0]==1
    assert c.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership").fetchone()[0]==100
    assert_db_health(c)
    print("SCOREMAX_V12_EXACT100_INLINE_PASS schema=1.2.0 accepted=100 staged=true learner_live=false replay_idempotent=true quick_check=ok fk=0",flush=True)
    c.close()

    # B. 1.2 MANIFEST_PULL mechanics using the exact same 100 question/stimulus objects.
    package_body={
        "package_schema_version":"1.2.0",
        "release_id":str(release["release_id"]),
        "release_version":str(release["release_version"]),
        "stimuli":copy.deepcopy(stimuli),
        "questions":copy.deepcopy(questions),
    }
    zip_bytes,manifest_bytes=build_manifest_zip(package_body,release)
    manifest_env=copy.deepcopy(env)
    manifest_env["payload"]["delivery_mode"]="MANIFEST_PULL"
    manifest_env["payload"]["package_download_url"]="https://qualification.invalid/package.zip"
    manifest_env["payload"]["questions"]=[]
    manifest_env["payload"]["stimuli"]=[]
    manifest_env["payload"]["release"]["package_checksum_sha256"]=hashlib.sha256(zip_bytes).hexdigest()
    manifest_env["payload"]["release"]["manifest_checksum_sha256"]=hashlib.sha256(manifest_bytes).hexdigest()
    set_message_identity(manifest_env,"EXACT100-MANIFEST")

    old_download=sm._download_manifest_package
    sm._download_manifest_package=lambda url,timeout=20: zip_bytes
    try:
        c=conn("/tmp/scoremax_v12_exact100_manifest.db")
        rec3,status3=sm.admit_content_envelope(c,manifest_env,manifest_env["payload_checksum_sha256"])
        assert status3==202,(status3,rec3)
        row=c.execute("SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",
                      (release["release_id"],release["release_version"])).fetchone()
        assert row and row["local_status"]=="STAGED"
        assert int(row["question_count"])==100
        assert c.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership").fetchone()[0]==100
        assert c.execute("SELECT COUNT(*) FROM integration_ph_product_activation_authorizations").fetchone()[0]==0
        assert_db_health(c)
        print("SCOREMAX_V12_EXACT100_MANIFEST_PASS schema=1.2.0 package_questions=100 staged=true learner_live=false manifest_integrity=true quick_check=ok fk=0",flush=True)
        c.close()
    finally:
        sm._download_manifest_package=old_download

    print("SCOREMAX_V12_RECEIVER_ACCEPTANCE_PASS exact100=100 source_objects_exact=true inline=true manifest_pull=true staged_only=true activation_authority_required=true",flush=True)


SAFE98_BLOCKED_IDS={
    "PH-RS-Q-BE9C43562034461C7B484A",
    "PH-RS-Q-717ACEAD333442AF065264",
}

def _stimulus_id(obj):
    if not isinstance(obj,dict):
        return ""
    for k in ("stimulus_id","id","public_id"):
        v=str(obj.get(k) or "").strip()
        if v:
            return v
    return ""

def main_safe98():
    env_raw,env=load_fixture(ENV_FIX)
    pkg_raw,durable=load_fixture(PKG_FIX)
    assert str(env.get("schema_version"))=="1.2.0",env.get("schema_version")
    payload=dict(env["payload"])
    release=copy.deepcopy(payload["release"])
    full_questions=list(durable.get("questions") or [])
    full_stimuli=list(durable.get("stimuli") or [])
    assert len(full_questions)==100,len(full_questions)

    full_by_id={str(q.get("question_id") or ""):q for q in full_questions}
    assert SAFE98_BLOCKED_IDS.issubset(set(full_by_id)), SAFE98_BLOCKED_IDS-set(full_by_id)
    questions=[copy.deepcopy(q) for q in full_questions if str(q.get("question_id") or "") not in SAFE98_BLOCKED_IDS]
    assert len(questions)==98,len(questions)
    assert not (SAFE98_BLOCKED_IDS & {str(q.get("question_id") or "") for q in questions})

    # Retain only governed stimuli actually referenced by the 98 safe questions.
    refs=set()
    for q in questions:
        content=q.get("content") or {}
        for k in ("stimulus_ref","stimulus_id"):
            v=str(content.get(k) or "").strip()
            if v:
                refs.add(v)
    stimuli=[copy.deepcopy(x) for x in full_stimuli if _stimulus_id(x) in refs] if refs else []
    stimulus_ids={_stimulus_id(x) for x in stimuli}
    missing_refs=sorted(refs-stimulus_ids)
    assert not missing_refs,missing_refs

    # Prove retained question objects are untouched relative to the governed exact100 fixture.
    for q in questions:
        qid=str(q.get("question_id") or "")
        assert canonical_bytes(q)==canonical_bytes(full_by_id[qid]),qid

    release["release_id"]="REL::QUAL::BIO12-CH13::SAFE98::V015L9AE"
    release["release_version"]="1"
    release["question_count"]=98
    release["stimulus_count"]=len(stimuli)
    release["supersedes_release_version"]=None
    release["withdrawn_at"]=None
    release["withdrawal_reason"]=None

    package_body={
        "package_schema_version":"1.2.0",
        "release_id":str(release["release_id"]),
        "release_version":str(release["release_version"]),
        "stimuli":copy.deepcopy(stimuli),
        "questions":copy.deepcopy(questions),
    }
    zip_bytes,manifest_bytes=build_manifest_zip(package_body,release)
    release["package_checksum_sha256"]=hashlib.sha256(zip_bytes).hexdigest()
    release["manifest_checksum_sha256"]=hashlib.sha256(manifest_bytes).hexdigest()

    print("SCOREMAX_V12_SAFE98_SELECTION_PASS "+json.dumps({
        "source_population":100,
        "selected":98,
        "held":2,
        "held_ids":sorted(SAFE98_BLOCKED_IDS),
        "stimuli":len(stimuli),
        "retained_question_objects_exact":True,
    },sort_keys=True),flush=True)

    # A. INLINE receiver admission of exact safe98 objects.
    inline=copy.deepcopy(env)
    inline["payload"]["release"]=copy.deepcopy(release)
    inline["payload"]["delivery_mode"]="INLINE"
    inline["payload"]["package_download_url"]=None
    inline["payload"]["questions"]=copy.deepcopy(questions)
    inline["payload"]["stimuli"]=copy.deepcopy(stimuli)
    set_message_identity(inline,"SAFE98-INLINE")

    c=conn("/tmp/scoremax_v12_safe98_inline.db")
    rec,status=sm.admit_content_envelope(c,inline,inline["payload_checksum_sha256"])
    assert status==202,(status,rec)
    row=c.execute("SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",
                  (release["release_id"],release["release_version"])).fetchone()
    assert row and row["local_status"]=="STAGED",dict(row) if row else None
    assert int(row["question_count"])==98,dict(row)
    assert c.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership").fetchone()[0]==98
    assert c.execute("SELECT COUNT(*) FROM integration_ph_question_version_store").fetchone()[0]==98
    assert c.execute("SELECT COUNT(*) FROM integration_ph_product_activation_authorizations").fetchone()[0]==0
    rec2,status2=sm.admit_content_envelope(c,inline,inline["payload_checksum_sha256"])
    assert status2==200,(status2,rec2)
    assert c.execute("SELECT COUNT(*) FROM integration_ph_content_releases").fetchone()[0]==1
    assert c.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership").fetchone()[0]==98
    assert_db_health(c)
    print("SCOREMAX_V12_SAFE98_INLINE_PASS schema=1.2.0 accepted=98 staged=true learner_live=false replay_idempotent=true quick_check=ok fk=0",flush=True)
    c.close()

    # B. MANIFEST_PULL receiver admission of the same exact safe98 objects.
    manifest_env=copy.deepcopy(env)
    manifest_env["payload"]["release"]=copy.deepcopy(release)
    manifest_env["payload"]["delivery_mode"]="MANIFEST_PULL"
    manifest_env["payload"]["package_download_url"]="https://qualification.invalid/safe98-package.zip"
    manifest_env["payload"]["questions"]=[]
    manifest_env["payload"]["stimuli"]=[]
    set_message_identity(manifest_env,"SAFE98-MANIFEST")

    old_download=sm._download_manifest_package
    sm._download_manifest_package=lambda url,timeout=20: zip_bytes
    try:
        c=conn("/tmp/scoremax_v12_safe98_manifest.db")
        rec3,status3=sm.admit_content_envelope(c,manifest_env,manifest_env["payload_checksum_sha256"])
        assert status3==202,(status3,rec3)
        row=c.execute("SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",
                      (release["release_id"],release["release_version"])).fetchone()
        assert row and row["local_status"]=="STAGED",dict(row) if row else None
        assert int(row["question_count"])==98
        assert c.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership").fetchone()[0]==98
        assert c.execute("SELECT COUNT(*) FROM integration_ph_question_version_store").fetchone()[0]==98
        assert c.execute("SELECT COUNT(*) FROM integration_ph_product_activation_authorizations").fetchone()[0]==0
        assert_db_health(c)
        print("SCOREMAX_V12_SAFE98_MANIFEST_PASS schema=1.2.0 package_questions=98 staged=true learner_live=false manifest_integrity=true quick_check=ok fk=0",flush=True)
        c.close()
    finally:
        sm._download_manifest_package=old_download

    print("SCOREMAX_V12_SAFE98_RECEIVER_ACCEPTANCE_PASS selected=98 held=2 source_objects_exact=true inline=true manifest_pull=true staged_only=true activation_authority_required=true",flush=True)
    return 0


def transfer_safe98_persistent():
    """One-time controlled transport of the exact PH-derived safe98 payload to persistent ScoreMax."""
    import hmac
    from datetime import datetime, timezone
    from urllib import request as urlrequest, error as urlerror

    _,env=load_fixture(ENV_FIX)
    _,durable=load_fixture(PKG_FIX)
    questions=list(durable.get("questions") or [])
    stimuli=list(durable.get("stimuli") or [])
    assert len(questions)==100,len(questions)
    full_by_id={str(q.get("question_id") or ""):q for q in questions}
    assert SAFE98_BLOCKED_IDS.issubset(set(full_by_id))

    safe=[copy.deepcopy(q) for q in questions if str(q.get("question_id") or "") not in SAFE98_BLOCKED_IDS]
    assert len(safe)==98,len(safe)
    for q in safe:
        qid=str(q.get("question_id") or "")
        assert canonical_bytes(q)==canonical_bytes(full_by_id[qid]),qid

    refs=set()
    for q in safe:
        content=q.get("content") or {}
        for k in ("stimulus_ref","stimulus_id"):
            v=str(content.get(k) or "").strip()
            if v: refs.add(v)
    safe_stimuli=[copy.deepcopy(x) for x in stimuli if _stimulus_id(x) in refs] if refs else []
    assert refs=={_stimulus_id(x) for x in safe_stimuli},(refs,{_stimulus_id(x) for x in safe_stimuli})

    release=copy.deepcopy(env["payload"]["release"])
    release.update({
        "release_id":"REL::PILOT::BIO12-CH13::SAFE98::20260919",
        "release_version":"1",
        "question_count":98,
        "stimulus_count":len(safe_stimuli),
        "supersedes_release_version":None,
        "withdrawn_at":None,
        "withdrawal_reason":None,
    })
    package_body={
        "package_schema_version":"1.2.0",
        "release_id":release["release_id"],
        "release_version":release["release_version"],
        "stimuli":copy.deepcopy(safe_stimuli),
        "questions":copy.deepcopy(safe),
    }
    zip_bytes,manifest_bytes=build_manifest_zip(package_body,release)
    release["package_checksum_sha256"]=hashlib.sha256(zip_bytes).hexdigest()
    release["manifest_checksum_sha256"]=hashlib.sha256(manifest_bytes).hexdigest()

    outbound=copy.deepcopy(env)
    outbound["payload"]["release"]=copy.deepcopy(release)
    outbound["payload"]["delivery_mode"]="INLINE"
    outbound["payload"]["package_download_url"]=None
    outbound["payload"]["questions"]=copy.deepcopy(safe)
    outbound["payload"]["stimuli"]=copy.deepcopy(safe_stimuli)
    outbound["message_id"]="PH-SEND::BIO12-CH13::SAFE98::20260919::1"
    outbound["correlation_id"]="PH-SEND::BIO12-CH13::SAFE98::20260919"
    outbound["idempotency_key"]="PH-SEND::BIO12-CH13::SAFE98::20260919::1"
    outbound["payload_checksum_sha256"]=sm.payload_checksum(outbound["payload"])

    # Local receiver validation immediately before network transport.
    local=conn("/tmp/scoremax_v12_safe98_pretransport.db")
    receipt,status=sm.admit_content_envelope(local,copy.deepcopy(outbound),outbound["payload_checksum_sha256"])
    assert status==202,(status,receipt)
    assert local.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership").fetchone()[0]==98
    assert local.execute("SELECT COUNT(*) FROM integration_ph_product_activation_authorizations").fetchone()[0]==0
    assert_db_health(local); local.close()

    base=os.environ.get("SAFE98_SCOREMAX_BASE_URL","").rstrip("/")
    token=os.environ.get("SAFE98_PH_TO_SM_TOKEN","")
    secret=os.environ.get("SAFE98_PH_TO_SM_HMAC_SECRET","")
    if not base or not token or not secret:
        raise RuntimeError("SAFE98 transport credentials/base URL are not configured")
    path="/api/integration/v1/power-house/content-releases"
    url=base+path
    sent=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    checksum=outbound["payload_checksum_sha256"]
    raw="\n".join(["POST",path,outbound["message_id"],sent,checksum])
    signature=hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()
    body=canonical_bytes(outbound)
    req=urlrequest.Request(url,data=body,method="POST",headers={
        "Content-Type":"application/json",
        "Authorization":"Bearer "+token,
        "X-Message-Id":outbound["message_id"],
        "X-Sent-At":sent,
        "X-Content-SHA256":checksum,
        "X-Signature":"hmac-sha256="+signature,
    })
    try:
        with urlrequest.urlopen(req,timeout=30) as resp:
            status=int(resp.status)
            response_body=resp.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        status=int(exc.code)
        response_body=exc.read().decode("utf-8","replace")
    response=json.loads(response_body)
    if status not in (200,202):
        raise RuntimeError("SAFE98 persistent receiver rejected transport: status="+str(status)+" response="+json.dumps(response,sort_keys=True))
    if str(response.get("status") or "").upper() not in {"ACCEPTED","DUPLICATE"}:
        raise RuntimeError("SAFE98 persistent receiver receipt is not accepted/duplicate: "+json.dumps(response,sort_keys=True))
    print("PH_TO_SCOREMAX_SAFE98_TRANSFER_PASS "+json.dumps({
        "release_id":release["release_id"],
        "release_version":release["release_version"],
        "question_count":98,
        "stimulus_count":len(safe_stimuli),
        "held_excluded":2,
        "retained_objects_exact":True,
        "receiver_http_status":status,
        "receiver_status":response.get("status"),
        "accepted_schema_version":response.get("accepted_schema_version"),
        "receipt_id":response.get("receipt_id"),
        "learner_activation_requested":False,
    },sort_keys=True),flush=True)
    return 0

if __name__=="__main__":
    if os.environ.get("SCOREMAX_V12_SAFE98_PERSISTENT_TRANSFER")=="1":
        raise SystemExit(transfer_safe98_persistent())
    if os.environ.get("SCOREMAX_V12_SAFE98_ONLY")=="1":
        raise SystemExit(main_safe98())
    raise SystemExit(main())
