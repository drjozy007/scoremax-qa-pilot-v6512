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
parser.add_argument("--profile",action="store_true")
parser.add_argument("--candidate-indexes",action="store_true")
args=parser.parse_args()

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
    question_ids=[row[0] for row in c.execute("SELECT id FROM questions WHERE subject='Biology' ORDER BY id LIMIT 2400")]
    c.executemany("INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct) VALUES (?,?,?,?)",
         [(attempt_id,qid,"A",int(i%3!=0)) for i,qid in enumerate(question_ids)])
    c.commit()
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.close()
    print("SCOREMAX_SYNTHETIC_SEED="+json.dumps({"questions":4*12*args.per_chapter,"attempt_answers":len(question_ids),"student_id":uid}))
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
    row=c.execute("SELECT id,COALESCE(session_version,0) AS session_version FROM users WHERE system_user_id=?",(STUDENT,)).fetchone()
    if not row:raise RuntimeError("MISSING_SYNTHETIC_STUDENT")
    client=app.test_client()
    with client.session_transaction(base_url="https://localhost") as session:
        session.update(user_id=row["id"],role="student",session_version=int(row["session_version"]),_csrf_token="synthetic")
    results={}
    routes=["/student/learn-vnext","/student/subject/Biology",
            "/student/chapter?subject=Biology&chapter=Synthetic%20Chapter%201",
            "/student/catalogue/year11/Biology"]
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
        results[path]={"status":status,"median_ms":round(median(measurements),2),
                       "html_bytes":len(payload),"gzip_estimated_bytes":len(gzip.compress(payload)),
                       "response_cache_control":response.headers.get("Cache-Control",""),
                       "response_content_encoding":response.headers.get("Content-Encoding",""),
                       "min_ms":round(min(measurements),2),"max_ms":round(max(measurements),2),
                       "body_sha256":digest}
    c.close()
    print("SCOREMAX_ROUTE_BENCH="+json.dumps({"label":args.label,"routes":results},sort_keys=True))
