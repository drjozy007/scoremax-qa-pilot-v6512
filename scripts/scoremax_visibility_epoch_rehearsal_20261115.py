"""Disposable transactional cache-invalidation rehearsal for ScoreMax PH eligibility.

NOT a production migration or deployed read cache. Validates an architecture
requirement: every mutation of governed eligibility inputs invalidates a
derived visibility snapshot atomically; read transactions fall back to the
native authoritative predicates until a reconciled refresh commits.

Includes question/family edits, PH membership, version/checksum, release
status, authorisation and withdrawal. All data is synthetic and in-memory.
"""
from __future__ import annotations
import json
import sqlite3
import sys
from pathlib import Path
from scoremax_governed_visibility_relational_probe_20261115 import fixture,native_scope,candidate_sql

WATCHED=(
 "questions",
 "question_families",
 "integration_ph_question_version_store",
 "integration_ph_release_question_membership",
 "integration_ph_content_releases",
 "integration_ph_product_activation_authorizations",
 "ph_bridge_staged_withdrawal_exclusions_v6611e",
)
PROGRAMMES=("FSc Part 1","FSc Part 2","MDCAT","ECAT")
def init(c):
    c.executescript("""
      ALTER TABLE questions ADD COLUMN family_key TEXT;
      CREATE TABLE question_families(family_key TEXT PRIMARY KEY,review_status TEXT,active INTEGER);
      UPDATE questions SET family_key='FAM-'||id;
      INSERT INTO question_families
        SELECT family_key,'Approved',1 FROM questions;
      CREATE TABLE sm_visibility_authority_epoch(id INTEGER PRIMARY KEY CHECK(id=1),epoch INTEGER NOT NULL);
      INSERT INTO sm_visibility_authority_epoch VALUES(1,0);
      CREATE TABLE sm_visibility_snapshot_epoch(id INTEGER PRIMARY KEY CHECK(id=1),epoch INTEGER NOT NULL);
      INSERT INTO sm_visibility_snapshot_epoch VALUES(1,-1);
      CREATE TABLE sm_visibility_snapshot(programme TEXT NOT NULL,question_id INTEGER NOT NULL,
        PRIMARY KEY(programme,question_id));
    """)
    for table in WATCHED:
        for event in ("INSERT","UPDATE","DELETE"):
            name=f"sm_probe_invalidate_{table}_{event.lower()}"
            c.execute(f"""CREATE TRIGGER {name} AFTER {event} ON {table}
            BEGIN UPDATE sm_visibility_authority_epoch SET epoch=epoch+1 WHERE id=1; END""")
    c.commit()

def family_fence(alias="q"):
    return f"""COALESCE({alias}.family_key,'')<>''
      AND EXISTS (SELECT 1 FROM question_families qf
      WHERE qf.family_key={alias}.family_key AND qf.review_status='Approved'
        AND COALESCE(qf.active,0)=1)"""

def authoritative(c,scope,aliases):
    where,args=scope(aliases,"q")
    return [r[0] for r in c.execute(
        "SELECT q.id FROM questions q WHERE "+where+" AND "+family_fence()+" ORDER BY q.id",args)]

def candidate(c,aliases):
    sql,args=candidate_sql(aliases)
    return [r[0] for r in c.execute(
        "SELECT q.id FROM ("+sql+") selected JOIN questions q ON q.id=selected.id WHERE "+
        family_fence()+" ORDER BY q.id",args)]

def refresh(c,scope,contracts):
    # Everything, including the source epoch, is read in the same write
    # transaction. A different connection's mutator cannot interleave.
    c.execute("BEGIN IMMEDIATE")
    try:
        source_epoch=c.execute("SELECT epoch FROM sm_visibility_authority_epoch WHERE id=1").fetchone()[0]
        populations=[]
        for programme in PROGRAMMES:
            aliases=contracts.programme_aliases(programme)
            expected=authoritative(c,scope,aliases)
            actual=candidate(c,aliases)
            if expected!=actual:raise RuntimeError("REFRESH_GOVERNANCE_PARITY_FAILED:"+programme)
            populations.extend((programme,qid) for qid in actual)
        c.execute("DELETE FROM sm_visibility_snapshot")
        c.executemany("INSERT INTO sm_visibility_snapshot VALUES(?,?)",populations)
        c.execute("UPDATE sm_visibility_snapshot_epoch SET epoch=? WHERE id=1",(source_epoch,))
        c.commit()
    except Exception:
        c.rollback()
        raise

def read(c,programme,scope,contracts):
    # One SQLite snapshot pins epoch check + rows to the same source state.
    c.execute("BEGIN")
    try:
        epoch=c.execute("SELECT epoch FROM sm_visibility_authority_epoch WHERE id=1").fetchone()[0]
        snapshot=c.execute("SELECT epoch FROM sm_visibility_snapshot_epoch WHERE id=1").fetchone()[0]
        aliases=contracts.programme_aliases(programme)
        if epoch==snapshot:
            result=[r[0] for r in c.execute(
                "SELECT question_id FROM sm_visibility_snapshot WHERE programme=? ORDER BY question_id",
                (programme,))]
            origin="CACHE"
        else:
            result=authoritative(c,scope,aliases)
            origin="AUTHORITATIVE_FALLBACK"
        expected=authoritative(c,scope,aliases)
        if result!=expected:raise RuntimeError("STALE_VISIBILITY_LEAK:"+programme)
        c.commit()
        return origin,result,epoch,snapshot
    except Exception:
        c.rollback()
        raise

