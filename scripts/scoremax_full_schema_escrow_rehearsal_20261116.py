"""Full SQLite table/schema escrow fidelity, disposable ScoreMax -> ephemeral PostgreSQL.

This captures *every* non-internal SQLite table, with every value's original
storage class, complete declared column metadata and DDL, into a portable
text-encoded escrow. PG is just a temporary verification medium.

Not a typed PostgreSQL application schema, ORM, academic read model, trigger
port, or safe production cutover. No production files, data, or credentials.
A source writer fence/CDC and whole-app semantic port remain mandatory.
"""
from __future__ import annotations
import base64
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys
import uuid
from psycopg import connect, sql

PREFIX="sm_full_escrow_"
def canonical_value(v):
    if v is None:return ["null",None]
    if type(v) is bool:return ["int",str(int(v))]
    if type(v) is int:return ["int",str(v)]
    if type(v) is float:
        if not math.isfinite(v):raise RuntimeError("NONFINITE_NATIVE_FLOAT")
        return ["float_hex",v.hex()]
    if type(v) is str:return ["text",v]
    if isinstance(v,(bytes,bytearray,memoryview)):
        return ["blob_base64",base64.b64encode(bytes(v)).decode("ascii")]
    raise RuntimeError("UNKNOWN_SQLITE_STORAGE_CLASS:"+type(v).__name__)

def canonical_json(v):
    # Escaped ASCII JSON is safe even if source text contains embedded NUL:
    # PostgreSQL TEXT cannot store raw NUL, but "\\u0000" roundtrips.
    return json.dumps(v,ensure_ascii=True,separators=(",",":"),sort_keys=False)

def table_names(c):
    rows=c.execute("""SELECT name,sql FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name""").fetchall()
    if len(rows)<200:raise RuntimeError("NATIVE_SCHEMA_COVERAGE_SUSPICIOUSLY_LOW")
    if any("VIRTUAL TABLE" in str(ddl or "").upper() for _,ddl in rows):
        raise RuntimeError("VIRTUAL_TABLE_MIGRATION_NOT_QUALIFIED")
    return rows

def column_manifest(c,table):
    quoted='"'+table.replace('"','""')+'"'
    info=c.execute("PRAGMA table_xinfo("+quoted+")").fetchall()
    if not info:raise RuntimeError("MISSING_COLUMN_MANIFEST:"+table)
    return [{"cid":r[0],"name":r[1],"declared_type":r[2],
             "notnull":r[3],"default_sql":r[4],"pk_rank":r[5],
             "hidden":r[6]} for r in info]

def sqlite_snapshot(path):
    p=Path(path).resolve()
    if (not p.is_file() or p.is_symlink()
        or not p.is_relative_to(Path("/tmp"))):
        raise RuntimeError("REFUSE_NON_DISPOSABLE_SQLITE")
    c=sqlite3.connect(p.as_uri()+"?mode=ro",uri=True,isolation_level=None)
    c.execute("PRAGMA query_only=ON")
    c.execute("BEGIN")
    return c

