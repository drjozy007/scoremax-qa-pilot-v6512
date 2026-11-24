"""Actual SQLite handle reuse with separate request, identity and restore fences."""
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
import importlib.util,os,sqlite3,threading,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('clean_thread_idle_tested',ROOT/'scoremax_runtime_v669b/navigation_request_connections_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CleanIdle(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.path=Path(self.temp.name)/'main.db';self.created=[];self.app=Flask(__name__);m.install(self.app);self.addCleanup(m.clear_idle);m.clear_idle()
  with closing(sqlite3.connect(self.path)) as c,c:c.executescript('PRAGMA journal_mode=WAL; CREATE TABLE q(id PRIMARY KEY,value);INSERT INTO q VALUES(1,10),(2,20);')
 def factory(self):
  c=sqlite3.connect(self.path,timeout=.1);c.row_factory=sqlite3.Row;c.create_function('native_identity',1,lambda x:x,deterministic=True);self.created.append(c);return c
 def borrow(self,factory=None,path=None):return m.borrow(factory or self.factory,database=path or self.path)
 def test_distinct_request_leases_reuse_clean_handle_and_reject_stale_cursor(self):
  with self.app.test_request_context('/student/chapter'):
   a=self.borrow();raw=a._physical['connection'];cursor=a.execute('SELECT value FROM q WHERE id=1');self.assertEqual(cursor.fetchone()[0],10);a.close()
  with self.app.test_request_context('/student/subject/Biology'):
   b=self.borrow();self.assertIs(b._physical['connection'],raw);self.assertEqual(b.execute('SELECT value FROM q WHERE id=?',(2,)).fetchone()[0],20)
   with self.assertRaises(sqlite3.ProgrammingError):a.execute('SELECT 1')
   with self.assertRaises(sqlite3.ProgrammingError):cursor.fetchone()
   b.close()
 def test_external_commits_seen_after_handle_reuse(self):
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();self.assertEqual(c.execute('SELECT value FROM q WHERE id=1').fetchone()[0],10);c.close()
  with closing(sqlite3.connect(self.path)) as writer,writer:writer.execute('UPDATE q SET value=33 WHERE id=1')
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();self.assertEqual(c.execute('SELECT value FROM q WHERE id=1').fetchone()[0],33);c.close()
 def test_committed_and_rolled_back_writes_are_never_retained(self):
  for commit in (False,True):
   with self.subTest(commit=commit),self.app.test_request_context('/student/chapter'):
    c=self.borrow();raw=c._physical['connection'];c.execute('UPDATE q SET value=44 WHERE id=1')
    if commit:c.commit()
    c.close()
   with self.assertRaises(sqlite3.ProgrammingError):raw.execute('SELECT 1')
   with self.app.test_request_context('/student/chapter'):
    c=self.borrow();self.assertEqual(c.execute('SELECT value FROM q WHERE id=1').fetchone()[0],44 if commit else 10);c.close()
 def test_changed_functions_factory_and_temp_state_are_retired(self):
  for change in (lambda c:c.create_function('native_identity',1,lambda x:99),lambda c:setattr(c,'text_factory',bytes),lambda c:c.execute('CREATE TEMP TABLE private(value)')):
   with self.app.test_request_context('/student/chapter'):
    c=self.borrow();raw=c._physical['connection'];change(c);c.close()
   with self.assertRaises(sqlite3.ProgrammingError):raw.execute('SELECT 1')
   with self.app.test_request_context('/student/chapter'):
    c=self.borrow();self.assertEqual(c.execute('SELECT native_identity(5)').fetchone()[0],5);self.assertIs(c.text_factory,str);c.close()
 def test_factory_identity_never_borrows_another_configuration(self):
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();raw=c._physical['connection'];c.close()
  def other():
   c=self.factory();c.create_function('native_identity',1,lambda x:88);return c
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow(other);self.assertIsNot(c._physical['connection'],raw);self.assertEqual(c.execute('SELECT native_identity(5)').fetchone()[0],88);c.close()
  with self.assertRaises(sqlite3.ProgrammingError):raw.execute('SELECT 1')
 def test_same_factory_switched_db_target_cannot_read_previous_database(self):
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();raw=c._physical['connection'];c.close()
  self.path=self.path.with_name('other.db')
  with closing(sqlite3.connect(self.path)) as c,c:c.executescript('CREATE TABLE q(id,value);INSERT INTO q VALUES(1,77)')
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();self.assertEqual(c.execute('SELECT value FROM q').fetchone()[0],77);self.assertIsNot(c._physical['connection'],raw);c.close()
 def test_replace_and_same_inode_metadata_changes_retire_idle(self):
  m.clear_idle()
  with closing(sqlite3.connect(self.path)) as c,c:c.execute('PRAGMA journal_mode=DELETE')
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();raw=c._physical['connection'];c.close()
  other=self.path.with_name('replacement.db')
  with closing(sqlite3.connect(other)) as c,c:c.executescript('CREATE TABLE q(id,value); INSERT INTO q VALUES(1,77)')
  if os.name=='nt':
   with self.assertRaises(PermissionError):other.replace(self.path)
   m.clear_idle()
  other.replace(self.path)
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();self.assertEqual(c.execute('SELECT value FROM q').fetchone()[0],77);self.assertIsNot(c._physical['connection'],raw);raw=c._physical['connection'];c.close()
  stamp=self.path.stat();os.utime(self.path,ns=(stamp.st_atime_ns,stamp.st_mtime_ns+1000000000))
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();self.assertIsNot(c._physical['connection'],raw);c.close()
 def test_pid_boundary_retires_inherited_idle(self):
  with self.app.test_request_context('/student/chapter'):
   c=self.borrow();raw=c._physical['connection'];c.close()
  with patch.object(m.os,'getpid',return_value=os.getpid()+1000),self.app.test_request_context('/student/chapter'):
   c=self.borrow();self.assertIsNot(c._physical['connection'],raw);c.close()
 def test_distinct_server_threads_keep_isolated_bounded_idle_handles(self):
  barrier=threading.Barrier(4)
  def reader(index):
   try:
    with self.app.test_request_context('/student/chapter'):
     c=self.borrow();identity=id(c._physical['connection']);c.close()
    barrier.wait(timeout=5)
    with self.app.test_request_context('/student/chapter'):
     c=self.borrow();self.assertEqual(id(c._physical['connection']),identity);self.assertEqual(c.execute('SELECT value FROM q WHERE id=1').fetchone()[0],10);c.close()
    barrier.wait(timeout=5);return identity
   finally:m.clear_idle()
  with ThreadPoolExecutor(max_workers=4) as pool:identities=list(pool.map(reader,range(4)))
  self.assertEqual(len(set(identities)),4)
 def test_only_one_clean_idle_handle_survives_request_teardown(self):
  with self.app.test_request_context('/student/chapter'):
   leases=[self.borrow() for _ in range(3)];raw=[c._physical['connection'] for c in leases]
   for c in leases:c.close()
  alive=0
  for c in raw:
   try:c.execute('SELECT 1');alive+=1
   except sqlite3.ProgrammingError:pass
  self.assertEqual(alive,1);m.clear_idle()
  for c in raw:
   with self.assertRaises(sqlite3.ProgrammingError):c.execute('SELECT 1')
 def test_no_explicit_target_retains_original_close_on_teardown(self):
  with self.app.test_request_context('/student/chapter'):
   c=m.borrow(self.factory);raw=c._physical['connection'];c.close()
  with self.assertRaises(sqlite3.ProgrammingError):raw.execute('SELECT 1')

if __name__=='__main__':unittest.main(verbosity=2)
