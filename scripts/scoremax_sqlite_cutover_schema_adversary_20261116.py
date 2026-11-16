"""Adversarial native ScoreMax cutover safety preflight, disposable only.

Reports source schema coverage and demonstrates why SQLite WAL snapshot plus
PRAGMA data_version does NOT mean source writers are frozen. Exercises an
isolated scratch DB for concurrency. This is a NO-GO detector, NOT a
PostgreSQL application migration or a production write-lock implementation.
"""
from __future__ import annotations
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile

from scoremax_native_pg_snapshot_rehearsal_20261116 import TABLES


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
                expression_indexes+=int(any(x[2] is None and x[5] for x in detail))
            foreign_keys+=len(c.execute(
                'PRAGMA foreign_key_list("'+table.replace('"','""')+'")').fetchall())
        views=[n for n,t,_ in rows if t=="view"]
        triggers=[n for n,t,_ in rows if t=="trigger"]
        if not extra:
            raise RuntimeError("FULL_SCHEMA_GAP_FIXTURE_INCONCLUSIVE")
        return {
            "source_tables_total":len(tables),
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
    if len(sys.argv)!=2:
        raise SystemExit("USAGE: script <disposable_native_sqlite_db>")
    report=audit_schema(Path(sys.argv[1]))
    lock=writer_fence_rehearsal()
    print("SCOREMAX_SCHEMA_MIGRATION_COVERAGE_GAP="+json.dumps(
        report,sort_keys=True),flush=True)
    print("SCOREMAX_CUTOVER_WRITER_BLINDSPOT_REPRODUCED="+json.dumps(
        lock,sort_keys=True),flush=True)
    if report["not_copied_tables"]==0 or not lock["sqlite_pinned_snapshot_misses_concurrent_commit"]:
        raise RuntimeError("CUTOVER_PRECHECK_NO_GO_NOT_DEMONSTRATED")


if __name__=="__main__":main()
