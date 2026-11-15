"""Isolated end-to-end ScoreMax Flask route benchmark, baseline vs candidate.

No production credentials or data. Each invocation is a separate Python process
to prevent module/cache contamination. The caller copies the same synthetic
SQLite database for each variant; no ScoreMax deployment or network requests.
"""
import argparse
import hashlib
import gzip
import json
import os
from pathlib import Path
import sqlite3
import sys
from time import perf_counter
from statistics import median

parser=argparse.ArgumentParser()
parser.add_argument("mode",choices=["seed","measure"])
parser.add_argument("runtime",type=Path)
parser.add_argument("database",type=Path)
parser.add_argument("--label",default="baseline")
parser.add_argument("--per-chapter",type=int,default=20)
parser.add_argument("--additional-learners",type=int,default=0)
parser.add_argument("--answers-per-learner",type=int,default=100)
parser.add_argument("--profile",action="store_true")
parser.add_argument("--sql-profile",action="store_true")
parser.add_argument("--candidate-indexes",action="store_true")
parser.add_argument("--prepare-shadow-after-startup",action="store_true")
args=parser.parse_args()

# Optional disposable-only SQL instrumentation. Never injected in production.
_sql_profile={}
_sql_examples={}
if args.sql_profile and args.mode=="measure":
    _original_connect=sqlite3.connect
    class TimedConnection(sqlite3.Connection):
        def execute(self, statement, parameters=(), /):
            start=perf_counter()
            try:
                return super().execute(statement,parameters)
            finally:
                elapsed=(perf_counter()-start)*1000
                normalized=" ".join(str(statement).split())
                # Group identical query shapes; the SQL contains only synthetic
                # fixture query structure, never learner answers or credentials.
                fingerprint=normalized[:500]
                prev=_sql_profile.setdefault(fingerprint,[0,0.0])
                prev[0]+=1
                prev[1]+=elapsed
                if normalized.upper().startswith(('SELECT ','WITH ')) and fingerprint not in _sql_examples:
                    _sql_examples[fingerprint]=(str(statement),tuple(parameters))
    def profiled_connect(*a,**k):
        k.setdefault("factory",TimedConnection)
        return _original_connect(*a,**k)
    sqlite3.connect=profiled_connect

root=args.database.parent.parent.resolve()
for name in ("state","backup","intake"):
    (root/name).mkdir(parents=True,exist_ok=True)
os.environ.update({
    "SCOREMAX_ENV":"production",
    "SCOREMAX_SECRET":"navigation-isolated-synthetic-secret-2026-not-for-production",
    "SCOREMAX_STAGING_SESSION_SECRET":"synthetic-stage-20261114",
    "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"synthetic-only-admin-secret-20261114",
    "SCOREMAX_BOOTSTRAP_ADMIN_EMAIL":"synthetic-admin@scoremax.invalid",
    "SCOREMAX_SMTP_HOST":"smtp.invalid",
    "SCOREMAX_SMTP_FROM":"test@scoremax.invalid",
    "SCOREMAX_SEND_EMAIL_VERIFICATION":"0",
    "SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
    "SCOREMAX_PUBLIC_STUDENT_OPENING":"0",
    "SCOREMAX_ENFORCE_PAYWALL":"0",
    "SCOREMAX_INTERNAL_FULL_ACCESS":"0",
    "SCOREMAX_DB":str(args.database.resolve()),
    "SCOREMAX_PERSISTENT_ROOT":str(root),
    "SCOREMAX_BACKUP_DIR":str(root/"backup"),
    "SCOREMAX_CONTENT_INTAKE_DIR":str(root/"intake"),
    "SCOREMAX_INSTANCE_COUNT":"1",
    "WEB_CONCURRENCY":"1",
    "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
})
sys.path.insert(0,str(args.runtime.resolve()))
import scoremax_production
sm=scoremax_production.scoremax
app=scoremax_production.application

