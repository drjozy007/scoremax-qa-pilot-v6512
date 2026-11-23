"""Populate the accepted ScoreMax native assessment ledger before PG transfer.

Only a bounded /tmp/ synthetic SQLite database is permitted. Reuses the
existing academic question-contract fixture and the real Flask save/submit
route; never manufactures an official mastery award or PH acknowledgement.
"""
from __future__ import annotations
import ast
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys

def main(dbpath, runtime):
    dbpath=Path(dbpath).resolve()
    runtime=Path(runtime).resolve()
    if not dbpath.is_file() or not dbpath.is_relative_to(Path("/tmp")):
        raise RuntimeError("NON_DISPOSABLE_DATABASE_REFUSED")
    if runtime.name!="scoremax_runtime_v669b":
        raise RuntimeError("ACCEPTED_RUNTIME_REQUIRED")
    home=dbpath.parent.parent
    os.environ.update({
        "SCOREMAX_ENV":"production",
        "SCOREMAX_SECRET":"synthetic-pg-migration-native-test-session-secret",
        "SCOREMAX_STAGING_SESSION_SECRET":"synthetic-migration-staging-secret",
        "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"Synthetic-Native-Only-PG-2026",
        "SCOREMAX_BOOTSTRAP_ADMIN_EMAIL":"synthetic-admin@scoremax.invalid",
        "SCOREMAX_DB":str(dbpath),"SCOREMAX_PERSISTENT_ROOT":str(home),
        "SCOREMAX_BACKUP_DIR":str(home/"backup"),
        "SCOREMAX_CONTENT_INTAKE_DIR":str(home/"intake"),
        "SCOREMAX_SMTP_HOST":"smtp.invalid","SCOREMAX_SMTP_FROM":"test@scoremax.invalid",
        "SCOREMAX_SEND_EMAIL_VERIFICATION":"0","SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
        "SCOREMAX_PUBLIC_STUDENT_OPENING":"0","SCOREMAX_ENFORCE_PAYWALL":"0",
        "SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
        "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
    })
    sys.path.insert(0,str(runtime))
    import scoremax_production
    sm=scoremax_production.scoremax
    app=scoremax_production.application
    fixtures=Path(__file__).with_name("qualify_assessment_contract_repair.py").read_text()
    nodes=[node for node in ast.parse(fixtures).body
           if (isinstance(node,ast.FunctionDef) and node.name in {"question","rubric_question"})
            or (isinstance(node,ast.Assign) and any(
                isinstance(t,ast.Name) and t.id in {"RUBRIC","SPECS"}
                for t in node.targets))]
    env={"copy":copy,"json":json}
    exec(compile(ast.Module(body=nodes,type_ignores=[]),"<accepted-questions>","exec"),env)
    with sm.db() as c:
        user=c.execute("SELECT id,session_version FROM users WHERE system_user_id=?",
                       ("SYN-STUDENT-NAV-PERF",)).fetchone()
        if not user:raise RuntimeError("NATIVE_SYNTHETIC_STUDENT_ABSENT")
        student_id=user["id"]
        question=copy.deepcopy(env["SPECS"]["MCQ"][0])
        question.update(
            question_id="SYN-PG-NATIVE-RELEASE-SAFE-MCQ",
            family_id="SYN-PG-NATIVE-FAMILY",
            country="Pakistan",programme="FSc Part 1",qualification="FSc Part 1",
            subject="Biology",chapter="Synthetic Chapter 1",topic="Migration fixture",
            level="Foundation",difficulty="Foundation",
            status="Approved",review_status="Approved",active=1,is_demo=0,
            scoremax_ready=1,ph_projection_owner="",
            source_type="ISOLATED_SYNTHETIC_TEST",rights_status="ScoreMax Original",
            content_environment="PRODUCTION",family_key="SYN-PG-NATIVE-FAMILY",
        )
        question["family_key"]=sm.upsert_question_family(
            c,question,review_status="Approved",active=1)
        permitted={row[1] for row in c.execute("PRAGMA table_info(questions)")}
        item={k:v for k,v in question.items() if k in permitted}
        qid=c.execute("INSERT INTO questions("+",".join(item)+") VALUES("+
                      ",".join("?" for _ in item)+")",tuple(item.values())).lastrowid
        c.commit()
        aid=sm.create_assessment_session(
            c,student_id,"practice",None,[qid],{
                "programme":"FSc Part 1","subject":"Biology","scope":"chapter",
                "chapters":"Synthetic Chapter 1",
            })
        c.commit()
        if not aid:raise RuntimeError("NATIVE_ASSESSMENT_NOT_CREATED")
        client=app.test_client()
        with client.session_transaction(base_url="https://localhost") as session:
            session.update(user_id=student_id,role="student",
                session_version=int(user["session_version"] or 0),
                _csrf_token="synthetic-csrf")
        saved=client.post("/test/session/"+str(aid),
            data={"_csrf_token":"synthetic-csrf","response_present":"1",
                  "answer":"B","action":"review"},base_url="https://localhost")
        if saved.status_code not in (200,302):
            raise RuntimeError("NATIVE_MIGRATION_ANSWER_SAVE_FAILED:"+str(saved.status_code))
        submitted=client.post(f"/test/session/{aid}/submit",
            data={"_csrf_token":"synthetic-csrf"},base_url="https://localhost")
        if submitted.status_code!=302:
            raise RuntimeError("NATIVE_MIGRATION_ASSESSMENT_SUBMIT_FAILED:"+str(submitted.status_code))
        attempt=c.execute(
            "SELECT id,score,marking_status FROM attempts WHERE assessment_session_id=?",
            (aid,)).fetchall()
        if len(attempt)!=1 or attempt[0]["score"] is None or attempt[0]["marking_status"]!="FINAL":
            raise RuntimeError("NATIVE_MIGRATION_MARKING_NOT_FINAL")
        answers=c.execute("SELECT question_db_id FROM attempt_answers WHERE attempt_id=?",
                          (attempt[0]["id"],)).fetchall()
        if len(answers)!=1 or answers[0]["question_db_id"]!=qid:
            raise RuntimeError("NATIVE_MIGRATION_PINNED_ANSWER_NOT_STORED")
        if c.execute("SELECT COUNT(*) FROM mastery_records").fetchone()[0]:
            raise RuntimeError("SYNTHETIC_PRACTICE_GAINED_FORMAL_MASTERY")
        if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("SOURCE_SQLITE_INTEGRITY_NOT_OK")
        print("SCOREMAX_PG_MIGRATION_REAL_NATIVE_SUBMISSION_PASS="+json.dumps({
           "native_assessment_sessions_created":1,"final_attempts_created":1,
           "frozen_answers_created":1,"formal_mastery_unearned":True,
           "source":"real_accepted_Flask_save_submit_and_marking",
           "production_touched":False,
        },sort_keys=True),flush=True)

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("USAGE: database_path generated_runtime_root")
    main(sys.argv[1],sys.argv[2])
