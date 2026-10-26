"""Affected gate/registration checks; synthetic accounts only, no question payloads."""
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'.test_deps'))
from flask import Flask, Response, request, session
RUNTIME=Path(sys.argv[1]) if len(sys.argv)>1 else REPO/'scoremax_runtime_v669b'
if len(sys.argv)>1:sys.argv.pop(1)
sys.path.insert(0,str(RUNTIME))
import invite_only_pilot_runtime as gate
import security_rate_limit_engine as limits

ENV={'SCOREMAX_INVITE_ONLY_PILOT':'0','SCOREMAX_PUBLIC_STUDENT_OPENING':'1',
     'SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1','SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW':'0',
     'SCOREMAX_PUBLIC_BASE_URL':'https://scoremax.pk','SCOREMAX_PUBLIC_STUDENT_ACCOUNT_LIMIT':'20',
     'SCOREMAX_PUBLIC_STUDENT_REQUESTS_PER_SECOND':'2','SCOREMAX_INTERNAL_FULL_ACCESS':'0'}

class PublicOpeningTests(unittest.TestCase):
    def setUp(self):
        fixture_root=(REPO/'.test_runs').resolve()
        assert fixture_root.is_relative_to(REPO.resolve()) and not fixture_root.is_symlink()
        fixture_root.mkdir(exist_ok=True)
        self.work=tempfile.TemporaryDirectory(dir=fixture_root)
        self.path=Path(self.work.name)/'synthetic.sqlite3'
        c=self.connect()
        c.executescript("CREATE TABLE users(id INTEGER PRIMARY KEY,role,system_user_id,account_status,email_verified,is_demo_account);"
                        "CREATE TABLE assessment_sessions(id,student_id,meta_json);")
        c.executemany('INSERT INTO users VALUES(?,?,?,?,?,?)',[
            (1,'student','STU-999901','active',1,0),
            (2,'student','STU-999902','active',0,0),
            (3,'student','STU-999903','suspended',1,0),
            (4,'student','STU-999904','active',1,1),
            (5,'admin','ADM-SYNTHETIC','active',1,0)])
        c.executemany('INSERT INTO assessment_sessions VALUES(?,?,?)',[
            (1,1,'{"assessment_kind":"mastery"}'),(2,1,'{"assessment_kind":"practice"}')])
        c.commit();limits.init_schema(c);c.commit();c.close()
        self.app=Flask(__name__);self.app.secret_key='synthetic-public-opening-test-key'
        self.executed=0
        @self.app.route('/register/<role>',methods=['GET','POST'])
        def register(role):
            if request.method=='GET':return 'native registration form'
            c=self.connect()
            try:
                c.execute('BEGIN IMMEDIATE')
                denied=self.app.extensions['scoremax_registration_admission'](c,role)
                if denied is not None:c.rollback();return denied
                c.execute("INSERT INTO users(role,system_user_id,account_status,email_verified,is_demo_account) VALUES('student','STU-999999','pending_email_verification',0,0)")
                c.commit()
                return Response('native registration',302)
            finally:c.close()
        @self.app.route('/practice',methods=['GET','POST'])
        def practice():
            self.executed+=1
            return '<html><body>native practice</body></html>'
        @self.app.route('/student/mastery',methods=['GET','POST'])
        def mastery_page():
            self.executed+=1
            return 'mastery'
        @self.app.route('/test/session/<int:assessment_id>/submit',methods=['POST'])
        def submit(assessment_id):
            self.executed+=1
            return 'native submitted'
        @self.app.route('/admin')
        def admin():
            return Response('native admin',200 if session.get('role')=='admin' else 403)
        gate.install(self.app,self.connect,ENV)

    def tearDown(self):self.work.cleanup()
    def connect(self):
        c=sqlite3.connect(self.path,timeout=5);c.row_factory=sqlite3.Row;return c
    def client(self,uid=1,role='student'):
        c=self.app.test_client()
        with c.session_transaction() as s:s.update(user_id=uid,role=role)
        return c
    def fill(self,count):
        c=self.connect();n=gate._real_student_count(c)
        for i in range(count-n):c.execute("INSERT INTO users(role,system_user_id,account_status,email_verified,is_demo_account) VALUES('student',?,'pending_email_verification',0,0)",('STU-'+str(990000+i),))
        c.commit();c.close()

    def test_new_verified_noninvited_student_uses_native_route(self):
        self.assertEqual(self.client().get('/practice').status_code,200)
        self.assertEqual(self.executed,1)
    def test_unverified_suspended_and_demo_are_denied(self):
        for uid in (2,3,4):self.assertEqual(self.client(uid).post('/practice').status_code,403)
        self.assertEqual(self.executed,0)
    def test_native_admin_and_student_boundaries_remain(self):
        self.assertEqual(self.client().get('/admin').status_code,403)
        self.assertEqual(self.client(5,'admin').get('/admin').status_code,200)
        self.assertEqual(self.client(2,'admin').get('/admin').status_code,403)
    def test_formal_mastery_cannot_be_created_or_submitted(self):
        c=self.client()
        self.assertEqual(c.get('/student/mastery').status_code,403)
        self.assertEqual(c.post('/student/mastery').status_code,403)
        self.assertEqual(c.post('/test/session/1/submit').status_code,403)
        self.assertEqual(self.executed,0)
        self.assertEqual(c.post('/test/session/2/submit').status_code,200)
    def test_native_registration_is_open_and_pending_not_verified(self):
        c=self.app.test_client()
        self.assertEqual(c.get('/register/student').status_code,200)
        self.assertEqual(c.post('/register/student').status_code,302)
        db=self.connect();r=db.execute('SELECT account_status,email_verified FROM users ORDER BY id DESC LIMIT 1').fetchone();db.close()
        self.assertEqual(tuple(r),('pending_email_verification',0))
    def test_capacity_rejection_does_not_create_account(self):
        self.fill(20);c=self.app.test_client()
        self.assertEqual(c.get('/register/student').status_code,429)
        self.assertEqual(c.post('/register/student').status_code,429)
        db=self.connect();self.assertEqual(gate._real_student_count(db),20);db.close()
    def test_last_registration_slot_cannot_be_oversubscribed(self):
        self.fill(19);results=[];errors=[];start=threading.Barrier(2)
        def register_one():
            try:
                start.wait();results.append(self.app.test_client().post('/register/student').status_code)
            except BaseException as e:errors.append(str(e))
        workers=[threading.Thread(target=register_one) for _ in range(2)]
        for w in workers:w.start()
        for w in workers:w.join(10)
        self.assertFalse(errors);self.assertEqual(sorted(results),[302,429])
        c=self.connect();self.assertEqual(gate._real_student_count(c),20);c.close()
    def test_admission_requires_existing_native_transaction(self):
        c=self.connect()
        try:
            with self.assertRaises(RuntimeError):self.app.extensions['scoremax_registration_admission'](c,'student')
        finally:c.close()
    def test_two_request_budget_rejects_before_third_business_operation(self):
        c=self.client()
        real_consume=limits.consume
        with patch('security_rate_limit_engine.consume',side_effect=lambda c,**kw:real_consume(c,now=100,**kw)):
            self.assertEqual([c.post('/practice').status_code for _ in range(3)],[200,200,429])
        self.assertEqual(self.executed,2)
        with patch('security_rate_limit_engine.consume',side_effect=lambda c,**kw:real_consume(c,now=101,**kw)):
            self.assertEqual(c.post('/practice').status_code,200)
    def test_public_notice_describes_partial_coverage(self):
        text=self.client().get('/practice').get_data(as_text=True)
        self.assertIn('Coverage is partial',text);self.assertNotIn('Invitation-only pilot',text)
    def test_conflicting_unsafe_or_unqualified_configurations_fail_closed(self):
        for key,value in [('SCOREMAX_INVITE_ONLY_PILOT','1'),('SCOREMAX_REQUIRE_EMAIL_VERIFICATION','0'),
            ('SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW','1'),('SCOREMAX_INTERNAL_FULL_ACCESS','1'),
            ('SCOREMAX_PUBLIC_STUDENT_ACCOUNT_LIMIT','21'),('SCOREMAX_PUBLIC_STUDENT_REQUESTS_PER_SECOND','3'),
            ('SCOREMAX_PUBLIC_BASE_URL','http://scoremax.pk'),('SCOREMAX_PUBLIC_STUDENT_OPENING','other')]:
            with self.subTest(key=key),self.assertRaises(ValueError):gate._public_configuration(dict(ENV,**{key:value}))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PublicOpeningTests)
    # The existing eight invitation checks are affected by the shared module edit.
    previous=REPO/'tests/test_invite_only_pilot.py'
    if previous.exists():
        spec=importlib.util.spec_from_file_location('existing_invitation_regressions',previous)
        old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);old.pilot=gate
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(old))
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    if not r.wasSuccessful():raise SystemExit(1)
