"""Real Flask synthetic-learner journeys on the ScoreMax SQLite release candidate.

Runs separately for native and PR#56 generated runtimes with identical copies
of one disposable synthetic SQLite seed. Checks Foundation/Exam Ready ceilings,
FSc/MDCAT context isolation, real authenticated navigation, frozen practice
assessment submission, anti-hijack, duplicate submit, and formal mastery.
No live accounts, external Power House, network, paid AI or deployment.
"""
from __future__ import annotations
import ast
from contextlib import closing
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

def main(runtime,dbpath,label):
    runtime=Path(runtime).resolve()
    dbpath=Path(dbpath).resolve()
    if not runtime.is_dir() or not (runtime/"scoremax_production.py").is_file():
        raise RuntimeError("ACCEPTED_SCOREMAX_RUNTIME_REQUIRED")
    if not dbpath.is_file() or dbpath.is_symlink() or not dbpath.is_relative_to(Path("/tmp")):
        raise RuntimeError("DISPOSABLE_SYNTHETIC_SQLITE_REQUIRED")
    home=dbpath.parent.parent
    for directory in ("state","backup","intake"):(home/directory).mkdir(parents=True,exist_ok=True)
    os.environ.update({
        "SCOREMAX_ENV":"production",
        "SCOREMAX_SECRET":"synthetic-persona-matrix-shared-secret-2026",
        "SCOREMAX_STAGING_SESSION_SECRET":"synthetic-persona-matrix-staging-secret",
        "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"synthetic-only-not-for-production",
        "SCOREMAX_BOOTSTRAP_ADMIN_EMAIL":"synthetic-admin@scoremax.invalid",
        "SCOREMAX_SMTP_HOST":"smtp.invalid","SCOREMAX_SMTP_FROM":"test@scoremax.invalid",
        "SCOREMAX_SEND_EMAIL_VERIFICATION":"0","SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
        "SCOREMAX_PUBLIC_STUDENT_OPENING":"0","SCOREMAX_ENFORCE_PAYWALL":"0",
        "SCOREMAX_INTERNAL_FULL_ACCESS":"0",
        "SCOREMAX_DB":str(dbpath),"SCOREMAX_PERSISTENT_ROOT":str(home),
        "SCOREMAX_BACKUP_DIR":str(home/"backup"),
        "SCOREMAX_CONTENT_INTAKE_DIR":str(home/"intake"),
        "SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
        "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
    })
    sys.path.insert(0,str(runtime))
    import scoremax_production
    sm=scoremax_production.scoremax
    app=scoremax_production.application
    personas=(
        ("FSC_FOUNDATION","SYN-STUDENT-NAV-PERF","FSc Part 1",None),
        ("FSC_EXAM_READY","SYN-STUDENT-SCALE-0","FSc Part 1","level_1_access"),
        ("MDCAT_FOUNDATION","SYN-STUDENT-SCALE-1","MDCAT",None),
        ("FSC_YEAR12_FOUNDATION","SYN-STUDENT-SCALE-1","FSc Part 2",None),
    )
    paths=(
      "/student/learn-vnext",
      "/student/subject/Biology",
      "/student/chapter?subject=Biology&chapter=Synthetic%20Chapter%201",
      "/student/catalogue/year11/Biology",
      "/student/catalogue/mdcat/Biology",
      "/test/setup?subject=Biology&chapter=Synthetic%20Chapter%201&scope=chapter",
    )
    output={}
    with closing(sm.db()) as c:
        before={table:c.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
            for table in ("mastery_records","mastery_form_results",
                          "integration_ph_content_releases","integration_outbox")}
        def signed_client(uid):
            user=c.execute("SELECT session_version FROM users WHERE id=?",(uid,)).fetchone()
            if not user:raise RuntimeError("UNKNOWN_SYNTHETIC_LEARNER")
            client=app.test_client()
            with client.session_transaction(base_url="https://localhost") as session:
                session.update(user_id=uid,role="student",
                    session_version=int(user["session_version"] or 0),
                    _csrf_token="synthetic-csrf")
            return client
        for tag,system_id,programme,override in personas:
            row=c.execute("SELECT id FROM users WHERE system_user_id=?",(system_id,)).fetchone()
            if not row:raise RuntimeError("SYNTHETIC_PROFILE_NOT_FOUND:"+tag)
            uid=int(row["id"])
            c.execute("""UPDATE users SET active_programme=?,access_override_code=?
                         WHERE id=?""",(programme,override,uid))
            c.commit()
            access=sm.get_access_profile(c,uid)
            ceiling=str(access.get("mastery_ceiling") or "")
            if tag=="FSC_EXAM_READY" and ceiling!="Exam Ready":
                raise RuntimeError("EXAM_READY_CEILING_WRONG:"+repr(access))
            if tag!="FSC_EXAM_READY" and ceiling!="Foundation":
                raise RuntimeError("FOUNDATION_CEILING_WRONG:"+tag+":"+repr(access))
            evidence=sm.learner_answer_evidence(c,uid,programme)
            if programme!="FSc Part 1" and evidence:
                raise RuntimeError("FSC_HISTORY_CROSSED_PROGRAMME_BOUNDARY:"+tag)
            if programme=="FSc Part 1" and not evidence:
                raise RuntimeError("FSC_HISTORY_NOT_DISPLAYABLE:"+tag)
            client=signed_client(uid)
            navigation={}
            for path in paths:
                resp=client.get(path,base_url="https://localhost")
                if resp.status_code>=500:
                    raise RuntimeError("SYNTHETIC_LEARNER_ROUTE_ERROR:"+tag+":"+path)
                cc=(resp.headers.get("Cache-Control") or "").lower()
                if "public" in cc or "s-maxage" in cc:
                    raise RuntimeError("STUDENT_PRIVATE_PAGE_PUBLIC_CACHE:"+tag+":"+path)
                navigation[path]={
                    "status":resp.status_code,
                    "sha256":hashlib.sha256(resp.data).hexdigest(),
                    "bytes":len(resp.data),
                    "location":resp.location or "",
                    "cache_control":cc,
                }
            output[tag]={"programme":programme,"ceiling":ceiling,
                "eligible_frozen_evidence":len(evidence),"routes":navigation}
        # Restore both overlapping account roles after cross-programme probes.
        c.execute("""UPDATE users SET active_programme='FSc Part 1',
                     access_override_code=NULL WHERE system_user_id='SYN-STUDENT-NAV-PERF'""")
        c.execute("""UPDATE users SET active_programme='FSc Part 1',
                     access_override_code='level_1_access'
                     WHERE system_user_id='SYN-STUDENT-SCALE-0'""")
        c.execute("""UPDATE users SET active_programme='MDCAT',
                     access_override_code=NULL
                     WHERE system_user_id='SYN-STUDENT-SCALE-1'""")
        c.commit()
        # Actual native assessment scenario, NOT a fabricated SQL grading row.
        source=Path(__file__).with_name("qualify_assessment_contract_repair.py").read_text()
        tree=ast.parse(source)
        nodes=[n for n in tree.body if
            (isinstance(n,ast.FunctionDef) and n.name in ("question","rubric_question"))
            or (isinstance(n,ast.Assign) and any(isinstance(k,ast.Name) and
                   k.id in ("RUBRIC","SPECS") for k in n.targets))]
        ns={"json":json,"copy":copy}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),
                     "<accepted-synthetic-question-fixture>","exec"),ns)
        outcomes={}
        for tag,system_id,level in (
            ("FSC_FOUNDATION","SYN-STUDENT-NAV-PERF","Foundation"),
            ("FSC_EXAM_READY","SYN-STUDENT-SCALE-0","Exam Ready")):
            uid=c.execute("SELECT id FROM users WHERE system_user_id=?",
                          (system_id,)).fetchone()[0]
            q=copy.deepcopy(ns["SPECS"]["MCQ"][0])
            q.update(question_id="SYN-PERSONA-MCQ-"+tag,
                     family_id="SYN-PERSONA-FAMILY-"+tag,
                     programme="FSc Part 1",qualification="FSc Part 1",
                     subject="Biology",chapter="Synthetic Chapter 1",
                     topic="SYN-PERSONA",level=level,difficulty=level,
                     status="Approved",review_status="Approved",
                     active=1,is_demo=0,scoremax_ready=1,
                     ph_projection_owner="",source_type="ISOLATED_SYNTHETIC_TEST",
                     rights_status="ScoreMax Original",
                     content_environment="PRODUCTION",country="Pakistan",
                     family_key="SYN-PERSONA-FAMILY-"+tag)
            q["family_key"]=sm.upsert_question_family(c,q,review_status="Approved",active=1)
            columns={r[1] for r in c.execute("PRAGMA table_info(questions)")}
            record={key:value for key,value in q.items() if key in columns}
            qid=c.execute("INSERT INTO questions("+",".join(record)+") VALUES("+
                          ",".join("?" for _ in record)+")",
                          tuple(record.values())).lastrowid
            aid=sm.create_assessment_session(c,uid,"practice",None,[qid],{
                "programme":"FSc Part 1","subject":"Biology",
                "scope":"chapter","chapters":"Synthetic Chapter 1"})
            if not aid:raise RuntimeError("LEARNER_PRACTICE_SESSION_NOT_CREATED:"+tag)
            c.commit()
            own=signed_client(uid)
            initial=own.get("/test/session/"+str(aid),base_url="https://localhost")
            if initial.status_code!=200:
                raise RuntimeError("LEARNER_CANNOT_OPEN_OWN_SESSION:"+tag+
                                    ":"+str(initial.status_code))
            saved=own.post("/test/session/"+str(aid),base_url="https://localhost",
                data={"_csrf_token":"synthetic-csrf","response_present":"1",
                      "answer":q.get("answer") or "B","action":"review"})
            if saved.status_code not in (200,302):
                raise RuntimeError("LEARNER_PRACTICE_ANSWER_NOT_SAVED:"+tag)
            other_id=c.execute("SELECT id FROM users WHERE system_user_id=?",
                ("SYN-STUDENT-SCALE-1",)).fetchone()[0]
            attack=signed_client(other_id).get("/test/session/"+str(aid),
                base_url="https://localhost")
            if attack.status_code==200 or attack.status_code>=500:
                raise RuntimeError("OTHER_LEARNER_CAN_READ_SESSION:"+tag)
            returned=own.post("/test/session/"+str(aid)+"/submit",
                base_url="https://localhost",data={"_csrf_token":"synthetic-csrf"})
            if returned.status_code!=302:
                raise RuntimeError("LEARNER_SUBMIT_FAILED:"+tag+":"+str(returned.status_code))
            duplicate=own.post("/test/session/"+str(aid)+"/submit",
                base_url="https://localhost",data={"_csrf_token":"synthetic-csrf"})
            if duplicate.status_code!=302:
                raise RuntimeError("DUPLICATE_SUBMISSION_NOT_IDEMPOTENT:"+tag)
            attempts=c.execute("""SELECT id,student_id,marking_status,score
                FROM attempts WHERE assessment_session_id=?""",(aid,)).fetchall()
            if len(attempts)!=1 or attempts[0]["student_id"]!=uid:
                raise RuntimeError("LEARNER_ATTEMPT_IDENTITY_OR_DUPLICATE:"+tag)
            if attempts[0]["marking_status"]!="FINAL" or attempts[0]["score"] is None:
                raise RuntimeError("LEARNER_MARKING_NOT_FINAL:"+tag)
            answer=c.execute("""SELECT question_db_id FROM attempt_answers
                WHERE attempt_id=?""",(attempts[0]["id"],)).fetchall()
            if len(answer)!=1 or answer[0]["question_db_id"]!=qid:
                raise RuntimeError("LEARNER_FROZEN_RESPONSE_MISSING:"+tag)
            if c.execute("""SELECT COUNT(*) FROM mastery_records WHERE
                 student_id=?""",(uid,)).fetchone()[0]!=0:
                raise RuntimeError("PRACTICE_GRANTED_FORMAL_MASTERY:"+tag)
            outcomes[tag]={"practice_session_created":True,"final_attempts":1,
                "frozen_answers":1,"response_status":returned.status_code,
                "duplicate_post_status":duplicate.status_code,
                "cross_student_session_blocked":True,
                "formal_mastery_awards":0,"score":attempts[0]["score"]}
        after={table:c.execute("SELECT COUNT(*) FROM "+table).fetchone()[0]
            for table in before}
        if any(after[k]!=before[k] for k in before):
            raise RuntimeError("LEARNER_JOURNEY_CHANGED_PROTECTED_AUTHORITY:"+repr((before,after)))
        if c.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise RuntimeError("LEARNER_JOURNEY_SQLITE_INTEGRITY_FAILURE")
    print("SCOREMAX_SYNTHETIC_PERSONA_JOURNEYS="+json.dumps({
        "label":label,"personas":output,"assessment_journeys":outcomes,
        "synthetic_accounts":3,"programme_scenarios":4,
        "real_native_Flask_render_and_POST":True,
        "actual_Ph_signed_delivery_tested":False,
        "actual_production_students_tested":False,
        "no_external_services_contacted":True,
    },sort_keys=True),flush=True)

if __name__=="__main__":
    if len(sys.argv)!=4:raise SystemExit("USAGE: runtime disposable_sqlite label")
    main(sys.argv[1],sys.argv[2],sys.argv[3])
