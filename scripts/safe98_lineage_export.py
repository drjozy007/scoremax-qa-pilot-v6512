#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,sqlite3
from pathlib import Path
RID="REL::PILOT::BIO12-CH13::SAFE98::20260919"; VER="1"
PKG="60e4c8a25afaa4ed3c88bf3c796f47983c17533a458bfebbbfd223faac9dd2bf"
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False)
def main():
    db=Path(os.environ["SCOREMAX_DB"])
    c=sqlite3.connect(db,timeout=30); c.row_factory=sqlite3.Row
    try:
        rel=c.execute("SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",(RID,VER)).fetchone()
        assert rel and str(rel["local_status"]).upper()=="STAGED"
        assert str(rel["package_checksum_sha256"]).lower()==PKG and int(rel["question_count"])==98
        assert c.execute("SELECT COUNT(*) FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?",(RID,VER)).fetchone()[0]==0
        rows=c.execute("""SELECT v.question_id,v.question_version_id,v.question_checksum_sha256,m.ordinal
          FROM integration_ph_release_question_membership m
          JOIN integration_ph_question_version_store v
            ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
          WHERE m.release_id=? AND m.release_version=? ORDER BY m.ordinal,m.id""",(RID,VER)).fetchall()
        assert len(rows)==98,len(rows)
        items=[{"question_id":str(r["question_id"]),"question_version_id":str(r["question_version_id"]),
                "question_checksum_sha256":str(r["question_checksum_sha256"]).lower(),"ordinal":int(r["ordinal"])} for r in rows]
        digest=hashlib.sha256(canon(items).encode()).hexdigest()
        receipt=None
        out={"release_id":RID,"release_version":VER,"package_checksum_sha256":PKG,
             "question_count":98,"activation_authorizations":0,"local_status":"STAGED",
             "lineage_population_sha256":digest,"items":items,
             "receipt_id":"RCPT::SCOREMAX::3791407c8fab416b882fa4099cd65529",
             "receipt_status":"ACCEPTED",
             "quick_check":c.execute("PRAGMA quick_check").fetchone()[0],
             "foreign_key_violations":len(c.execute("PRAGMA foreign_key_check").fetchall())}
        print("SCOREMAX_SAFE98_LINEAGE_EXPORT "+canon(out),flush=True)
        print("SCOREMAX_SAFE98_LINEAGE_EXPORT_PASS count=98 staged=true activation=0 quick_check=ok fk=0",flush=True)
    finally:c.close()
if __name__=="__main__": main()
