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
        # SAFE98_SECTION_DIGESTS_V2: canonical section digests, content not emitted.
        def _safe98_canon(v):
            return _safe98_json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
        _safe98_section_keys=sorted(set().union(*(set(q.keys()) for q in _safe98_payload_q)))
        _safe98_section_digests={}
        for _k in _safe98_section_keys:
            if _k in {"question_version_id","question_checksum_sha256"}:
                continue
            _pairs=[]
            for _q in sorted(_safe98_payload_q,key=lambda x:str(x.get("question_id") or "")):
                _qid=str(_q.get("question_id") or "")
                _vh=_safe98_hashlib.sha256(_safe98_canon(_q.get(_k)).encode()).hexdigest()
                _pairs.append(_qid+"|"+_vh)
            _safe98_section_digests[_k]=_safe98_hashlib.sha256("\n".join(_pairs).encode()).hexdigest()
        _safe98_semantic_pairs=[]
        for _q in sorted(_safe98_payload_q,key=lambda x:str(x.get("question_id") or "")):
            _clean={k:v for k,v in _q.items() if k not in {"question_version_id","question_checksum_sha256"}}
            _safe98_semantic_pairs.append(str(_q.get("question_id") or "")+"|"+_safe98_hashlib.sha256(_safe98_canon(_clean).encode()).hexdigest())
        _safe98_semantic_digest=_safe98_hashlib.sha256("\n".join(_safe98_semantic_pairs).encode()).hexdigest()
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
          "question_semantic_digest_excluding_version_checksum":_safe98_semantic_digest,
          "question_section_keys":_safe98_section_keys,
          "question_section_digests":_safe98_section_digests,
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


