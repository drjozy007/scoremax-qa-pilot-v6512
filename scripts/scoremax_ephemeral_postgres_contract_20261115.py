"""Ephemeral PostgreSQL-vs-SQLite transactional contract rehearsal.

This verifies a SHARED-DATABASE DESIGN SLICE, NOT ScoreMax PostgreSQL support.
Actual ScoreMax remains SQLite-only and must NOT be redirected at this fixture.
No real questions, students, credentials, PH receipts or production connections.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile

try:
    import psycopg
except ImportError as exc:
    raise SystemExit("EPHEMERAL_PG_CONTRACT_REQUIRES_PSYCOPG") from exc

CREATE_SQLITE = """
CREATE TABLE questions(qid TEXT PRIMARY KEY, family TEXT NOT NULL,
    ph_version TEXT NOT NULL, checksum TEXT NOT NULL,
    independence_weight REAL NOT NULL, role TEXT NOT NULL, dependency TEXT NOT NULL);
CREATE TABLE releases(release_id TEXT PRIMARY KEY,programme TEXT NOT NULL,
    status TEXT NOT NULL,authorised INTEGER NOT NULL);
CREATE TABLE members(release_id TEXT NOT NULL,qid TEXT NOT NULL,
    PRIMARY KEY(release_id,qid));
CREATE TABLE withdrawals(release_id TEXT NOT NULL,qid TEXT NOT NULL,
    PRIMARY KEY(release_id,qid));
CREATE TABLE attempts(id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL UNIQUE,student_id TEXT NOT NULL,
    programme TEXT NOT NULL,marking_status TEXT NOT NULL);
CREATE TABLE answers(attempt_id INTEGER NOT NULL,qid TEXT NOT NULL,
    marks REAL NOT NULL,formal_evidence INTEGER NOT NULL,
    PRIMARY KEY(attempt_id,qid));
CREATE TABLE outbox(event_key TEXT PRIMARY KEY,state TEXT NOT NULL);
"""
CREATE_PG = """
CREATE TEMP TABLE questions(qid TEXT PRIMARY KEY,family TEXT NOT NULL,
    ph_version TEXT NOT NULL,checksum TEXT NOT NULL,
    independence_weight DOUBLE PRECISION NOT NULL,role TEXT NOT NULL,dependency TEXT NOT NULL)
    ON COMMIT PRESERVE ROWS;
