"""Adversarial native ScoreMax cutover safety preflight, disposable only.

Reports source schema coverage and demonstrates why SQLite WAL snapshot plus
PRAGMA data_version does NOT mean source writers are frozen. Exercises an
isolated scratch DB for concurrency. This is a NO-GO detector, NOT a
PostgreSQL application migration or a production write-lock implementation.
"""
from __future__ import annotations
from contextlib import closing
import ast
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

def copied_tables_from_source():
    # Read the migration manifest without importing its psycopg runtime.
    # Audit tools must not depend on a database adapter merely to inspect
    # a source file; missing manifests fail before any readiness claim.
    script=Path(__file__).with_name("scoremax_native_pg_snapshot_rehearsal_20261116.py")
    parsed=ast.parse(script.read_text(encoding="utf8"))
    for node in parsed.body:
        if isinstance(node,ast.Assign) and any(
            isinstance(target,ast.Name) and target.id=="TABLES"
            for target in node.targets):
            tables=ast.literal_eval(node.value)
            if not isinstance(tables,tuple) or not all(
                isinstance(t,str) for t in tables):
                raise RuntimeError("INVALID_POSTGRES_COVERAGE_MANIFEST")
            return tables
    raise RuntimeError("MISSING_POSTGRES_COVERAGE_MANIFEST")


TABLES=copied_tables_from_source()


def writer_fence_rehearsal():
    with tempfile.TemporaryDirectory(prefix="sm-cutover-fence-") as td:
        path=Path(td)/"scratch.db"
        with closing(sqlite3.connect(path,isolation_level=None)) as init:
            init.execute("PRAGMA journal_mode=WAL")
            init.execute("CREATE TABLE versioned (id INTEGER PRIMARY KEY, authority TEXT)")
            init.execute("INSERT INTO versioned VALUES(1,'ACTIVE')")
        reader=sqlite3.connect(path,isolation_level=None,timeout=.2)
        writer=sqlite3.connect(path,isolation_level=None,timeout=.1)
        try:
            reader.execute("BEGIN")
            initial=reader.execute("SELECT authority FROM versioned WHERE id=1").fetchone()[0]
            v_before=reader.execute("PRAGMA data_version").fetchone()[0]
            writer.execute("UPDATE versioned SET authority='WITHDRAWN' WHERE id=1")
            old=reader.execute("SELECT authority FROM versioned WHERE id=1").fetchone()[0]
            v_after=reader.execute("PRAGMA data_version").fetchone()[0]
            current=writer.execute("SELECT authority FROM versioned WHERE id=1").fetchone()[0]
            if (initial,old,current)!=("ACTIVE","ACTIVE","WITHDRAWN"):
                raise RuntimeError("CUTOVER_SNAPSHOT_BLIND_SPOT_NOT_REPRODUCED")
            if v_before!=v_after:
                raise RuntimeError("DATA_VERSION_WAS_NOT_PINNED_DURING_READ_TXN")
            reader.rollback()
            now=reader.execute("PRAGMA data_version").fetchone()[0]
            if now==v_before:
                raise RuntimeError("DATA_VERSION_NOT_VISIBLE_AFTER_READER_END")
            # A properly established exclusive writer boundary must prevent
            # subsequent concurrent SQLite writes before snapshot/copy.
            reader.execute("BEGIN IMMEDIATE")
            locked=reader.execute("SELECT authority FROM versioned WHERE id=1").fetchone()[0]
            if locked!="WITHDRAWN":
                raise RuntimeError("WRITER_FENCE_WRONG_START_STATE")
            blocked=False
            try:
                writer.execute("UPDATE versioned SET authority='ACTIVE' WHERE id=1")
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower():
                    raise
                blocked=True
            if not blocked:
                raise RuntimeError("SQLITE_CONCURRENT_WRITER_NOT_FENCED")
            reader.rollback()
            writer.execute("UPDATE versioned SET authority='ACTIVE' WHERE id=1")
            recovered=reader.execute("SELECT authority FROM versioned WHERE id=1").fetchone()[0]
            if recovered!="ACTIVE":
                raise RuntimeError("WRITER_DID_NOT_RECOVER_AFTER_UNLOCK")
            return {"sqlite_pinned_snapshot_misses_concurrent_commit":True,
                    "pragma_data_version_unchanged_inside_read_transaction":True,
                    "data_version_changes_only_after_snapshot_end":True,
                    "begin_immediate_blocks_later_writers":True,
                    "post_fence_writes_can_resume":True,
                    "production_writer_fence_installed":False}
        finally:
            reader.close()
            writer.close()


