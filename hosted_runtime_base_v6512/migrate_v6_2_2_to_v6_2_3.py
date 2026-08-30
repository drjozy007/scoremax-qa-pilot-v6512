"""Safely migrate a ScoreMax V6.2.2 SQLite database to V6.2.3.

Usage:
    python migrate_v6_2_2_to_v6_2_3.py path/to/scoremax.db
    python migrate_v6_2_2_to_v6_2_3.py path/to/scoremax.db --dry-run
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, tempfile
from datetime import datetime
from pathlib import Path
from pilot_readiness_engine import sqlite_backup

CORE_TABLES=('users','questions','attempts','attempt_answers','mastery_records','study_plans','study_plan_activities','assessment_blueprints','exam_papers','written_attempts','teacher_profiles','academic_messages','pilot_feedback','knowledge_articles')
NEW_TABLES=('student_pathway_preferences','coach_nudge_events','platform_social_links')

def counts(path: Path):
    c=sqlite3.connect(str(path)); tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; out={}
    for table in CORE_TABLES: out[table]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in tables else None
    c.close(); return out

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('database'); parser.add_argument('--dry-run',action='store_true'); args=parser.parse_args()
    source=Path(args.database).resolve()
    if not source.exists(): raise SystemExit(f'Database not found: {source}')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); backup=source.with_name(f'{source.stem}.pre-v6_2_3-{stamp}.db')
    ok,message=sqlite_backup(source,backup)
    if not ok: raise SystemExit(f'Backup failed: {message}')
    target=source
    if args.dry_run:
        folder=Path(tempfile.mkdtemp(prefix='scoremax_v623_migration_')); target=folder/source.name; shutil.copy2(source,target)
    before=counts(target); os.environ['SCOREMAX_DB']=str(target); os.environ.setdefault('SCOREMAX_ENV','local')
    import app; app.init(); after=counts(target)
    c=sqlite3.connect(str(target)); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; columns={r[1] for r in c.execute('PRAGMA table_info(users)')}; c.close()
    preserved={t:(before[t],after[t]) for t in CORE_TABLES if before.get(t) is not None}; reduced={t:v for t,v in preserved.items() if v[1]<v[0]}; missing=[t for t in NEW_TABLES if t not in tables]; missing_columns=[x for x in ('coach_enabled','future_pathway_code') if x not in columns]
    result={'mode':'DRY_RUN' if args.dry_run else 'LIVE','source':str(source),'target':str(target),'backup':str(backup),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'integrity':integrity,'core_counts':preserved,'reduced_tables':reduced,'missing_new_tables':missing,'missing_user_columns':missing_columns}
    print(json.dumps(result,indent=2))
    if integrity!='ok' or reduced or missing or missing_columns: raise SystemExit('Migration verification failed. Restore the backup and review the report.')
    print('V6.2.2 -> V6.2.3 migration verified successfully.')
if __name__=='__main__': main()