"""
# Temporary PostgreSQL tables are session-specific, so concurrent workers
# require an ephemeral persistent schema isolated inside the GitHub Actions
# disposable database, not one connection's temporary tables.
PG_SCHEMA = (
"""CREATE TABLE questions(qid TEXT PRIMARY KEY,family TEXT NOT NULL,
 ph_version TEXT NOT NULL,checksum TEXT NOT NULL,
 independence_weight DOUBLE PRECISION NOT NULL,role TEXT NOT NULL,dependency TEXT NOT NULL)""",
"""CREATE TABLE releases(release_id TEXT PRIMARY KEY,programme TEXT NOT NULL,
 status TEXT NOT NULL,authorised INTEGER NOT NULL)""",
"""CREATE TABLE members(release_id TEXT NOT NULL,qid TEXT NOT NULL,
 PRIMARY KEY(release_id,qid))""",
"""CREATE TABLE withdrawals(release_id TEXT NOT NULL,qid TEXT NOT NULL,
 PRIMARY KEY(release_id,qid))""",
"""CREATE TABLE attempts(id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 session_id TEXT NOT NULL UNIQUE,student_id TEXT NOT NULL,
 programme TEXT NOT NULL,marking_status TEXT NOT NULL)""",
"""CREATE TABLE answers(attempt_id BIGINT NOT NULL,qid TEXT NOT NULL,
 marks DOUBLE PRECISION NOT NULL,formal_evidence INTEGER NOT NULL,
 PRIMARY KEY(attempt_id,qid))""",
"""CREATE TABLE outbox(event_key TEXT PRIMARY KEY,state TEXT NOT NULL)""",
)
QUERY = """SELECT q.qid FROM questions q
 JOIN members m ON m.qid=q.qid
 JOIN releases r ON r.release_id=m.release_id
 WHERE r.programme={p} AND r.status='ACTIVE' AND r.authorised=1
 AND q.ph_version='version-A' AND q.checksum='sha-valid'
 AND NOT EXISTS(SELECT 1 FROM withdrawals w
    WHERE w.release_id=m.release_id AND w.qid=m.qid)
 GROUP BY q.qid ORDER BY q.qid"""
MASTER = """SELECT qid FROM questions WHERE independence_weight>0
 AND role='INDEPENDENT' AND dependency='NONE' ORDER BY qid"""

class Store:
    def __init__(self,kind,location):
        self.kind=kind;self.location=location
    def connect(self):
        if self.kind=="sqlite":
            c=sqlite3.connect(self.location,timeout=12,isolation_level=None)
            c.execute("PRAGMA busy_timeout=12000")
            return c
        return psycopg.connect(self.location,connect_timeout=10)
    def q(self,sql):
        return sql.replace("{p}","?" if self.kind=="sqlite" else "%s")
    def execute(self,c,sql,args=()):
        return c.execute(sql,args)
    def prepare(self):
        with closing(self.connect()) as c:
            if self.kind=="sqlite":
                c.executescript(CREATE_SQLITE)
                c.execute("PRAGMA journal_mode=WAL")
            else:
                c.execute("BEGIN")
                for name in ("outbox","answers","attempts","withdrawals",
                             "members","releases","questions"):
                    c.execute("DROP TABLE IF EXISTS "+name)
                for statement in PG_SCHEMA:c.execute(statement)
                c.commit()
            self.begin(c)
            try:
                for qid,weight,role,dependency in [
                    ("Q-SHARED",1,"INDEPENDENT","NONE"),
                    ("Q-PRACTICE",0,"DEPENDENT","SOURCE_ONLY"),
                    ("Q-VARIANT",1,"INDEPENDENT","NONE"),
                ]:
                    self.execute(c,self.q("""INSERT INTO questions
                     VALUES({p},{p},{p},{p},{p},{p},{p})"""),
                     (qid,"FAMILY-SHARED" if qid!="Q-PRACTICE" else "FAMILY-ONLY",
                      "version-A","sha-valid",weight,role,dependency))
                for release_id,programme in (("REL-FSC","FSc Part 1"),("REL-MDCAT","MDCAT")):
                    self.execute(c,self.q("INSERT INTO releases VALUES({p},{p},'ACTIVE',1)"),
                                 (release_id,programme))
                    for qid in ("Q-SHARED","Q-PRACTICE","Q-VARIANT"):
                        self.execute(c,self.q("INSERT INTO members VALUES({p},{p})"),
                                     (release_id,qid))
                c.commit()
            except Exception:c.rollback();raise
    def begin(self,c):
        if self.kind=="sqlite":c.execute("BEGIN IMMEDIATE")
        else:c.execute("BEGIN")
    def visible(self,c,programme):
        return [r[0] for r in c.execute(self.q(QUERY),(programme,)).fetchall()]
    def master(self,c):
        return [r[0] for r in c.execute(MASTER).fetchall()]
    def change_release(self,sql,args=()):
        with closing(self.connect()) as c:
            self.begin(c)
            try:
                c.execute(self.q(sql),args)
                c.commit()
            except Exception:c.rollback();raise
    def submit(self,student,session_id):
        with closing(self.connect()) as c:
            self.begin(c)
            try:
                if self.kind=="sqlite":
                    c.execute("""INSERT OR IGNORE INTO attempts
                         (session_id,student_id,programme,marking_status)
                         VALUES(?,?,'FSc Part 1','FINAL')""",(session_id,student))
                    existing=c.execute("SELECT id FROM attempts WHERE session_id=?",
                                       (session_id,)).fetchone()
                else:
                    c.execute("""INSERT INTO attempts(session_id,student_id,programme,marking_status)
                        VALUES(%s,%s,'FSc Part 1','FINAL')
                        ON CONFLICT(session_id) DO NOTHING""",(session_id,student))
                    existing=c.execute("SELECT id FROM attempts WHERE session_id=%s",
                                       (session_id,)).fetchone()
                if existing is None:raise RuntimeError("ATTEMPT_ID_MISSING")
                aid=existing[0]
                if self.kind=="sqlite":
                    c.execute("INSERT OR IGNORE INTO answers VALUES(?,?,?,?)",
                              (aid,"Q-SHARED",1,1))
                    c.execute("INSERT OR IGNORE INTO outbox VALUES(?,?)",
                              ("ACK-"+session_id,"PENDING"))
                else:
                    c.execute("""INSERT INTO answers VALUES(%s,%s,%s,%s)
                           ON CONFLICT(attempt_id,qid) DO NOTHING""",
                              (aid,"Q-SHARED",1,1))
                    c.execute("""INSERT INTO outbox VALUES(%s,%s)
                           ON CONFLICT(event_key) DO NOTHING""",
                              ("ACK-"+session_id,"PENDING"))
                c.commit()
                return aid
            except Exception:c.rollback();raise
    def census(self):
        with closing(self.connect()) as c:
            return {t:c.execute("SELECT COUNT(*) FROM "+t).fetchone()[0]
                    for t in ("attempts","answers","outbox")}
    def rollback_probe(self):
        with closing(self.connect()) as c:
            self.begin(c)
            try:
                c.execute(self.q("""INSERT INTO attempts(session_id,student_id,programme,marking_status)
                   VALUES({p},'SYN-ROLLBACK','FSc Part 1','FINAL')"""),("UNCOMMITTED-TEST",))
                raise RuntimeError("INJECTED_ROLLBACK")
            except RuntimeError:c.rollback()
            found=c.execute(self.q("SELECT COUNT(*) FROM attempts WHERE session_id={p}"),
                            ("UNCOMMITTED-TEST",)).fetchone()[0]
            if found:raise RuntimeError("PARTIAL_WRITE_SURVIVED_ROLLBACK")

def qualify(store):
    store.prepare()
    with closing(store.connect()) as c:
        initial=(store.visible(c,"FSc Part 1"),store.visible(c,"MDCAT"),store.master(c))
    if initial[0]!=initial[1] or initial[2]!=["Q-SHARED","Q-VARIANT"]:
        raise RuntimeError("SOURCE_AUTHORITY_OR_MASTERY_PARITY_WRONG")
    store.change_release("UPDATE releases SET authorised=0 WHERE release_id={p}",
                         ("REL-MDCAT",))
    with closing(store.connect()) as c:
        revoked=(store.visible(c,"FSc Part 1"),store.visible(c,"MDCAT"))
    if not revoked[0] or revoked[1]:raise RuntimeError("CROSS_PROGRAMME_REVOCATION_LEAK")
    store.change_release("UPDATE releases SET authorised=1 WHERE release_id={p}",
                         ("REL-MDCAT",))
    store.change_release("INSERT INTO withdrawals VALUES({p},{p})",
                         ("REL-FSC","Q-SHARED"))
    with closing(store.connect()) as c:
        withdrawn=(store.visible(c,"FSc Part 1"),store.visible(c,"MDCAT"))
    if "Q-SHARED" in withdrawn[0] or "Q-SHARED" not in withdrawn[1]:
        raise RuntimeError("CROSS_PROGRAMME_WITHDRAWAL_LEAK")
    store.change_release("DELETE FROM withdrawals WHERE release_id={p}",
                         ("REL-FSC",))
    store.rollback_probe()
    attempts=[("SYN-LEARNER-"+str(i%4),"SYN-SESSION-"+str(i%4))
              for i in range(32)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        ids=list(pool.map(lambda p:store.submit(*p),attempts))
    counts=store.census()
    if counts!={"attempts":4,"answers":4,"outbox":4} or len(set(ids))!=4:
        raise RuntimeError("TRANSACTIONAL_IDEMPOTENCY_BREAK:"+repr(counts))
    with closing(store.connect()) as c:
        restored=(store.visible(c,"FSc Part 1"),store.visible(c,"MDCAT"),store.master(c))
    if restored!=initial:raise RuntimeError("RESTORED_SOURCE_AUTHORITY_DRIFT")
    return {"distinct_sessions":4,"concurrent_submits":32,
        "row_census":counts,"shared_programme_revocation":True,
        "question_withdrawal_isolated":True,"practice_mastery_exclusion":True,
        "failed_transaction_rollback":True,"exactly_once_event_keys":True}


def snapshot_isolation_rehearsal(store,repeatable):
    """Show if a mid-request withdrawal changes an existing read snapshot."""
    with closing(store.connect()) as reader,closing(store.connect()) as writer:
        if store.kind=="sqlite":
            reader.execute("BEGIN")
        else:
            reader.execute("BEGIN ISOLATION LEVEL "+
              ("REPEATABLE READ" if repeatable else "READ COMMITTED"))
        initial=reader.execute("""SELECT status FROM releases
            WHERE release_id='REL-MDCAT'""").fetchone()[0]
        if initial!="ACTIVE":
            raise RuntimeError("ISOLATION_PRECONDITION_DRIFT")
        store.begin(writer)
        try:
            writer.execute(store.q("""UPDATE releases SET status='STAGED'
                WHERE release_id={p}"""),("REL-MDCAT",))
            writer.commit()
        except Exception:
            writer.rollback()
            raise
        still=reader.execute("""SELECT status FROM releases
            WHERE release_id='REL-MDCAT'""").fetchone()[0]
        reader.rollback()
    store.change_release("UPDATE releases SET status='ACTIVE' WHERE release_id={p}",
                         ("REL-MDCAT",))
    return still

def main():
    dsn=os.environ.get("SCOREMAX_EPHEMERAL_POSTGRES_DSN","")
    if "127.0.0.1" not in dsn and "localhost" not in dsn:
        raise RuntimeError("EPHEMERAL_LOCAL_POSTGRES_ONLY")
    with tempfile.TemporaryDirectory(prefix="scoremax-shared-store-test-") as td:
        sqlite_store=Store("sqlite",str(Path(td)/"scratch.sqlite"))
        postgres_store=Store("postgres",dsn)
        sqlite_result=qualify(sqlite_store)
        pg_result=qualify(postgres_store)
        if sqlite_result!=pg_result:
            raise RuntimeError("CROSS_BACKEND_TRANSACTION_RESULT_DRIFT")
        sqlite_stable=snapshot_isolation_rehearsal(sqlite_store,True)
        postgres_default=snapshot_isolation_rehearsal(postgres_store,False)
        postgres_pinned=snapshot_isolation_rehearsal(postgres_store,True)
        if (sqlite_stable!="ACTIVE" or postgres_default!="STAGED"
            or postgres_pinned!="ACTIVE"):
            raise RuntimeError("POSTGRES_GOVERNED_READ_SNAPSHOT_SEMANTICS_DRIFT:"+
                repr((sqlite_stable,postgres_default,postgres_pinned)))
        print("SCOREMAX_POSTGRES_ISOLATION_MIGRATION_GATE="+json.dumps({
            "sqlite_pinned_snapshot":True,
            "postgres_read_committed_is_not_equivalent":True,
            "postgres_repeatable_read_pins_snapshot":True,
            "real_postgres_application_transaction_layer":False,
            "cutover":"BLOCKED_UNTIL_ALL_GOVERNED_READ_TRANSACTIONS_ADAPTED"
        },sort_keys=True),flush=True)
        # Deliberate cross-dialect semantic checks. Native SQLite lower()
        # is ASCII-only, while PostgreSQL lower() follows Unicode case rules.
        # If this changes programme/subject matching, question eligibility
        # or mastery could silently drift during a migration.
        values=("BIOLOGY","Biology","FÍSICA","İSTANBUL","Mathematics","",None,"A_B")
        with closing(sqlite_store.connect()) as sq,closing(postgres_store.connect()) as pg:
            pairs=[]
            for value in values:
                before=sq.execute("SELECT lower(?)",(value,)).fetchone()[0]
                pg_native=pg.execute("SELECT lower(%s)",(value,)).fetchone()[0]
                pg_compatible=pg.execute("""SELECT translate(%s,
                    'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')""",
                    (value,)).fetchone()[0]
                if pg_compatible!=before:
                    raise RuntimeError("POSTGRES_SQLITE_ASCII_LOWER_PARITY_FAILED:"+repr(value))
                pairs.append({"value":value,"sqlite_lower":before,
                    "postgres_lower":pg_native,"compatible_lower":pg_compatible,
                    "native_dialect_mismatch":before!=pg_native})
            differences=[x["value"] for x in pairs if x["native_dialect_mismatch"]]
            if "FÍSICA" not in differences:
                raise RuntimeError("DIALECT_DIFFERENCE_FIXTURE_DID_NOT_DETECT_UNICODE")
            # Preserve NULL and text ordering behavior in the future SQL
            # adapter; simple casefold/lower substitution is NOT sufficient.
            native_null=[r[0] for r in sq.execute(
                "SELECT v FROM (SELECT NULL AS v UNION ALL SELECT 'X' AS v) ORDER BY v")]
            pg_null=[r[0] for r in pg.execute(
                "SELECT v FROM (SELECT NULL::text AS v UNION ALL SELECT 'X'::text AS v) t ORDER BY v")]
            if native_null==pg_null:
                raise RuntimeError("DIALECT_NULL_ORDER_FIXTURE_INCONCLUSIVE")
        print("SCOREMAX_POSTGRES_DIALECT_MIGRATION_GATE="+json.dumps({
            "source":"real_ephemeral_SQLite_and_Postgres16",
            "cases":pairs,
            "native_unicode_lower_mismatch_detected":True,
            "ascii_lower_compatibility_query_passed":True,
            "native_null_sort_difference_detected":True,
            "application_queries_translated":False,
            "full_scoremax_migration_ready":False,
            "cutover":"BLOCKED_UNTIL_ALL_NATIVE_QUERY_SEMANTICS_MAPPED"
        },sort_keys=True),flush=True)
        print("SCOREMAX_SHARED_STORE_CONTRACT_PASS="+json.dumps({
            "result":"SYNTHETIC_TRANSACTION_PARITY_PASS",
            "backend_a":"sqlite_disposable",
            "backend_b":"postgres_ephemeral_actions_service",
            "details":sqlite_result,
            "real_scoremax_sql_migrated":False,
            "source_question_parity_tested":False,
            "real_signed_PH_ACK_tested":False,
            "production_db_changed":False,
            "postgres_production_ready":False,
        },sort_keys=True),flush=True)
if __name__=="__main__":main()
