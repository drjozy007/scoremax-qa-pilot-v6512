"""Adversarial concurrent native-governed visibility rehearsal, NOT a release certificate.

Runs only against a disposable SQLite database based on the existing 3,000
record PH/legacy synthetic fixture. It uses ScoreMax's actual _programme_scope_sql,
current live_question_clause and source-governed shadow builder, not a replacement
academic rule. Exercises real database transactions with multiple reader threads
and an independent release/withdrawal writer, always comparing under one pinned
SQLite read snapshot. Does NOT simulate production-grade marking or real PH receipts.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import importlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

from scoremax_governed_visibility_relational_probe_20261115 import fixture, native_scope
from scoremax_persistent_shadow_visibility_candidate_20261115 import (
    native_live, install, rebuild, read, PROGRAMMES,
)

def register(conn, contracts):
    conn.row_factory = sqlite3.Row
    conn.create_function("scoremax_release_programme", 2,
        contracts.programme_for_release, deterministic=True)
    conn.execute("PRAGMA busy_timeout=8000")
    return conn

def setup(path, contracts):
    src=fixture()
    try:
        src.executescript("""
          ALTER TABLE questions ADD COLUMN family_key TEXT;
          ALTER TABLE questions ADD COLUMN family_id TEXT;
          ALTER TABLE questions ADD COLUMN subject TEXT DEFAULT 'Biology';
          ALTER TABLE questions ADD COLUMN chapter TEXT DEFAULT 'Synthetic Chapter 1';
          ALTER TABLE questions ADD COLUMN status TEXT DEFAULT 'Approved';
          ALTER TABLE questions ADD COLUMN review_status TEXT DEFAULT 'Approved';
          ALTER TABLE questions ADD COLUMN active INTEGER DEFAULT 1;
          ALTER TABLE questions ADD COLUMN is_demo INTEGER DEFAULT 0;
          ALTER TABLE questions ADD COLUMN marking_config TEXT DEFAULT '{}';
          ALTER TABLE questions ADD COLUMN ph_is_auto_markable INTEGER DEFAULT 1;
          ALTER TABLE questions ADD COLUMN calibration_status TEXT DEFAULT 'APPROVED';
          ALTER TABLE questions ADD COLUMN ph_evidence_role TEXT;
          ALTER TABLE questions ADD COLUMN ph_dependency_type TEXT;
          ALTER TABLE questions ADD COLUMN ph_independent_mastery_weight REAL;
          ALTER TABLE questions ADD COLUMN source_type TEXT;
          ALTER TABLE questions ADD COLUMN qtype TEXT;
          ALTER TABLE questions ADD COLUMN ph_knowledge_node_ids_json TEXT;
          CREATE TABLE question_families(family_key TEXT PRIMARY KEY,
            review_status TEXT,active INTEGER);
          UPDATE questions SET family_key='FAM-'||id,family_id='FAM-'||id;
          INSERT INTO question_families
            SELECT family_key,'Approved',1 FROM questions;
          UPDATE questions SET ph_evidence_role='INDEPENDENT',
            ph_dependency_type='NONE',ph_independent_mastery_weight=1,
            source_type='POWER_HOUSE',qtype='True/False',
            ph_knowledge_node_ids_json='["TEST::NODE::1"]'
            WHERE ph_projection_owner='POWER_HOUSE';
          UPDATE questions SET ph_independent_mastery_weight=0
            WHERE id=1502;
          UPDATE questions SET ph_evidence_role='DEPENDENT',
            ph_independent_mastery_weight=1 WHERE id=1503;
          UPDATE questions SET family_id='FAM-1501' WHERE id=1504;
        """)
        with closing(sqlite3.connect(path)) as c:
            src.backup(c)
            c.execute("PRAGMA journal_mode=WAL")
            register(c,contracts)
            if install(c)!=27:
                raise RuntimeError("CONCURRENT_GUARD_27_TRIGGERS_REQUIRED")
        return 3000
    finally:
        src.close()

def native_ids(conn, programme, scope, contracts, live):
    clause,params=scope(contracts.programme_aliases(programme),"q")
    return [r["id"] for r in conn.execute(
        "SELECT q.id FROM questions q WHERE "+live+" AND "+clause+" ORDER BY q.id",
        params)]

def independently_markable(root, db):
    # The accepted formal evidence predicate is tested against actual
    # source rows with valid/zero-weight/dependent/shared-family metadata.
    evidence=importlib.import_module("ph_mastery_evidence")
    with closing(sqlite3.connect(db)) as c:
        register(c,None) if False else None
        c.row_factory=sqlite3.Row
        rows={r["id"]:dict(r) for r in c.execute(
            "SELECT * FROM questions WHERE id IN (1501,1502,1503,1504)")}
        for key in (1501,1504):
            if not evidence.eligible_for_formal_mastery(rows[key]):
                raise RuntimeError("INDEPENDENT_PH_FALSE_NEGATIVE:"+str(key))
        for key in (1502,1503):
            if evidence.eligible_for_formal_mastery(rows[key]):
                raise RuntimeError("PRACTICE_OR_DEPENDENT_EARNED_CREDIT:"+str(key))
        if rows[1501]["family_id"]!=rows[1504]["family_id"]:
            raise RuntimeError("SHARED_VARIANT_FAMILY_FIXTURE_DRIFT")
        return {"positive":[1501,1504],"rejected":[1502,1503],
                "variants_one_family":True}

def pinned_compare(conn, programmes, scope, contracts, live, helper):
    conn.execute("BEGIN")
    try:
        state=conn.execute("""SELECT dirty,epoch,snapshot_epoch FROM
          sm_shadow_visibility_authority WHERE id=1""").fetchone()
        fresh=(not state["dirty"] and state["epoch"]==state["snapshot_epoch"])
        count=0
        for programme in programmes:
            expected=native_ids(conn,programme,scope,contracts,live)
            actual=conn.execute("""SELECT question_db_id FROM sm_shadow_visibility_member
              WHERE programme=? ORDER BY question_db_id""",(programme,)).fetchall()
            shadow_ids=[x[0] for x in actual]
            inventory=helper.try_shadow_inventory(conn,programme)
            if fresh:
                if inventory is None or shadow_ids!=expected:
                    raise RuntimeError("CONCURRENT_GOVERNED_ID_DRIFT:"+programme)
                grouped=[(r["subject"],r["chapter"],r["question_count"],r["first_id"])
                    for r in inventory]
                clause,args=scope(contracts.programme_aliases(programme),"q")
                native=[(r["subject"],r["chapter"],r["question_count"],r["first_id"])
                  for r in conn.execute("""SELECT q.subject subject,q.chapter chapter,
                       COUNT(*) question_count,MIN(q.id) first_id
                       FROM questions q WHERE """+live+" AND "+clause+"""
                       AND COALESCE(q.subject,'')<>'' GROUP BY q.subject,q.chapter
                       ORDER BY q.subject""",args)]
                if grouped!=native:
                    raise RuntimeError("CONCURRENT_GOVERNED_GROUP_DRIFT:"+programme)
            elif inventory is not None:
                raise RuntimeError("DIRTY_SHADOW_ADMITTED:"+programme)
            # Real helper must preserve native mastery item set when fresh;
            # when dirty it must REFUSE optimisation, not return stale rows.
            clauses=[live,"COALESCE(q.is_demo,0)=0",
                "COALESCE(q.calibration_status,'PROVISIONAL') NOT IN ('BLOCKED','REVIEW_NEGATIVE')",
                "lower(COALESCE(q.subject,''))=lower(?)",
                "COALESCE(q.chapter,'')=?"]
            subject,chapter="Biology","Synthetic Chapter 1"
            projection=helper.try_shadow_mastery_rows(
                conn,programme,clauses,[subject,chapter],["id"])
            scope_sql,scope_params=scope(contracts.programme_aliases(programme),"q")
            native_mastery=[row[0] for row in conn.execute(
                "SELECT q.id FROM questions q WHERE "+" AND ".join(clauses)
                +" AND "+scope_sql+" ORDER BY q.id",
                [subject,chapter]+scope_params)]
            if fresh:
                if projection is None or sorted(r[0] for r in projection)!=native_mastery:
                    raise RuntimeError("CONCURRENT_MASTERY_MEMBER_DRIFT:"+programme)
            elif projection is not None:
                raise RuntimeError("DIRTY_MASTERY_PREFILTER_ADMITTED:"+programme)
            count+=1
        conn.commit()
        return fresh,count
    except Exception:
        conn.rollback()
        raise

def main(root):
    root=root.resolve()
    sys.path.insert(0,str(root))
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import question_contract_engine as contracts
    import scoremax_shadow_navigation_v1 as helper
    import os
    os.environ["SCOREMAX_NAV_SHADOW_ENABLED"]="1"
    scope=native_scope(root)
    live=native_live(root)
    with tempfile.TemporaryDirectory(prefix="scoremax-p0-concurrency-") as td:
        path=Path(td)/"disposable.db"
        setup(path,contracts)
        mastery=independently_markable(root,path)
        def connection():
            c=sqlite3.connect(path,timeout=8,isolation_level=None)
            register(c,contracts)
            return c
        with closing(connection()) as c:
            rebuild(c,scope,contracts.programme_aliases,live)
            _,before=read(c,"FSc Part 1",scope,contracts.programme_aliases,live)
            _,other=read(c,"MDCAT",scope,contracts.programme_aliases,live)
            if 1501 not in [r[0] for r in before] or 1501 not in [r[0] for r in other]:
                raise RuntimeError("SHARED_CANONICAL_MEMBERSHIP_NOT_PRESENT")
            pinned_compare(c,("FSc Part 1","MDCAT"),scope,contracts,live,helper)
        stats={"fresh":0,"dirty":0,"parity_checks":0}
        def readers(seed):
            local={"fresh":0,"dirty":0,"parity_checks":0}
            with closing(connection()) as c:
                for _ in range(12):
                    fresh,n=pinned_compare(c,("FSc Part 1","MDCAT"),scope,contracts,live,helper)
                    local["fresh" if fresh else "dirty"]+=1
                    local["parity_checks"]+=n
                    time.sleep(.005 if seed%2 else .009)
            return local
        def writer():
            with closing(connection()) as c:
                def mutate(statement,params=()):
                    c.execute("BEGIN IMMEDIATE")
                    try:
                        c.execute(statement,params)
                        c.commit()
                    except Exception:
                        c.rollback()
                        raise
                    time.sleep(.01)
                # Revoke only MDCAT; canonical PH item must remain FSc eligible.
                mutate("""UPDATE integration_ph_product_activation_authorizations
                  SET activation_status='REVOKED' WHERE release_id='R-MDCAT'""")
                if 1501 in native_ids(c,"MDCAT",scope,contracts,live):
                    raise RuntimeError("REVOKED_MDCAT_LEAK")
                if 1501 not in native_ids(c,"FSc Part 1",scope,contracts,live):
                    raise RuntimeError("REVOCATION_CROSSMARKET_LEAK")
                rebuild(c,scope,contracts.programme_aliases,live)
                mutate("""INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e
                  VALUES('R-FSC','1','PH-Q::alpha::1','PH-V::beta::1')""")
                if 1501 in native_ids(c,"FSc Part 1",scope,contracts,live):
                    raise RuntimeError("WITHDRAWN_FSC_LEAK")
                rebuild(c,scope,contracts.programme_aliases,live)
                mutate("UPDATE questions SET ph_question_checksum_sha256='CORRUPT' WHERE id=1505")
                rebuild(c,scope,contracts.programme_aliases,live)
                mutate("UPDATE question_families SET active=0 WHERE family_key='FAM-1506'")
                rebuild(c,scope,contracts.programme_aliases,live)
                # Restoring all authorities must restore *separate* programme sets.
                c.execute("BEGIN IMMEDIATE")
                try:
                    c.execute("""UPDATE integration_ph_product_activation_authorizations
                     SET activation_status='ACTIVATED' WHERE release_id='R-MDCAT'""")
                    c.execute("DELETE FROM ph_bridge_staged_withdrawal_exclusions_v6611e WHERE release_id='R-FSC'")
                    c.execute("UPDATE questions SET ph_question_checksum_sha256='CHECKSUM-5' WHERE id=1505")
                    c.execute("UPDATE question_families SET active=1 WHERE family_key='FAM-1506'")
                    c.commit()
                except Exception:
                    c.rollback()
                    raise
                rebuild(c,scope,contracts.programme_aliases,live)
                original=c.execute("SELECT epoch,dirty,snapshot_epoch FROM sm_shadow_visibility_authority").fetchone()
                c.execute("BEGIN IMMEDIATE")
                c.execute("UPDATE questions SET review_status='Draft' WHERE id=1507")
                c.rollback()
                after=c.execute("SELECT epoch,dirty,snapshot_epoch FROM sm_shadow_visibility_authority").fetchone()
                if tuple(original)!=tuple(after):
                    raise RuntimeError("ROLLED_BACK_GOVERNANCE_BROKE_SHADOW_EPOCH")
                if 1501 not in native_ids(c,"FSc Part 1",scope,contracts,live) or 1501 not in native_ids(c,"MDCAT",scope,contracts,live):
                    raise RuntimeError("RESTORE_DID_NOT_REAUTHORIZE_BOTH")
            return {"mutations":5,"rebuilds":5,"restore":True,"rollback_safe":True}
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures=[executor.submit(readers,1),executor.submit(readers,2),executor.submit(writer)]
            observations=[f.result() for f in futures]
        for item in observations[:2]:
            for k in stats:stats[k]+=item[k]
        with closing(connection()) as c:
            good,checked=pinned_compare(c,("FSc Part 1","MDCAT"),scope,contracts,live,helper)
            if not good:raise RuntimeError("FINAL_VISIBILITY_NOT_FRESH")
            if 1501 not in native_ids(c,"FSc Part 1",scope,contracts,live) or 1501 not in native_ids(c,"MDCAT",scope,contracts,live):
                raise RuntimeError("FINAL_SHARED_MEMBER_NOT_AUTHORIZED")
            ci=c.execute("PRAGMA integrity_check").fetchone()[0]
            if ci!="ok":raise RuntimeError("DB_INTEGRITY_CHECK_FAILED:"+ci)
        print("SCOREMAX_CONCURRENT_GOVERNANCE_REHEARSAL_PASS="+json.dumps({
            "fixture":"disposable_3000_synthetic_legacy_PH_1500_shared_PH_members",
            "native_programme_scope":True,"native_family_and_guided_release_gate":True,
            "formal_independent_practice_dependency":mastery,
            "reader_transactions":sum(stats[k] for k in ("fresh","dirty")),
            "programme_parity_checks":stats["parity_checks"]+checked,
            "writer":observations[2],"wal_readers":2,
            "sqlite_integrity":"ok","production_touched":False,
            "real_ph_receipts_tested":False,
            "actual_grade_submit_ack_tested":False,
            "scale_50_http_qualified":False,
        },sort_keys=True),flush=True)

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("USAGE: script <generated_runtime_root>")
    main(Path(sys.argv[1]))
