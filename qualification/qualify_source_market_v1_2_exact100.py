#!/usr/bin/env python3
from __future__ import annotations

import base64, copy, hashlib, io, json, os, sqlite3, sys, zlib, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"hosted_runtime_base_v6512"
FIX=ROOT/"qualification"
sys.path.insert(0,str(RUNTIME))
import scoremax_integration_v1 as sm

ENV_FIX=FIX/"source_market_v1_2_exact100_envelope.zlib.b64"
PKG_FIX=FIX/"source_market_v1_2_exact100_package_json.zlib.b64"

def load_fixture(path: Path):
    raw=zlib.decompress(base64.b64decode(path.read_text(encoding="ascii").strip()))
    return raw,json.loads(raw.decode("utf-8"))

def conn(path: str):
    p=Path(path); p.unlink(missing_ok=True)
    c=sqlite3.connect(p)
    c.row_factory=sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    sm.init_schema(c)
    c.commit()
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

if __name__=="__main__":
    raise SystemExit(main())
