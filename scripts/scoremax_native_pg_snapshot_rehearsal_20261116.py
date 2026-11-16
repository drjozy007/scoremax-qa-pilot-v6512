"""Data-exact, all-or-nothing ScoreMax SQLite -> PostgreSQL snapshot rehearsal.

DISPOSABLE CI ONLY. Never a live migrator or an application Postgres backend.
Copies critical columns and *stored values* from a generated native ScoreMax
SQLite database into queryable, typed PostgreSQL staging tables. Independently
compares a multiset SHA256 of every row, field and type, count and primary-key
population before commit. A simulated mid-import failure must roll back the
entire schema. No real questions, learners, receipts or production credentials.

Cutover remains BLOCKED: SQL functions/collation, all tables, sequences, unique
indexes, constraints, app reads/writes, signed PH roundtrip, backup and replay
are NOT ported by this isolated migration rehearsal.
"""
from __future__ import annotations

import base64
from contextlib import closing
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import uuid

from psycopg import connect, sql

TABLES = (
    "users", "questions", "question_families",
    "assessment_sessions", "attempts", "attempt_answers",
    "mastery_records", "mastery_form_results", "mastery_history",
    "integration_ph_question_version_store",
    "integration_ph_release_question_membership",
    "integration_ph_content_releases",
    "integration_ph_product_activation_authorizations",
    "ph_bridge_staged_withdrawal_exclusions_v6611e",
    "integration_outbox", "integration_receipts",
)
IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
SCHEMA_PREFIX = "sm_snapshot_rehearsal_"

# These exact-once boundaries are already enforced by SQLite. Do not call an
# imported PostgreSQL database safe if they are absent after source conversion.
CRITICAL_UNIQUES={
    "attempts":("assessment_session_id",),
    "integration_outbox":("contract_name","idempotency_key"),
}


def declared_type(value):
    """Explicitly map SQLite affinity, never make guessed application semantics."""
    t = str(value or "").upper().strip()
    if not t:
        return "TEXT", "UNTYPED"
    if "INT" in t or t in ("BOOLEAN", "BOOL"):
        return "BIGINT", "INTEGER"
    if "CHAR" in t or "CLOB" in t or "TEXT" in t or "JSON" in t or "DATE" in t or "TIME" in t:
        return "TEXT", "TEXT"
    if "BLOB" in t:
        return "BYTEA", "BLOB"
    if "REAL" in t or "FLOA" in t or "DOUB" in t:
        return "DOUBLE PRECISION", "REAL"
    if "NUM" in t or "DEC" in t:
        return "NUMERIC", "NUMERIC"
    raise RuntimeError("UNKNOWN_SQLITE_AFFINITY:" + t)


def normalize(value, affinity):
    if value is None:
        return ["null", None]
    if affinity == "INTEGER":
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeError("INTEGER_VALUE_AFFINITY_DRIFT")
        return ["int", str(value)]
    if affinity == "REAL":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RuntimeError("REAL_VALUE_AFFINITY_DRIFT")
        f = float(value)
        if not math.isfinite(f):
            raise RuntimeError("NONFINITE_REAL_NOT_MIGRATABLE")
        return ["real", format(f, ".17g")]
    if affinity == "NUMERIC":
        try:
            d = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise RuntimeError("NUMERIC_VALUE_AFFINITY_DRIFT")
        if not d.is_finite():
            raise RuntimeError("NONFINITE_NUMERIC_NOT_MIGRATABLE")
        return ["numeric", str(d.normalize())]
    if affinity == "BLOB":
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise RuntimeError("BLOB_VALUE_AFFINITY_DRIFT")
        return ["blob", base64.b64encode(bytes(value)).decode("ascii")]
    if not isinstance(value, str):
        raise RuntimeError("TEXT_VALUE_AFFINITY_DRIFT")
    return ["text", value]


