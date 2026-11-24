from contextlib import closing
"""Commit, concurrency and isolation controls on a disposable real SQLite DB."""
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from flask import Flask

spec=importlib.util.spec_from_file_location('display_inventory_tested_v3',
    Path(__file__).resolve().parents[2]/'scoremax_runtime_v669b/navigation_display_reads_v5.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
SQL="""SELECT subject,lower(subject) subject_key,chapter,
 COUNT(*) question_count,MIN(id) first_id FROM q
 WHERE active=1 AND programme=? GROUP BY subject,chapter ORDER BY subject"""


class DisplayInventory(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'test.db'
        self.c=sqlite3.connect(self.path,check_same_thread=False);self.c.row_factory=sqlite3.Row
        self.addCleanup(self.c.close);self.addCleanup(m.clear)
        self.c.executescript("PRAGMA journal_mode=WAL; CREATE TABLE q(id INTEGER PRIMARY KEY,programme,subject,chapter,active); INSERT INTO q VALUES(1,'FSc','Biology','opaque/0001',1); INSERT INTO q VALUES(2,'MDCAT','BIOLOGY','opaque/0001 ',1);")
        self.app=Flask(__name__)

    def read(self,programme='FSc',method='GET'):
        with self.app.test_request_context('/student/learn-vnext',method=method):
            return m.display_inventory(self.c,SQL,[programme])

    def test_commit_invalidation_and_row_copy_are_current(self):
        first=self.read();first[0]['question_count']=99
        self.assertEqual(self.read()[0]['question_count'],1)
        with closing(sqlite3.connect(self.path)) as writer,writer:writer.execute('UPDATE q SET active=0 WHERE id=1')
        self.assertEqual(self.read(),[])
        with closing(sqlite3.connect(self.path)) as writer,writer:writer.execute('UPDATE q SET active=1 WHERE id=1')
        self.assertEqual(self.read()[0]['question_count'],1)
        self.assertEqual(self.read('MDCAT')[0]['chapter'],'opaque/0001 ')

    def test_own_uncommitted_changes_are_never_cached_or_rolled_back(self):
        self.read();self.c.execute('UPDATE q SET active=0 WHERE id=1')
        self.assertEqual(self.read(),[]);self.assertTrue(self.c.in_transaction)
        self.c.rollback();self.assertEqual(self.read()[0]['question_count'],1)
        self.c.execute('UPDATE q SET active=0 WHERE id=1');self.c.commit()
        self.assertEqual(self.read(),[])

    def test_post_and_no_request_always_use_native_reader(self):
        self.read()
        with patch.object(m,'_rows',wraps=m._rows) as native:
            self.read(method='POST');self.assertEqual(native.call_count,1)
            m.display_inventory(self.c,SQL,['FSc']);self.assertEqual(native.call_count,2)

    def test_commit_during_fill_prevents_old_snapshot_reuse(self):
        real=m._rows;done=[]
        def racing(c,sql,values,columns):
            rows=real(c,sql,values,columns)
            with closing(sqlite3.connect(self.path)) as writer,writer:writer.execute('UPDATE q SET active=0 WHERE id=1')
            done.append(True);return rows
        with patch.object(m,'_rows',side_effect=racing):self.assertEqual(self.read()[0]['question_count'],1)
        self.assertEqual(done,[True]);self.assertEqual(self.read(),[])

    def test_same_request_reader_udfs_survive_observer_separation(self):
        self.c.create_function('opaque_identity',1,lambda value:value,deterministic=True)
        with self.app.test_request_context('/student/learn-vnext'):
            rows=m.display_inventory(self.c,SQL.replace('programme=?','opaque_identity(programme)=?'),['FSc'])
        self.assertEqual(rows[0]['chapter'],'opaque/0001')

    def test_concurrent_first_reads_build_once_with_isolated_results(self):
        real=m._rows;count=[];barrier=threading.Barrier(8);results=[]
        def reader():
            c=sqlite3.connect(self.path)
            try:
                barrier.wait()
                with self.app.test_request_context('/student/learn-vnext'):
                    results.append(m.display_inventory(c,SQL,['FSc']))
            finally:c.close()
        def measured(*args):count.append(True);return real(*args)
        with patch.object(m,'_rows',side_effect=measured):
            threads=[threading.Thread(target=reader) for _ in range(8)]
            for t in threads:t.start()
            for t in threads:t.join(5);self.assertFalse(t.is_alive())
        self.assertEqual(len(count),1);self.assertEqual(len(results),8)
        results[0][0]['subject']='changed';self.assertEqual(results[1][0]['subject'],'Biology')

    def test_query_memory_and_fork_domains_are_bounded(self):
        for n in range(40):self.read('opaque-programme-'+str(n))
        self.assertLessEqual(len(next(iter(m._states.values()))['queries']),m.MAX_QUERIES)
        with patch.object(m,'_pid',-1):self.assertEqual(self.read()[0]['question_count'],1)
        m.clear();self.assertFalse(m._states)


if __name__=='__main__':unittest.main(verbosity=2)
