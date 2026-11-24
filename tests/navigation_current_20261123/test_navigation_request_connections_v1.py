import os
from contextlib import closing
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from flask import Flask

spec=importlib.util.spec_from_file_location('request_connections_under_test',Path(__file__).resolve().parents[2]/'scoremax_runtime_v669b/navigation_request_connections_v1.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class RequestConnections(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'main.db';self.created=[];self.app=Flask(__name__);m.install(self.app)
        with closing(sqlite3.connect(self.path)) as c,c:
            c.executescript('PRAGMA journal_mode=WAL; CREATE TABLE q(id PRIMARY KEY,value); INSERT INTO q VALUES(1,10);')
    def factory(self):
        c=sqlite3.connect(self.path,timeout=.1);c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=100')
        c.create_function('native_identity',1,lambda x:x,deterministic=True);self.created.append(c);return c
    def read(self,c):return c.execute('SELECT value FROM q WHERE id=1').fetchone()[0]
    def test_clean_close_reuses_handle_with_distinct_closed_leases_and_cursors(self):
        with self.app.test_request_context('/student/learn-vnext'):
            a=m.borrow(self.factory);cursor=a.execute('SELECT value FROM q');self.assertEqual(cursor.fetchone()[0],10)
            raw=a._physical['connection'];a.close();b=m.borrow(self.factory)
            self.assertIsNot(a,b);self.assertIs(raw,b._physical['connection'])
            self.assertEqual(self.read(b),10)
            with self.assertRaises(sqlite3.ProgrammingError):self.read(a)
            with self.assertRaises(sqlite3.ProgrammingError):cursor.fetchone()
            b.close();self.assertEqual(len(self.created),1)
        with self.assertRaises(sqlite3.ProgrammingError):raw.execute('SELECT 1')
    def test_pending_write_close_rolls_back_and_retires(self):
        with self.app.test_request_context('/student/learn-vnext'):
            a=m.borrow(self.factory);a.execute('UPDATE q SET value=99');self.assertTrue(a.in_transaction);a.close()
            b=m.borrow(self.factory);self.assertEqual(self.read(b),10);b.close();self.assertEqual(len(self.created),2)
    def test_nested_leases_never_share_pending_transactions(self):
        with self.app.test_request_context('/student/learn-vnext'):
            a=m.borrow(self.factory);a.execute('UPDATE q SET value=99')
            b=m.borrow(self.factory);self.assertIsNot(a._physical,b._physical);self.assertEqual(self.read(b),10)
            b.close();a.rollback();a.close()
    def test_new_commits_are_seen_by_each_lease_even_after_reuse(self):
        with self.app.test_request_context('/student/learn-vnext'):
            a=m.borrow(self.factory);self.assertEqual(self.read(a),10);a.close()
            with closing(sqlite3.connect(self.path)) as writer,writer:writer.execute('UPDATE q SET value=20')
            b=m.borrow(self.factory);self.assertEqual(self.read(b),20);b.close()
    def test_cursor_operations_and_context_commit_keep_native_semantics(self):
        with self.app.test_request_context('/student/learn-vnext'):
            a=m.borrow(self.factory)
            with a:
                cur=a.cursor();self.assertIs(cur.execute('INSERT INTO q VALUES(2,25)'),cur)
                last=cur.lastrowid
            a.close();self.assertEqual(cur.lastrowid,last)
            b=m.borrow(self.factory);self.assertEqual(b.execute('SELECT COUNT(*) FROM q').fetchone()[0],2);b.close()
    def test_temp_schema_is_never_reused(self):
        with self.app.test_request_context('/student/learn-vnext'):
            a=m.borrow(self.factory);a.execute('CREATE TEMP TABLE q(value)');a.execute('INSERT INTO temp.q VALUES(99)');a.commit();a.close()
            b=m.borrow(self.factory);self.assertEqual(self.read(b),10);b.close()
    def test_changed_udf_pragma_factory_and_authorizer_cannot_leak(self):
        for change in (lambda c:c.create_function('native_identity',1,lambda x:999),
                       lambda c:c.execute('PRAGMA foreign_keys=OFF'),
                       lambda c:setattr(c,'text_factory',bytes),
                       lambda c:c.set_authorizer(lambda *args:sqlite3.SQLITE_OK)):
            with self.subTest(change=change),self.app.test_request_context('/student/learn-vnext'):
                a=m.borrow(self.factory);change(a);a.close();b=m.borrow(self.factory)
                self.assertEqual(b.execute('SELECT native_identity(5)').fetchone()[0],5)
                self.assertEqual(b.execute('PRAGMA foreign_keys').fetchone()[0],1)
                self.assertIs(b.text_factory,str);b.close()
    def test_post_other_routes_and_no_request_use_native_connections(self):
        for path,method in (('/student/learn-vnext','POST'),('/test/session/x/submit','POST'),('/admin/backups','GET')):
            with self.app.test_request_context(path,method=method):
                c=m.borrow(self.factory);self.assertIs(type(c),sqlite3.Connection);c.close()
        c=m.borrow(self.factory);self.assertIs(type(c),sqlite3.Connection);c.close()
    def test_replacement_file_and_same_inode_restore_retire_cached_handle(self):
        def plain():
            c=sqlite3.connect(self.path);c.row_factory=sqlite3.Row;self.created.append(c);return c
        # Restore an owned inactive DELETE-mode fixture; no WAL sidecars are mixed.
        with closing(sqlite3.connect(self.path)) as c,c:c.execute('PRAGMA journal_mode=DELETE')
        with self.app.test_request_context('/student/learn-vnext'):
            a=m.borrow(plain);old=a._physical['connection'];a.close()
            other=self.path.with_name('replacement.db')
            with closing(sqlite3.connect(other)) as c,c:c.executescript('CREATE TABLE q(id PRIMARY KEY,value); INSERT INTO q VALUES(1,77);')
            if os.name=='nt':
                # Windows disallows deleting/replacing an open SQLite file.
                # Prove that fence; release the inactive owned handle before
                # replacing, while retaining the same retirement/new-read test.
                with self.assertRaises(PermissionError):other.replace(self.path)
                m._retire(a._state,a._physical)
            other.replace(self.path)
            b=m.borrow(plain);self.assertEqual(self.read(b),77);self.assertIsNot(b._physical['connection'],old);b.close()
            with closing(sqlite3.connect(self.path)) as c,c:c.execute('UPDATE q SET value=88')
            c=m.borrow(plain);self.assertEqual(self.read(c),88);c.close()
            # Both OSes must retire a cached handle on same-inode restore metadata.
            retired=c._physical['connection'];stamp=self.path.stat().st_mtime_ns
            os.utime(self.path,ns=(self.path.stat().st_atime_ns,stamp+1000000000))
            d=m.borrow(plain);self.assertIsNot(d._physical['connection'],retired)
            self.assertEqual(self.read(d),88);d.close()
            with self.assertRaises(sqlite3.ProgrammingError):retired.execute('SELECT 1')
    def test_distinct_requests_and_threads_do_not_share_handles(self):
        barrier=threading.Barrier(8)
        def request(index):
            with self.app.test_request_context('/student/learn-vnext'):
                a=m.borrow(self.factory);ident=id(a._physical['connection']);barrier.wait(timeout=5)
                self.assertEqual(self.read(a),10);a.close();b=m.borrow(self.factory)
                self.assertEqual(id(b._physical['connection']),ident);b.close();barrier.wait(timeout=5)
                return ident
        with ThreadPoolExecutor(max_workers=8) as pool:ids=list(pool.map(request,range(8)))
        self.assertEqual(len(set(ids)),8)
        for c in self.created:
            # sqlite3's thread fence also proves these handles are not borrowed here.
            with self.assertRaises(sqlite3.ProgrammingError):c.execute('SELECT 1')
    def test_teardown_closes_leaked_connections_and_cursors(self):
        with self.app.test_request_context('/student/learn-vnext'):
            a=m.borrow(self.factory);cur=a.execute('SELECT * FROM q');raw=a._physical['connection']
        with self.assertRaises(sqlite3.ProgrammingError):cur.fetchone()
        with self.assertRaises(sqlite3.ProgrammingError):raw.execute('SELECT 1')

if __name__=='__main__':unittest.main(verbosity=2)