def fingerprint_rows(rows, schema):
    row_hashes = []
    for record in rows:
        ordered = [normalize(value, info["affinity"])
                   for value, info in zip(record, schema)]
        canonical = json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
        row_hashes.append(hashlib.sha256(canonical.encode("utf-8")).digest())
    row_hashes.sort()
    combined = hashlib.sha256()
    for digest in row_hashes:
        combined.update(digest)
    return len(row_hashes), combined.hexdigest()


def schema_for(conn, table):
    if not IDENT.fullmatch(table):
        raise RuntimeError("INVALID_TABLE_NAME")
    entry = conn.execute("""SELECT type,sql FROM sqlite_master
              WHERE name=? AND type='table'""", (table,)).fetchone()
    if not entry:
        raise RuntimeError("REQUIRED_SOURCE_TABLE_MISSING:" + table)
    if "VIRTUAL TABLE" in str(entry[1] or "").upper():
        raise RuntimeError("VIRTUAL_TABLE_NOT_SUPPORTED:" + table)
    raw = conn.execute("PRAGMA table_info(" + '"' + table + '"' + ")").fetchall()
    if not raw:
        raise RuntimeError("SOURCE_TABLE_EMPTY_SCHEMA:" + table)
    columns = []
    names = set()
    for cid, name, dtype, required, default, pk_rank in raw:
        if not IDENT.fullmatch(name) or name in names:
            raise RuntimeError("AMBIGUOUS_COLUMN_NAME:" + table)
        names.add(name)
        target_type, affinity = declared_type(dtype)
        columns.append({"name": name, "sqlite_declared": dtype,
            "postgres_type": target_type, "affinity": affinity,
            "primary_key_rank": int(pk_rank), "sqlite_notnull": bool(required)})
    if not any(info["primary_key_rank"] for info in columns):
        raise RuntimeError("CORE_TABLE_LACKS_STABLE_PRIMARY_KEY:" + table)
    return columns



def source_has_strict_unique(conn,table,expected):
    """Require an actual unconditional SQLite BINARY unique index."""
    indices=conn.execute('PRAGMA index_list("'+table+'")').fetchall()
    for index in indices:
        # sequence, name, unique, origin, partial
        if not index[2]:
            continue
        name=index[1]
        if index[4]:
            # SQLite uses a partial unique index for session identity.
            # PostgreSQL plain UNIQUE has the same NULL-distinctness on
            # this specific one-column key. Accept only this exact source
            # predicate, never arbitrary partial indexes.
            defined=conn.execute("SELECT sql FROM sqlite_master WHERE name=? AND type='index'",
                                 (name,)).fetchone()
            ddl=(defined[0] or "") if defined else ""
            if (tuple(expected)!=("assessment_session_id",) or
                re.search(r"\bWHERE\s+assessment_session_id\s+IS\s+NOT\s+NULL\s*$",
                          ddl,re.I) is None):
                continue
        key_cols=[(row[2],row[4])
                  for row in conn.execute('PRAGMA index_xinfo("'+name+'")')
                  if row[5]]
        if tuple(x[0] for x in key_cols)==tuple(expected) and all(
            c=="BINARY" for _,c in key_cols):
            return True
    return False


