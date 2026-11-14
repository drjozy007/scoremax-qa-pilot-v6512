"""Isolated real-HTTP Gunicorn concurrency probe for the accepted ScoreMax runtime.

Exercises one and two Gunicorn worker processes with distinct, synthetically
signed student sessions against the *same disposable* SQLite database.

This is not a Render/Pakistan mobile SLA, a transactional marking load test, or
evidence of live PH membership equivalence. It never contacts production.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
import http.client
import json
import math
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from statistics import median

def arguments():
    parser=argparse.ArgumentParser()
    parser.add_argument("runtime",type=Path)
    parser.add_argument("database",type=Path)
    parser.add_argument("--workers",default="1,2")
    parser.add_argument("--levels",default="1,10,50")
    parser.add_argument("--threads",type=int,default=4)
    parser.add_argument("--port",type=int,default=18761)
    parser.add_argument("--route",default="/student/learn-vnext")
    return parser.parse_args()

def snapshot(db):
    with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)) as c:
        return {table:c.execute("SELECT COUNT(*) FROM "+table).fetchone()[0] for table in (
            "users","questions","attempts","attempt_answers","mastery_records",
            "integration_ph_content_releases","integration_ph_release_question_membership",
            "integration_ph_product_activation_authorizations",
            "ph_bridge_staged_withdrawal_exclusions_v6611e")}

def make_environment(database):
    root=database.parent.parent
    for name in ("state","backup","intake"):
        (root/name).mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update({
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
        "SCOREMAX_DB":str(database),
        "SCOREMAX_PERSISTENT_ROOT":str(root),
        "SCOREMAX_BACKUP_DIR":str(root/"backup"),
        "SCOREMAX_CONTENT_INTAKE_DIR":str(root/"intake"),
        "SCOREMAX_INSTANCE_COUNT":"1",
        "WEB_CONCURRENCY":"1",
        "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
    })
    return env

def request_once(port,path,cookie,barrier=None):
    if barrier is not None:barrier.wait(timeout=15)
    c=http.client.HTTPConnection("127.0.0.1",port,timeout=120)
    start=time.perf_counter()
    try:
        c.request("GET",path,headers={"Cookie":cookie,"Accept":"text/html",
                                      "Connection":"close"})
        response=c.getresponse()
        payload=response.read()
        elapsed=(time.perf_counter()-start)*1000
        return {"status":response.status,"ms":round(elapsed,2),"bytes":len(payload)}
    finally:
        c.close()

def wait_until_ready(process,port):
    until=time.monotonic()+80
    while time.monotonic()<until:
        if process.poll() is not None:
            raise RuntimeError("GUNICORN_DIED_BEFORE_HEALTH")
        try:
            probe=request_once(port,"/","")
            if probe["status"]==200:return
        except (OSError,TimeoutError,http.client.HTTPException):
            pass
        time.sleep(.5)
    raise RuntimeError("GUNICORN_NOT_READY_80S")

def main():
    args=arguments()
    runtime=args.runtime.resolve();db=args.database.resolve()
    if not (runtime/"scoremax_production.py").is_file() or not db.is_file():
        raise RuntimeError("PROBE_RUNTIME_OR_DATABASE_MISSING")
    if "/tmp/" not in str(db) and not str(db).startswith("/tmp/"):
        raise RuntimeError("PROBE_REFUSES_NON_TMP_DATABASE")
    if not (1<=args.threads<=8) or not (1024<=args.port<=60000):
        raise RuntimeError("PROBE_UNSAFE_PROCESS_OPTIONS")
    workers=[int(x) for x in args.workers.split(",") if x]
    levels=[int(x) for x in args.levels.split(",") if x]
    if not workers or not levels or min(workers)<1 or max(workers)>4 or min(levels)<1 or max(levels)>50:
        raise RuntimeError("PROBE_UNSAFE_LOAD_OPTIONS")
    before=snapshot(db)
    env=make_environment(db)
    # The parent is the only place that creates cookies. Never log cookies,
    # identifiers, synthetic credentials or any real database content.
    for key,val in env.items():
        if key.startswith("SCOREMAX_"):os.environ[key]=val
    sys.path.insert(0,str(runtime))
    import scoremax_production
    app=scoremax_production.application
    serializer=app.session_interface.get_signing_serializer(app)
    if serializer is None:raise RuntimeError("NO_SIGNED_SESSION_SERIALIZER")
    with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)) as conn:
        students=conn.execute("""SELECT id,COALESCE(session_version,0) FROM users
                WHERE system_user_id LIKE 'SYN-STUDENT-SCALE-%'
                ORDER BY id LIMIT ?""",(max(levels),)).fetchall()
    if len(students)<max(levels):raise RuntimeError("INSUFFICIENT_DISTINCT_STUDENTS")
    cookies=[]
    for student,ver in students:
        value=serializer.dumps({"user_id":student,"role":"student",
                               "session_version":int(ver),"_csrf_token":"synthetic"})
        cookies.append(app.config.get("SESSION_COOKIE_NAME","session")+"="+value)
    del serializer
    for i,worker_count in enumerate(workers):
        port=args.port+i
        command=[sys.executable,"-m","gunicorn","scoremax_production:application",
                 "--workers",str(worker_count),"--threads",str(args.threads),
                 "--bind",f"127.0.0.1:{port}","--timeout","120",
                 "--access-logfile","-","--error-logfile","-"]
        with tempfile.TemporaryFile(mode="w+t") as logs:
            proc=subprocess.Popen(command,cwd=runtime,env=env,stdout=logs,
                                  stderr=subprocess.STDOUT,start_new_session=True)
            try:
                wait_until_ready(proc,port)
                for n in levels:
                    barrier=threading.Barrier(n) if n>1 else None
                    start=time.perf_counter()
                    with ThreadPoolExecutor(max_workers=n) as pool:
                        futures=[pool.submit(request_once,port,args.route,cookies[j],barrier)
                                 for j in range(n)]
                        observations=[future.result() for future in as_completed(futures)]
                    if any(x["status"]!=200 or x["bytes"]<1000 for x in observations):
                        raise RuntimeError("GUNICORN_STUDENT_REQUEST_MISMATCH:"+repr(
                            [(x["status"],x["bytes"]) for x in observations]))
                    durations=sorted(x["ms"] for x in observations)
                    p95=durations[max(0,math.ceil(.95*n)-1)]
                    print("SCOREMAX_GUNICORN_ISOLATED_HTTP="+json.dumps({
                       "workers":worker_count,"threads_per_worker":args.threads,
                       "distinct_students":n,"route":args.route,
                       "median_ms":round(median(durations),2),"p95_ms":p95,
                       "max_ms":durations[-1],
                       "wall_ms":round((time.perf_counter()-start)*1000,2),
                       "p95_under_1500ms":p95<1500,
                       "production_render_capacity_qualified":False,
                       "submitted_student_answers":False,
                       "ph_governed_fixture_qualified":False
                    },sort_keys=True),flush=True)
            except Exception:
                logs.seek(0);excerpt=logs.read()[-4500:]
                print("SCOREMAX_GUNICORN_PROBE_DIAGNOSTIC="+repr(excerpt),flush=True)
                raise
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try:proc.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL)
                        proc.wait(timeout=10)
    after=snapshot(db)
    if before!=after:raise RuntimeError("PROTECTED_TABLE_ROW_COUNTS_CHANGED")
    print("SCOREMAX_GUNICORN_PROTECTED_CENSUS_UNCHANGED",flush=True)

if __name__=="__main__":
    main()
