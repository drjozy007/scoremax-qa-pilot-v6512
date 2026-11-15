"""Disposable-only persistent governed visibility projection qualification.

This extends the existing native ScoreMax SQLite/PHAUTH contract, not another
source of academic authority. A persisted derived question visibility table is
refreshed under BEGIN IMMEDIATE, validates against the native reader, and is
usable only if the source-dirty epoch matches the published snapshot epoch.

Every source-table mutation dirties the snapshot in its own transaction.
No app/runtime routing, production DB, Render, Power House or user state changes.
This module is intentionally NOT installed or called by production startup.
"""
from __future__ import annotations
import ast
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
from time import perf_counter
from statistics import median

from scoremax_visibility_epoch_rehearsal_20261115 import WATCHED, family_fence
from scoremax_governed_visibility_relational_probe_20261115 import native_scope,fixture

PROGRAMMES=("FSc Part 1","FSc Part 2","MDCAT","ECAT")
SCHEMA_MARK="SCOREMAX_SHADOW_VISIBILITY_PROJECTION_20261115"

def native_live(root:Path):
    path=root/"app.py"
    tree=ast.parse(path.read_text(encoding="utf8"))
    nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="live_question_clause"]
    if not nodes:raise RuntimeError("SHADOW_NATIVE_LIVE_CLAUSE_MISSING")
    # Accepted ScoreMax wraps the original family approval gate with a
    # guided/self-marking release fence. Reconstruct the two source functions
    # in their actual definition order, including the captured original
    # binding; do not accidentally test only the earlier weaker definition.
    nodes=sorted(nodes,key=lambda n:n.lineno)
    source=path.read_text(encoding="utf8")
    if len(nodes)!=2:raise RuntimeError("SHADOW_LIVE_WRAPPER_CARDINALITY_DRIFT")
    base=ast.get_source_segment(source,nodes[0]) or ""
    wrapper=ast.get_source_segment(source,nodes[1]) or ""
    for token in ("question_families","review_status","active","is_demo"):
        if token not in base:raise RuntimeError("SHADOW_SOURCE_LIVE_POLICY_DRIFT:"+token)
    for token in ("_self_marking_original_live_question_clause_v2",
                  "ph_is_auto_markable","guided_self_assessment"):
        if token not in wrapper:raise RuntimeError("SHADOW_GUIDED_RELEASE_FENCE_DRIFT:"+token)
    ns={"SCOREMAX_ENV":"production"}
    exec(compile(ast.Module(body=[nodes[0]],type_ignores=[]),str(path),"exec"),ns)
    ns["_self_marking_original_live_question_clause_v2"]=ns["live_question_clause"]
    exec(compile(ast.Module(body=[nodes[1]],type_ignores=[]),str(path),"exec"),ns)
    return ns["live_question_clause"]("q")

def install(conn):
    # Disposable fixture only. Real deployment would require a separately
    # verified migration manifest and full existing writer coverage.
    if conn.in_transaction:conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.executescript("""CREATE TABLE IF NOT EXISTS sm_shadow_visibility_authority(
          id INTEGER PRIMARY KEY CHECK(id=1),
          epoch INTEGER NOT NULL DEFAULT 0,
          dirty INTEGER NOT NULL CHECK(dirty IN (0,1)) DEFAULT 1,
          snapshot_epoch INTEGER NOT NULL DEFAULT -1);
        INSERT OR IGNORE INTO sm_shadow_visibility_authority(id,epoch,dirty,snapshot_epoch)
          VALUES(1,0,1,-1);
        CREATE TABLE IF NOT EXISTS sm_shadow_visibility_member(
          programme TEXT NOT NULL,
          question_db_id INTEGER NOT NULL,
          subject TEXT,
          chapter TEXT,
          PRIMARY KEY(programme,question_db_id));
        CREATE INDEX IF NOT EXISTS sm_shadow_visibility_lookup
          ON sm_shadow_visibility_member(programme,subject,chapter,question_db_id);
        """)
        # SQLite executescript() may commit transaction; installation is
        # disposable-only. Refresh/read operations below use explicit txn.
        for table in WATCHED:
            for action in ("INSERT","UPDATE","DELETE"):
                name="sm_shadow_dirty_"+table+"_"+action.lower()
                conn.execute(f"""CREATE TRIGGER IF NOT EXISTS {name} AFTER {action}
                    ON {table}
                    BEGIN
                    UPDATE sm_shadow_visibility_authority
                    SET epoch=epoch+1,dirty=1
                    WHERE id=1 AND dirty=0;
                    END""")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    trigger_count=conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'sm_shadow_dirty_%'").fetchone()[0]
    if trigger_count != len(WATCHED)*3:raise RuntimeError("SHADOW_TRIGGER_SET_INCOMPLETE")
    return trigger_count