def enforce_staging_uniqueness(pg,source,namespace,table,columns):
    fields=CRITICAL_UNIQUES.get(table)
    if fields is None:
        return False
    if not source_has_strict_unique(source,table,fields):
        # Only source schema metadata, no students or answer values.
        discovered=[]
        for _,index_name,unique,*remaining in source.execute(
                'PRAGMA index_list("'+table+'")').fetchall():
            detail=[{"field":r[2],"collation":r[4],"key":r[5]} for r
                    in source.execute('PRAGMA index_xinfo("'+index_name+'")').fetchall()]
            discovered.append({"name":index_name,"unique":bool(unique),
                "metadata":remaining,"keys":detail})
        raise RuntimeError("NATIVE_EXACT_ONCE_UNIQUE_INDEX_MISSING:"+table+
                           ":METADATA="+repr(discovered))
    index_name="sm_rehearsal_unique_"+table
    data_types={x["name"]:x["postgres_type"] for x in columns}
    col_spec=sql.SQL(",").join(
        sql.SQL("{} COLLATE {}").format(sql.Identifier(x),sql.Identifier("C"))
        if data_types.get(x)=="TEXT" else sql.Identifier(x)
        for x in fields)
    pg.execute(sql.SQL("CREATE UNIQUE INDEX {} ON {}.{} ({})").format(
        sql.Identifier(index_name),sql.Identifier(namespace),
        sql.Identifier(table),col_spec))
    # Make duplicate-value re-insertion fail while the candidate import is
    # still in a transaction. This probes the ACTUAL PostgreSQL constraint.
    all_names=[x["name"] for x in columns]
    real=pg.execute(sql.SQL("SELECT {} FROM {}.{} WHERE {} LIMIT 1").format(
       sql.SQL(",").join(sql.Identifier(x) for x in all_names),
       sql.Identifier(namespace),sql.Identifier(table),
       sql.SQL(" AND ").join(
           sql.SQL("{} IS NOT NULL").format(sql.Identifier(x)) for x in fields)
       )).fetchone()
    if real is None:
        raise RuntimeError("NATIVE_EXACT_ONCE_KEY_FIXTURE_NOT_EXERCISED:"+table)
    copy_row=list(real)
    pk=[x for x in columns if x["primary_key_rank"]>0]
    if len(pk)!=1 or pk[0]["postgres_type"]!="BIGINT":
        raise RuntimeError("EXACT_ONCE_TEST_NEEDS_SINGLE_INTEGER_PRIMARY_KEY:"+table)
    pk_i=all_names.index(pk[0]["name"])
    maximum=pg.execute(sql.SQL("SELECT MAX({}) FROM {}.{}").format(
       sql.Identifier(pk[0]["name"]),sql.Identifier(namespace),
       sql.Identifier(table))).fetchone()[0]
    copy_row[pk_i]=int(maximum)+1000000
    statement=sql.SQL("INSERT INTO {}.{} ({}) VALUES ({})").format(
       sql.Identifier(namespace),sql.Identifier(table),
       sql.SQL(",").join(sql.Identifier(x) for x in all_names),
       sql.SQL(",").join(sql.Placeholder() for _ in all_names))
    from psycopg.errors import UniqueViolation
    try:
        with pg.transaction():
            pg.execute(statement,tuple(copy_row))
    except UniqueViolation:
        pass
    else:
        raise RuntimeError("POSTGRES_EXACT_ONCE_INDEX_NOT_ENFORCED:"+table)
    return True