def apply_cross50_math16_destination_verifier(root: Path) -> None:
    p=Path(root)/"scoremax_production.py"
    text=p.read_text(encoding="utf-8")
    marker="# SCOREMAX_CROSS50_MATH16_DESTINATION_VERIFIER_V1"
    if marker in text:
        return
    text += r'''

# SCOREMAX_CROSS50_MATH16_DESTINATION_VERIFIER_V1
import os as _c50_os
if _c50_os.environ.get("SCOREMAX_VERIFY_CROSS50_MATH16_DESTINATION")=="1":
    import json as _c50_json
    import scoremax_integration_v1 as _c50_integration
    _c50_release_id="REL::CROSS50-QA13::MATHEMATICS::CH6"
    _c50_release_version="QA13-C874939F972614A1"
    _c50_c=scoremax.db()
    try:
        _c50_integration.init_schema(_c50_c)
        _c50_rel=_c50_c.execute(
          "SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",
          (_c50_release_id,_c50_release_version)
        ).fetchone()
        if not _c50_rel:
            raise RuntimeError("CROSS50_MATH16_RELEASE_MISSING")
        _c50_rel=dict(_c50_rel)
        _c50_members=_c50_c.execute(
          """SELECT m.question_id,m.question_version_id,v.question_checksum_sha256,
                    v.local_question_db_id,v.scoremax_projection_json,v.architecture_json,v.governance_json
             FROM integration_ph_release_question_membership m
             JOIN integration_ph_question_version_store v
               ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
             WHERE m.release_id=? AND m.release_version=? ORDER BY m.ordinal,m.id""",
          (_c50_release_id,_c50_release_version)
        ).fetchall()
        _c50_activation=int(_c50_c.execute(
          "SELECT COUNT(*) FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?",
          (_c50_release_id,_c50_release_version)
        ).fetchone()[0])
        _c50_local=[int(r["local_question_db_id"]) for r in _c50_members if r["local_question_db_id"] is not None]
        _c50_active=0
        if _c50_local:
            _marks=",".join("?" for _ in _c50_local)
            _c50_active=int(_c50_c.execute(
              f"SELECT COUNT(*) FROM questions WHERE id IN ({_marks}) AND COALESCE(active,0)<>0",_c50_local
            ).fetchone()[0])
        _c50_mastery_bad=0; _c50_gov_bad=0; _c50_projection_bad=0
        for _r in _c50_members:
            _a=_c50_json.loads(str(_r["architecture_json"] or "{}"))
            _g=_c50_json.loads(str(_r["governance_json"] or "{}"))
            _p=_c50_json.loads(str(_r["scoremax_projection_json"] or "{}"))
            if str(_a.get("mastery_status") or "")!="PENDING_CONTRACT" or bool(_a.get("independent_mastery_eligible")) or float(_a.get("independent_mastery_weight") or 0)!=0:
                _c50_mastery_bad+=1
            if str(_g.get("release_readiness") or "")!="NOT_AUTHORIZED" or bool(_g.get("release_authority_conferred")) or bool(_g.get("mastery_authority_conferred")):
                _c50_gov_bad+=1
            if int(_p.get("active") or 0)!=0 or int(_p.get("scoremax_ready") or 0)!=0 or str(_p.get("content_environment") or "")!="QA_STAGED":
                _c50_projection_bad+=1
        _c50_qc=str(_c50_c.execute("PRAGMA quick_check").fetchone()[0])
        _c50_fk=len(_c50_c.execute("PRAGMA foreign_key_check").fetchall())
        _c50_q=int(_c50_c.execute(
          "SELECT COUNT(*) FROM integration_quarantine WHERE status='OPEN' AND payload_json LIKE ?",
          ("%"+_c50_release_id+"%",)
        ).fetchone()[0])
        assert str(_c50_rel["local_status"])=="STAGED",_c50_rel["local_status"]
        assert str(_c50_rel["schema_version"])=="1.3.0",_c50_rel["schema_version"]
        assert str(_c50_rel["release_operation"])=="STAGE_FOR_DELIVERY_QA",_c50_rel["release_operation"]
        assert int(_c50_rel["question_count"])==16,_c50_rel["question_count"]
        assert len(_c50_members)==16,len(_c50_members)
        assert len({str(r["question_id"]) for r in _c50_members})==16
        assert _c50_activation==0,_c50_activation
        assert len(_c50_local)==0,len(_c50_local)
        assert _c50_active==0,_c50_active
        assert _c50_mastery_bad==0,_c50_mastery_bad
        assert _c50_gov_bad==0,_c50_gov_bad
        assert _c50_projection_bad==0,_c50_projection_bad
        assert _c50_qc=="ok",_c50_qc
        assert _c50_fk==0,_c50_fk
        assert _c50_q==0,_c50_q
        print("SCOREMAX_CROSS50_MATH16_DESTINATION_PASS "+_c50_json.dumps({
          "release_id":_c50_release_id,
          "release_version":_c50_release_version,
          "schema_version":str(_c50_rel["schema_version"]),
          "release_operation":str(_c50_rel["release_operation"]),
          "local_status":str(_c50_rel["local_status"]),
          "question_count":16,
          "membership_count":16,
          "activation_authorizations":_c50_activation,
          "local_materialised_question_rows":len(_c50_local),
          "learner_active_rows":_c50_active,
          "mastery_pending":16,
          "release_authority_conferred":False,
          "mastery_authority_conferred":False,
          "projection_qa_staged":16,
          "quick_check":_c50_qc,
          "foreign_key_violations":_c50_fk,
          "open_release_quarantine":_c50_q
        },sort_keys=True),flush=True)
    finally:
        _c50_c.close()
'''
    compile(text,str(p),"exec")
    p.write_text(text,encoding="utf-8")
    print("SCOREMAX_CROSS50_MATH16_DESTINATION_VERIFIER_V1 BUILD_PASS read_only=true activation=false",flush=True)


