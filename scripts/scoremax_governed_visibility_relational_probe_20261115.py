"""Prove equivalence of a release-driven visibility relation to native ScoreMax.

Source of truth remains existing native _programme_scope_sql and signed PH
membership/authorisation/withdrawal tables. This is a disposable-only SQL
candidate and adversarial regression, NOT a published student read model.

Tests opaque IDs, shared FSc/MDCAT memberships, version/checksum, staged and
withdrawn releases, revoked authorisation and legacy qualification fallback.
Does not access production, alter the accepted runtime or grant release status.
"""
from __future__ import annotations
import ast
import json
from pathlib import Path
import re
import sqlite3
import sys
from time import perf_counter

def native_scope(root:Path):
    source=(root/"app.py").read_text(encoding="utf8")
    matches=[x for x in ast.parse(source).body
             if isinstance(x,ast.FunctionDef) and x.name=="_programme_scope_sql"]
    if len(matches)!=1:raise RuntimeError("NATIVE_SCOPE_FUNCTION_DRIFT")
    segment=ast.get_source_segment(source,matches[0]) or ""
    for required in (
        "integration_ph_question_version_store",
        "integration_ph_release_question_membership",
        "integration_ph_content_releases",
        "integration_ph_product_activation_authorizations",
        "ph_bridge_staged_withdrawal_exclusions_v6611e",
        "local_status='ACTIVE'","AUTHORIZED","ACTIVATED",
        "scoremax_release_programme",
    ):
        if required not in segment:raise RuntimeError("NATIVE_GOVERNANCE_PREDICATE_MISSING:"+required)
    ns={"re":re}
    exec(compile(ast.Module(body=matches,type_ignores=[]),str(root/"app.py"),"exec"),ns)
    return ns["_programme_scope_sql"]

def candidate_sql(aliases):
    vals=sorted({str(x).strip().casefold() for x in aliases or [] if str(x).strip()})
    if not vals:return "SELECT id FROM questions WHERE 0=1",[]
    marks=",".join("?" for _ in vals)
    return f"""WITH candidate_ids AS (
      SELECT q.id id FROM questions q
      WHERE COALESCE(q.ph_projection_owner,'')<>'POWER_HOUSE'
        AND lower(COALESCE(NULLIF(trim(q.programme),''),trim(q.qualification),'')) IN ({marks})
      UNION
      SELECT q.id id
      FROM integration_ph_content_releases pr
      JOIN integration_ph_product_activation_authorizations pa
        ON pa.release_id=pr.release_id AND pa.release_version=pr.release_version
       AND pa.package_checksum_sha256=pr.package_checksum_sha256
      JOIN integration_ph_release_question_membership pm
        ON pm.release_id=pr.release_id AND pm.release_version=pr.release_version
      JOIN integration_ph_question_version_store pv
        ON pv.question_id=pm.question_id AND pv.question_version_id=pm.question_version_id
      JOIN questions q ON q.id=pv.local_question_db_id
      WHERE pr.local_status='ACTIVE'
        AND pa.activation_status IN ('AUTHORIZED','ACTIVATED')
        AND COALESCE(q.ph_projection_owner,'')='POWER_HOUSE'
        AND pv.question_id=q.ph_question_id
        AND pv.question_version_id=q.ph_question_version_id
        AND pv.question_checksum_sha256=q.ph_question_checksum_sha256
        AND lower(scoremax_release_programme(pr.programme_id,pv.curriculum_json)) IN ({marks})
        AND NOT EXISTS(
          SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e pe
          WHERE pe.release_id=pm.release_id AND pe.release_version=pm.release_version
            AND pe.question_id=pm.question_id AND pe.question_version_id=pm.question_version_id)
    )
    SELECT id FROM candidate_ids ORDER BY id""", vals+vals