def qualify_native_pg_programme_membership(pg,src,namespace):
    """Compare actual accepted SQLite governance with a bounded PG port.

    This is ONLY an FSc/MDCAT shared-canonical fixture query. It does NOT
    implement the full native application SQL or its marking/rights policy.
    """
    import question_contract_engine as contracts
    from scoremax_governed_visibility_relational_probe_20261115 import native_scope
    from scoremax_persistent_shadow_visibility_candidate_20261115 import native_live
    root=Path(__file__).resolve().parents[1]/"scoremax_runtime_v669b"
    if not (root/"app.py").is_file():
        raise RuntimeError("NATIVE_GENERATED_RUNTIME_NOT_AVAILABLE")
    source_scope=native_scope(root)
    source_live=native_live(root)
    src.create_function("scoremax_release_programme",2,
                        contracts.programme_for_release,deterministic=True)
    query=sql.SQL("""SELECT DISTINCT q.id FROM {}.questions q
      JOIN {}.question_families family
        ON family.family_key=q.family_key AND family.active=1
      JOIN {}.integration_ph_question_version_store pv
        ON pv.local_question_db_id=q.id
       AND pv.question_id=q.ph_question_id
       AND pv.question_version_id=q.ph_question_version_id
       AND pv.question_checksum_sha256=q.ph_question_checksum_sha256
      JOIN {}.integration_ph_release_question_membership membership
        ON membership.question_id=pv.question_id
       AND membership.question_version_id=pv.question_version_id
      JOIN {}.integration_ph_content_releases release
        ON release.release_id=membership.release_id
       AND release.release_version=membership.release_version
      JOIN {}.integration_ph_product_activation_authorizations auth
        ON auth.release_id=release.release_id
       AND auth.release_version=release.release_version
       AND auth.package_checksum_sha256=release.package_checksum_sha256
      WHERE q.ph_projection_owner='POWER_HOUSE' AND q.active=1
        AND q.ph_question_id=%s AND release.programme_id=%s
        AND release.local_status='ACTIVE'
        AND auth.activation_status IN ('AUTHORIZED','ACTIVATED')
        AND NOT EXISTS(SELECT 1 FROM
            {}.ph_bridge_staged_withdrawal_exclusions_v6611e ex
          WHERE ex.release_id=membership.release_id
            AND ex.release_version=membership.release_version
            AND ex.question_id=membership.question_id
            AND ex.question_version_id=membership.question_version_id)
      ORDER BY q.id""").format(*([sql.Identifier(namespace)]*7))
    specimen="SYN-PG-PH-CANONICAL-Q"
    results={}
    for programme,release_programme in (("FSc Part 1","FSC_PART_I"),("MDCAT","MDCAT")):
        clause,arguments=source_scope(contracts.programme_aliases(programme),"q")
        expected=[x[0] for x in src.execute("SELECT q.id FROM questions q WHERE "
            +source_live+" AND "+clause+" AND q.ph_question_id=? ORDER BY q.id",
            arguments+[specimen]).fetchall()]
        actual=[x[0] for x in pg.execute(
            query,(specimen,release_programme)).fetchall()]
        if expected!=actual or len(expected)!=1:
            raise RuntimeError("NATIVE_TO_POSTGRES_PH_SCOPE_DRIFT:"+programme+
                ":"+repr((expected,actual)))
        results[programme]=len(actual)
    class _RollbackProbe(Exception):
        pass
    try:
        with pg.transaction():
            pg.execute(sql.SQL("""UPDATE {}.integration_ph_product_activation_authorizations
                  SET activation_status='REVOKED'
                  WHERE release_id='SYN-PG-PH-RELEASE-MDCAT'""").format(
                  sql.Identifier(namespace)))
            mdcat=[r[0] for r in pg.execute(query,(specimen,"MDCAT"))]
            fsc=[r[0] for r in pg.execute(query,(specimen,"FSC_PART_I"))]
            if mdcat or len(fsc)!=1:
                raise RuntimeError("POSTGRES_CROSS_PROGRAMME_AUTHORITY_ISOLATION_DRIFT")
            raise _RollbackProbe()
    except _RollbackProbe:
        pass
    # Revoke is rolled back, and the canonical question still belongs to
    # both authorised products through distinct programme memberships.
    if len(pg.execute(query,(specimen,"MDCAT")).fetchall())!=1:
        raise RuntimeError("STAGED_AUTHORITY_REVOKE_ROLLBACK_FAILED")
    return {"native_vs_pg_fsc_mdcat_exact_ids":True,
            "cross_programme_authorisation_revocation_isolated":True,
            "revocation_transaction_rolled_back":True,
            "synthetic_programme_counts":results,
            "full_scoremax_sql_ported":False}


def staging_source_snapshot(source):
    if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(Path("/tmp")):
        raise RuntimeError("DISPOSABLE_TMP_SQLITE_ONLY")
    conn = sqlite3.connect(source.resolve().as_uri() + "?mode=ro",
                           uri=True, isolation_level=None, timeout=8)
    conn.execute("PRAGMA query_only=ON")
    conn.execute("BEGIN")
    version = conn.execute("PRAGMA data_version").fetchone()[0]
    return conn, version


