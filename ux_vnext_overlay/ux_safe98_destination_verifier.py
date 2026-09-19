from __future__ import annotations
from pathlib import Path

MARKER="SCOREMAX_SAFE98_DESTINATION_VERIFIER_V1"

def apply_safe98_destination_verifier(root: Path) -> None:
    p=Path(root)/"scoremax_production.py"
    s=p.read_text(encoding="utf-8")
    marker="# "+MARKER
    if marker in s:
        return
    s += r'''

# SCOREMAX_SAFE98_DESTINATION_VERIFIER_V1
import os as _safe98_os
if _safe98_os.environ.get("SCOREMAX_VERIFY_SAFE98_DESTINATION")=="1":
    import hashlib as _safe98_hashlib
    import json as _safe98_json
    import scoremax_integration_v1 as _safe98_integration
    _safe98_release_id="REL::PILOT::BIO12-CH13::SAFE98::20260919"
    _safe98_release_version="1"
    _safe98_held={"PH-RS-Q-BE9C43562034461C7B484A","PH-RS-Q-717ACEAD333442AF065264"}
    _safe98_c=scoremax.db()
    try:
        _safe98_integration.init_schema(_safe98_c)
        _safe98_rel=_safe98_c.execute(
          "SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",
          (_safe98_release_id,_safe98_release_version)
        ).fetchone()
        if not _safe98_rel:
            raise RuntimeError("SAFE98_DESTINATION_RELEASE_MISSING")
        _safe98_rel=dict(_safe98_rel)
        _safe98_members=_safe98_c.execute(
          """SELECT m.question_id,m.question_version_id,v.question_checksum_sha256,
                    v.local_question_db_id,v.scoremax_projection_json
             FROM integration_ph_release_question_membership m
             JOIN integration_ph_question_version_store v
               ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
             WHERE m.release_id=? AND m.release_version=? ORDER BY m.ordinal,m.id""",
          (_safe98_release_id,_safe98_release_version)
        ).fetchall()
        _safe98_ids=[str(r["question_id"]) for r in _safe98_members]
        _safe98_pair_digest=_safe98_hashlib.sha256(
          "\n".join(str(r["question_id"])+"|"+str(r["question_version_id"])+"|"+str(r["question_checksum_sha256"]) for r in _safe98_members).encode()
        ).hexdigest()
        _safe98_payload=_safe98_json.loads(str(_safe98_rel["immutable_payload_json"]))
        _safe98_payload_q=list(_safe98_payload.get("questions") or [])
        _safe98_payload_map={
          str(q.get("question_id") or ""):(str(q.get("question_version_id") or ""),str(q.get("question_checksum_sha256") or ""))
          for q in _safe98_payload_q
        }
        _safe98_store_map={
          str(r["question_id"]):(str(r["question_version_id"]),str(r["question_checksum_sha256"]))
          for r in _safe98_members
        }
        _safe98_activation=int(_safe98_c.execute(
          "SELECT COUNT(*) FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?",
          (_safe98_release_id,_safe98_release_version)
        ).fetchone()[0])
        _safe98_receipt=_safe98_c.execute(
          "SELECT * FROM integration_receipts WHERE message_id=? ORDER BY received_at DESC LIMIT 1",
          ("PH-SEND::BIO12-CH13::SAFE98::20260919::1",)
        ).fetchone()
        _safe98_local_ids=[int(r["local_question_db_id"]) for r in _safe98_members if r["local_question_db_id"] is not None]
        _safe98_active=0
        if _safe98_local_ids:
            _marks=",".join("?" for _ in _safe98_local_ids)
            _safe98_active=int(_safe98_c.execute(
              f"SELECT COUNT(*) FROM questions WHERE id IN ({_marks}) AND COALESCE(active,0)<>0",
              _safe98_local_ids
            ).fetchone()[0])
        _safe98_qc=_safe98_c.execute("PRAGMA quick_check").fetchone()[0]
        _safe98_fk=len(_safe98_c.execute("PRAGMA foreign_key_check").fetchall())
        _safe98_quarantine=int(_safe98_c.execute(
          "SELECT COUNT(*) FROM integration_quarantine WHERE status='OPEN' AND payload_json LIKE ?",
          ("%"+_safe98_release_id+"%",)
        ).fetchone()[0])
        assert str(_safe98_rel["local_status"])=="STAGED",_safe98_rel["local_status"]
        assert str(_safe98_rel["schema_version"])=="1.2.0",_safe98_rel["schema_version"]
        assert int(_safe98_rel["question_count"])==98,_safe98_rel["question_count"]
        assert int(_safe98_rel["stimulus_count"])==65,_safe98_rel["stimulus_count"]
        assert len(_safe98_members)==98,len(_safe98_members)
        assert len(set(_safe98_ids))==98
        assert not (_safe98_held & set(_safe98_ids)),_safe98_held & set(_safe98_ids)
        assert len(_safe98_payload_q)==98,len(_safe98_payload_q)
        assert _safe98_payload_map==_safe98_store_map
        assert _safe98_activation==0,_safe98_activation
        # STAGED content must remain outside learner-local question materialisation until
        # explicit ScoreMax-owned activation authority is created.
        assert len(_safe98_local_ids)==0,len(_safe98_local_ids)
        assert _safe98_active==0,_safe98_active
        assert _safe98_receipt and str(_safe98_receipt["status"])=="ACCEPTED",dict(_safe98_receipt) if _safe98_receipt else None
        assert str(_safe98_receipt["accepted_schema_version"])=="1.2.0",_safe98_receipt["accepted_schema_version"]
        assert _safe98_qc=="ok",_safe98_qc
        assert _safe98_fk==0,_safe98_fk
        assert _safe98_quarantine==0,_safe98_quarantine
        print("SCOREMAX_SAFE98_DESTINATION_QA_PASS "+_safe98_json.dumps({
          "release_id":_safe98_release_id,
          "release_version":_safe98_release_version,
          "local_status":_safe98_rel["local_status"],
          "schema_version":_safe98_rel["schema_version"],
          "question_count":98,
          "stimulus_count":65,
          "membership_count":len(_safe98_members),
          "held_ids_absent":True,
          "activation_authorizations":_safe98_activation,
          "local_materialised_question_rows":len(_safe98_local_ids),
          "learner_active_rows":_safe98_active,
          "payload_store_exact":True,
          "question_version_checksum_digest":_safe98_pair_digest,
          "package_checksum_sha256":str(_safe98_rel["package_checksum_sha256"]),
          "probe_question":{
            "question_id":str(_safe98_members[0]["question_id"]),
            "question_version_id":str(_safe98_members[0]["question_version_id"]),
            "question_checksum_sha256":str(_safe98_members[0]["question_checksum_sha256"]),
            "projection":_safe98_json.loads(str(_safe98_members[0]["scoremax_projection_json"] or "{}")),
          },
          "receipt_id":str(_safe98_receipt["receipt_id"]),
          "receipt_status":str(_safe98_receipt["status"]),
          "quick_check":_safe98_qc,
          "foreign_key_violations":_safe98_fk,
          "open_release_quarantine":_safe98_quarantine,
        },sort_keys=True),flush=True)
    finally:
        _safe98_c.close()
'''
    compile(s,str(p),"exec")
    p.write_text(s,encoding="utf-8")
    print(MARKER+" BUILD_PASS read_only=true gated=true learner_activation=false",flush=True)
