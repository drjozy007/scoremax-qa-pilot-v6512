"""Safely migrate a ScoreMax V6.2.4 SQLite database to V6.2.5.

Usage:
    python migrate_v6_2_4_to_v6_2_5.py path/to/scoremax.db
    python migrate_v6_2_4_to_v6_2_5.py path/to/scoremax.db --dry-run
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sqlite3, tempfile
from datetime import datetime
from pathlib import Path
from pilot_readiness_engine import sqlite_backup

CORE_TABLES=('users','questions','attempts','attempt_answers','mastery_records','study_plans','study_plan_activities',
             'assessment_blueprints','exam_papers','written_attempts','teacher_profiles','academic_messages',
             'pilot_feedback','knowledge_articles','student_pathway_preferences','coach_nudge_events')
NEW_TABLES=('sustainability_feature_controls','sustainability_content_blocks','sustainability_policies',
            'sustainability_commitments','sustainability_progress_reports','sustainability_draft_intake',
            'daily_spark_feature_controls','daily_spark_words','daily_spark_assignments','daily_spark_events')


def counts(path: Path):
    c=sqlite3.connect(str(path)); tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; out={}
    for table in CORE_TABLES: out[table]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in tables else None
    c.close(); return out


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('database'); parser.add_argument('--dry-run',action='store_true'); args=parser.parse_args()
    source=Path(args.database).resolve()
    if not source.exists(): raise SystemExit(f'Database not found: {source}')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); backup=source.with_name(f'{source.stem}.pre-v6_2_5-{stamp}.db')
    ok,message=sqlite_backup(source,backup)
    if not ok: raise SystemExit(f'Backup failed: {message}')
    target=source
    if args.dry_run:
        folder=Path(tempfile.mkdtemp(prefix='scoremax_v625_migration_')); target=folder/source.name; shutil.copy2(source,target)
    before=counts(target); os.environ['SCOREMAX_DB']=str(target); os.environ.setdefault('SCOREMAX_ENV','local')
    import app; app.init(); after=counts(target)
    c=sqlite3.connect(str(target)); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    words=c.execute('SELECT COUNT(*) FROM daily_spark_words').fetchone()[0] if 'daily_spark_words' in tables else 0
    blocks=c.execute("SELECT COUNT(*) FROM sustainability_content_blocks WHERE status='PUBLISHED'").fetchone()[0] if 'sustainability_content_blocks' in tables else 0
    c.close()
    preserved={t:(before[t],after[t]) for t in CORE_TABLES if before.get(t) is not None}; reduced={t:v for t,v in preserved.items() if v[1]<v[0]}; missing=[t for t in NEW_TABLES if t not in tables]
    result={'mode':'DRY_RUN' if args.dry_run else 'LIVE','source':str(source),'target':str(target),'backup':str(backup),
            'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'integrity':integrity,'core_counts':preserved,
            'reduced_tables':reduced,'missing_new_tables':missing,'seeded_vocabulary_words':words,'published_sustainability_blocks':blocks}
    print(json.dumps(result,indent=2))
    if integrity!='ok' or reduced or missing or words<30 or blocks<4:
        raise SystemExit('Migration verification failed. Restore the backup and review the report.')
    print('V6.2.4 -> V6.2.5 migration verified successfully.')

if __name__=='__main__': main()
