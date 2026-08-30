"""Safely migrate a ScoreMax V6.2.7 SQLite database to V6.2.7.1.

Unused V6.2.7 reviewer invitations are invalidated because they do not have the new
separately delivered verification code. Admins can reissue them from Reviewer Workspace.

Usage:
    python migrate_v6_2_7_to_v6_2_7_1.py path/to/scoremax.db --dry-run
    python migrate_v6_2_7_to_v6_2_7_1.py path/to/scoremax.db
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
PRESERVED_REVIEWER_TABLES=(
 'reviewer_batches','reviewer_questions','reviewer_assignments','reviewer_assignment_items',
 'reviewer_time_events','reviewer_question_outcomes')
REQUIRED_INDEXES={
 'uq_reviewer_batch_checksum','uq_reviewer_first_assignment','uq_reviewer_second_question'}


def counts(path: Path, tables):
    c=sqlite3.connect(str(path)); existing={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}; out={}
    for table in tables: out[table]=c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] if table in existing else None
    c.close(); return out


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('database'); parser.add_argument('--dry-run',action='store_true'); args=parser.parse_args()
    source=Path(args.database).resolve()
    if not source.exists(): raise SystemExit(f'Database not found: {source}')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S'); backup=source.with_name(f'{source.stem}.pre-v6_2_7_1-{stamp}.db')
    ok,message=sqlite_backup(source,backup)
    if not ok: raise SystemExit(f'Backup failed: {message}')
    target=source
    if args.dry_run:
        folder=Path(tempfile.mkdtemp(prefix='scoremax_v6271_migration_')); target=folder/source.name; shutil.copy2(source,target)
    before_core=counts(target,CORE_TABLES); before_reviewer=counts(target,PRESERVED_REVIEWER_TABLES)
    c=sqlite3.connect(str(target));
    legacy_invites=c.execute("SELECT COUNT(*) FROM reviewer_assignments WHERE status='INVITED'").fetchone()[0] if before_reviewer.get('reviewer_assignments') is not None else 0
    c.close()
    os.environ['SCOREMAX_DB']=str(target); os.environ.setdefault('SCOREMAX_ENV','local')
    try:
        import flask  # noqa: F401
    except ModuleNotFoundError:
        from smoke_tests_v5_5 import install_framework_stubs
        install_framework_stubs()
    import app; app.init()
    after_core=counts(target,CORE_TABLES); after_reviewer=counts(target,PRESERVED_REVIEWER_TABLES)
    c=sqlite3.connect(str(target)); integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    indexes={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assignment_columns={r[1] for r in c.execute('PRAGMA table_info(reviewer_assignments)')}
    item_columns={r[1] for r in c.execute('PRAGMA table_info(reviewer_assignment_items)')}
    reissue_required=c.execute("SELECT COUNT(*) FROM reviewer_assignments WHERE status='INVITATION_REISSUE_REQUIRED'").fetchone()[0]
    legacy_tokens=c.execute("SELECT COUNT(*) FROM reviewer_assignments WHERE status='INVITATION_REISSUE_REQUIRED' AND invitation_token_hash IS NOT NULL").fetchone()[0]
    c.close()
    reduced={t:(before_core[t],after_core[t]) for t in CORE_TABLES if before_core.get(t) is not None and after_core.get(t,0)<before_core[t]}
    reviewer_changed={t:(before_reviewer[t],after_reviewer[t]) for t in PRESERVED_REVIEWER_TABLES if before_reviewer.get(t) is not None and before_reviewer[t]!=after_reviewer[t]}
    missing_indexes=sorted(REQUIRED_INDEXES-indexes)
    missing_columns=sorted({'invitation_verification_hash','invitation_verification_attempts','invitation_locked_at'}-assignment_columns)
    if 'round_no' not in item_columns: missing_columns.append('reviewer_assignment_items.round_no')
    result={'mode':'DRY_RUN' if args.dry_run else 'LIVE','source':str(source),'target':str(target),'backup':str(backup),
      'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'integrity':integrity,
      'core_counts_before_after':{t:(before_core[t],after_core[t]) for t in CORE_TABLES if before_core.get(t) is not None},
      'reviewer_counts_before_after':{t:(before_reviewer[t],after_reviewer[t]) for t in PRESERVED_REVIEWER_TABLES if before_reviewer.get(t) is not None},
      'reduced_core_tables':reduced,'changed_reviewer_row_counts':reviewer_changed,
      'legacy_invites_before':legacy_invites,'invitations_requiring_reissue_after':reissue_required,
      'reissue_rows_retaining_old_tokens':legacy_tokens,'missing_indexes':missing_indexes,'missing_columns':missing_columns}
    print(json.dumps(result,indent=2))
    if integrity!='ok' or reduced or reviewer_changed or missing_indexes or missing_columns or legacy_tokens:
        raise SystemExit('Migration verification failed. Restore the backup and review the report.')
    print('V6.2.7 -> V6.2.7.1 migration verified successfully.')

if __name__=='__main__': main()
