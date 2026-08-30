"""Safely migrate a ScoreMax V6.2.6 SQLite database to V6.2.7.

Usage:
    python migrate_v6_2_6_to_v6_2_7.py path/to/scoremax.db --dry-run
    python migrate_v6_2_6_to_v6_2_7.py path/to/scoremax.db
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, tempfile
from datetime import datetime
from pathlib import Path
from pilot_readiness_engine import sqlite_backup

CORE_TABLES=(
 'users','questions','attempts','attempt_answers','mastery_records','study_plans','study_plan_activities',
 'assessment_blueprints','exam_papers','written_attempts','teacher_profiles','academic_messages','pilot_feedback',
 'knowledge_articles','daily_spark_assignments','sustainability_content_blocks','content_import_batches',
 'mastery_lab_questions','mastery_lab_runs')
NEW_TABLES=(
 'reviewer_feature_controls','reviewer_batches','reviewer_questions','reviewer_assignments','reviewer_assignment_items',
 'reviewer_time_events','reviewer_question_outcomes','reviewer_audit_events')


def counts(path: Path):
    c=sqlite3.connect(str(path)); tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; out={}
    for table in CORE_TABLES: out[table]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in tables else None
    c.close(); return out


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('database'); parser.add_argument('--dry-run',action='store_true'); args=parser.parse_args()
    source=Path(args.database).resolve()
    if not source.exists(): raise SystemExit(f'Database not found: {source}')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); backup=source.with_name(f'{source.stem}.pre-v6_2_7-{stamp}.db')
    ok,message=sqlite_backup(source,backup)
    if not ok: raise SystemExit(f'Backup failed: {message}')
    target=source
    if args.dry_run:
        folder=Path(tempfile.mkdtemp(prefix='scoremax_v627_migration_')); target=folder/source.name; shutil.copy2(source,target)
    before=counts(target); os.environ['SCOREMAX_DB']=str(target); os.environ.setdefault('SCOREMAX_ENV','local')
    try:
        import flask  # noqa: F401
    except ModuleNotFoundError:
        from smoke_tests_v5_5 import install_framework_stubs
        install_framework_stubs()
    import app; app.init(); after=counts(target)
    c=sqlite3.connect(str(target)); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    reviewer_rows={t:c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in NEW_TABLES if t in tables}
    control=c.execute("SELECT state,configuration_json FROM reviewer_feature_controls WHERE feature_code='academic_reviewer_workspace'").fetchone() if 'reviewer_feature_controls' in tables else None
    reviewer_users=c.execute("SELECT COUNT(*) FROM users WHERE role='reviewer'").fetchone()[0] if 'users' in tables else -1
    c.close()
    preserved={t:(before[t],after[t]) for t in CORE_TABLES if before.get(t) is not None}; reduced={t:v for t,v in preserved.items() if v[1]<v[0]}; missing=[t for t in NEW_TABLES if t not in tables]
    result={'mode':'DRY_RUN' if args.dry_run else 'LIVE','source':str(source),'target':str(target),'backup':str(backup),
      'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'integrity':integrity,'core_counts':preserved,
      'reduced_tables':reduced,'missing_new_tables':missing,'reviewer_table_counts':reviewer_rows,
      'reviewer_feature_state':control[0] if control else None,'reviewer_users_created_automatically':reviewer_users}
    print(json.dumps(result,indent=2))
    if integrity!='ok' or reduced or missing or not control or control[0]!='QA_ONLY' or any(reviewer_rows.get(t,0) for t in NEW_TABLES if t!='reviewer_feature_controls') or reviewer_users!=0:
        raise SystemExit('Migration verification failed. Restore the backup and review the report.')
    print('V6.2.6 -> V6.2.7 migration verified successfully.')

if __name__=='__main__': main()
