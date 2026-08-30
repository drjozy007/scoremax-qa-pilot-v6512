"""Migrate an existing ScoreMax V6.1 SQLite database to V6.2 safely.

Usage:
    python migrate_v6_1_to_v6_2.py path/to/scoremax.db
    python migrate_v6_1_to_v6_2.py path/to/scoremax.db --dry-run

The script creates an integrity-checked backup before changing the live file.
Dry-run mode migrates a disposable copy and leaves the source untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from pilot_readiness_engine import sqlite_backup

CORE_TABLES=(
    'users','questions','attempts','attempt_answers','mastery_records','mastery_history',
    'classrooms','classroom_students','assessment_blueprints','exam_papers',
    'written_assessment_packages','written_attempts','teacher_profiles','academic_messages')
NEW_TABLES=(
    'pilot_feature_controls','powerhouse_prompt_packs','powerhouse_generation_batches',
    'content_import_batches','content_import_batch_rows','pilot_backups','pilot_feedback',
    'pilot_activity_events','demo_cleanup_runs','knowledge_feature_controls',
    'knowledge_articles','knowledge_sources','growth_content_intake')


def counts(db_path: Path):
    c=sqlite3.connect(str(db_path)); out={}
    tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table in CORE_TABLES:
        out[table]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in tables else None
    c.close(); return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('database')
    parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    source=Path(args.database).resolve()
    if not source.exists(): raise SystemExit(f'Database not found: {source}')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=source.with_name(f'{source.stem}.pre-v6_2-{stamp}.db')
    ok,message=sqlite_backup(source,backup)
    if not ok: raise SystemExit(f'Backup failed: {message}')
    target=source
    temp_dir=None
    if args.dry_run:
        temp_dir=Path(tempfile.mkdtemp(prefix='scoremax_v62_migration_'))
        target=temp_dir/source.name
        shutil.copy2(source,target)
    before=counts(target)
    os.environ['SCOREMAX_DB']=str(target)
    os.environ.setdefault('SCOREMAX_ENV','local')
    import app
    app.init()
    after=counts(target)
    c=sqlite3.connect(str(target)); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    tables={row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; c.close()
    preserved={table:(before[table],after[table]) for table in CORE_TABLES if before.get(table) is not None}
    reduced={table:pair for table,pair in preserved.items() if pair[1] < pair[0]}
    missing=[table for table in NEW_TABLES if table not in tables]
    result={'mode':'DRY_RUN' if args.dry_run else 'LIVE','source':str(source),'target':str(target),
            'backup':str(backup),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
            'integrity':integrity,'core_counts':preserved,'reduced_tables':reduced,'missing_new_tables':missing}
    print(json.dumps(result,indent=2))
    if integrity!='ok' or reduced or missing:
        raise SystemExit('Migration verification failed. Restore the backup and review the report.')
    print('V6.1 -> V6.2 migration verified successfully.')


if __name__=='__main__':
    main()