def fixture():
    c=sqlite3.connect(":memory:")
    c.row_factory=sqlite3.Row
    c.executescript("""
      CREATE TABLE questions(
        id INTEGER PRIMARY KEY,programme TEXT,qualification TEXT,
        ph_projection_owner TEXT,ph_question_id TEXT,
        ph_question_version_id TEXT,ph_question_checksum_sha256 TEXT
      );
      CREATE TABLE integration_ph_question_version_store(
        question_id TEXT,question_version_id TEXT,
        local_question_db_id INTEGER,curriculum_json TEXT,
        question_checksum_sha256 TEXT
      );
      CREATE TABLE integration_ph_release_question_membership(
        release_id TEXT,release_version TEXT,
        question_id TEXT,question_version_id TEXT
      );
      CREATE TABLE integration_ph_content_releases(
        release_id TEXT,release_version TEXT,local_status TEXT,
        programme_id TEXT,subject_id TEXT,chapter_id TEXT,
        package_checksum_sha256 TEXT
      );
      CREATE TABLE integration_ph_product_activation_authorizations(
        release_id TEXT,release_version TEXT,
        package_checksum_sha256 TEXT,activation_status TEXT
      );
      CREATE TABLE ph_bridge_staged_withdrawal_exclusions_v6611e(
        release_id TEXT,release_version TEXT,
        question_id TEXT,question_version_id TEXT
      );
      CREATE INDEX idx_test_ph_version ON integration_ph_question_version_store(question_id,question_version_id);
      CREATE INDEX idx_test_ph_member ON integration_ph_release_question_membership(question_id,question_version_id);
      CREATE INDEX idx_test_ph_release ON integration_ph_content_releases(release_id,release_version);
      CREATE INDEX idx_test_ph_activation ON integration_ph_product_activation_authorizations(release_id,release_version);
      CREATE INDEX idx_test_ph_withdrawal ON ph_bridge_staged_withdrawal_exclusions_v6611e(release_id,release_version,question_id,question_version_id);
    """)
    c.executemany("INSERT INTO questions(id,programme,qualification,ph_projection_owner) VALUES(?,?,?,?)",[
        (j,("FSc Part 1" if j%3==0 else "FSc Part 2" if j%3==1 else ""),("MDCAT" if j%3==2 else "FSc Part 1"),None)
        for j in range(1,1501)
    ])
    # PH identities are opaque and cannot be inferred from internal row IDs.
    c.executemany("""INSERT INTO questions(id,programme,qualification,ph_projection_owner,ph_question_id,ph_question_version_id,ph_question_checksum_sha256)
        VALUES(?,?,?,?,?,?,?)""",[
        (1500+j,"FSc Part 1","FSc Part 1","POWER_HOUSE",
         "PH-Q::alpha::"+str(j),"PH-V::beta::"+str(j),"CHECKSUM-"+str(j))
        for j in range(1,1501)
    ])
    curriculum=json.dumps({"programme_id":"FSC_PART_I","grade_year_id":"11","display":{"programme":"FSc Part 1","grade_year":"11"}})
    c.executemany("""INSERT INTO integration_ph_question_version_store
        (question_id,question_version_id,local_question_db_id,curriculum_json,question_checksum_sha256)
        VALUES(?,?,?,?,?)""",[
        ("PH-Q::alpha::"+str(j),"PH-V::beta::"+str(j),1500+j,curriculum,"CHECKSUM-"+str(j))
        for j in range(1,1501)
    ])
    releases=[
        ("R-FSC","1","ACTIVE","FSC_PART_I","BIOLOGY","OPAQUE-CH-11","A"*64),
        ("R-MDCAT","1","ACTIVE","MDCAT","BIOLOGY","MDCAT::BIOLOGY::UNIT::14","B"*64),
        ("R-STAGED","1","STAGED","ECAT","BIOLOGY","OPAQUE-ECAT","C"*64)
    ]
    c.executemany("INSERT INTO integration_ph_content_releases VALUES(?,?,?,?,?,?,?)",releases)
    c.executemany("INSERT INTO integration_ph_product_activation_authorizations VALUES(?,?,?,?)",[
        ("R-FSC","1","A"*64,"ACTIVATED"),
        ("R-MDCAT","1","B"*64,"AUTHORIZED"),
        ("R-STAGED","1","C"*64,"ACTIVATED")
    ])
    c.executemany("INSERT INTO integration_ph_release_question_membership VALUES(?,?,?,?)",[
        (r,"1","PH-Q::alpha::"+str(j),"PH-V::beta::"+str(j))
        for r in ("R-FSC","R-MDCAT","R-STAGED") for j in range(1,1501)
    ])
    c.commit()
    return c

