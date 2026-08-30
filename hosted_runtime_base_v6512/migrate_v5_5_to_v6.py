"""ScoreMax V5.5 Final -> V6.0 controlled SQLite migration utility.

Usage:
  python migrate_v5_5_to_v6.py path/to/scoremax_v4.db --dry-run
  python migrate_v5_5_to_v6.py path/to/scoremax_v4.db
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
PRESERVED_TABLES = [
    "users", "questions", "attempts", "attempt_answers", "mastery_records",
    "study_plans", "study_plan_activities", "classrooms", "classroom_students",
    "parent_student_links", "exam_papers", "exam_paper_questions",
    "assessment_blueprints", "assessment_blueprint_sections",
    "assessment_assembly_policies", "assessment_policy_activations",
]
V6_TABLES = [
    "written_feature_controls", "written_assessment_packages", "written_questions",
    "written_attempts", "written_answer_versions", "written_marking_runs",
    "written_mark_point_results", "written_mastery_evidence", "written_recovery_tasks",
    "written_upload_pages", "written_processing_jobs", "written_exemplar_candidates",
    "written_exemplar_consents", "written_exemplars", "written_usage_ledger",
]


def table_counts(path: Path, names: list[str]) -> dict[str, int | None]:
    conn = sqlite3.connect(path)
    try:
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        return {
            name: (conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0] if name in existing else None)
            for name in names
        }
    finally:
        conn.close()


def run_migration(target: Path) -> dict:
    before = table_counts(target, PRESERVED_TABLES)
    os.environ["SCOREMAX_DB"] = str(target)
    os.environ.setdefault("SCOREMAX_ENV", "local")
    sys.path.insert(0, str(ROOT))
    import app  # noqa: PLC0415 - environment must be fixed first

    conn = sqlite3.connect(target, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        app.migrate_v5(conn)
        app.migrate_v6(conn)
        conn.commit()
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()

    after = table_counts(target, PRESERVED_TABLES)
    v6_counts = table_counts(target, V6_TABLES)
    return {
        "database": str(target),
        "integrity_check": integrity,
        "preserved_counts_before": before,
        "preserved_counts_after": after,
        "preserved": {k: before[k] == after[k] for k in before if before[k] is not None},
        "v6_table_counts": v6_counts,
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run or execute ScoreMax V5.5 Final to V6.0 migration")
    parser.add_argument("database", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Migrate a temporary copy only")
    parser.add_argument("--no-backup", action="store_true", help="Skip backup for a real migration (not recommended)")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()

    source = args.database.resolve()
    if not source.exists():
        parser.error(f"Database not found: {source}")

    backup = None
    if args.dry_run:
        tmp_dir = Path(tempfile.mkdtemp(prefix="scoremax_v6_migration_"))
        target = tmp_dir / source.name
        shutil.copy2(source, target)
    else:
        target = source
        if not args.no_backup:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup = source.with_name(f"{source.name}.pre_v6_0_{stamp}.bak")
            shutil.copy2(source, backup)

    try:
        result = run_migration(target)
        result.update({
            "mode": "dry-run" if args.dry_run else "real",
            "source_database": str(source),
            "backup": str(backup) if backup else None,
        })
        if result["integrity_check"] != "ok":
            raise RuntimeError(f"SQLite integrity check failed: {result['integrity_check']}")
        if not all(result["preserved"].values()):
            raise RuntimeError("One or more preserved table counts changed during migration")
        report_path = args.report or source.with_name("V6_0_MIGRATION_RESULT.json")
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