def copy_source_schema_catalog(src,pg,namespace):
    """Escrow source indexes, triggers, views, SQLite PK autoindexes and ID watermarks.

    Preserve definitions as DATA, not runnable PostgreSQL DDL.
    """
    root=sql.Identifier(namespace)
    pg.execute(sql.SQL("""CREATE TABLE {}.source_objects(
        ordinal BIGINT PRIMARY KEY,payload_json TEXT NOT NULL,
        sha256 TEXT NOT NULL)""").format(root))
    statements=src.execute("""SELECT type,name,tbl_name,sql FROM sqlite_master
        WHERE type IN ('table','index','trigger','view')
        ORDER BY type,name""").fetchall()
    if len(statements)<300:
        raise RuntimeError("NATIVE_SCHEMA_OBJECTS_SUSPICIOUSLY_LOW")
    info={"user_version":src.execute("PRAGMA user_version").fetchone()[0],
          "application_id":src.execute("PRAGMA application_id").fetchone()[0],
          "encoding":src.execute("PRAGMA encoding").fetchone()[0]}
    seq_rows=[]
    if any(t=="table" and name=="sqlite_sequence" for t,name,_,_ in statements):
        seq_rows=src.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name").fetchall()
    payloads=[{"kind":"sqlite_master","record":[canonical_value(x) for x in statement]}
              for statement in statements]
    payloads.append({"kind":"header_pragmas","record":info})
    payloads.append({"kind":"sqlite_sequence",
                     "records":[[canonical_value(x) for x in r] for r in seq_rows]})
    for ordinal,item in enumerate(payloads):
        encoded=canonical_json(item)
        digest=hashlib.sha256(encoded.encode("ascii")).hexdigest()
        pg.execute(sql.SQL("""INSERT INTO {}.source_objects
            (ordinal,payload_json,sha256) VALUES(%s,%s,%s)""").format(root),
            (ordinal,encoded,digest))
    replay=pg.execute(sql.SQL("""SELECT ordinal,payload_json,sha256
           FROM {}.source_objects ORDER BY ordinal""").format(root)).fetchall()
    if len(replay)!=len(payloads):
        raise RuntimeError("SCHEMA_CATALOG_COUNT_MISMATCH")
    for ordinal,payload,digest in replay:
        if ordinal<0 or ordinal>=len(payloads) or canonical_json(payloads[ordinal])!=payload:
            raise RuntimeError("SCHEMA_CATALOG_CONTENT_MISMATCH")
        if hashlib.sha256(payload.encode("ascii")).hexdigest()!=digest:
            raise RuntimeError("SCHEMA_CATALOG_SHA_MISMATCH")
    by_type={}
    for kind,*_ in statements:
        by_type[kind]=by_type.get(kind,0)+1
    return {"native_schema_objects":len(statements),
        "escrow_schema_objects":len(statements),
        "native_object_type_census":by_type,
        "sqlite_sequence_watermarks":len(seq_rows),
        "db_header_pragmas_preserved":True,
        "sqlite_master_definitions_and_identity_watermarks_preserved":True,
        "actual_pg_indexes_triggers_or_constraints_created":False}


def copy_one(src,pg,namespace,inject=False):
    name=sql.Identifier(namespace)
    pg.execute(sql.SQL("CREATE SCHEMA {}").format(name))
    pg.execute(sql.SQL("""CREATE TABLE {}.manifest (
       table_name TEXT PRIMARY KEY, create_sql TEXT, columns_json TEXT,
       row_count BIGINT NOT NULL,row_sha256 TEXT NOT NULL)""").format(name))
    pg.execute(sql.SQL("""CREATE TABLE {}.records (
       table_name TEXT NOT NULL,ordinal BIGINT NOT NULL,
       payload_json TEXT NOT NULL,row_sha256 TEXT NOT NULL,
       PRIMARY KEY(table_name,ordinal))""").format(name))
    object_report=copy_source_schema_catalog(src,pg,namespace)
    tables=table_names(src)
    count_rows=0
    nonempty=0
    report=[]
    for table,ddl in tables:
        manifest=column_manifest(src,table)
        visible=[m for m in manifest if int(m["hidden"])!=1]
        if not visible:raise RuntimeError("NO_VISIBLE_NATIVE_COLUMNS:"+table)
        quoted_table='"'+table.replace('"','""')+'"'
        projection=",".join('"'+m["name"].replace('"','""')+'"' for m in visible)
        stream=src.execute("SELECT "+projection+" FROM "+quoted_table)
        sha=hashlib.sha256();ordinal=0
        command=sql.SQL("COPY {}.records (table_name,ordinal,payload_json,row_sha256) FROM STDIN").format(name)
        with pg.cursor().copy(command) as copier:
            while True:
                batch=stream.fetchmany(250)
                if not batch:break
                for values in batch:
                    record=canonical_json([canonical_value(v) for v in values])
                    digest=hashlib.sha256(record.encode("ascii")).hexdigest()
                    copier.write_row((table,ordinal,record,digest))
                    sha.update(bytes.fromhex(digest))
                    ordinal+=1
        before_sha=sha.hexdigest()
        pg.execute(sql.SQL("""INSERT INTO {}.manifest
          (table_name,create_sql,columns_json,row_count,row_sha256)
          VALUES(%s,%s,%s,%s,%s)""").format(name),
          (table,ddl,canonical_json(manifest),ordinal,before_sha))
        if inject and table=="questions":
            pg.execute(sql.SQL("""UPDATE {}.records SET payload_json='CORRUPTED'
              WHERE table_name=%s AND ordinal=0""").format(name),(table,))
        check=pg.execute(sql.SQL("""SELECT ordinal,payload_json,row_sha256
             FROM {}.records WHERE table_name=%s ORDER BY ordinal""").format(name),
             (table,))
        seen=hashlib.sha256()
        verified=0
        for seq,payload,stored_digest in check:
            if seq!=verified:
                raise RuntimeError("ESCROW_MISSING_RECORD:"+table)
            observed=hashlib.sha256(payload.encode("ascii")).hexdigest()
            if observed!=stored_digest:
                raise RuntimeError("ESCROW_ROW_CORRUPTED:"+table)
            seen.update(bytes.fromhex(observed))
            verified+=1
        if seen.hexdigest()!=before_sha or verified!=ordinal:
            raise RuntimeError("ESCROW_SOURCE_TO_PG_MISMATCH:"+table)
        count_rows+=ordinal
        nonempty+=int(ordinal>0)
        report.append((table,ordinal))
    target=pg.execute(sql.SQL("SELECT COUNT(*) FROM {}.manifest").format(name)).fetchone()[0]
    if target!=len(tables):
        raise RuntimeError("ESCROW_SCHEMA_MANIFEST_INCOMPLETE")
    return {**object_report,"native_tables":len(tables),"staged_tables":int(target),
            "staged_rows":count_rows,"nonempty_tables":nonempty,
            "source_schema_sql_and_columns_preserved":True,
            "source_value_types_encoded_losslessly":True,
            "all_row_digests_validated":True,
            "record_count_includes_duplicate_rows":True,
            "sample_table_counts":{n:v for n,v in report if n in (
               "questions","attempt_answers","mastery_records",
               "integration_outbox","mastery_policies","assessment_assembly_policies",
               "ph_bridge_delivery_events_v6611d","integration_worker_state")}}