def apply_cross50_rejection_diagnostic(root: Path) -> None:
    p=Path(root)/"scoremax_production.py"
    text=p.read_text(encoding="utf-8")
    marker="# SCOREMAX_CROSS50_REJECTION_DIAGNOSTIC_V1"
    if marker in text:
        return
    text += r'''

# SCOREMAX_CROSS50_REJECTION_DIAGNOSTIC_V1
import os as _c50diag_os
if _c50diag_os.environ.get("SCOREMAX_DIAG_CROSS50_REJECTION")=="1":
    import json as _c50diag_json
    _c50diag_c=scoremax.db()
    try:
        _c50diag_cols=[str(r[1]) for r in _c50diag_c.execute("PRAGMA table_info(integration_receipts)").fetchall()]
        _c50diag_row=_c50diag_c.execute(
            "SELECT * FROM integration_receipts WHERE status='REJECTED' ORDER BY received_at DESC LIMIT 1"
        ).fetchone()
        if not _c50diag_row:
            print("SCOREMAX_CROSS50_REJECTION_DIAG "+_c50diag_json.dumps({"status":"NO_REJECTED_RECEIPT","columns":_c50diag_cols},sort_keys=True),flush=True)
        else:
            _d=dict(_c50diag_row)
            _safe={}
            for _k,_v in _d.items():
                _lk=str(_k).lower()
                if any(_x in _lk for _x in ("payload","envelope","token","secret","authorization")):
                    continue
                if _v is None or isinstance(_v,(int,float)):
                    _safe[_k]=_v
                else:
                    _safe[_k]=str(_v)[:16000]
            print("SCOREMAX_CROSS50_REJECTION_DIAG "+_c50diag_json.dumps({"status":"FOUND","receipt":_safe,"columns":_c50diag_cols},sort_keys=True),flush=True)
    finally:
        _c50diag_c.close()
'''
    compile(text,str(p),"exec")
    p.write_text(text,encoding="utf-8")
    print("SCOREMAX_CROSS50_REJECTION_DIAGNOSTIC_V1 BUILD_PASS read_only=true",flush=True)


