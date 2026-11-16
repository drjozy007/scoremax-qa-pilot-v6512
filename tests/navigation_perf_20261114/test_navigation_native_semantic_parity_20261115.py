"""Adversarial native-vs-optimised chapter/subject identity regressions.

Execute the actual source-bound replacement snippets, not a reimplementation.
Only in-memory SQLite and frozen fake answer records are used.
"""
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from scoremax_navigation_batch_student_evidence_20261114 import NEW_ANCHOR as CHAPTER_ANCHOR, NEW_STATS
from scoremax_navigation_grouped_scope_delta_20261114 import (
    NEW_ANCHOR as GROUPED_ANCHOR, NEW_COUNT, NEW_CHAPTER,
)
from scoremax_fused_subject_inventory_20261114 import NEW_LIVE, NEW_GROUP


class _FrozenEvidence:
    def __init__(self, rows):
        self.rows = list(rows)

    def learner_answer_evidence(self, _conn, _student, _programme, _subject, chapter=""):
        # Exact accepted native reader: strip only the requested chapter,
        # never the frozen source chapter from the validated row.
        if not chapter:
            return list(self.rows)
        return [r for r in self.rows
                if str(r.get("chapter") or "").casefold() == chapter.strip().casefold()]

    @staticmethod
    def evidence_summary(rows):
        return tuple(r["id"] for r in rows)


class NativeSemanticParity(unittest.TestCase):
    def test_batched_frozen_chapter_evidence_matches_native_with_whitespace(self):
        rows = [
            {"id": 1, "chapter": "Chapter 2"},
            {"id": 2, "chapter": "Chapter 2 "},
            {"id": 3, "chapter": "CHAPTER 2"},
            {"id": 4, "chapter": ""},
            {"id": 5, "chapter": None},
            {"id": 6, "chapter": "Café"},
        ]
        inputs = ["Chapter 2", "Chapter 2 ", "CHAPTER 2", "", "   ", "Café", "Nonexistent"]
        runtime = _FrozenEvidence(rows)
        src = (
            "def candidate(runtime, browse_items, conn, student_id, programme, subject):\n"
            + CHAPTER_ANCHOR
            + "        source_chapter=item\n"
            + NEW_STATS + "\n"
            + "        out.append(stats)\n"
            + "    return out\n"
        )
        ns = {}
        exec(compile(src, "<candidate-chapter-evidence>", "exec"), ns)
        actual = ns["candidate"](runtime, inputs, None, 1, "FSc Part 1", "Biology")
        native = [runtime.evidence_summary(runtime.learner_answer_evidence(
            None, 1, "FSc Part 1", "Biology", ch)) for ch in inputs]
        self.assertEqual(actual, native)
        self.assertEqual(actual[0], (1, 3))
        self.assertEqual(actual[3], (1, 2, 3, 4, 5, 6))

    def test_grouped_and_fused_subject_counts_match_native_sqlite_lower(self):
        with sqlite3.connect(":memory:") as c:
            c.row_factory = sqlite3.Row
            c.execute("CREATE TABLE questions(id INTEGER PRIMARY KEY, programme TEXT, subject TEXT, chapter TEXT, active INTEGER)")
            c.executemany("INSERT INTO questions VALUES(?,?,?,?,?)", [
                (1, "FSc Part 1", "FÍSICA", "C1", 1),
                (2, "FSc Part 1", "Física", "C2", 1),
                (3, "FSc Part 1", "Biology", "C3", 1),
                (4, "FSc Part 1", "BIOLOGY", "C4", 1),
                (5, "FSc Part 1", "FÍSICA", "C5", 0),
                (6, "MDCAT", "FÍSICA", "C6", 1),
                (7, "FSc Part 1", "İSTANBUL", "C7", 1),
                (8, "FSc Part 1", "İstanbul", "C8", 1),
            ])
            visible = ["FÍSICA", "Física", "Biology", "BIOLOGY", "İSTANBUL", "İstanbul"]
            common = """        display=subject
        data.append((
            display,qcount,[(row['chapter'],row['first_id']) for row in chapter_rows]
        ))
    return data
"""
            for prefix, script in (
                ("grouped", GROUPED_ANCHOR),
                ("fused", NEW_LIVE + "\n" + NEW_GROUP),
            ):
                with self.subTest(prefix=prefix):
                    body = (
                        "def candidate(c,visible,scope_clause,scope_params,live_question_clause):\n"
                        + script
                        + NEW_COUNT + "\n"
                        + NEW_CHAPTER + "\n"
                        + common
                    )
                    # NEW_COUNT uses 'subject'; NEW_CHAPTER uses 'display'.
                    # Ensure display is bound before the chapter lookup.
                    body = body.replace(
                        NEW_COUNT + "\n" + NEW_CHAPTER,
                        NEW_COUNT + "\n" + "        display=subject\n" + NEW_CHAPTER,
                        1,
                    )
                    ns = {}
                    exec(compile(body, "<candidate-" + prefix + ">", "exec"), ns)
                    actual = ns["candidate"](
                        c, visible, "q.programme=?", ["FSc Part 1"],
                        lambda alias: alias + ".active=1",
                    )
                    expected = []
                    for name in visible:
                        count = c.execute(
                            "SELECT COUNT(*) FROM questions q WHERE q.active=1 "
                            "AND q.programme=? AND lower(q.subject)=lower(?)",
                            ("FSc Part 1", name),
                        ).fetchone()[0]
                        chapters = c.execute(
                            "SELECT q.chapter, MIN(q.id) first_id FROM questions q "
                            "WHERE q.active=1 AND q.programme=? AND lower(q.subject)=lower(?) "
                            "AND COALESCE(q.chapter,'')<>'' GROUP BY q.chapter ORDER BY first_id",
                            ("FSc Part 1", name),
                        ).fetchall()
                        expected.append((name, count,
                                         [(r["chapter"], r["first_id"]) for r in chapters]))
                    self.assertEqual(actual, expected)
                    self.assertEqual(actual[0][1], 1)
                    self.assertEqual(actual[1][1], 1)
                    self.assertEqual(actual[2][1], 2)


if __name__ == "__main__":
    unittest.main()