def main(root:Path):
    sys.path.insert(0,str(root))
    import question_contract_engine as contracts
    native=native_scope(root)
    c=fixture()
    c.create_function("scoremax_release_programme",2,contracts.programme_for_release,deterministic=True)
    cases=("FSc Part 1","FSc Part 2","MDCAT","ECAT","Unlisted Scope")
    def ids(programme,mode):
        aliases=contracts.programme_aliases(programme)
        if mode=="native":
            clause,args=native(aliases,"q")
            statement="SELECT q.id FROM questions q WHERE "+clause+" ORDER BY q.id"
        else:statement,args=candidate_sql(aliases)
        return [row[0] for row in c.execute(statement,args)]
    def check(tag):
        stats={}
        for programme in cases:
            old=ids(programme,"native")
            new=ids(programme,"candidate")
            if old!=new:raise RuntimeError("GOVERNED_VISIBILITY_DRIFT:"+tag+":"+programme)
            if len(new)!=len(set(new)):raise RuntimeError("DUPLICATED_MEMBER_ID:"+tag)
            stats[programme]=len(new)
        print("SCOREMAX_GOVERNED_RELATION_EQUIVALENCE="+json.dumps({
            "scenario":tag,"visible_question_counts":stats,
            "native_equivalence":True,"production_data_used":False,
            "candidate_runtime_applied":False},sort_keys=True),flush=True)
    try:
        check("baseline_shared_crossmarket")
        c.execute("""INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e
          VALUES('R-FSC','1','PH-Q::alpha::1','PH-V::beta::1')""")
        check("question_level_fsc_withdrawal")
        c.execute("""UPDATE integration_ph_product_activation_authorizations
          SET activation_status='REVOKED' WHERE release_id='R-MDCAT'""")
        check("mdcat_authority_revoked")
        c.execute("""UPDATE integration_ph_content_releases SET local_status='STAGED'
          WHERE release_id='R-FSC'""")
        check("fsc_release_staged")
        c.execute("""UPDATE integration_ph_content_releases SET local_status='ACTIVE'
          WHERE release_id='R-FSC'""")
        c.execute("""UPDATE integration_ph_product_activation_authorizations
          SET activation_status='ACTIVATED' WHERE release_id='R-MDCAT'""")
        c.execute("""DELETE FROM ph_bridge_staged_withdrawal_exclusions_v6611e
          WHERE release_id='R-FSC'""")
        check("active_restored_after_reconciliation")
        c.execute("UPDATE questions SET ph_question_checksum_sha256='CORRUPT' WHERE id=1501")
        check("mismatched_checksum_not_visible")
        c.execute("UPDATE questions SET ph_question_version_id='CORRUPT' WHERE id=1502")
        check("mismatched_version_not_visible")
        c.execute("UPDATE integration_ph_question_version_store SET local_question_db_id=999999 WHERE question_id='PH-Q::alpha::3'")
        check("mismatched_internal_link_not_visible")
        c.execute("UPDATE questions SET ph_projection_owner='POWER_HOUSE' WHERE id=1")
        check("partial_projection_cannot_borrow_legacy_visibility")
        c.execute("UPDATE questions SET programme='' WHERE id=1501")
        check("ph_ignores_legacy_programme_and_uses_signed_release")
        from statistics import median
        for p in ("FSc Part 1","MDCAT"):
            aliases=contracts.programme_aliases(p)
            stmt,params=candidate_sql(aliases)
            plan=[r[3] for r in c.execute("EXPLAIN QUERY PLAN "+stmt,params).fetchall()]
            print("SCOREMAX_GOVERNED_RELATION_PLAN="+json.dumps({
                "programme":p,"steps":plan[:20],"source":"synthetic_query_plan",
                "persistent_projection_created":False},sort_keys=True),flush=True)
            native_clause,native_params=native(aliases,"q")
            old_stmt="SELECT q.id FROM questions q WHERE "+native_clause+" ORDER BY q.id"
            timings={"native":[],"release_driven":[]}
            # ABBA reduces systematic cache-order bias; synthetic fixture only.
            for mode in ("native","release_driven","release_driven","native")*3:
                statement,arguments=(old_stmt,native_params) if mode=="native" else (stmt,params)
                started=perf_counter()
                rows=c.execute(statement,arguments).fetchall()
                ms=(perf_counter()-started)*1000
                timings[mode].append(ms)
                if not rows:raise RuntimeError("GOVERNED_TIMING_EMPTY")
            print("SCOREMAX_GOVERNED_RELATION_TIMING="+json.dumps({
                "programme":p,"questions":3000,"shared_ph_questions":1500,
                "native_median_ms":round(median(timings["native"]),3),
                "release_driven_median_ms":round(median(timings["release_driven"]),3),
                "source":"ABBA_disposable_fixture","target_runtime_switched":False,
                "governed_production_equivalence":False},sort_keys=True),flush=True)
        print("SCOREMAX_GOVERNED_RELATION_CONTRACT_PASS",flush=True)
    finally:
        c.close()

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("USAGE: script runtime_root")
    main(Path(sys.argv[1]).resolve())