def apply_cross50_all_destination_verifier(root: Path) -> None:
    p=Path(root)/"scoremax_production.py"
    text=p.read_text(encoding="utf-8")
    marker="# SCOREMAX_CROSS50_ALL_DESTINATION_VERIFIER_V1"
    if marker in text:
        return
    text += r'''

# SCOREMAX_CROSS50_ALL_DESTINATION_VERIFIER_V1
import os as _c50all_os
if _c50all_os.environ.get("SCOREMAX_VERIFY_CROSS50_ALL_DESTINATIONS")=="1":
    import json as _c50all_json
    import scoremax_integration_v1 as _c50all_integration
    _c50all_specs=(
      ("Mathematics","REL::CROSS50-QA13::MATHEMATICS::CH6",16),
      ("Chemistry","REL::CROSS50-QA13::CHEMISTRY::CH7",16),
      ("Physics","REL::CROSS50-QA13::PHYSICS::CH13",18),
    )
    _c50all_c=scoremax.db()
    try:
        _c50all_integration.init_schema(_c50all_c)
        _c50all_seen=[]
        for _subj,_rid,_expected in _c50all_specs:
            _rel=_c50all_c.execute(
              "SELECT * FROM integration_ph_content_releases WHERE release_id=? ORDER BY admitted_at DESC LIMIT 1",
              (_rid,)
            ).fetchone()
            if not _rel:
                continue
            _rel=dict(_rel); _rv=str(_rel["release_version"])
            _members=_c50all_c.execute(
              """SELECT m.question_id,m.question_version_id,v.local_question_db_id,
                        v.scoremax_projection_json,v.architecture_json,v.governance_json
                 FROM integration_ph_release_question_membership m
                 JOIN integration_ph_question_version_store v
                   ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
                 WHERE m.release_id=? AND m.release_version=? ORDER BY m.ordinal,m.id""",
              (_rid,_rv)
            ).fetchall()
            _activation=int(_c50all_c.execute(
              "SELECT COUNT(*) FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?",
              (_rid,_rv)
            ).fetchone()[0])
            _local=[int(x["local_question_db_id"]) for x in _members if x["local_question_db_id"] is not None]
            _active=0
            if _local:
                _marks=",".join("?" for _ in _local)
                _active=int(_c50all_c.execute(
                  f"SELECT COUNT(*) FROM questions WHERE id IN ({_marks}) AND COALESCE(active,0)<>0",_local
                ).fetchone()[0])
            _mastery_bad=_gov_bad=_projection_bad=0
            for _row in _members:
                _a=_c50all_json.loads(str(_row["architecture_json"] or "{}"))
                _g=_c50all_json.loads(str(_row["governance_json"] or "{}"))
                _p=_c50all_json.loads(str(_row["scoremax_projection_json"] or "{}"))
                if str(_a.get("mastery_status") or "")!="PENDING_CONTRACT" or bool(_a.get("independent_mastery_eligible")) or float(_a.get("independent_mastery_weight") or 0)!=0:
                    _mastery_bad+=1
                if str(_g.get("release_readiness") or "")!="NOT_AUTHORIZED" or bool(_g.get("release_authority_conferred")) or bool(_g.get("mastery_authority_conferred")):
                    _gov_bad+=1
                if int(_p.get("active") or 0)!=0 or int(_p.get("scoremax_ready") or 0)!=0 or str(_p.get("content_environment") or "")!="QA_STAGED":
                    _projection_bad+=1
            _q=int(_c50all_c.execute(
              "SELECT COUNT(*) FROM integration_quarantine WHERE status='OPEN' AND payload_json LIKE ?",
              ("%"+_rid+"%",)
            ).fetchone()[0])
            assert str(_rel["local_status"])=="STAGED",(_subj,_rel["local_status"])
            assert str(_rel["schema_version"])=="1.3.0",(_subj,_rel["schema_version"])
            assert str(_rel["release_operation"])=="STAGE_FOR_DELIVERY_QA",(_subj,_rel["release_operation"])
            assert int(_rel["question_count"])==_expected,(_subj,_rel["question_count"])
            assert len(_members)==_expected,(_subj,len(_members))
            assert len({str(x["question_id"]) for x in _members})==_expected
            assert _activation==0,(_subj,_activation)
            assert len(_local)==0,(_subj,len(_local))
            assert _active==0,(_subj,_active)
            assert _mastery_bad==0,(_subj,_mastery_bad)
            assert _gov_bad==0,(_subj,_gov_bad)
            assert _projection_bad==0,(_subj,_projection_bad)
            assert _q==0,(_subj,_q)
            _c50all_seen.append(_subj)
            print("SCOREMAX_CROSS50_DESTINATION_PASS "+_c50all_json.dumps({
              "subject":_subj,"release_id":_rid,"release_version":_rv,
              "question_count":_expected,"membership_count":len(_members),
              "local_status":"STAGED","schema_version":"1.3.0",
              "release_operation":"STAGE_FOR_DELIVERY_QA",
              "activation_authorizations":0,"local_materialised_question_rows":0,
              "learner_active_rows":0,"mastery_pending":_expected,
              "projection_qa_staged":_expected,"release_authority_conferred":False,
              "mastery_authority_conferred":False,"open_release_quarantine":0
            },sort_keys=True),flush=True)
        _qc=str(_c50all_c.execute("PRAGMA quick_check").fetchone()[0])
        _fk=len(_c50all_c.execute("PRAGMA foreign_key_check").fetchall())
        assert _qc=="ok",_qc
        assert _fk==0,_fk
        print("SCOREMAX_CROSS50_DESTINATION_SUMMARY "+_c50all_json.dumps({
          "verified_subjects":_c50all_seen,"verified_count":len(_c50all_seen),
          "quick_check":_qc,"foreign_key_violations":_fk
        },sort_keys=True),flush=True)
    finally:
        _c50all_c.close()
'''
    compile(text,str(p),"exec")
    p.write_text(text,encoding="utf-8")
    print("SCOREMAX_CROSS50_ALL_DESTINATION_VERIFIER_V1 BUILD_PASS read_only=true optional_subjects=true activation=false",flush=True)
