"""Safely migrate a ScoreMax V6.2.7.2 SQLite database to V6.2.8.

V6.2.8 adds guided large reviewer imports and programme/subject package
entitlements. Existing questions, users, attempts, mastery, Study Plans,
reviewer batches, assignments, decisions and timing records are preserved.

Usage:
    python migrate_v6_2_7_2_to_v6_2_8.py path/to/scoremax.db --dry-run
    python migrate_v6_2_7_2_to_v6_2_8.py path/to/scoremax.db
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

CORE_TABLES = (
    'users','questions','attempts','attempt_answers','mastery_records','study_plans','study_plan_activities',
    'assessment_blueprints','exam_papers','written_attempts','teacher_profiles','academic_messages','pilot_feedback',
    'knowledge_articles','daily_spark_assignments','sustainability_content_blocks','content_import_batches',
    'mastery_lab_questions','mastery_lab_runs','subscriptions','payments'
)
REVIEWER_TABLES = (
    'reviewer_batches','reviewer_questions','reviewer_assignments','reviewer_assignment_items',
    'reviewer_time_events','reviewer_question_outcomes','reviewer_audit_events','reviewer_workspace_controls'
)
NEW_TABLES = {
    'reviewer_imports','coverage_packages','student_package_entitlements',
    'package_entitlement_history','checkout_requests'
}
REQUIRED_INDEXES = {
    'idx_reviewer_imports_created','idx_reviewer_batches_import','idx_reviewer_assignments_group',
    'idx_student_package_entitlements','idx_coverage_packages_programme'
}
EXPECTED_PACKAGE_CODES = {
    'fsc1_biology','fsc1_two_subjects','fsc1_science_bundle','fsc1_full',
    'grade9_full','grade10_full','fsc2_full','mdcat_full'
}


def table_names(c: sqlite3.Connection) -> set[str]:
    return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def counts(path: Path, tables) -> dict[str, int | None]:
    c=sqlite3.connect(str(path))
    existing=table_names(c)
    out={}
    for table in tables:
        out[table]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in existing else None
    c.close()
    return out


def columns(c: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in c.execute(f'PRAGMA table_info({table})')}


def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument('database')
    parser.add_argument('--dry-run', action='store_true')
    args=parser.parse_args()

    source=Path(args.database).resolve()
    if not source.exists():
        raise SystemExit(f'Database not found: {source}')

    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=source.with_name(f'{source.stem}.pre-v6_2_8-{stamp}.db')
    ok,message=sqlite_backup(source,backup)
    if not ok:
        raise SystemExit(f'Backup failed: {message}')

    target=source
    if args.dry_run:
        folder=Path(tempfile.mkdtemp(prefix='scoremax_v628_migration_'))
        target=folder/source.name
        shutil.copy2(source,target)

    before_core=counts(target,CORE_TABLES)
    before_reviewer=counts(target,REVIEWER_TABLES)

    os.environ['SCOREMAX_DB']=str(target)
    os.environ.setdefault('SCOREMAX_ENV','local')
    try:
        import flask  # noqa: F401
    except ModuleNotFoundError:
        from smoke_tests_v5_5 import install_framework_stubs
        install_framework_stubs()

    import app
    app.init()

    after_core=counts(target,CORE_TABLES)
    after_reviewer=counts(target,REVIEWER_TABLES)

    c=sqlite3.connect(str(target))
    c.row_factory=sqlite3.Row
    integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    existing_tables=table_names(c)
    existing_indexes={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}

    batch_columns=columns(c,'reviewer_batches')
    assignment_columns=columns(c,'reviewer_assignments')
    subscription_columns=columns(c,'subscriptions')

    package_codes={r[0] for r in c.execute('SELECT code FROM coverage_packages')} if 'coverage_packages' in existing_tables else set()
    auto_imports=c.execute('SELECT COUNT(*) FROM reviewer_imports').fetchone()[0] if 'reviewer_imports' in existing_tables else -1
    auto_entitlements=c.execute('SELECT COUNT(*) FROM student_package_entitlements').fetchone()[0] if 'student_package_entitlements' in existing_tables else -1
    auto_history=c.execute('SELECT COUNT(*) FROM package_entitlement_history').fetchone()[0] if 'package_entitlement_history' in existing_tables else -1
    auto_checkout=c.execute('SELECT COUNT(*) FROM checkout_requests').fetchone()[0] if 'checkout_requests' in existing_tables else -1
    c.close()

    reduced_core={
        t:(before_core[t],after_core[t]) for t in CORE_TABLES
        if before_core.get(t) is not None and after_core.get(t,0)<before_core[t]
    }
    reviewer_changed={
        t:(before_reviewer[t],after_reviewer[t]) for t in REVIEWER_TABLES
        if before_reviewer.get(t) is not None and before_reviewer[t]!=after_reviewer[t]
    }
    missing_tables=sorted(NEW_TABLES-existing_tables)
    missing_indexes=sorted(REQUIRED_INDEXES-existing_indexes)
    missing_columns=[]
    for name in ('import_id','batch_number','batch_count'):
        if name not in batch_columns:
            missing_columns.append(f'reviewer_batches.{name}')
    if 'assignment_group_code' not in assignment_columns:
        missing_columns.append('reviewer_assignments.assignment_group_code')
    if 'coverage_package_id' not in subscription_columns:
        missing_columns.append('subscriptions.coverage_package_id')
    missing_packages=sorted(EXPECTED_PACKAGE_CODES-package_codes)

    result={
        'mode':'DRY_RUN' if args.dry_run else 'LIVE',
        'source':str(source),
        'target':str(target),
        'backup':str(backup),
        'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
        'integrity':integrity,
        'core_counts_before_after':{t:(before_core[t],after_core[t]) for t in CORE_TABLES if before_core.get(t) is not None},
        'reviewer_counts_before_after':{t:(before_reviewer[t],after_reviewer[t]) for t in REVIEWER_TABLES if before_reviewer.get(t) is not None},
        'reduced_core_tables':reduced_core,
        'changed_reviewer_row_counts':reviewer_changed,
        'missing_tables':missing_tables,
        'missing_indexes':missing_indexes,
        'missing_columns':missing_columns,
        'missing_seed_package_codes':missing_packages,
        'automatic_reviewer_imports_created':auto_imports,
        'automatic_student_entitlements_created':auto_entitlements,
        'automatic_entitlement_history_created':auto_history,
        'automatic_checkout_requests_created':auto_checkout,
    }
    print(json.dumps(result,indent=2))

    failed=(
        integrity!='ok' or reduced_core or reviewer_changed or missing_tables or missing_indexes or
        missing_columns or missing_packages or auto_imports!=0 or auto_entitlements!=0 or
        auto_history!=0 or auto_checkout!=0
    )
    if failed:
        raise SystemExit('Migration verification failed. Restore the backup and review the report.')
    print('V6.2.7.2 -> V6.2.8 migration verified successfully.')


if __name__=='__main__':
    main()
