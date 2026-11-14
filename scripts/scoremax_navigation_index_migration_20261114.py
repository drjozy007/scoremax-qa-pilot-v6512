"""Explicit guarded ScoreMax navigation index migration.

ONLY run during a coordinated ScoreMax migration window. It is NEVER invoked by
normal boot, delivery/ACK dispatch, or this repository's production start command.

Creates only additive SQLite indexes. Requires a verified SQLite backup in a
separate file, an exclusive write probe, and sufficient free disk space. Repeated
invocations are idempotent. No question, attempt, release or mastery rows change.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3

INDEXES={
 "idx_sm_nav_subject_programme_20261114":
   "CREATE INDEX idx_sm_nav_subject_programme_20261114 ON questions(lower(subject),lower(COALESCE(programme,'')),chapter)",
 "idx_sm_nav_subject_qualification_20261114":
   "CREATE INDEX idx_sm_nav_subject_qualification_20261114 ON questions(lower(subject),lower(COALESCE(qualification,'')),chapter)",
 "idx_sm_nav_programme_20261114":
   "CREATE INDEX idx_sm_nav_programme_20261114 ON questions(lower(COALESCE(programme,'')),lower(subject))",
 "idx_sm_nav_qualification_20261114":
   "CREATE INDEX idx_sm_nav_qualification_20261114 ON questions(lower(COALESCE(qualification,'')),lower(subject))",
}

def quickcheck(connection):
    result=connection.execute("PRAGMA quick_check").fetchone()
    if not result or result[0]!="ok":raise RuntimeError("SCOREMAX_NAV_DB_INTEGRITY_FAILED")
    return True

def census(connection):
    # Read-only checkpoints, unchanged by index creation.
    return {table:connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("questions","attempts","attempt_answers","mastery_records",
                          "integration_ph_content_releases","integration_ph_release_question_membership")}

def existing_indexes(connection):
    return {row[0]:row[1] for row in connection.execute(
        "SELECT name,sql FROM sqlite_master WHERE type='index' AND name IN (?,?,?,?)",
        tuple(INDEXES))}

def migrate(database: Path, backup: Path|None, apply: bool=False):
    database=database.resolve()
    if not database.is_file() or database.is_symlink():
        raise RuntimeError("SCOREMAX_NAV_DATABASE_MISSING_OR_SYMLINK")
    # Never adopt an arbitrary target database or a new one created by sqlite3.connect.
    c=sqlite3.connect(database.as_uri()+"?mode=rw",uri=True,timeout=2,isolation_level=None)
    try:
        c.execute("PRAGMA busy_timeout=2000")
        quickcheck(c)
        counts=census(c)
        current=existing_indexes(c)
        for name,sql in current.items():
            if sql!=INDEXES[name]:
                raise RuntimeError("SCOREMAX_NAV_INDEX_NAME_CONFLICT:"+name)
        missing=[name for name in INDEXES if name not in current]
        if not apply:
            return {"status":"PLAN_ONLY","database":str(database),"missing_indexes":missing,
                    "existing_indexes":list(current),"row_census":counts,"database_changed":False}
        if not missing:
            return {"status":"ALREADY_APPLIED","indexes":list(INDEXES),
                    "row_census":counts,"database_changed":False}
        if backup is None:raise RuntimeError("SCOREMAX_NAV_BACKUP_PATH_REQUIRED")
        backup=backup.resolve()
        if backup==database or backup.exists() or not backup.parent.is_dir() or backup.is_symlink():
            raise RuntimeError("SCOREMAX_NAV_BACKUP_DESTINATION_UNSAFE")
        size=database.stat().st_size
        free=shutil.disk_usage(backup.parent).free
        # Conservative capacity buffer for backup + index construction.
        if free < max(2*size+128*1024*1024,256*1024*1024):
            raise RuntimeError("SCOREMAX_NAV_DISK_CAPACITY_INSUFFICIENT")
        fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
        try:
            with sqlite3.connect(backup) as target:c.backup(target)
            with sqlite3.connect(backup) as verify:
                quickcheck(verify)
                if census(verify)!=counts:raise RuntimeError("SCOREMAX_NAV_BACKUP_CENSUS_MISMATCH")
        except Exception:
            # Leave the evidence file in place for diagnosis; never silently proceed.
            raise
        # Acquire the write lock before schema DDL; fail cleanly if PH delivery
        # has an active write transaction rather than blocking it for a long time.
        c.execute("BEGIN IMMEDIATE")
        try:
            for name in missing:c.execute(INDEXES[name])
            if census(c)!=counts:raise RuntimeError("SCOREMAX_NAV_ROW_CENSUS_CHANGED")
            quickcheck(c)
            c.execute("COMMIT")
        except Exception:
            if c.in_transaction:c.execute("ROLLBACK")
            raise
        return {"status":"APPLIED","created_indexes":missing,"backup":str(backup),
                "indexes":list(existing_indexes(c)),"row_census":counts,"database_changed":"SCHEMA_ONLY"}
    finally:c.close()

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",type=Path,required=True)
    parser.add_argument("--backup",type=Path)
    parser.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    print("SCOREMAX_NAV_INDEX_MIGRATION="+json.dumps(migrate(args.db,args.backup,args.apply),sort_keys=True))
