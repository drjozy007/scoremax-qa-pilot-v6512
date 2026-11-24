"""Non-production multi-student concurrency characterization using the real Flask routes.

This is an isolated Python-thread stress probe, NOT a Gunicorn/Render capacity
certificate. It exercises request-local caches and separate SQLite connections
across different synthetic student identities, preserving the source database.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import sqlite3
from statistics import median
import sys
from time import perf_counter

p=argparse.ArgumentParser()
p.add_argument("runtime",type=Path)
p.add_argument("database",type=Path)
p.add_argument("--levels",default="1,10,50")
p.add_argument("--path",default="/student/learn-vnext")
a=p.parse_args()
levels=[int(x) for x in a.levels.split(",") if x]
if not levels or min(levels)<1 or max(levels)>100:
    raise RuntimeError("CONCURRENCY_LEVEL_OUT_OF_BOUNDS")
root=a.database.resolve().parent.parent
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
    "SCOREMAX_DB":str(a.database.resolve()),
    "SCOREMAX_PERSISTENT_ROOT":str(root),
    "SCOREMAX_BACKUP_DIR":str(root/"backup"),
    "SCOREMAX_CONTENT_INTAKE_DIR":str(root/"intake"),
    "SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
    "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
})
sys.path.insert(0,str(a.runtime.resolve()))
import scoremax_production
app=scoremax_production.application

def protected_counts():
    with sqlite3.connect("file:"+str(a.database.resolve())+"?mode=ro",uri=True) as c:
        return {table:c.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
                for table in ("questions","attempts","attempt_answers","mastery_records",
                              "integration_ph_content_releases",
                              "integration_ph_release_question_membership")}

with sqlite3.connect("file:"+str(a.database.resolve())+"?mode=ro",uri=True) as c:
    rows=c.execute("""SELECT id,COALESCE(session_version,0) FROM users
        WHERE system_user_id LIKE 'SYN-STUDENT-SCALE-%'
        ORDER BY id LIMIT ?""",(max(levels),)).fetchall()
if len(rows)<max(levels):
    raise RuntimeError("NOT_ENOUGH_SYNTHETIC_STUDENTS")
before=protected_counts()

def get_one(row):
    uid,version=row
    client=app.test_client()
    with client.session_transaction(base_url="https://localhost") as session:
        session.update(user_id=uid,role="student",session_version=int(version),
                       _csrf_token="synthetic")
    start=perf_counter()
    r=client.get(a.path,base_url="https://localhost")
    ms=(perf_counter()-start)*1000
    return (int(r.status_code),round(ms,2),len(r.data))

for n in levels:
    start=perf_counter()
    with ThreadPoolExecutor(max_workers=n) as executor:
        tasks=[executor.submit(get_one,row) for row in rows[:n]]
        results=[f.result() for f in as_completed(tasks)]
    statuses=[x[0] for x in results]
    if any(x!=200 for x in statuses):
        raise RuntimeError("CONCURRENT_STUDENT_ROUTE_FAILED:"+repr(statuses))
    durations=sorted(x[1] for x in results)
    idx=max(0,int((len(durations)-1)*0.95+0.99999))
    total=(perf_counter()-start)*1000
    print("SCOREMAX_CONCURRENT_STUDENT_CHARACTERIZATION="+json.dumps({
        "student_requests":n,"distinct_students":n,"route":a.path,
        "median_ms":round(median(durations),2),"p95_ms":durations[idx],
        "max_ms":durations[-1],"wall_ms":round(total,2),
        "p95_under_1500ms":durations[idx]<1500,
        "worker_model":"in_process_threads_not_production_gunicorn",
        "render_capacity_qualified":False},sort_keys=True),flush=True)
after=protected_counts()
if before!=after:
    raise RuntimeError("CONCURRENT_GET_CHANGED_PROTECTED_COUNTS")
print("SCOREMAX_CONCURRENT_GOVERNED_ROW_COUNTS_UNCHANGED",flush=True)
