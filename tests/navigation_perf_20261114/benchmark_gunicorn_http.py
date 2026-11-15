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
    parser.add_argument("--require-shadow-fresh",action="store_true")
    return parser.parse_args()

def snapshot(db):
    with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)) as c:
        return {table:c.execute("SELECT COUNT(*) FROM "+table).fetchone()[0] for table in (
            "users","questions","attempts","attempt_answers","mastery_records",
            "integration_ph_content_releases","integration_ph_release_question_membership",
            "integration_ph_product_activation_authorizations",
            "ph_bridge_staged_withdrawal_exclusions_v6611e")}

def read_shadow_state(database):
    with closing(sqlite3.connect(database.as_uri()+"?mode=ro",uri=True)) as connection:
        row=connection.execute("""SELECT epoch,dirty,snapshot_epoch,
            first_dirty_table,first_dirty_action
            FROM sm_shadow_visibility_authority WHERE id=1""").fetchone()
        if row is None:raise RuntimeError("SHADOW_HTTP_AUTHORITY_STATE_MISSING")
        return {"epoch":row[0],"dirty":row[1],"snapshot_epoch":row[2],
                "first_dirty_table":row[3],"first_dirty_action":row[4]}

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
    if args.require_shadow_fresh:
        if os.environ.get("SCOREMAX_NAV_SHADOW_ENABLED")!="1":
            raise RuntimeError("SHADOW_HTTP_PROBE_OPTIN_REQUIRED")
        with closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)) as source:
            status=source.execute("SELECT epoch,dirty,snapshot_epoch FROM sm_shadow_visibility_authority WHERE id=1").fetchone()
            if not status or status[1]!=0 or status[0]!=status[2]:
                raise RuntimeError("SHADOW_HTTP_START_STATE_STALE")
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
                if args.require_shadow_fresh:
                    startup_state=read_shadow_state(db)
                    print("SCOREMAX_SHADOW_HTTP_STARTUP_STATE="+json.dumps({
                        **startup_state,"workers":worker_count
                    },sort_keys=True),flush=True)
                    if startup_state["dirty"] or startup_state["epoch"]!=startup_state["snapshot_epoch"]:
                        raise RuntimeError("SHADOW_DIRTIED_DURING_HTTP_STARTUP:"+
                          str(startup_state["first_dirty_table"])+":"+
                          str(startup_state["first_dirty_action"]))
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
                    if args.require_shadow_fresh:
                        state=read_shadow_state(db)
                        if state["dirty"] or state["epoch"]!=state["snapshot_epoch"]:
                            print("SCOREMAX_SHADOW_HTTP_DIRTY_SOURCE="+json.dumps({
                                **state,"workers":worker_count,"students":n
                            },sort_keys=True),flush=True)
                            raise RuntimeError("SHADOW_HTTP_DIRTY_DURING_NAVIGATION:"+
                                str(state["first_dirty_table"])+":"+
                                str(state["first_dirty_action"]))
                    print("SCOREMAX_GUNICORN_ISOLATED_HTTP="+json.dumps({
                       "shadow_enabled":args.require_shadow_fresh,
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
