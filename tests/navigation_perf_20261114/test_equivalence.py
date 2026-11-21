import sqlite3
import unittest

class StudentNavigationQueryEquivalence(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.row_factory=sqlite3.Row
        self.c.executescript("""
            CREATE TABLE questions(id INTEGER PRIMARY KEY, subject TEXT, chapter TEXT, programme TEXT);
            CREATE TABLE attempts(id INTEGER PRIMARY KEY, student_id INTEGER);
            CREATE TABLE attempt_answers(id INTEGER PRIMARY KEY, attempt_id INTEGER, question_db_id INTEGER, is_correct INTEGER);
            INSERT INTO questions VALUES (1,'Biology','Ch1','FSc Part 1'),(2,'Biology','Ch1','FSc Part 1'),
            (3,'Biology','Ch2','FSc Part 1'),(4,'Biology','Ch2','MDCAT'),
            (5,'Biology','Ch3','FSc Part 1'),(6,'Physics','Ch1','FSc Part 1');
            INSERT INTO attempts VALUES (1,17),(2,17),(3,99);
            INSERT INTO attempt_answers VALUES (1,1,1,1),(2,1,1,0),(3,2,3,1),
            (4,2,4,1),(5,3,2,0),(6,2,6,0);
        """)
    def test_grouped_progress_matches_individual_queries(self):
        chapter_names=['Ch1','Ch2','Ch3','Ch4']
        params=[17,'FSc Part 1','Biology']
        old={}
        for chapter in chapter_names:
            r=self.c.execute("""
                SELECT COUNT(aa.id) answered,ROUND(100.0*SUM(aa.is_correct)/COUNT(aa.id),1) accuracy
                FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id
                JOIN questions q ON q.id=aa.question_db_id
                WHERE a.student_id=? AND q.programme=? AND lower(q.subject)=lower(?) AND q.chapter=?
                """,params+[chapter]).fetchone()
            old[chapter]=(int(r['answered'] or 0),float(r['accuracy'] or 0) if r['accuracy'] is not None else 0)
        rows=self.c.execute("""
            SELECT q.chapter,COUNT(aa.id) answered,ROUND(100.0*SUM(aa.is_correct)/COUNT(aa.id),1) accuracy
            FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id
            JOIN questions q ON q.id=aa.question_db_id
            WHERE a.student_id=? AND q.programme=? AND lower(q.subject)=lower(?)
            GROUP BY q.chapter
            """,params).fetchall()
        new={r['chapter']:(int(r['answered'] or 0),float(r['accuracy'] or 0) if r['accuracy'] is not None else 0) for r in rows}
        self.assertEqual(old,{ch:new.get(ch,(0,0)) for ch in chapter_names})
        self.assertEqual(old['Ch1'],(2,50.0))
        self.assertEqual(old['Ch2'],(1,100.0))
        self.assertEqual(old['Ch3'],(0,0))
    def test_no_mutation_from_grouped_query(self):
        before=self.c.total_changes
        self.test_grouped_progress_matches_individual_queries()
        self.assertEqual(before,self.c.total_changes)
if __name__ == '__main__':
    unittest.main()
