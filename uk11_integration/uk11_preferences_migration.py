"""Explicit, idempotent UK11 preference migration for a DISPOSABLE UK test DB.

Usage (from the isolated UK runtime and with approved database path):
  python uk11_preferences_migration.py /path/to/disposable-uk-test.db

Never run against Pakistan production. This migration does not populate data
or modify users, exam content, learning results or existing contract tables.
"""
from __future__ import annotations
import argparse
import sqlite3
from pathlib import Path

DDL = """
CREATE TABLE IF NOT EXISTS uk11_student_preferences (
 student_user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 entry_year INTEGER NOT NULL CHECK(entry_year BETWEEN 2027 AND 2032),
 selected_school_keys_json TEXT NOT NULL CHECK(json_valid(selected_school_keys_json)),
 revision INTEGER NOT NULL DEFAULT 1 CHECK(revision>=1),
 updated_at TEXT NOT NULL
);
"""


# UK-only learner identity is independent of school selection. In the real
# ScoreMax runtime this mapping must come from an approved UK onboarding path.
UK_MARKET_DDL = """
CREATE TABLE IF NOT EXISTS uk11_learner_markets (
 student_user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
 market_id TEXT NOT NULL CHECK (market_id='UK'),
 programme_id TEXT NOT NULL CHECK (programme_id='UK11'),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


GUARDIAN_DDL = """
CREATE TABLE IF NOT EXISTS uk11_guardian_onboarding (
 parent_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 student_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 consent_scope TEXT NOT NULL CHECK (consent_scope='UK11_ONBOARDING'),
 status TEXT NOT NULL CHECK (status IN ('APPROVED','REVOKED')),
 consent_text_version TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 PRIMARY KEY (parent_user_id,student_user_id,consent_scope)
);
CREATE INDEX IF NOT EXISTS idx_uk11_guardian_student
 ON uk11_guardian_onboarding(student_user_id,consent_scope,status);
"""

def migrate(db_path: Path):
    if not db_path.is_file():
        raise ValueError("UK11_DB_MUST_EXIST_ON_DISPOSABLE_TEST_ENV")
    with sqlite3.connect(str(db_path), timeout=5) as c:
        c.execute("PRAGMA foreign_keys=ON")
        if c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'").fetchone() is None:
            raise ValueError("UK11_EXISTING_SCOREMAX_USERS_TABLE_REQUIRED")
        c.execute("BEGIN IMMEDIATE")
        c.execute(DDL)
        c.execute(UK_MARKET_DDL)
        c.executescript(GUARDIAN_DDL)
        c.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("disposable_database", type=Path)
    args = parser.parse_args()
    migrate(args.disposable_database)
    print("UK11_PREFERENCE_MIGRATION_APPLIED_TO_EXPLICIT_TEST_DATABASE")
