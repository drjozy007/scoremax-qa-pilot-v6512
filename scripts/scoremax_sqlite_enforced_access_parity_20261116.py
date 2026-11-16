"""Compare native and SQLite-speed candidate under enforced commercial access.

No ScoreMax production, no network, no PH ingress, no payments. Captures
actual Flask student route status/redirect/body digest under paywall ENABLED
for frozen synthetic users, including a disposable programme switch.

This is an equivalence check, not validation of a real billing provider or
proof that a particular learner is entitled to a subject.
"""
from __future__ import annotations
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

def main(runtime,database):
    runtime=Path(runtime).resolve()
    database=Path(database).resolve()
    if runtime.name!="scoremax_runtime_v669b" or not database.is_file() or not database.is_relative_to(Path("/tmp")):
        raise RuntimeError("DISPOSABLE_ACCEPTED_RUNTIME_ONLY")
    base=database.parent.parent
    for name in ("state","backup","intake"):(base/name).mkdir(parents=True,exist_ok=True)
    os.environ.update({
        "SCOREMAX_ENV":"production",
        "SCOREMAX_SECRET":"disposable-paywall-access-parity-secret-2026",
        "SCOREMAX_STAGING_SESSION_SECRET":"disposable-access-staging-secret",
        "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"synthetic-only-password",
        "SCOREMAX_BOOTSTRAP_ADMIN_EMAIL":"synthetic-admin@scoremax.invalid",
        "SCOREMAX_SMTP_HOST":"smtp.invalid","SCOREMAX_SMTP_FROM":"test@scoremax.invalid",
        "SCOREMAX_SEND_EMAIL_VERIFICATION":"0","SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
        "SCOREMAX_PUBLIC_STUDENT_OPENING":"0","SCOREMAX_ENFORCE_PAYWALL":"1",
        "SCOREMAX_INTERNAL_FULL_ACCESS":"0","SCOREMAX_DB":str(database),
        "SCOREMAX_PERSISTENT_ROOT":str(base),
        "SCOREMAX_BACKUP_DIR":str(base/"backup"),
        "SCOREMAX_CONTENT_INTAKE_DIR":str(base/"intake"),
        "SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
        "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
    })
    sys.path.insert(0,str(runtime))
    import scoremax_production
    sm=scoremax_production.scoremax
    app=scoremax_production.application
    with closing(sm.db()) as conn:
        row=conn.execute("""SELECT id,COALESCE(session_version,0) version
          FROM users WHERE system_user_id='SYN-STUDENT-NAV-PERF'""").fetchone()
        if row is None:raise RuntimeError("SYNTHETIC_STUDENT_NOT_SEEDED")
        uid=int(row["id"])
        client=app.test_client()
        with client.session_transaction(base_url="https://localhost") as session:
            session.update(user_id=uid,role="student",
                           session_version=int(row["version"]),_csrf_token="synthetic")
        routes=("/student/learn-vnext","/student/subject/Biology",
            "/student/chapter?subject=Biology&chapter=Synthetic%20Chapter%201",
            "/student/catalogue/year11/Biology")
        output={}
        for programme in ("FSc Part 1","MDCAT"):
            conn.execute("UPDATE users SET active_programme=? WHERE id=?",
                         (programme,uid))
            conn.commit()
            route_results={}
            for target in routes:
                resp=client.get(target,base_url="https://localhost")
                if resp.status_code>=500:
                    raise RuntimeError("ENFORCED_ACCESS_ROUTE_ERROR:"+programme+":"+target)
                cache=(resp.headers.get("Cache-Control") or "").lower()
                if "public" in cache or "s-maxage" in cache:
                    raise RuntimeError("PERSONALIZED_RESPONSE_PUBLIC_CACHE")
                route_results[target]={
                    "status":resp.status_code,
                    "sha256":hashlib.sha256(resp.data).hexdigest(),
                    "location":resp.location or "",
                    "cache_control":cache}
            output[programme]=route_results
        # Restore the original synthetic programme for independent suites.
        conn.execute("UPDATE users SET active_programme='FSc Part 1' WHERE id=?",(uid,))
        conn.commit()
    print("SCOREMAX_SQLITE_ENFORCED_ACCESS_PARITY="+json.dumps({
      "paywall_enabled":True,"programme_scopes":output,
      "external_payment_or_PH_service_contacted":False,
      "real_account_data_used":False,"production_touched":False,
    },sort_keys=True),flush=True)

if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("USAGE: script generated_runtime disposable_sqlite_db")
    main(sys.argv[1],sys.argv[2])
