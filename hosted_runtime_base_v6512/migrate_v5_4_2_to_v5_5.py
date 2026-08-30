"""ScoreMax V5.4.2 -> V5.5 controlled SQLite migration utility.

Usage:
  py migrate_v5_4_2_to_v5_5.py path/to/scoremax_v4.db --dry-run
  py migrate_v5_4_2_to_v5_5.py path/to/scoremax_v4.db

The application also performs an idempotent startup migration, but this utility
adds a dry-run, explicit backup and a machine-readable impact report for a
controlled pilot migration.
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

ROOT = Path(__file__).resolve().parent
TRACKED_TABLES = [
    "users", "questions", "attempts", "attempt_answers", "mastery_records",
    "study_plans", "study_plan_activities", "classrooms", "classroom_students",
    "parent_student_links", "exam_papers", "exam_paper_questions",
    "assessment_blueprints", "assessment_assembly_policies",
]


def table_counts(path: Path) -> dict[str, int | None]:
    conn = sqlite3.connect(path)
    try:
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {name: (conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] if name in existing else None)
                for name in TRACKED_TABLES}
    finally:
        conn.close()


def run_migration(target: Path) -> dict:
    os.environ["SCOREMAX_DB"] = str(target)
    os.environ.setdefault("SCOREMAX_ENV", "local")
    sys.path.insert(0, str(ROOT))
    import app  # imported only after SCOREMAX_DB is fixed

    conn = sqlite3.connect(target, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        before = table_counts(target)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        app.migrate_v5(conn)
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        after = table_counts(target)
        legacy = None
        if after.get("exam_papers") is not None:
            legacy = conn.execute("SELECT COUNT(*) FROM exam_papers WHERE COALESCE(authenticity_status,'')='LEGACY_UNPINNED'").fetchone()[0]
        return {
            "database": str(target),
            "integrity_check": integrity,
            "counts_before": before,
            "counts_after": after,
            "preserved_counts": {k: before[k] == after[k] for k in before if before[k] is not None},
            "legacy_unpinned_exam_papers": legacy,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
        }
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or execute ScoreMax V5.4.2 to V5.5 migration")
    parser.add_argument("database", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Migrate a temporary copy only")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup for a real migration (not recommended)")
    parser.add_argument("--report", type=Path, default=None, help="Optional JSON report path")
    args = parser.parse_args()

    source = args.database.resolve()
    if not source.exists():
        parser.error(f"Database not found: {source}")

    backup = None
    if args.dry_run:
        tmp_dir = Path(tempfile.mkdtemp(prefix="scoremax_v55_migration_"))
        target = tmp_dir / source.name
        shutil.copy2(source, target)
    else:
        target = source
        if not args.no_backup:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = source.with_name(f"{source.name}.pre_v5_5_{stamp}.bak")
            shutil.copy2(source, backup)

    try:
        result = run_migration(target)
        result.update({"mode": "dry-run" if args.dry_run else "real", "source_database": str(source),
                       "backup": str(backup) if backup else None})
        if result["integrity_check"] != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {result['integrity_check']}")
        report_path = args.report or source.with_name("V5_5_MIGRATION_RESULT.json")
        report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        print(f"Migration report: {report_path}")
        return 0
    except Exception:
        if backup and backup.exists():
            print(f"Migration failed. Restore backup from: {backup}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
