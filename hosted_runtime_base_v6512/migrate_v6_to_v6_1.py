"""ScoreMax V6.0 -> V6.1 controlled SQLite migration utility.

Usage:
  python migrate_v6_to_v6_1.py path/to/scoremax_v4.db --dry-run
  python migrate_v6_to_v6_1.py path/to/scoremax_v4.db
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PRESERVED_TABLES=[
    'users','questions','attempts','attempt_answers','mastery_records','mastery_history',
    'study_plans','study_plan_activities','classrooms','classroom_students','parent_student_links',
    'exam_papers','exam_paper_questions','assessment_blueprints','assessment_blueprint_sections',
    'assessment_assembly_policies','assessment_policy_activations','written_feature_controls',
    'written_assessment_packages','written_questions','written_attempts','written_answer_versions',
    'written_marking_runs','written_mastery_evidence','written_exemplars'
]
V61_TABLES=[
    'community_feature_controls','community_user_agreements','teacher_profiles','teacher_verification_events','teacher_service_listings',
    'teacher_enquiries','academic_groups','academic_group_members','academic_conversations',
    'academic_conversation_members','academic_messages','academic_message_reports','academic_user_blocks',
    'academic_guardian_consents','teacher_engagements','teacher_reviews'
]


def table_counts(path:Path,names:list[str])->dict[str,int|None]:
    conn=sqlite3.connect(path)
    try:
        existing={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name:(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] if name in existing else None) for name in names}
    finally:
        conn.close()


def run_migration(target:Path)->dict:
    before=table_counts(target,PRESERVED_TABLES)
    os.environ['SCOREMAX_DB']=str(target)
    os.environ.setdefault('SCOREMAX_ENV','local')
    sys.path.insert(0,str(ROOT))
    try:
        import flask  # noqa: F401
    except ModuleNotFoundError:
        from smoke_tests_v5_5 import install_framework_stubs
        install_framework_stubs()
    import app
    conn=sqlite3.connect(target,timeout=30)
    conn.row_factory=sqlite3.Row
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA busy_timeout=30000')
        app.migrate_v5(conn)
        app.migrate_v6(conn)
        app.migrate_v6_1(conn)
        conn.commit()
        integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
    finally:
        conn.close()
    after=table_counts(target,PRESERVED_TABLES)
    return {
        'database':str(target),
        'integrity_check':integrity,
        'preserved_counts_before':before,
        'preserved_counts_after':after,
        'preserved':{k:before[k]==after[k] for k in before if before[k] is not None},
        'v6_1_table_counts':table_counts(target,V61_TABLES),
        'completed_at':datetime.now().isoformat(timespec='seconds')
    }


def main()->int:
    parser=argparse.ArgumentParser(description='Dry-run or execute ScoreMax V6.0 to V6.1 migration')
    parser.add_argument('database',type=Path)
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--no-backup',action='store_true')
    parser.add_argument('--report',type=Path,default=None)
    args=parser.parse_args()
    source=args.database.resolve()
    if not source.exists(): parser.error(f'Database not found: {source}')
    backup=None
    if args.dry_run:
        tmp_dir=Path(tempfile.mkdtemp(prefix='scoremax_v61_migration_'))
        target=tmp_dir/source.name
        shutil.copy2(source,target)
    else:
        target=source
        if not args.no_backup:
            stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
            backup=source.with_name(f'{source.name}.pre_v6_1_{stamp}.bak')
            shutil.copy2(source,backup)
    try:
        result=run_migration(target)
        result.update({'mode':'dry-run' if args.dry_run else 'real','source_database':str(source),'backup':str(backup) if backup else None})
        if result['integrity_check']!='ok': raise RuntimeError(f"SQLite integrity check failed: {result['integrity_check']}")
        if not all(result['preserved'].values()): raise RuntimeError('One or more preserved table counts changed during migration')
        report_path=args.report or source.with_name('V6_1_MIGRATION_RESULT.json')
        report_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result,indent=2)); print(f'Migration report: {report_path}')
        return 0
    except Exception:
        if backup and backup.exists(): print(f'Migration failed. Restore backup from: {backup}',file=sys.stderr)
        raise

if __name__=='__main__':
    raise SystemExit(main())
