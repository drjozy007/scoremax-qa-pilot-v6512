"""Safely migrate a ScoreMax V6.2.8 SQLite database to V6.2.8.1.

V6.2.8.1 adds Power House academic-review workbook lineage fields only.
Existing live questions, users, attempts, mastery, Study Plans, reviewer batches,
assignments, decisions, timing and commercial entitlements are preserved.

Usage:
    python migrate_v6_2_8_to_v6_2_8_1.py path/to/scoremax.db --dry-run
    python migrate_v6_2_8_to_v6_2_8_1.py path/to/scoremax.db
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from pilot_readiness_engine import sqlite_backup

CORE_TABLES=(
    'users','questions','attempts','attempt_answers','mastery_records','study_plans','study_plan_activities',
    'assessment_blueprints','exam_papers','written_attempts','teacher_profiles','academic_messages','pilot_feedback',
    'knowledge_articles','daily_spark_assignments','sustainability_content_blocks','content_import_batches',
    'mastery_lab_questions','mastery_lab_runs','subscriptions','payments','coverage_packages',
    'student_package_entitlements','package_entitlement_history','checkout_requests'
)
REVIEWER_TABLES=(
    'reviewer_imports','reviewer_batches','reviewer_questions','reviewer_assignments','reviewer_assignment_items',
    'reviewer_time_events','reviewer_question_outcomes','reviewer_audit_events','reviewer_feature_controls'
)
QUESTION_COLUMNS={
    'stimulus_context','review_content','question_type','review_priority','review_requirement','reviewer2_required',
    'source_sheet','source_row'
}
BATCH_COLUMNS={'source_sheet','source_part_number','source_part_count'}
REQUIRED_INDEXES={'idx_reviewer_batches_source_sheet'}


def table_names(c):
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def counts(path: Path,tables):
    c=sqlite3.connect(str(path)); existing=table_names(c); out={}
    for table in tables:
        out[table]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in existing else None
    c.close(); return out


def columns(c,table):
    return {r[1] for r in c.execute(f'PRAGMA table_info({table})')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('database')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    source=Path(args.database).resolve()
    if not source.exists(): raise SystemExit(f'Database not found: {source}')

    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=source.with_name(f'{source.stem}.pre-v6_2_8_1-{stamp}.db')
    ok,message=sqlite_backup(source,backup)
    if not ok: raise SystemExit(f'Backup failed: {message}')

    target=source
    if args.dry_run:
        folder=Path(tempfile.mkdtemp(prefix='scoremax_v6281_migration_'))
        target=folder/source.name
        shutil.copy2(source,target)

    before_core=counts(target,CORE_TABLES); before_reviewer=counts(target,REVIEWER_TABLES)
    os.environ['SCOREMAX_DB']=str(target); os.environ.setdefault('SCOREMAX_ENV','local')
    try:
        import flask  # noqa: F401
    except ModuleNotFoundError:
        from smoke_tests_v5_5 import install_framework_stubs
        install_framework_stubs()
    import app
    app.init()
    after_core=counts(target,CORE_TABLES); after_reviewer=counts(target,REVIEWER_TABLES)

    c=sqlite3.connect(str(target))
    integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    qcols=columns(c,'reviewer_questions'); bcols=columns(c,'reviewer_batches')
    indexes={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    c.close()

    reduced_core={t:(before_core[t],after_core[t]) for t in CORE_TABLES if before_core.get(t) is not None and after_core.get(t,0)<before_core[t]}
    changed_reviewer={t:(before_reviewer[t],after_reviewer[t]) for t in REVIEWER_TABLES if before_reviewer.get(t) is not None and before_reviewer[t]!=after_reviewer[t]}
    result={
        'mode':'DRY_RUN' if args.dry_run else 'LIVE','source':str(source),'target':str(target),'backup':str(backup),
        'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'integrity':integrity,
        'reduced_core_tables':reduced_core,'changed_reviewer_row_counts':changed_reviewer,
        'missing_reviewer_question_columns':sorted(QUESTION_COLUMNS-qcols),
        'missing_reviewer_batch_columns':sorted(BATCH_COLUMNS-bcols),
        'missing_indexes':sorted(REQUIRED_INDEXES-indexes),
    }
    print(json.dumps(result,indent=2))
    if integrity!='ok' or reduced_core or changed_reviewer or result['missing_reviewer_question_columns'] or result['missing_reviewer_batch_columns'] or result['missing_indexes']:
        raise SystemExit('Migration verification failed. Restore the backup and review the report.')
    print('V6.2.8 -> V6.2.8.1 migration verified successfully.')


if __name__=='__main__':
    main()