def create_target(pg, namespace, table, fields):
    integer_pk=[x for x in fields if x["primary_key_rank"] and
                x["sqlite_declared"].strip().upper()=="INTEGER"]
    definitions = [sql.SQL("{} {}").format(
        sql.Identifier(x["name"]),
        sql.SQL("BIGINT GENERATED BY DEFAULT AS IDENTITY")
        if x in integer_pk else sql.SQL(x["postgres_type"]))
        for x in fields]
    primary = sorted(
        (x["primary_key_rank"], x["name"]) for x in fields
        if x["primary_key_rank"])
    definitions.append(sql.SQL("PRIMARY KEY ({})").format(
        sql.SQL(",").join(sql.Identifier(name) for _, name in primary)))
    pg.execute(sql.SQL("CREATE TABLE {}.{} ({})").format(
        sql.Identifier(namespace), sql.Identifier(table),
        sql.SQL(",").join(definitions)))


def restore_identity_sequence(pg,source,namespace,table,columns):
    """Never let a migrated insert reuse a deleted SQLite AUTOINCREMENT ID."""
    matches=[x for x in columns if x["primary_key_rank"]==1
             and x["sqlite_declared"].strip().upper()=="INTEGER"]
    if len(matches)!=1:
        return None
    col=matches[0]["name"]
    sqlite_max=source.execute('SELECT COALESCE(MAX("'+col+'"),0) FROM "'+
                             table+'"').fetchone()[0]
    seq=None
    if source.execute("""SELECT name FROM sqlite_master
                         WHERE type='table' AND name='sqlite_sequence'""").fetchone():
        seen=source.execute("SELECT seq FROM sqlite_sequence WHERE name=?",
                            (table,)).fetchone()
        seq=int(seen[0]) if seen else None
    next_id=max(int(sqlite_max or 0),int(seq or 0))+1
    if next_id<=0 or next_id>=9223372036854775807:
        raise RuntimeError("UNSAFE_POSTGRES_NEXT_ID:"+table)
    pg.execute(sql.SQL("ALTER TABLE {}.{} ALTER COLUMN {} RESTART WITH {}").format(
        sql.Identifier(namespace),sql.Identifier(table),
        sql.Identifier(col),sql.Literal(next_id)))
    if table=="attempts":
        # Live application inserts without explicit IDs; assert a fresh
        # insert would receive a safe ID, then roll it back without altering
        # the migrated staging dataset.
        class _ProbeRollback(Exception):pass
        try:
            with pg.transaction():
                created=pg.execute(sql.SQL(
                    "INSERT INTO {}.{} (assessment_session_id) VALUES (NULL) RETURNING {}"
                    ).format(sql.Identifier(namespace),
                      sql.Identifier(table),sql.Identifier(col))).fetchone()[0]
                if int(created)!=next_id:
                    raise RuntimeError("POSTGRES_SEQUENCE_WOULD_REUSE_ATTEMPT_ID")
                raise _ProbeRollback()
        except _ProbeRollback:
            pass
        after=pg.execute(sql.SQL("SELECT COUNT(*) FROM {}.{}").format(
            sql.Identifier(namespace),sql.Identifier(table))).fetchone()[0]
        original=source.execute('SELECT COUNT(*) FROM "'+table+'"').fetchone()[0]
        if after!=original:
            raise RuntimeError("ID_PROBE_DAMAGED_COPIED_LEDGER")
    return {"column":col,"next_id":next_id,
            "source_sqlite_sequence":seq,
            "source_max_id":int(sqlite_max or 0)}


def source_records(conn, table, fields):
    names = ",".join('"' + x["name"] + '"' for x in fields)
    cur = conn.execute('SELECT ' + names + ' FROM "' + table + '"')
    while True:
        batch = cur.fetchmany(250)
        if not batch:
            break
        for row in batch:
            yield tuple(row)


