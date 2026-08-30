"""Safely migrate a ScoreMax V6.2.5 SQLite database to V6.2.6.

Usage:
    python migrate_v6_2_5_to_v6_2_6.py path/to/scoremax.db
    python migrate_v6_2_5_to_v6_2_6.py path/to/scoremax.db --dry-run
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, tempfile
from datetime import datetime
from pathlib import Path
from pilot_readiness_engine import sqlite_backup

CORE_TABLES=(
 'users','questions','attempts','attempt_answers','mastery_records','study_plans','study_plan_activities',
 'assessment_blueprints','exam_papers','written_attempts','teacher_profiles','academic_messages','pilot_feedback',
 'knowledge_articles','student_pathway_preferences','coach_nudge_events','daily_spark_assignments','daily_spark_events',
 'sustainability_content_blocks','content_import_batches')
NEW_TABLES=(
 'mastery_lab_feature_controls','mastery_lab_batches','mastery_lab_questions','mastery_lab_question_relations',
 'mastery_lab_policies','mastery_lab_synthetic_profiles','mastery_lab_runs','mastery_lab_responses','mastery_lab_evidence',
 'mastery_lab_state_history','mastery_lab_recovery_needs','mastery_lab_gate_results','mastery_lab_blockers','mastery_lab_audit_events')


def table_counts(path: Path):
    c=sqlite3.connect(str(path)); tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; out={}
    for table in CORE_TABLES:
        out[table]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in tables else None
    c.close(); return out


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('database'); parser.add_argument('--dry-run',action='store_true'); args=parser.parse_args()
    source=Path(args.database).resolve()
    if not source.exists(): raise SystemExit(f'Database not found: {source}')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); backup=source.with_name(f'{source.stem}.pre-v6_2_6-{stamp}.db')
    ok,message=sqlite_backup(source,backup)
    if not ok: raise SystemExit(f'Backup failed: {message}')
    target=source
    if args.dry_run:
        folder=Path(tempfile.mkdtemp(prefix='scoremax_v626_migration_')); target=folder/source.name; shutil.copy2(source,target)
    before=table_counts(target); os.environ['SCOREMAX_DB']=str(target); os.environ.setdefault('SCOREMAX_ENV','local')
    try:
        import flask  # noqa: F401
    except ModuleNotFoundError:
        from smoke_tests_v5_5 import install_framework_stubs
        install_framework_stubs()
    import app; app.init(); after=table_counts(target)
    c=sqlite3.connect(str(target)); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    policies=c.execute('SELECT COUNT(*) FROM mastery_lab_policies WHERE active=1').fetchone()[0] if 'mastery_lab_policies' in tables else 0
    profiles=c.execute('SELECT COUNT(*) FROM mastery_lab_synthetic_profiles WHERE active=1').fetchone()[0] if 'mastery_lab_synthetic_profiles' in tables else 0
    sandbox_questions=c.execute('SELECT COUNT(*) FROM mastery_lab_questions').fetchone()[0] if 'mastery_lab_questions' in tables else -1
    live_attempt_leaks=c.execute("SELECT COUNT(*) FROM attempts WHERE assessment_kind='mastery_lab' OR scope='mastery_lab'").fetchone()[0] if 'attempts' in tables else 0
    live_mastery_leaks=c.execute("SELECT COUNT(*) FROM mastery_records WHERE source='Mastery Laboratory'").fetchone()[0] if 'mastery_records' in tables else 0
    c.close()
    preserved={t:(before[t],after[t]) for t in CORE_TABLES if before.get(t) is not None}; reduced={t:v for t,v in preserved.items() if v[1]<v[0]}; missing=[t for t in NEW_TABLES if t not in tables]
    result={'mode':'DRY_RUN' if args.dry_run else 'LIVE','source':str(source),'target':str(target),'backup':str(backup),
      'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'integrity':integrity,'core_counts':preserved,
      'reduced_tables':reduced,'missing_new_tables':missing,'seeded_lab_policies':policies,'seeded_synthetic_profiles':profiles,
      'sandbox_candidate_count_after_migration':sandbox_questions,'live_attempt_leaks':live_attempt_leaks,'live_mastery_leaks':live_mastery_leaks}
    print(json.dumps(result,indent=2))
    if integrity!='ok' or reduced or missing or policies!=4 or profiles!=7 or sandbox_questions!=0 or live_attempt_leaks or live_mastery_leaks:
        raise SystemExit('Migration verification failed. Restore the backup and review the report.')
    print('V6.2.5 -> V6.2.6 migration verified successfully.')

if __name__=='__main__': main()