STUDENT="SYN-STUDENT-NAV-PERF"
if args.mode=="seed":
    c=sm.db()
    uid=c.execute("""INSERT INTO users(role,system_user_id,full_name,email,username,password_hash,account_status,
        email_verified,is_demo_account,academic_level,active_programme,subjects)
        VALUES('student',?,?,?,?,?,'active',1,0,'FSc Part 1','FSc Part 1',?)""",
        (STUDENT,"Synthetic Navigation Student","perf@scoremax.invalid","perf-nav",
         "not-a-real-hash","Biology,Chemistry,Physics,Mathematics")).lastrowid
    columns={row[1] for row in c.execute("PRAGMA table_info(questions)")}
    for subject in ("Biology","Chemistry","Physics","Mathematics"):
        for chapter_n in range(1,13):
            chapter="Synthetic Chapter "+str(chapter_n)
            family_cache={}
            for n in range(args.per_chapter):
                key=f"SYN-{subject}-{chapter_n}-{n}"
                family=f"SYN-FAMILY-{subject}-{chapter_n}-{n%20}"
                q=dict(question_id=key,family_id=family,country="Pakistan",
                       qualification="FSc Part 1",programme="FSc Part 1",
                       subject=subject,chapter=chapter,topic="Synthetic Topic",
                       qtype="single_choice",level="Foundation",question="Synthetic question only",
                       option_a="A",option_b="B",option_c="C",option_d="D",answer="A",
                       status="Approved",review_status="Approved",active=1,is_demo=0,
                       source_type="ISOLATED_SYNTHETIC_TEST")
                if family not in family_cache:
                    family_cache[family]=sm.upsert_question_family(c,q,review_status="Approved",active=1)
                q["family_key"]=family_cache[family]
                item={k:v for k,v in q.items() if k in columns}
                c.execute("INSERT INTO questions("+",".join(item)+") VALUES("+",".join("?" for _ in item)+")",tuple(item.values()))
    attempt_id=c.execute("INSERT INTO attempts(student_id,scope,programme,subject,score,total_count,correct_count) VALUES (?,?,?,?,?,?,?)",
              (uid,"subject","FSc Part 1","Biology",70,240,168)).lastrowid
    # Frozen FINAL evidence is the governed learner-navigation hot path. Earlier
    # synthetic seeds inserted unanswered/unfinalised rows, giving a misleading
    # estimate of actual per-student evidence validation work.
    source_rows=c.execute(
        "SELECT id,subject,chapter,topic,family_id,level FROM questions "
        "WHERE subject='Biology' ORDER BY id LIMIT 2400").fetchall()
    answer_rows=[]
    for i,q in enumerate(source_rows):
        context={"schema":"SM-EVIDENCE-CONTEXT-1","question_db_id":q["id"],
                 "programme":"FSc Part 1","subject":q["subject"],"chapter":q["chapter"],
                 "topic":q["topic"],"family_id":q["family_id"],"level":q["level"]}
        context["checksum_sha256"]=hashlib.sha256(
            sm.integration_v1.canonical_json(context).encode()).hexdigest()
        correct=int(i%3!=0)
        answer_rows.append((attempt_id,q["id"],"A",correct,"FINAL",1,correct,
                            json.dumps(context,sort_keys=True,separators=(",",":"))))
    c.execute("UPDATE attempts SET marking_status='FINAL',mastery_evidence_eligible=1,"
              "guided_mode=0,assessment_kind='practice' WHERE id=?",(attempt_id,))
    c.executemany(
        "INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,"
        "marking_status,mastery_evidence_eligible,marks_awarded,evidence_context_json)"
        " VALUES (?,?,?,?,?,?,?,?)",answer_rows)
    c.commit()
    eligible=sm.learner_answer_evidence(c,uid,"FSc Part 1")
    if len(eligible)!=len(answer_rows) or any(
        row["context_authority"]!="FROZEN_CONTEXT" for row in eligible):
        raise RuntimeError("BENCHMARK_FINAL_EVIDENCE_NOT_QUALIFIED")
    # Scale the database with distinct learners and their own FINAL attempts.
    # No copied production identities, question wording, or learner records.
    others=args.additional_learners
    sample_size=args.answers_per_learner
    if others<0 or sample_size<0 or sample_size>len(source_rows):
        raise RuntimeError("INVALID_SYNTHETIC_LEARNER_SCALE")
    sample_answers=[tuple(row[1:]) for row in answer_rows[:sample_size]]
    for student_n in range(others):
        synthetic_id="SYN-STUDENT-SCALE-"+str(student_n)
        other_uid=c.execute("""INSERT INTO users(role,system_user_id,full_name,email,
            username,password_hash,account_status,email_verified,is_demo_account,
            academic_level,active_programme,subjects)
            VALUES('student',?,?,?,?,?,'active',1,0,'FSc Part 1','FSc Part 1',?)""",
            (synthetic_id,"Synthetic Scale Student",
             f"perf-scale-{student_n}@scoremax.invalid",
             f"perf-scale-{student_n}","not-a-real-hash",
             "Biology,Chemistry,Physics,Mathematics")).lastrowid
        other_attempt=c.execute("""INSERT INTO attempts(student_id,scope,programme,
            subject,score,total_count,correct_count,marking_status,
            mastery_evidence_eligible,guided_mode,assessment_kind)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (other_uid,"subject","FSc Part 1","Biology",70,sample_size,
             sample_size*2//3,"FINAL",1,0,"practice")).lastrowid
        c.executemany(
            "INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,"
            "marking_status,mastery_evidence_eligible,marks_awarded,evidence_context_json)"
            " VALUES (?,?,?,?,?,?,?,?)",
            [(other_attempt,)+row for row in sample_answers])
    c.commit()
    if others:
        verify=c.execute("SELECT id FROM users WHERE system_user_id=?",(
            "SYN-STUDENT-SCALE-"+str(others-1),)).fetchone()
        subset=sm.learner_answer_evidence(c,verify["id"],"FSc Part 1")
        if len(subset)!=sample_size:
            raise RuntimeError("SCALE_STUDENT_EVIDENCE_ISOLATION_FAILED")
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.close()
    print("SCOREMAX_SYNTHETIC_SEED="+json.dumps({"questions":4*12*args.per_chapter,
       "attempt_answers":len(answer_rows)+others*sample_size,
       "final_evidence_primary":len(eligible),
       "distinct_learners":others+1,"student_id":uid,
       "fixture":"frozen_final_eligible_multi_user"}))
else:
    c=sm.db()
    if args.candidate_indexes:
        # Exercise the exact explicit migration, not a test-only substitute.
        import importlib.util
        c.close()
        tool=Path(__file__).resolve().parents[2]/"scripts"/"scoremax_navigation_index_migration_20261114.py"
        spec=importlib.util.spec_from_file_location("scoremax_nav_index_migration",tool)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        backup=root/"backup"/"navigation_preindex_snapshot.db"
        planned=module.migrate(args.database,backup,apply=False)
        done=module.migrate(args.database,backup,apply=True)
        repeat=module.migrate(args.database,backup,apply=True)
        if done["status"]!="APPLIED" or repeat["status"]!="ALREADY_APPLIED":
            raise RuntimeError("INDEX_MIGRATION_NOT_IDEMPOTENT")
        print("SCOREMAX_DISPOSABLE_INDEX_PROBE="+json.dumps(
            {"plan":planned["status"],"result":done["status"],
             "repeat":repeat["status"],"indexes":len(module.INDEXES)}))
        c=sm.db()
    if args.prepare_shadow_after_startup:
        if (os.environ.get("SCOREMAX_NAV_SHADOW_ENABLED")!="1"
            or not str(args.database.resolve()).startswith("/tmp/")):
            raise RuntimeError("SHADOW_BENCHMARK_REQUIRES_EXPLICIT_DISPOSABLE_OPTIN")
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
        from scoremax_persistent_shadow_visibility_candidate_20261115 import install,rebuild,source_state
        installed=install(c)
        outcome=rebuild(c,sm._programme_scope_sql,sm._programme_aliases,
                        sm.live_question_clause('q'))
        print("SCOREMAX_SHADOW_AFTER_BOOTSTRAP="+json.dumps({
            "triggers":installed,"rebuild_ms":outcome["rebuild_ms"],
            "size":outcome["sizes"],"state":source_state(c),
            "production_runtime_updated":False},sort_keys=True),flush=True)
    row=c.execute("SELECT id,COALESCE(session_version,0) AS session_version FROM users WHERE system_user_id=?",(STUDENT,)).fetchone()
    if not row:raise RuntimeError("MISSING_SYNTHETIC_STUDENT")
    client=app.test_client()
    with client.session_transaction(base_url="https://localhost") as session:
        session.update(user_id=row["id"],role="student",session_version=int(row["session_version"]),_csrf_token="synthetic")
    results={}
    routes=["/student/learn-vnext","/student/subject/Biology",
            "/student/chapter?subject=Biology&chapter=Synthetic%20Chapter%201",
            "/student/catalogue/year11/Biology"]
    # Exclude app initialization, schema qualification and index DDL from
    # the first page's SQL report; those are not student GET requests.
    if args.sql_profile:
        _sql_profile.clear()
    for path in routes:
        measurements=[];status=None;digest=None
        for i in range(3):
            if args.profile and i==0:
                import cProfile, pstats, io
                pr=cProfile.Profile();pr.enable()
            start=perf_counter()
            response=client.get(path,base_url="https://localhost")
            duration_ms=(perf_counter()-start)*1000
            if args.profile and i==0:
                pr.disable(); out=io.StringIO()
                pstats.Stats(pr,stream=out).sort_stats("cumtime").print_stats(22)
                print("SCOREMAX_ROUTE_PROFILE="+json.dumps({"label":args.label,"route":path,"profile":out.getvalue()}))
            if response.status_code!=200:
                raise RuntimeError(f"HTTP_FAILED:{path}:{response.status_code}:{response.location}")
            measurements.append(duration_ms)
            digest=hashlib.sha256(response.data).hexdigest()
            status=response.status_code
        payload=response.data
        if args.sql_profile:
            top=sorted(_sql_profile.items(),key=lambda pair:-pair[1][1])[:12]
            # The query plan is captured from the same disposable database,
            # with the native SQL functions registered, but never reveals values.
            # This is diagnosis only, not a production EXPLAIN or schema migration.
            plans=[]
            plan_conn=sm.db()
            try:
                for sql,values in top[:7]:
                    if sql not in _sql_examples:
                        continue
                    statement,parameters=_sql_examples[sql]
                    try:
                        details=[row[3] for row in plan_conn.execute(
                            "EXPLAIN QUERY PLAN "+statement,parameters).fetchall()]
                    except Exception as exc:
                        details=["PLAN_UNAVAILABLE:"+type(exc).__name__]
                    plans.append({"query_shape":sql[:200],
                                  "execute_ms":round(values[1],3),
                                  "plan":details[:16]})
            finally:
                plan_conn.close()
            print("SCOREMAX_SQL_ROUTE_PROFILE="+json.dumps({
                "route":path,
                "top_sql":[{"statement":sql,"execute_calls":values[0],
                            "total_execute_ms":round(values[1],3)}
                           for sql,values in top]},sort_keys=True))
            print("SCOREMAX_SQL_QUERY_PLANS="+json.dumps({
                "route":path,"plans":plans},sort_keys=True))
            _sql_profile.clear()
            _sql_examples.clear()
        if args.prepare_shadow_after_startup:
            try:
                state=source_state(c)
                print("SCOREMAX_SHADOW_NAV_ROUTE_STATE="+json.dumps({
                    "route":path,"dirty":state["dirty"],
                    "epochs_match":state["epoch"]==state["snapshot_epoch"],
                    "live_production_data_used":False},sort_keys=True),flush=True)
            except Exception as exc:
                raise RuntimeError("SHADOW_NAV_STATE_UNAVAILABLE:"+type(exc).__name__)
        results[path]={"status":status,"median_ms":round(median(measurements),2),
                       "html_bytes":len(payload),"gzip_estimated_bytes":len(gzip.compress(payload)),
                       "response_cache_control":response.headers.get("Cache-Control",""),
                       "response_content_encoding":response.headers.get("Content-Encoding",""),
                       "min_ms":round(min(measurements),2),"max_ms":round(max(measurements),2),
                       "body_sha256":digest}
    c.close()
    print("SCOREMAX_ROUTE_BENCH="+json.dumps({"label":args.label,"routes":results},sort_keys=True))