def perform_copy(source, dsn, inject_failure=False, inject_corruption=False):
    if "127.0.0.1" not in dsn and "localhost" not in dsn:
        raise RuntimeError("EPHEMERAL_LOCAL_POSTGRES_ONLY")
    if os.environ.get("SCOREMAX_EPHEMERAL_PG_REHEARSAL") != "1":
        raise RuntimeError("EXPLICIT_EPHEMERAL_MIGRATION_OPTIN_REQUIRED")
    reader, first_version = staging_source_snapshot(source)
    namespace = SCHEMA_PREFIX + uuid.uuid4().hex[:12]
    result = {}
    try:
        with closing(connect(dsn, connect_timeout=8)) as pg:
            with pg.transaction():
                name = pg.execute("SELECT current_database()").fetchone()[0]
                if name != "scoremax_contract":
                    raise RuntimeError("UNAPPROVED_POSTGRES_TEST_DATABASE")
                pg.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))
                for index, table in enumerate(TABLES):
                    fields = schema_for(reader, table)
                    create_target(pg, namespace, table, fields)
                    names = [field["name"] for field in fields]
                    source_data = list(source_records(reader, table, fields))
                    expected_count, expected_sha = fingerprint_rows(source_data, fields)
                    if source_data:
                        command = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
                            sql.Identifier(namespace), sql.Identifier(table),
                            sql.SQL(",").join(sql.Identifier(n) for n in names))
                        with pg.cursor().copy(command) as copy:
                            for values in source_data:
                                # Raw SQLite storage classes only; no academic
                                # field values or identities are rewritten.
                                copy.write_row(values)
                    projection = sql.SQL("SELECT {} FROM {}.{}").format(
                        sql.SQL(",").join(sql.Identifier(n) for n in names),
                        sql.Identifier(namespace), sql.Identifier(table))
                    if inject_corruption and table=="questions":
                        # Tamper a real copied field to test the HASH gate.
                        # Never touch the immutable SQLite source.
                        pg.execute(sql.SQL("""UPDATE {}.{} SET question=%s
                               WHERE id=(SELECT MIN(id) FROM {}.{})""").format(
                               sql.Identifier(namespace),sql.Identifier(table),
                               sql.Identifier(namespace),sql.Identifier(table)),
                               ("SYNTHETIC_CORRUPTION_INJECTION",))
                    actual_data = pg.execute(projection).fetchall()
                    actual_count, actual_sha = fingerprint_rows(actual_data, fields)
                    if (actual_count, actual_sha) != (expected_count, expected_sha):
                        raise RuntimeError("MIGRATED_SOURCE_RECORD_MISMATCH:" + table)
                    unique_enforced=enforce_staging_uniqueness(
                        pg,reader,namespace,table,fields)
                    identity=restore_identity_sequence(
                        pg,reader,namespace,table,fields)
                    result[table] = {
                        "critical_unique_enforced":unique_enforced,
                        "identity_continuation":identity,
                        "rows": expected_count,
                        "columns": len(fields),
                        "row_fingerprint": expected_sha[:16],
                        "primary_key_fields": [n for _, n in sorted(
                            (x["primary_key_rank"], x["name"]) for x in fields
                            if x["primary_key_rank"])],
                    }
                    if inject_failure and index == 3:
                        raise RuntimeError("INJECTED_MID_MIGRATION_FAILURE")
                native_scope_proof=qualify_native_pg_programme_membership(
                    pg,reader,namespace)
                final_version = reader.execute("PRAGMA data_version").fetchone()[0]
                if final_version != first_version:
                    raise RuntimeError("SOURCE_CHANGED_DURING_SNAPSHOT")
                if not result.get("attempt_answers") or not result.get("mastery_records"):
                    raise RuntimeError("MISSING_PROTECTED_LEDGER_CHECKS")
                for required in ("questions","users","question_families",
                                 "assessment_sessions","attempts","attempt_answers",
                                 "integration_ph_content_releases",
                                 "integration_ph_question_version_store",
                                 "integration_ph_release_question_membership",
                                 "integration_ph_product_activation_authorizations",
                                 "integration_outbox","integration_receipts",
                                 "mastery_records","mastery_form_results","mastery_history",
                                 "ph_bridge_staged_withdrawal_exclusions_v6611e"):
                    if result[required]["rows"]<1:
                        raise RuntimeError("UNEXERCISED_NATIVE_CORE_LEDGER:"+required)
                # Source snapshot remains pinned while staging checks pass.
                # Committing the target is safe only in this disposable test.
            if inject_failure:
                raise RuntimeError("EXPECTED_INJECTED_ROLLBACK_WAS_NOT_RAISED")
            return namespace, result, native_scope_proof
    finally:
        reader.rollback()
        reader.close()