def native_rows(conn,programme,scope,aliases,live):
    clause,args=scope(aliases(programme),"q")
    return [(r["id"],r["subject"],r["chapter"]) for r in conn.execute(
        "SELECT q.id,q.subject,q.chapter FROM questions q WHERE "+live+" AND "+clause+" ORDER BY q.id",args).fetchall()]

def rebuild(conn,scope,aliases,live):
    if conn.in_transaction:raise RuntimeError("SHADOW_REBUILD_REQUIRES_EXTERNAL_TXN_CLOSED")
    start=perf_counter()
    conn.execute("BEGIN IMMEDIATE")
    try:
        epoch,dirty=conn.execute("SELECT epoch,dirty FROM sm_shadow_visibility_authority WHERE id=1").fetchone()
        conn.execute("DELETE FROM sm_shadow_visibility_member")
        sizes={}
        for programme in PROGRAMMES:
            rows=native_rows(conn,programme,scope,aliases,live)
            conn.executemany(
                "INSERT INTO sm_shadow_visibility_member(programme,question_db_id,subject,chapter) VALUES(?,?,?,?)",
                [(programme,*r) for r in rows])
            snapshot=[(r["question_db_id"],r["subject"],r["chapter"]) for r in
                conn.execute("SELECT question_db_id,subject,chapter FROM sm_shadow_visibility_member WHERE programme=? ORDER BY question_db_id",
                (programme,)).fetchall()]
            if rows != snapshot:
                raise RuntimeError("SHADOW_REBUILD_NATIVE_DRIFT:"+programme)
            sizes[programme]=len(rows)
        conn.execute("UPDATE sm_shadow_visibility_authority SET snapshot_epoch=?,dirty=0 WHERE id=1",(epoch,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"epoch":epoch,"sizes":sizes,"rebuild_ms":round((perf_counter()-start)*1000,3)}

def read(conn,programme,scope,aliases,live):
    # Explicit read transaction pins the epoch and fetched rows to one
    # immutable SQLite snapshot even when another writer commits concurrently.
    if conn.in_transaction:raise RuntimeError("SHADOW_READ_REQUIRES_EXTERNAL_TXN_CLOSED")
    conn.execute("BEGIN")
    try:
        state=conn.execute("SELECT epoch,dirty,snapshot_epoch FROM sm_shadow_visibility_authority WHERE id=1").fetchone()
        fresh=(state["dirty"]==0 and state["epoch"]==state["snapshot_epoch"])
        if fresh:
            rows=[(r["question_db_id"],r["subject"],r["chapter"]) for r in conn.execute(
                "SELECT question_db_id,subject,chapter FROM sm_shadow_visibility_member WHERE programme=? ORDER BY question_db_id",
                (programme,))]
            route="SHADOW"
        else:
            rows=native_rows(conn,programme,scope,aliases,live)
            route="AUTHORITATIVE_FALLBACK"
        conn.commit()
        return route,rows
    except Exception:
        conn.rollback()
        raise

def source_state(conn):
    return dict(conn.execute("SELECT epoch,dirty,snapshot_epoch FROM sm_shadow_visibility_authority WHERE id=1").fetchone())

def main(root:Path):
    root=root.resolve()
    if not (root/"app.py").is_file():raise RuntimeError("ACCEPTED_RUNTIME_MISSING")
    sys.path.insert(0,str(root))
    import question_contract_engine as contracts
    scope=native_scope(root)
    live=native_live(root)
    connection=fixture()
    connection.create_function("scoremax_release_programme",2,contracts.programme_for_release,deterministic=True)
    connection.executescript("""ALTER TABLE questions ADD COLUMN family_key TEXT;
      ALTER TABLE questions ADD COLUMN subject TEXT DEFAULT 'Biology';
      ALTER TABLE questions ADD COLUMN chapter TEXT DEFAULT 'Synthetic Chapter 1';
      ALTER TABLE questions ADD COLUMN status TEXT DEFAULT 'Approved';
      ALTER TABLE questions ADD COLUMN review_status TEXT DEFAULT 'Approved';
      ALTER TABLE questions ADD COLUMN active INTEGER DEFAULT 1;
      ALTER TABLE questions ADD COLUMN is_demo INTEGER DEFAULT 0;
      ALTER TABLE questions ADD COLUMN marking_config TEXT DEFAULT '{}';
      ALTER TABLE questions ADD COLUMN ph_is_auto_markable INTEGER DEFAULT 1;
      CREATE TABLE question_families(family_key TEXT PRIMARY KEY,review_status TEXT,active INTEGER);
      UPDATE questions SET family_key='FAM-'||id;
      INSERT INTO question_families SELECT family_key,'Approved',1 FROM questions;
    """)
    try:
        triggers=install(connection)
        result=rebuild(connection,scope,contracts.programme_aliases,live)
        assert source_state(connection)["dirty"]==0
        for programme in PROGRAMMES:
            route,rows=read(connection,programme,scope,contracts.programme_aliases,live)
            assert route=="SHADOW"
            assert rows==native_rows(connection,programme,scope,contracts.programme_aliases,live)
        # First source change in one transaction increments at most once; all
        # following 1500 row changes remain dirty without 1500 state writes.
        before=source_state(connection)["epoch"]
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE questions SET review_status='Draft' WHERE id BETWEEN 1501 AND 3000")
        connection.commit()
        dirty=source_state(connection)
        if dirty["dirty"]!=1 or dirty["epoch"]!=before+1:
            raise RuntimeError("SHADOW_BULK_DIRTY_COALESCING_FAILED")
        for programme in PROGRAMMES:
            route,rows=read(connection,programme,scope,contracts.programme_aliases,live)
            assert route=="AUTHORITATIVE_FALLBACK"
            assert rows==native_rows(connection,programme,scope,contracts.programme_aliases,live)
        after=rebuild(connection,scope,contracts.programme_aliases,live)
        for programme in PROGRAMMES:
            route,rows=read(connection,programme,scope,contracts.programme_aliases,live)
            assert route=="SHADOW"
            assert rows==native_rows(connection,programme,scope,contracts.programme_aliases,live)
        # Rollback cannot invalidate an otherwise clean snapshot.
        clean=source_state(connection)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE question_families SET active=0 WHERE family_key='FAM-1'")
        connection.rollback()
        if source_state(connection)!=clean:raise RuntimeError("SHADOW_SOURCE_ROLLBACK_DIRTIED_CACHE")
        # Persist all tables/triggers across restart, then repeat the dirty
        # fallback and rebuild operations using a second SQLite connection.
        with tempfile.TemporaryDirectory(prefix="scoremax-vis-shadow-",dir="/tmp") as t:
            path=Path(t)/"disposable.db"
            with sqlite3.connect(path) as on_disk:connection.backup(on_disk)
            with closing(sqlite3.connect(path)) as disk:
                disk.row_factory=sqlite3.Row
                disk.create_function("scoremax_release_programme",2,contracts.programme_for_release,deterministic=True)
                assert source_state(disk)==clean
                disk.execute("INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e VALUES(?,?,?,?)",
                    ("R-MDCAT","1","PH-Q::alpha::1499","PH-V::beta::1499"))
                disk.commit()
                assert source_state(disk)["dirty"]==1
                origin,rows=read(disk,"MDCAT",scope,contracts.programme_aliases,live)
                assert origin=="AUTHORITATIVE_FALLBACK"
                assert rows==native_rows(disk,"MDCAT",scope,contracts.programme_aliases,live)
                rebuild(disk,scope,contracts.programme_aliases,live)
                assert read(disk,"MDCAT",scope,contracts.programme_aliases,live)[0]=="SHADOW"
        print("SCOREMAX_PERSISTENT_SHADOW_PROJECTION_PASS="+json.dumps({
          "schema":SCHEMA_MARK,"source_tables":len(WATCHED),"installed_triggers":triggers,
          "initial_sizes":result["sizes"],"post_bulk_sizes":after["sizes"],
          "bulk_update_rows":1500,"epoch_increment_for_bulk":1,
          "source_transaction_rollback_safe":True,
          "interrupted_cache_fallback_safe":True,
          "persisted_restart_recovery":True,
          "native_question_set_parity":True,
          "real_ph_fixture":False,"production_migration":False,
          "runtime_enabled":False,"production_data_touched":False
        },sort_keys=True),flush=True)
    finally:connection.close()
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Usage: script <generated_runtime_root>")
    main(Path(sys.argv[1]))
