"""Populate *preservation-only* historical mastery and staged-stop ledger fixtures.

This does NOT award mastery, validate academic eligibility or fabricate Power
House approval. The records use isolated synthetic IDs and non-credit statuses
solely to test exact migration of historical values and rollback. Never run
outside an explicitly disposable /tmp/ ScoreMax database.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sqlite3
import sys

def main(path):
    path=Path(path).resolve()
    if not path.is_file() or not path.is_relative_to(Path("/tmp")):
        raise RuntimeError("REFUSE_NON_DISPOSABLE_LEDGER")
    c=sqlite3.connect(path,timeout=8)
    c.row_factory=sqlite3.Row
    try:
        user=c.execute("SELECT id FROM users WHERE system_user_id=?",
                       ("SYN-STUDENT-NAV-PERF",)).fetchone()
        row=c.execute("""SELECT id,assessment_session_id FROM attempts
           WHERE assessment_session_id IS NOT NULL ORDER BY id DESC LIMIT 1""").fetchone()
        if not user or not row:
            raise RuntimeError("NO_NATIVE_STUDENT_ATTEMPT_FOR_PRESERVATION")
        student=int(user["id"]);attempt=int(row["id"])
        session=int(row["assessment_session_id"])
        scope="SYN-MIGRATION::HISTORICAL::BIOLOGY"
        # This deliberately represents a stale historical record, not a
        # new formal achievement; native mastery awarding is NOT called.
        mastery=c.execute("""INSERT INTO mastery_records(
           student_id,scope_type,scope_key,programme,subject,chapter,
           mastery_level,status,verified_at,verification_due_at,
           best_accuracy,forms_passed,questions_total,failed_reconfirmations)
           VALUES(?, 'chapter', ?, 'FSc Part 1','Biology','Synthetic Chapter 1',
             'Foundation','Verification Due','2020-01-01T00:00:00Z',
             '2020-04-01',0,0,0,1)""",(student,scope)).lastrowid
        c.execute("""INSERT INTO mastery_form_results(
           student_id,assessment_session_id,attempt_id,scope_type,scope_key,
           programme,subject,chapter,target_level,score,question_count,
           passed,demo_only,breadth_ok,unseen_family_ratio,family_ids_json,
           policy_snapshot_json,assembly_policy_id,assembly_policy_version,
           effective_policy_json)
           VALUES(?,?,?,'chapter',?,'FSc Part 1','Biology',
             'Synthetic Chapter 1','Foundation',0,1,0,1,0,0,
             '[]','{"fixture":"non-credit"}',NULL,'1',
             '{"fixture":"preservation-only"}')""",
           (student,session,attempt,scope))
        c.execute("""INSERT INTO mastery_history(
           mastery_record_id,student_id,scope_type,scope_key,event_type,
           previous_level,new_level,previous_status,new_status,
           attempt_id,assessment_session_id,note,metadata_json)
           VALUES(?,?,'chapter',?,'verification_due',
             'Foundation','Foundation','Verification Due','Verification Due',
             ?,?,'SYNTHETIC PRESERVATION ONLY — NO ACADEMIC CREDIT',
             '{"fixture":"historical-row-migration"}')""",
           (mastery,student,scope,attempt,session))
        # An exclusion bound to a nonexistent staged release cannot remove
        # a genuine member. This is solely an exact-data-copy specimen.
        c.execute("""INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e(
          release_id,release_version,question_id,question_version_id,
          question_checksum_sha256,item_public_id,export_public_id,
          population_sha256,withdrawal_queue_id,hold_id,defect_code,
          reason,item_sha256,created_at)
          VALUES('SYN-EXCLUSION-NO-RELEASE','1','SYN-EXCLUDED-PH-Q',
           'SYN-EXCLUDED-PH-V', ?, 'SYN-STOP-ITEM','SYN-STOP-EXPORT',
           ?, 'SYN-STOP-QUEUE','SYN-HOLD','SYN-TEST-ONLY',
           'MIGRATION PRESERVATION ONLY', ?, '2026-11-16T00:00:00Z')""",
           ("a"*64,"b"*64,"c"*64))
        c.commit()
        tables=("mastery_records","mastery_form_results","mastery_history",
                "ph_bridge_staged_withdrawal_exclusions_v6611e")
        counts={t:c.execute("SELECT COUNT(*) FROM "+t).fetchone()[0]
                for t in tables}
        if any(v!=1 for v in counts.values()):
            raise RuntimeError("HISTORICAL_LEDGER_TEST_FIXTURE_DRIFT:"+str(counts))
        if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
            raise RuntimeError("HISTORICAL_LEDGER_SQLITE_INTEGRITY_FAILED")
        print("SCOREMAX_PG_HISTORY_PRESERVATION_FIXTURE_PASS="+json.dumps({
          "synthetic_noncredit_historical_rows":counts,
          "native_formal_mastery_awarded":False,
          "synthetic_no_live_release_scoped_staged_hold":True,
          "real_history_or_PH_data_used":False,
          "production_touched":False,
        },sort_keys=True),flush=True)
    finally:c.close()

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("USAGE: disposable_sqlite")
    main(sys.argv[1])
