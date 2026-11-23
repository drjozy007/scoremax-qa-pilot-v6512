"""Equivalence of old two-query and new single-query governed inventory shapes.

Synthetic in-memory cases deliberately include exact-vs-casefold subjects,
different chapter capitalization, empty source chapters and mixed insert order.
The actual application HTML equality is tested separately by Flask route CI.
"""
import sqlite3
import unittest

class FusedInventoryEquivalence(unittest.TestCase):
    def test_preserve_exact_subject_order_sql_lower_counts_and_chapter_first_id(self):
        db=sqlite3.connect(":memory:");db.row_factory=sqlite3.Row
        db.execute("CREATE TABLE questions(id INTEGER PRIMARY KEY,subject TEXT,chapter TEXT,programme TEXT,active INTEGER)")
        db.executemany("INSERT INTO questions VALUES(?,?,?,?,?)",[
            (7,"Biology","CH1","FSc Part 1",1),
            (2,"BIOLOGY","Ch1","FSc Part 1",1),
            (9,"Biology","Ch1","FSc Part 1",1),
            (4,"BIOLOGY","CH1","FSc Part 1",1),
            (3,"Maths","Ch2","FSc Part 1",1),
            (8,"Maths",None,"FSc Part 1",1),
            (12,"Maths","","FSc Part 1",1),
            (5,"Physics","Ch3","MDCAT",1),
            (6,"Physics","Ch3","FSc Part 1",0),
            (11,"chemistry","ch5","FSc Part 1",1),
            (10,"Chemistry","Ch5","FSc Part 1",1)])
        p=("FSc Part 1",)
        old_subjects=[r["subject"] for r in db.execute(
            "SELECT DISTINCT q.subject FROM questions q WHERE q.active=1 AND q.programme=? AND COALESCE(q.subject,'')<>'' ORDER BY q.subject",p)]
        old_groups=db.execute(
            "SELECT lower(q.subject) key,q.chapter,COUNT(*) n,MIN(q.id) first_id FROM questions q WHERE q.active=1 AND q.programme=? AND COALESCE(q.subject,'')<>'' GROUP BY lower(q.subject),q.chapter",p).fetchall()
        new_rows=db.execute(
            "SELECT q.subject subject,lower(q.subject) key,q.chapter,COUNT(*) n,MIN(q.id) first_id FROM questions q WHERE q.active=1 AND q.programme=? AND COALESCE(q.subject,'')<>'' GROUP BY q.subject,q.chapter ORDER BY q.subject",p).fetchall()
        new_subjects=[];seen=set();counts={};chapters={}
        for r in new_rows:
            if r["subject"] not in seen:
                seen.add(r["subject"]);new_subjects.append(r["subject"])
            key=r["key"];counts[key]=counts.get(key,0)+r["n"]
            if r["chapter"]:
                ck=(key,r["chapter"])
                if ck not in chapters or r["first_id"]<chapters[ck]:
                    chapters[ck]=r["first_id"]
        expected_counts={};expected_chapters={}
        for r in old_groups:
            key=r["key"];expected_counts[key]=expected_counts.get(key,0)+r["n"]
            if r["chapter"]:expected_chapters[(key,r["chapter"])]=r["first_id"]
        self.assertEqual(new_subjects,old_subjects)
        self.assertEqual(counts,expected_counts)
        self.assertEqual(chapters,expected_chapters)
        self.assertEqual(counts["biology"],4)
        self.assertEqual(chapters[("biology","CH1")],4)
        self.assertEqual(chapters[("biology","Ch1")],2)
        db.close()

if __name__=="__main__":unittest.main()
