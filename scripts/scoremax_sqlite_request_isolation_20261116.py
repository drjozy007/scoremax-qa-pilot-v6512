"""Adversarial request-local student cache and frozen-progress isolation.

Generated accepted ScoreMax runtime + SQLite-only navigation delta; explicitly
requires /tmp disposable synthetic database. No real learners, PH or network.

Tests partitioning by student AND programme, Flask g isolation across GETs,
copy-on-read mutation safety, freshness after committed attempt-answer change,
and no formal mastery awarded by navigation rendering.
"""
from __future__ import annotations
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys

def main(runtime,database):
    runtime=Path(runtime).resolve()
    database=Path(database).resolve()
    if runtime.name!="scoremax_runtime_v669b":
        raise RuntimeError("ACCEPTED_SQLITE_RUNTIME_REQUIRED")
    if not database.is_file() or database.is_symlink() or not database.is_relative_to(Path("/tmp")):
        raise RuntimeError("DISPOSABLE_SQLITE_ONLY")
    root=database.parent.parent
    for part in ("state","backup","intake"):(root/part).mkdir(parents=True,exist_ok=True)
    os.environ.update({
        "SCOREMAX_ENV":"production",
        "SCOREMAX_SECRET":"synthetic-read-isolation-and-identity-2026",
        "SCOREMAX_STAGING_SESSION_SECRET":"synthetic-nav-stage-long-secret-2026",
        "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"test-synthetic-not-for-production",
        "SCOREMAX_BOOTSTRAP_ADMIN_EMAIL":"synthetic-admin@scoremax.invalid",
        "SCOREMAX_SMTP_HOST":"smtp.invalid",
        "SCOREMAX_SMTP_FROM":"test@scoremax.invalid",
        "SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
        "SCOREMAX_SEND_EMAIL_VERIFICATION":"0",
        "SCOREMAX_PUBLIC_STUDENT_OPENING":"0",
        "SCOREMAX_ENFORCE_PAYWALL":"0",
        "SCOREMAX_INTERNAL_FULL_ACCESS":"0",
        "SCOREMAX_DB":str(database),
        "SCOREMAX_PERSISTENT_ROOT":str(root),
        "SCOREMAX_BACKUP_DIR":str(root/"backup"),
        "SCOREMAX_CONTENT_INTAKE_DIR":str(root/"intake"),
        "SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
        "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
    })
    sys.path.insert(0,str(runtime))
    import scoremax_production
    sm=scoremax_production.scoremax
    app=scoremax_production.application
    from flask import g
    with closing(sm.db()) as conn:
        rows=conn.execute("""SELECT id,system_user_id FROM users
           WHERE system_user_id IN ('SYN-STUDENT-NAV-PERF','SYN-STUDENT-SCALE-0',
                    'SYN-STUDENT-SCALE-1')""").fetchall()
        ids={row["system_user_id"]:row["id"] for row in rows}
        if len(ids)!=3:raise RuntimeError("SYNTHETIC_CACHE_ISOLATION_USERS_MISSING")
        a=ids["SYN-STUDENT-NAV-PERF"]
        b=ids["SYN-STUDENT-SCALE-0"]
        c=ids["SYN-STUDENT-SCALE-1"]
        counts={}
        for name,uid in (("primary",a),("secondary",b),("third",c)):
            rs=sm.learner_answer_evidence(conn,uid,"FSc Part 1")
            counts[name]=len(rs)
        if not(counts["primary"]>counts["secondary"]==counts["third"]>0):
            raise RuntimeError("SYNTHETIC_INDIVIDUAL_EVIDENCE_NOT_DISTINCT:"+repr(counts))
        if sm.learner_answer_evidence(conn,b,"MDCAT"):
            raise RuntimeError("FSC_EVIDENCE_LEAKED_INTO_MDCAT")
        formal_before={i:conn.execute("SELECT COUNT(*) FROM mastery_records WHERE student_id=?",
                                 (i,)).fetchone()[0] for i in (a,b,c)}
        def snap(uid):
            return sm._subject_map(conn,uid)
        with app.test_request_context("/student/learn-vnext",method="GET"):
            before=snap(a)
            other=snap(b)
            third=snap(c)
            if before==other:
                raise RuntimeError("SEPARATE_LEARNER_PROGRESS_NOT_DISTINGUISHED")
            if not before or not other:
                raise RuntimeError("SYNTHETIC_SUBJECT_MAP_EMPTY")
            fresh_again=snap(a)
            if before!=fresh_again:
                raise RuntimeError("REQUEST_LOCAL_MAP_NOT_IDEMPOTENT")
            before[0]["answered"]=int(before[0].get("answered") or 0)+9999
            if snap(a)==before:
                raise RuntimeError("REQUEST_LOCAL_SUBJECT_MAP_MUTATION_LEAK")
            if snap(b)!=other or snap(c)!=third:
                raise RuntimeError("CROSS_STUDENT_SUBJECT_MAP_LEAK")
            cache=getattr(g,"_scoremax_subject_map_cache",{})
            if len(cache)<3:
                raise RuntimeError("CACHE_MISSING_STUDENT_PARTITION:"+str(len(cache)))
            e_primary=sm.learner_answer_evidence(conn,a,"FSc Part 1","Biology")
            e_other=sm.learner_answer_evidence(conn,b,"FSc Part 1","Biology")
            if len(e_primary)<=len(e_other):
                raise RuntimeError("CROSS_STUDENT_BIOLOGY_EVIDENCE_MISMATCH")
            if not getattr(g,"_scoremax_frozen_evidence_20261114",{}):
                raise RuntimeError("FROZEN_EVIDENCE_REQUEST_CACHE_NOT_ACTIVE")
            e_other[0]["topic"]="SYN-TAMPER-VIEW-ONLY"
            replay=sm.learner_answer_evidence(conn,b,"FSc Part 1","Biology")
            if replay[0].get("topic")=="SYN-TAMPER-VIEW-ONLY":
                raise RuntimeError("FROZEN_ROW_MUTATION_REACHED_CACHE")
        # Flask request-local g must be reconstructed on the next GET.
        with app.test_request_context("/student/learn-vnext",method="GET"):
            if getattr(g,"_scoremax_subject_map_cache",None) or getattr(
                g,"_scoremax_frozen_evidence_20261114",None):
                raise RuntimeError("CROSS_REQUEST_LEARNER_CACHE_SURVIVED")
            original=sm.learner_answer_evidence(conn,b,"FSc Part 1","Biology")
            if len(original)!=counts["secondary"]:
                raise RuntimeError("EVIDENCE_CHANGED_BEFORE_MUTATION")
            affected=conn.execute("""SELECT aa.id FROM attempt_answers aa
                   JOIN attempts att ON att.id=aa.attempt_id
                   WHERE att.student_id=? ORDER BY aa.id LIMIT 1""",(b,)).fetchone()
            if not affected:raise RuntimeError("SYNTHETIC_DISPOSABLE_ANSWER_MISSING")
            conn.execute("DELETE FROM attempt_answers WHERE id=?",(affected["id"],))
            conn.commit()
            newest=sm.learner_answer_evidence(conn,b,"FSc Part 1","Biology")
            if len(newest)!=counts["secondary"]-1:
                raise RuntimeError("NEW_REQUEST_STALE_AFTER_COMMITTED_ANSWER_CHANGE")
            if len(sm.learner_answer_evidence(conn,a,"FSc Part 1","Biology"))!=counts["primary"]:
                raise RuntimeError("OTHER_STUDENT_EVIDENCE_CHANGED")
            if sm.learner_answer_evidence(conn,b,"MDCAT","Biology"):
                raise RuntimeError("MDCAT_CROSS_PROGRAMME_FROZEN_EVIDENCE_LEAK")
        after={i:conn.execute("SELECT COUNT(*) FROM mastery_records WHERE student_id=?",
                               (i,)).fetchone()[0] for i in (a,b,c)}
        if after!=formal_before:
            raise RuntimeError("NAVIGATION_RENDER_AWARDED_FORMAL_MASTERY")
        if conn.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise RuntimeError("DISPOSABLE_SQLITE_QUICKCHECK_FAILED")
    print("SCOREMAX_SQLITE_REQUEST_ISOLATION_PASS="+json.dumps({
        "source":"accepted_generated_runtime_SQLite_only_candidate",
        "distinct_students":3,"primary_evidence":counts["primary"],
        "secondary_evidence":counts["secondary"],
        "cross_student_subject_cache_isolated":True,
        "cross_request_cache_not_persistent":True,
        "cached_learner_dicts_defensively_copied":True,
        "fsc_context_not_visible_in_mdcat":True,
        "committed_new_answer_state_visible_next_request":True,
        "formal_mastery_rows_unchanged":True,
        "only_disposable_question_answer_removed":True,
        "production_touched":False,
    },sort_keys=True),flush=True)

if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("USAGE: generated_runtime disposable_sqlite")
    main(sys.argv[1],sys.argv[2])