def audit_schema(path):
    path=Path(path).resolve()
    if path.is_symlink() or not path.is_file() or not path.is_relative_to(Path("/tmp")):
        raise RuntimeError("CUTOVER_SCHEMA_AUDIT_DISPOSABLE_ONLY")
    with closing(sqlite3.connect(path.as_uri()+"?mode=ro",uri=True)) as c:
        c.execute("PRAGMA query_only=ON")
        c.execute("BEGIN")
        rows=c.execute("""SELECT name,type,COALESCE(sql,'') FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%' AND type IN ('table','view','trigger','index')
            ORDER BY type,name""").fetchall()
        tables=[(n,s) for n,t,s in rows if t=="table"]
        names={n for n,_ in tables}
        missing=[n for n in TABLES if n not in names]
        if missing:raise RuntimeError("PROTECTED_NATIVE_TABLE_MISSING:"+repr(missing))
        extra=sorted(names.difference(TABLES))
        protected_indexes=0
        protected_user_defined_indexes=0
        protected_autoindexes=0
        protected_partial_indexes=0
        protected_expression_indexes=0
        protected_triggers=[]
        for name,kind,ddl in rows:
            if kind=="trigger" and any(
                    (' ON "'+table+'"') in ddl or (' ON '+table+' ') in ddl
                    for table in TABLES):
                protected_triggers.append(name)
        live_nonempty=[]
        check_count=0
        triggers=0
        unique_count=0
        partial_indexes=0
        expression_indexes=0
        foreign_keys=0
        virtual=[]
        for table,ddl in tables:
            if "VIRTUAL TABLE" in ddl.upper():virtual.append(table)
            if table in extra:
                try:
                    if c.execute('SELECT 1 FROM "'+table.replace('"','""')+'" LIMIT 1').fetchone():
                        live_nonempty.append(table)
                except sqlite3.DatabaseError:
                    raise RuntimeError("SCHEMA_UNMIGRATED_TABLE_UNREADABLE:"+table)
            check_count+=ddl.upper().count("CHECK(")+ddl.upper().count("CHECK (")
            indexes=c.execute('PRAGMA index_list("'+table.replace('"','""')+'")').fetchall()
            for row in indexes:
                unique_count+=int(bool(row[2]))
                partial_indexes+=int(bool(row[4]))
                detail=c.execute('PRAGMA index_xinfo("'+row[1].replace('"','""')+'")').fetchall()
                is_expression=any(x[2] is None and x[5] for x in detail)
                expression_indexes+=int(is_expression)
                if table in TABLES:
                    protected_indexes+=1
                    protected_user_defined_indexes+=int(row[3]=="c")
                    protected_autoindexes+=int(row[3] in ("pk","u"))
                    protected_partial_indexes+=int(bool(row[4]))
                    protected_expression_indexes+=int(is_expression)
            foreign_keys+=len(c.execute(
                'PRAGMA foreign_key_list("'+table.replace('"','""')+'")').fetchall())
        views=[n for n,t,_ in rows if t=="view"]
        triggers=[n for n,t,_ in rows if t=="trigger"]
        if not extra:
            raise RuntimeError("FULL_SCHEMA_GAP_FIXTURE_INCONCLUSIVE")
        return {
            "source_tables_total":len(tables),
            "protected_table_source_indexes":protected_indexes,
            "protected_table_user_defined_indexes":protected_user_defined_indexes,
            "protected_table_primary_or_unique_autoindexes":protected_autoindexes,
            "protected_table_partial_indexes":protected_partial_indexes,
            "protected_table_expression_indexes":protected_expression_indexes,
            "protected_table_attached_triggers":protected_triggers[:24],
            "copy_prototype_restores_only_primary_and_two_critical_unique_indexes":True,
            "unverified_user_defined_index_definitions":max(
                0,protected_user_defined_indexes-2),
            "unported_source_trigger_count":len(triggers),
            "restored_source_trigger_count":0,
            "source_schema_is_complete_in_pg":False,
            "protected_copy_tables":len(TABLES),
            "not_copied_tables":len(extra),
            "unmigrated_nonempty_table_count":len(live_nonempty),
            "unmigrated_nonempty_table_examples":live_nonempty[:28],
            "unmigrated_table_examples":extra[:28],
            "source_views_count":len(views),
            "source_triggers_count":len(triggers),
            "source_unique_indexes_count":unique_count,
            "source_partial_indexes_count":partial_indexes,
            "source_expression_indexes_count":expression_indexes,
            "source_foreign_keys_count":foreign_keys,
            "source_check_clause_approx_count":check_count,
            "virtual_tables":virtual[:20],
            "all_source_schema_objects_migrated":False,
            "all_academic_read_write_paths_migrated":False,
            "postgres_cutover_ready":False,
        }


def main():
    if len(sys.argv) not in (2,3) or (len(sys.argv)==3 and sys.argv[2]!="--assert-ready"):
        raise SystemExit("USAGE: script <disposable_native_sqlite_db> [--assert-ready]")
    report=audit_schema(Path(sys.argv[1]))
    lock=writer_fence_rehearsal()
    print("SCOREMAX_SCHEMA_MIGRATION_COVERAGE_GAP="+json.dumps(
        report,sort_keys=True),flush=True)
    print("SCOREMAX_CUTOVER_WRITER_BLINDSPOT_REPRODUCED="+json.dumps(
        lock,sort_keys=True),flush=True)
    if (report["not_copied_tables"]==0 or
        report["unmigrated_nonempty_table_count"]==0 or
        not lock["sqlite_pinned_snapshot_misses_concurrent_commit"]):
        raise RuntimeError("CUTOVER_PRECHECK_NO_GO_NOT_DEMONSTRATED")
    if len(sys.argv)==3 and sys.argv[2]=="--assert-ready":
        # Release-blocking by design until full native SQL, schema and
        # write-epoch/fencing proof exist. Do not set false pass flags.
        if (report["not_copied_tables"]!=0 or
            report["unverified_user_defined_index_definitions"]!=0 or
            report["unported_source_trigger_count"]!=0 or
            not lock["production_writer_fence_installed"] or
            not report["all_source_schema_objects_migrated"] or
            not report["all_academic_read_write_paths_migrated"]):
            raise RuntimeError("P0_FULL_SCHEMA_CUTOVER_NOT_QUALIFIED:"
                +str(report["not_copied_tables"])+" unmigrated tables; "
                +str(report["unmigrated_nonempty_table_count"])+" nonempty; "
                +str(report["unverified_user_defined_index_definitions"])
                +" unverified declared index definitions; "
                +str(report["unported_source_trigger_count"])
                +" native triggers not ported; no production writer fence")


if __name__=="__main__":main()