def main():
    if len(sys.argv) != 2:
        raise SystemExit("USAGE: script <disposable_native_sqlite_path>")
    path = Path(sys.argv[1])
    dsn = os.environ.get("SCOREMAX_EPHEMERAL_POSTGRES_DSN", "")
    # Deliberately inject a failure after several tables are loaded, and
    # require PostgreSQL to roll back all DDL and data in the transaction.
    try:
        perform_copy(path, dsn, inject_failure=True)
    except RuntimeError as ex:
        if str(ex) != "INJECTED_MID_MIGRATION_FAILURE":
            raise
    else:
        raise RuntimeError("NO_ATOMIC_MIGRATION_ROLLBACK")
    # Deliberate corrupted destination row must reject and roll back the
    # entire PostgreSQL migration, not merely log a checksum discrepancy.
    try:
        perform_copy(path, dsn, inject_corruption=True)
    except RuntimeError as ex:
        if str(ex)!="MIGRATED_SOURCE_RECORD_MISMATCH:questions":
            raise
    else:
        raise RuntimeError("CORRUPTED_POSTGRES_ROW_PASSED_MIGRATION")
    namespace, report, native_scope_proof = perform_copy(path, dsn)
    with closing(connect(dsn, connect_timeout=8)) as pg:
        tables = pg.execute("""SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema=%s""", (namespace,)).fetchone()[0]
        if tables != len(TABLES):
            raise RuntimeError("MIGRATION_STAGING_SCHEMA_INCOMPLETE")
        pg.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(
            sql.Identifier(namespace)))
        pg.commit()
        remaining = pg.execute("""SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema=%s""", (namespace,)).fetchone()[0]
        if remaining:
            raise RuntimeError("DISPOSABLE_TARGET_CLEANUP_FAILED")
    print("SCOREMAX_POSTGRES_NATIVE_LEDGER_SNAPSHOT_PASS="+json.dumps({
        "source":"genuine_generated_ScoreMax_SQLite_disposable_synthetic",
        "source_path_private":True,
        "protected_tables":len(TABLES),
        "source_row_count":sum(x["rows"] for x in report.values()),
        "tables":report,
        "source_to_pg_each_value_sha256_equal":True,
        "native_saved_submission_and_frozen_answer_migrated":True,
        "source_PK_identity_preserved":True,
        "attempt_and_outbox_exact_once_indexes_enforced":True,
        "native_sqlite_identity_watermark_continuation_tested":True,
        "native_vs_pg_governed_fsc_mdcat_fixture":native_scope_proof,
        "all_or_nothing_injected_rollback":True,
        "destination_row_tamper_rejected_and_rolled_back":True,
        "temporary_schema_cleaned":True,
        "production_data_accessed":False,
        "real_scoremax_postgres_application_enabled":False,
        "signed_PH_end_to_end_migrated":False,
        "all_app_sql_translated":False,
        "cutover_ready":False,
    },sort_keys=True),flush=True)


if __name__ == "__main__":
    main()