def do_copy(path,dsn,corrupt=False):
    src=sqlite_snapshot(path)
    try:
        if "127.0.0.1" not in dsn and "localhost" not in dsn:
            raise RuntimeError("ONLY_EPHEMERAL_LOCAL_PG_PERMITTED")
        with closing(connect(dsn,connect_timeout=8)) as pg:
            name=pg.execute("SELECT current_database()").fetchone()[0]
            if name!="scoremax_contract":
                raise RuntimeError("REFUSE_NON_TEST_PG")
            namespace=PREFIX+uuid.uuid4().hex[:12]
            with pg.transaction():
                report=copy_one(src,pg,namespace,inject=corrupt)
            if corrupt:raise RuntimeError("INJECTED_ESCROW_CORRUPTION_NOT_CAUGHT")
            pg.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace)))
            pg.commit()
        return report
    finally:
        src.rollback()
        src.close()

def main():
    if len(sys.argv)!=2:
        raise SystemExit("USAGE: script <disposable_native_sqlite>")
    if os.environ.get("SCOREMAX_EPHEMERAL_PG_REHEARSAL")!="1":
        raise RuntimeError("EPHEMERAL_ESCROW_OPTIN_REQUIRED")
    path=Path(sys.argv[1])
    dsn=os.environ.get("SCOREMAX_EPHEMERAL_POSTGRES_DSN","")
    try:do_copy(path,dsn,corrupt=True)
    except RuntimeError as e:
        if str(e)!="ESCROW_ROW_CORRUPTED:questions":raise
    else:raise RuntimeError("MIGRATION_CORRUPTION_NOT_FAIL_CLOSED")
    report=do_copy(path,dsn)
    print("SCOREMAX_ALL_NATIVE_SCHEMA_ESCROW_PASS="+canonical_json({
       **report,"production_db_accessed":False,
       "real_native_application_pg_ported":False,
       "schema_indexes_triggers_restored":False,
       "live_writer_fence_installed":False,
       "cutover_ready":False,
       "corrupted_escrow_transaction_rejected":True
    }),flush=True)
if __name__=="__main__":main()