def main(root):
    sys.path.insert(0,str(root))
    import question_contract_engine as contracts
    scope=native_scope(root)
    c=fixture()
    c.create_function("scoremax_release_programme",2,contracts.programme_for_release,deterministic=True)
    init(c)
    totals={"cache":0,"fallback":0,"scenarios":0}
    def test(label,wanted):
        origins=set()
        for programme in PROGRAMMES:
            origin,questions,epoch,snapshot=read(c,programme,scope,contracts)
            origins.add(origin)
            totals["cache" if origin=="CACHE" else "fallback"]+=1
        if origins!={wanted}:raise RuntimeError("PROJECTION_STALE_STATUS_INCORRECT:"+label+":"+repr(origins))
        totals["scenarios"]+=1
        print("SCOREMAX_VISIBILITY_EPOCH_REHEARSAL="+json.dumps({
            "scenario":label,"reader":wanted,"native_equivalence":True,
            "production_mutation":False,"durable_projection_implemented":False
        },sort_keys=True),flush=True)
    try:
        test("no_projection","AUTHORITATIVE_FALLBACK")
        refresh(c,scope,contracts);test("initial_reconciled_projection","CACHE")
        c.execute("""INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e
          VALUES('R-FSC','1','PH-Q::alpha::1','PH-V::beta::1')""")
        c.commit()
        test("withdrawal_invalidates","AUTHORITATIVE_FALLBACK")
        refresh(c,scope,contracts);test("withdrawal_rebuilt","CACHE")
        c.execute("UPDATE integration_ph_product_activation_authorizations SET activation_status='REVOKED' WHERE release_id='R-MDCAT'")
        c.commit();test("revocation_invalidates","AUTHORITATIVE_FALLBACK")
        refresh(c,scope,contracts);test("revocation_rebuilt","CACHE")
        c.execute("UPDATE question_families SET active=0 WHERE family_key='FAM-1502'")
        c.commit();test("family_approval_invalidates","AUTHORITATIVE_FALLBACK")
        refresh(c,scope,contracts);test("family_approval_rebuilt","CACHE")
        c.execute("UPDATE questions SET ph_question_checksum_sha256='INVALID' WHERE id=1503")
        c.commit();test("question_version_checksum_invalidates","AUTHORITATIVE_FALLBACK")
        refresh(c,scope,contracts);test("question_version_checksum_rebuilt","CACHE")
        c.execute("UPDATE integration_ph_content_releases SET local_status='STAGED' WHERE release_id='R-FSC'")
        c.commit();test("release_status_invalidates","AUTHORITATIVE_FALLBACK")
        refresh(c,scope,contracts);test("release_status_rebuilt","CACHE")
        # Crash/rollback cannot leave the cache epoch and source disagreeing.
        c.execute("BEGIN")
        c.execute("UPDATE question_families SET active=0 WHERE family_key='FAM-1504'")
        c.rollback()
        test("rolled_back_source_mutation_keeps_valid_projection","CACHE")
        c.execute("BEGIN IMMEDIATE")
        c.execute("DELETE FROM sm_visibility_snapshot")
        c.execute("UPDATE sm_visibility_snapshot_epoch SET epoch=-1")
        c.rollback()
        test("interrupted_projection_rebuild_rolls_back_atomically","CACHE")
        c.execute("UPDATE integration_ph_release_question_membership SET question_version_id='INVALID' WHERE release_id='R-MDCAT' AND question_id='PH-Q::alpha::5'")
        c.commit();test("membership_edit_invalidates","AUTHORITATIVE_FALLBACK")
        refresh(c,scope,contracts);test("membership_edit_rebuilt","CACHE")
        c.execute("UPDATE integration_ph_question_version_store SET question_checksum_sha256='BAD' WHERE question_id='PH-Q::alpha::6'")
        c.commit();test("version_store_edit_invalidates","AUTHORITATIVE_FALLBACK")
        refresh(c,scope,contracts);test("version_store_rebuilt","CACHE")
        print("SCOREMAX_VISIBILITY_INVALIDATION_REHEARSAL_PASS="+json.dumps({
            "scenarios":totals["scenarios"],"reads_from_cache":totals["cache"],
            "reads_from_authoritative_fallback":totals["fallback"],
            "source_tables_watched":list(WATCHED),
            "rollback_atomicity":True,"runtime_modified":False,
            "production_database_touched":False,"materialized_projection_deployed":False
        },sort_keys=True),flush=True)
    finally:c.close()

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Usage: script <generated_runtime_root>")
    main(Path(sys.argv[1]).resolve())
