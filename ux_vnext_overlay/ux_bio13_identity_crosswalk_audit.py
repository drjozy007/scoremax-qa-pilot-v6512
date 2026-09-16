from __future__ import annotations
from pathlib import Path

MARKER='SCOREMAX_BIO13_IDENTITY_CROSSWALK_AUDIT_V1'


def apply_bio13_identity_crosswalk_audit(root: Path) -> None:
    module=root/'ux_bio13_identity_crosswalk_audit_runtime.py'
    module.write_text('''from __future__ import annotations\nimport json,os\nEXPECTED_CSV_SHA256="ba8e863c4793f694e5227e5b5525147df5e132ecdce0e5ccf5057ae552178fe5"\nPROMPT_PACK_ID="BIO13_SCOREMAX_PILOT100_DIRECT_INTAKE_SAFE_v1_1"\nPROMPT_PACK_VERSION="e1ddb25d2213058de86394fa00b119c29b18ac6eb98c285599ee8ca6b1651883"\n\ndef run(scoremax):\n    if str(os.environ.get("SCOREMAX_BIO13_IDENTITY_CROSSWALK_AUDIT","0")).strip().lower() not in {"1","true","yes","on"}:\n        print("SCOREMAX_BIO13_IDENTITY_CROSSWALK_AUDIT disabled=true",flush=True); return\n    c=scoremax.db()\n    try:\n        b=c.execute("SELECT id,batch_code,row_count,valid_count,error_count,warning_count FROM content_import_batches WHERE source_prompt_pack_id=? AND source_prompt_pack_version=? AND payload_checksum=? ORDER BY id",(PROMPT_PACK_ID,PROMPT_PACK_VERSION,EXPECTED_CSV_SHA256)).fetchall()\n        if len(b)!=1: raise RuntimeError(f"BIO13_IDENTITY_AUDIT_BATCH_COUNT={len(b)}")\n        batch=b[0]\n        if int(batch["row_count"] or 0)!=100 or int(batch["valid_count"] or 0)!=100 or int(batch["error_count"] or 0)!=0: raise RuntimeError("BIO13_IDENTITY_AUDIT_BATCH_NOT_CLEAN")\n        qs=c.execute("SELECT id,question_id,provenance_note FROM questions WHERE source_import_batch_id=? ORDER BY question_id",(int(batch["id"]),)).fetchall()\n        if len(qs)!=100: raise RuntimeError(f"BIO13_IDENTITY_AUDIT_QUESTION_COUNT={len(qs)}")\n        out=[]\n        for q in qs:\n            try: p=json.loads(q["provenance_note"] or "{}")\n            except Exception as exc: raise RuntimeError(f"BIO13_IDENTITY_AUDIT_PROVENANCE_JSON:{q['question_id']}") from exc\n            out.append({\n                "scoremax_db_id":int(q["id"]),\n                "source_question_id":str(q["question_id"] or ""),\n                "power_house_public_id":str(p.get("power_house_public_id") or ""),\n                "power_house_source_row":str(p.get("power_house_source_row") or ""),\n            })\n        if any(not x["source_question_id"] or not x["power_house_public_id"] or not x["power_house_source_row"] for x in out): raise RuntimeError("BIO13_IDENTITY_AUDIT_INCOMPLETE_TRIPLET")\n        print("SCOREMAX_BIO13_IDENTITY_CROSSWALK "+json.dumps({"batch_id":int(batch["id"]),"batch_code":str(batch["batch_code"] or ""),"count":len(out),"transport_sha256":EXPECTED_CSV_SHA256,"selection_ledger_sha256":PROMPT_PACK_VERSION,"triplets":out},sort_keys=True,separators=(",",":")),flush=True)\n    finally:\n        c.close()\n''',encoding='utf-8')
    production=root/'scoremax_production.py'
    s=production.read_text(encoding='utf-8')
    old='application=scoremax.app'
    new='from ux_bio13_identity_crosswalk_audit_runtime import run as _run_bio13_identity_crosswalk_audit\n_run_bio13_identity_crosswalk_audit(scoremax)\napplication=scoremax.app'
    if 'run as _run_bio13_identity_crosswalk_audit' not in s:
        idx=s.rfind(old)
        if idx<0: raise SystemExit('SCOREMAX_BIO13_IDENTITY_AUDIT_APPLICATION_ANCHOR_MISSING')
        s=s[:idx]+new+s[idx+len(old):]
        production.write_text(s,encoding='utf-8')
    print(f'{MARKER} PASS read_only=true exact_batch=true triplets_only=true learner_content=false answers=false users=false',flush=True)
