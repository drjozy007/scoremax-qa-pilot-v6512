from contextlib import closing
"""The ordinary profile GET must not acquire a SQLite writer reservation."""
import ast
from pathlib import Path
import sqlite3
import tempfile
import unittest
from flask import Flask,session

ROOT=Path(__file__).resolve().parents[2]


class PlanLabels(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'test.db';self.app=Flask(__name__)
        self.app.secret_key='disposable-label-test-only'
        c=self.connect();c.executescript("PRAGMA journal_mode=WAL; CREATE TABLE users(id PRIMARY KEY,academic_level,subjects); CREATE TABLE plans(code PRIMARY KEY,name); INSERT INTO users VALUES(1,'FSc Part 1','Biology'); INSERT INTO plans VALUES('level_1_access','Silver Access'),('level_2_access','Gold Access'),('full_access','Platinum Access');");c.close()
        source=(ROOT/'scoremax_runtime_v669b/ux_staging_routes.py').read_text()
        nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in ('_normalise_student_profile','_is_fsc_level')]
        namespace={'session':session,'_connect':self.connect,'sqlite3':sqlite3,'_PREMED_DEFAULT_SUBJECTS':('Biology','Chemistry','Physics')}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'<current native profile functions>','exec'),namespace)
        self.normalise=namespace['_normalise_student_profile']
    def connect(self):
        c=sqlite3.connect(self.path,timeout=.05);c.row_factory=sqlite3.Row;return c
    def test_current_labels_read_successfully_while_other_writer_is_reserved(self):
        writer=self.connect();self.addCleanup(writer.close);writer.execute('BEGIN IMMEDIATE')
        with self.app.test_request_context('/'):
            session.update(role='student',user_id=1)
            self.assertEqual(self.normalise(),('FSc Part 1',['Biology']))
        writer.rollback()
    def test_needed_repairs_and_missing_subject_defaults_retain_native_result(self):
        with closing(self.connect()) as c,c:
            c.execute("UPDATE plans SET name=NULL");c.execute("UPDATE users SET subjects='' WHERE id=1")
        with self.app.test_request_context('/'):
            session.update(role='student',user_id=1)
            self.assertEqual(self.normalise(),('FSc Part 1',['Biology','Chemistry','Physics']))
        with closing(self.connect()) as c,c:
            self.assertEqual(dict(c.execute('SELECT code,name FROM plans')),{'level_1_access':'Silver Access','level_2_access':'Gold Access','full_access':'Platinum Access'})
    def test_second_request_sees_profile_changes_and_repairs_new_label_change(self):
        with self.app.test_request_context('/'):
            session.update(role='student',user_id=1);self.normalise()
        with closing(self.connect()) as c,c:
            c.execute("UPDATE users SET subjects='Physics' WHERE id=1")
            c.execute("UPDATE plans SET name='Old label' WHERE code='full_access'")
        with self.app.test_request_context('/'):
            session.update(role='student',user_id=1)
            self.assertEqual(self.normalise(),('FSc Part 1',['Physics']))
        with closing(self.connect()) as c,c:self.assertEqual(c.execute("SELECT name FROM plans WHERE code='full_access'").fetchone()[0],'Platinum Access')

if __name__=='__main__':unittest.main(verbosity=2)
