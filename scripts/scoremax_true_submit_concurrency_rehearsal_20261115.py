"""Actual ScoreMax assessment-route idempotency under concurrent POSTs.

Generated accepted app, disposable SQLite and synthetic student only.
Never touches Render/Power House or real learner data. It tests the REAL
submit_assessment_v4 route and its resulting attempt/answer/session rows.
"""
from __future__ import annotations
import ast
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
from time import perf_counter

def main(runtime:Path):
    runtime=runtime.resolve()
    if runtime.name!="scoremax_runtime_v669b" or not (runtime/"scoremax_production.py").is_file():
        raise RuntimeError("REAL_SUBMIT_ACCEPTED_RUNTIME_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="scoremax-submit-real-") as tmp:
        base=Path(tmp);db_path=base/"state"/"scoremax.db"
        for name in ("state","backup","intake"): (base/name).mkdir()
        os.environ.update({
            "SCOREMAX_ENV":"production",
            "SCOREMAX_SECRET":"disposable-real-submit-rehearsal-secret-do-not-use",
            "SCOREMAX_STAGING_SESSION_SECRET":"test-stage-real-submit-only",
            "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"test-admin-password-not-live",
            "SCOREMAX_BOOTSTRAP_ADMIN_EMAIL":"disposable-admin@scoremax.invalid",
            "SCOREMAX_SMTP_HOST":"smtp.invalid","SCOREMAX_SMTP_FROM":"test@scoremax.invalid",
            "SCOREMAX_SEND_EMAIL_VERIFICATION":"0",
            "SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
            "SCOREMAX_PUBLIC_STUDENT_OPENING":"0",
            "SCOREMAX_ENFORCE_PAYWALL":"0",
            "SCOREMAX_INTERNAL_FULL_ACCESS":"0",
            "SCOREMAX_DB":str(db_path),
            "SCOREMAX_PERSISTENT_ROOT":str(base),
            "SCOREMAX_BACKUP_DIR":str(base/"backup"),
            "SCOREMAX_CONTENT_INTAKE_DIR":str(base/"intake"),
            "SCOREMAX_INSTANCE_COUNT":"1",
            "WEB_CONCURRENCY":"1",
            "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
        })
        sys.path.insert(0,str(runtime))
        import scoremax_production
        sm=scoremax_production.scoremax
        app=scoremax_production.application
        root=Path(__file__).resolve().parents[1]
        source=(root/"scripts"/"qualify_assessment_contract_repair.py").read_text()
        tree=ast.parse(source)
        nodes=[n for n in tree.body
               if (isinstance(n,ast.FunctionDef) and n.name in {"question","rubric_question"})
               or (isinstance(n,ast.Assign) and any(
                    isinstance(t,ast.Name) and t.id in {"SPECS","RUBRIC"}
                    for t in n.targets))]
        fixtures={"copy":copy,"json":json}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),"<approved-synthetic-fixture>","exec"),fixtures)
        if "MCQ" not in fixtures["SPECS"]:raise RuntimeError("MCQ_SYNTHETIC_FIXTURE_MISSING")
        c=sm.db()
        try:
            def make_student(n):
                uid=c.execute("""INSERT INTO users(role,system_user_id,full_name,email,
                    username,password_hash,account_status,email_verified,is_demo_account,
                    academic_level,active_programme,subjects)
                    VALUES('student',?,?,?,?,?,'active',1,0,'FSc Part 1','FSc Part 1','Biology')""",
                    (f"SYN-TRANSACTION-{n}","Synthetic Transaction Learner",
                     f"txn-{n}@scoremax.invalid",f"txn-{n}",
                     "not-a-valid-login-hash")).lastrowid
                return uid
            def make_question(n):
                q=copy.deepcopy(fixtures["SPECS"]["MCQ"][0])
                q.update(question_id=f"SYN-TRANSACTION-MCQ-{n}",family_id=f"SYN-TRANSACTION-FAMILY-{n}",
                  programme="FSc Part 1",qualification="FSc Part 1",
                  subject="Biology",chapter="Synthetic Chapter 1",topic="Synthetic Subject",
                  level="Foundation",difficulty="Foundation",status="Approved",
                  review_status="Approved",active=1,is_demo=0,scoremax_ready=1,
                  ph_projection_owner="",source_type="ISOLATED_SYNTHETIC_TEST",
                  rights_status="ScoreMax Original",content_environment="PRODUCTION",
                  country="Pakistan",family_key=f"SYN-TRANSACTION-FAMILY-{n}")
                q["family_key"]=sm.upsert_question_family(c,q,review_status="Approved",active=1)
                keys={r[1] for r in c.execute("PRAGMA table_info(questions)")}
                clean={k:v for k,v in q.items() if k in keys}
                qid=c.execute("INSERT INTO questions("+",".join(clean)+") VALUES("+
                     ",".join("?" for _ in clean)+")",tuple(clean.values())).lastrowid
                return qid, q.get("answer") or "B"
            session_ids=[]
            user_ids=[]
            for n in range(3):
                uid=make_student(n)
                qid,answer=make_question(n)
                assessment_id=sm.create_assessment_session(
                    c,uid,"practice",None,[qid],
                    {"programme":"FSc Part 1","subject":"Biology",
                     "scope":"chapter","chapters":"Synthetic Chapter 1"})
                if not assessment_id:raise RuntimeError("ASSESSMENT_CREATION_FAILED")
                session_ids.append((assessment_id,qid,answer))
                user_ids.append(uid)
            c.commit()
            session_versions={r["id"]:int(r["session_version"] or 0) for r in c.execute(
                "SELECT id,session_version FROM users WHERE id IN ("+
                ",".join("?" for _ in user_ids)+")",user_ids)}
            def client_for(uid):
                client=app.test_client()
                with client.session_transaction(base_url="https://localhost") as sess:
                    sess.update(user_id=uid,role="student",
                        session_version=session_versions[uid],
                        _csrf_token="synthetic-csrf")
                return client
            for uid,(assessment_id,qid,answer) in zip(user_ids,session_ids):
                client=client_for(uid)
                response=client.post("/test/session/"+str(assessment_id),
                    data={"_csrf_token":"synthetic-csrf",
                          "response_present":"1","answer":answer,"action":"review"},
                    base_url="https://localhost")
                if response.status_code not in (200,302):
                    raise RuntimeError(f"SAVED_ANSWER_ROUTE_FAILED:{response.status_code}")
                stored=c.execute("SELECT answers_json FROM assessment_sessions WHERE id=?",
                                 (assessment_id,)).fetchone()
                if stored is None or not stored["answers_json"]:
                    raise RuntimeError("ANSWER_NOT_SAVED_BEFORE_SUBMIT")
            c.commit()
            tasks=[(user_ids[0],session_ids[0][0])]*8 + [
                   (user_ids[1],session_ids[1][0])]*4 + [
                   (user_ids[2],session_ids[2][0])]*4
            barrier=threading.Barrier(len(tasks))
            def submit(item):
                uid,aid=item
                client=client_for(uid)
                barrier.wait(timeout=20)
                began=perf_counter()
                result=client.post(f"/test/session/{aid}/submit",
                    data={"_csrf_token":"synthetic-csrf"},base_url="https://localhost")
                return {"status":result.status_code,"location":result.location,
                        "ms":round((perf_counter()-began)*1000,2)}
            with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
                observations=list(pool.map(submit,tasks))
            if any(r["status"]!=302 for r in observations):
                raise RuntimeError("DUPLICATE_POST_RETURNED_NON_REDIRECT:"+repr(
                  [r["status"] for r in observations]))
            for uid,(aid,qid,_) in zip(user_ids,session_ids):
                attempts=c.execute("""SELECT id,student_id,marking_status,score,mastery_evidence_eligible
                   FROM attempts WHERE assessment_session_id=?""",(aid,)).fetchall()
                if len(attempts)!=1 or attempts[0]["student_id"]!=uid:
                    raise RuntimeError("DUPLICATE_ATTEMPT_IDENTITY:"+str(aid)+":"+str(len(attempts)))
                answers=c.execute("SELECT question_db_id FROM attempt_answers WHERE attempt_id=?",
                    (attempts[0]["id"],)).fetchall()
                if len(answers)!=1 or answers[0]["question_db_id"]!=qid:
                    raise RuntimeError("DUPLICATE_OR_MISSING_ANSWER:"+str(aid))
                row=c.execute("""SELECT status,submitted_attempt_id
                    FROM assessment_sessions WHERE id=?""",(aid,)).fetchone()
                if row["status"]!="submitted" or row["submitted_attempt_id"]!=attempts[0]["id"]:
                    raise RuntimeError("SESSION_ATTEMPT_ATOMICITY_FAILED:"+str(aid))
                if attempts[0]["marking_status"]!="FINAL" or attempts[0]["score"] is None:
                    raise RuntimeError("SUBMIT_MARKING_NOT_FINAL:"+str(aid))
                if c.execute("SELECT COUNT(*) FROM mastery_form_results WHERE assessment_session_id=?",
                      (aid,)).fetchone()[0]!=0:
                    raise RuntimeError("PRACTICE_WRONGFULLY_AWARDED_FORMAL_MASTERY")
                if c.execute("SELECT COUNT(*) FROM mastery_records WHERE student_id=?",
                      (uid,)).fetchone()[0]!=0:
                    raise RuntimeError("PRACTICE_WRONGFULLY_AWARDED_MASTERY_RECORD")
            if c.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]!=3:
                raise RuntimeError("CROSS_SESSION_ATTEMPTS_DUPLICATED")
            if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("DISPOSABLE_DATABASE_CORRUPTED")
            print("SCOREMAX_REAL_SUBMIT_CONCURRENCY_PASS="+json.dumps({
                "scope":"actual_Flask_submit_assessment_v4_disposable_app",
                "concurrent_requests":len(tasks),"distinct_students":3,
                "unique_sessions":3,"attempts":3,"answers":3,
                "all_responses_redirected":True,
                "single_identity_per_session":True,
                "practice_formal_mastery_records":0,
                "sqlite_integrity":"ok",
                "max_submission_ms":max(r["ms"] for r in observations),
                "production_touched":False,
                "PH_signed_ack_tested":False,
                "PostgreSQL_backend_tested":False,
            },sort_keys=True),flush=True)
        finally:c.close()
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("USAGE: script <generated_runtime_root>")
    main(Path(sys.argv[1]))
