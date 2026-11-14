"""Fail-closed ScoreMax student-navigation performance delta.

Applied only *after* the accepted Biology release runtime has passed its
existing content/hash gates. This changes learner read queries only: no schema
migration, no release/marking/mastery policy changes, no data mutation.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

MARKER = "SCOREMAX_STUDENT_NAVIGATION_BATCH_20261114"

SUBJECT_OLD = """        for ch in chapter_rows:
            cr=c.execute(f\"\"\"SELECT COUNT(aa.id) answered,ROUND(100.0*SUM(aa.is_correct)/COUNT(aa.id),1) accuracy
              FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_db_id
              WHERE a.student_id=? AND {scope_clause} AND lower(q.subject)=lower(?) AND q.chapter=?\"\"\",
              [student_id]+scope_params+[display,ch['chapter']]).fetchone()
            ca=int(cr['answered'] or 0) if cr else 0
            cp=float(cr['accuracy'] or 0) if cr and cr['accuracy'] is not None else 0"""

SUBJECT_NEW = """        # SCOREMAX_STUDENT_NAVIGATION_BATCH_20261114: one grouped evidence read
        # for all chapters of a subject, retaining exact programme filters.
        progress_rows=c.execute(f\"\"\"SELECT q.chapter,COUNT(aa.id) answered,
              ROUND(100.0*SUM(aa.is_correct)/COUNT(aa.id),1) accuracy
              FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id JOIN questions q ON q.id=aa.question_db_id
              WHERE a.student_id=? AND {scope_clause} AND lower(q.subject)=lower(?)
              GROUP BY q.chapter\"\"\", [student_id]+scope_params+[display]).fetchall()
        chapter_progress={r['chapter']:(int(r['answered'] or 0),
            float(r['accuracy'] or 0) if r['accuracy'] is not None else 0) for r in progress_rows}
        for ch in chapter_rows:
            ca,cp=chapter_progress.get(ch['chapter'],(0,0))"""

MASTERY_OLD = """    all_rows=c.execute(f"SELECT q.* FROM questions q WHERE {' AND '.join(clauses)}",params).fetchall()
    markable=[r for r in all_rows if canonical_question_type(r) in LIVE_MARKABLE_TYPES]"""

MASTERY_NEW = """    # SCOREMAX_STUDENT_NAVIGATION_BATCH_20261114: retain the exact governed
    # predicate, but avoid loading large question prompts, choices, JSON and
    # marking payloads for a chapter-card availability calculation.
    all_rows=c.execute(f\"\"\"SELECT q.id,q.level,q.family_id,
      scoremax_question_type(q.ph_response_contract,q.qtype,q.answer_config,q.marking_config) navigation_type
      FROM questions q WHERE {' AND '.join(clauses)}\"\"\",params).fetchall()
    markable=[r for r in all_rows if r['navigation_type'] in LIVE_MARKABLE_TYPES]"""


def _function_segment(source: str, name: str) -> str:
    tree = ast.parse(source)
    matches = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name]
    if len(matches) != 1:
        raise RuntimeError(f"PERF_FUNCTION_NOT_UNIQUE:{name}:{len(matches)}")
    return ast.get_source_segment(source, matches[0]) or ""


def apply(root: Path) -> dict:
    path = Path(root) / "app.py"
    before = path.read_text(encoding="utf-8")
    if MARKER in before:
        # Do not accept partial or differently composed patches.
        if before.count(MARKER) != 2 or MASTERY_NEW not in before or SUBJECT_NEW not in before:
            raise RuntimeError("PERF_PARTIAL_OR_INCONSISTENT_REPLAY")
        return {"performance_delta": "already_applied"}

    subject = _function_segment(before, "_subject_map")
    mastery = _function_segment(before, "chapter_mastery_opportunity")
    if subject.count(SUBJECT_OLD) != 1:
        raise RuntimeError("PERF_SUBJECT_BATCH_SOURCE_ANCHOR_NOT_UNIQUE")
    if mastery.count(MASTERY_OLD) != 1:
        raise RuntimeError("PERF_MASTERY_PROJECTION_SOURCE_ANCHOR_NOT_UNIQUE")

    # Only these row fields are used below the existing markable selection.
    # A change in the mastery algorithm must cause a qualification stop rather
    # than silently dropping fields that governance needs.
    rest = mastery.split(MASTERY_OLD, 1)[1]
    import re
    used_fields = set(re.findall(r"\br\[['\"]([^'\"]+)['\"]\]", rest))
    allowed = {"id", "level", "family_id"}
    if not used_fields <= allowed:
        raise RuntimeError(f"PERF_MASTERY_FIELDS_CHANGED:{sorted(used_fields - allowed)}")

    # Explicitly verify the existing SQL function is installed by the live DB
    # connection; it delegates to the SAME fail-closed canonical interpreter.
    db_function = _function_segment(before, "db")
    if "create_function('scoremax_question_type'" not in db_function:
        raise RuntimeError("PERF_MASTERY_CANONICAL_TYPE_SQL_MISSING")

    after = before.replace(SUBJECT_OLD, SUBJECT_NEW, 1).replace(MASTERY_OLD, MASTERY_NEW, 1)
    if after.count(MARKER) != 2:
        raise RuntimeError("PERF_UNEXPECTED_PATCH_COUNT")
    compile(after, str(path), "exec")

    # Compare AST source of critical policy/marking functions; only two
    # read-only functions above are allowed to change.
    old_tree = ast.parse(before)
    new_tree = ast.parse(after)
    def unchanged_map(tree, src):
        return {n.name: ast.dump(n, include_attributes=False)
                for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name not in {"_subject_map", "chapter_mastery_opportunity"}}
    if unchanged_map(old_tree, before) != unchanged_map(new_tree, after):
        raise RuntimeError("PERF_UNRELATED_FUNCTION_CHANGED")
    path.write_text(after, encoding="utf-8", newline="\n")
    return {
        "performance_delta": "applied",
        "before_sha256": hashlib.sha256(before.encode()).hexdigest(),
        "after_sha256": hashlib.sha256(after.encode()).hexdigest(),
        "changed_functions": ["_subject_map", "chapter_mastery_opportunity"],
        "release_or_marking_changes": 0,
        "database_migrations": 0,
    }


if __name__ == "__main__":
    import argparse, json
    p=argparse.ArgumentParser();p.add_argument("runtime_root",type=Path)
    args=p.parse_args()
    print("SCOREMAX_NAV_PERF_DELTA="+json.dumps(apply(args.runtime_root),sort_keys=True))
