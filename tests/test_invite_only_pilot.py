import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

from flask import Flask, Response, session

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pilot_runtime', ROOT/'ux_vnext_overlay/invite_only_pilot_runtime.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)


class InvitationBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.test_root = (ROOT/'.test_runs').resolve()
        assert self.test_root.is_relative_to(ROOT.resolve()) and not self.test_root.is_symlink()
        self.test_root.mkdir(exist_ok=True)
        self.work = tempfile.TemporaryDirectory(dir=self.test_root)
        assert Path(self.work.name).resolve().parent == self.test_root
        self.database = Path(self.work.name)/'synthetic.sqlite3'
        connection = sqlite3.connect(self.database)
        try:
            connection.execute('CREATE TABLE users(id,role,system_user_id,account_status,email_verified,is_demo_account)')
            connection.execute('CREATE TABLE assessment_sessions(id,student_id,meta_json)')
            connection.executemany('INSERT INTO assessment_sessions VALUES(?,?,?)', [
                (1,1,'{"assessment_kind":"mastery"}'),
                (2,1,'{"assessment_kind":"practice"}'),
            ])
            connection.executemany('INSERT INTO users VALUES(?,?,?,?,?,?)', [
                (1,'student','STU-999901','active',1,0),
                (2,'student','STU-999902','active',1,0),
                (3,'student','STU-999903','active',0,0),
                (4,'admin','ADM-SYNTHETIC','active',1,0),
                (5,'student','STU-999905','active',1,1),
            ])
            connection.commit()
        finally:
            connection.close()
        self.app = Flask(__name__)
        self.app.secret_key = 'synthetic-local-test-key'
        self.writes = 0

        @self.app.route('/register/<role>', methods=['GET','POST'])
        def register(role):
            self.writes += request.method == 'POST'
            return 'registration'

        from flask import request

        @self.app.route('/assessment/any/deep/link', methods=['GET','POST'])
        def assess():
            if session.get('role') != 'student':
                return Response('native student boundary',403)
            self.writes += request.method == 'POST'
            return '<html><body><math>x²</math><p>original question</p></body></html>'

        @self.app.route('/admin/private')
        def admin():
            return Response('native admin only',200 if session.get('role') == 'admin' else 403)

        @self.app.route('/student/mastery', methods=['GET','POST'])
        def mastery_page():
            self.writes += request.method == 'POST'
            return 'formal mastery'

        @self.app.route('/test/session/<int:assessment_id>/submit', methods=['POST'])
        def submit(assessment_id):
            self.writes += 1
            return 'native submitted'

    def tearDown(self):
        self.work.cleanup()

    def connect(self):
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def enable(self, ids='["STU-999901"]'):
        pilot.install(self.app,self.connect,{'SCOREMAX_INVITE_ONLY_PILOT':'1','SCOREMAX_PILOT_STUDENT_IDS_JSON':ids})

    def client(self, uid, role='student'):
        client = self.app.test_client()
        with client.session_transaction() as state:
            state['user_id'] = uid
            state['role'] = role
        return client

    def test_public_student_registration_cannot_create_accounts(self):
        self.enable()
        client = self.app.test_client()
        for method in ('get','post'):
            self.assertEqual(getattr(client,method)('/register/student').status_code,403)
        self.assertEqual(self.writes,0)

    def test_noninvited_student_is_blocked_on_direct_read_and_write_routes(self):
        self.enable()
        client = self.client(2)
        self.assertEqual(client.get('/assessment/any/deep/link').status_code,403)
        self.assertEqual(client.post('/assessment/any/deep/link').status_code,403)
        self.assertEqual(self.writes,0)

    def test_invited_student_preserves_question_bytes_and_native_role_checks(self):
        self.enable()
        client = self.client(1)
        response = client.get('/assessment/any/deep/link')
        self.assertEqual(response.status_code,200)
        self.assertIn('<math>x²</math><p>original question</p>',response.get_data(as_text=True))
        self.assertIn('Invitation-only pilot',response.get_data(as_text=True))
        self.assertEqual(client.get('/admin/private').status_code,403)
        self.assertEqual(client.post('/assessment/any/deep/link').status_code,200)
        self.assertEqual(self.writes,1)

    def test_unverified_or_demo_identity_is_not_admitted_by_an_invitation(self):
        self.enable('["STU-999903","STU-999905"]')
        for uid in (3,5):
            self.assertEqual(self.client(uid).post('/assessment/any/deep/link').status_code,403)
        self.assertEqual(self.writes,0)

    def test_session_role_does_not_override_database_identity(self):
        self.enable()
        self.assertEqual(self.client(2,'admin').get('/admin/private').status_code,403)
        self.assertEqual(self.client(4,'admin').get('/admin/private').status_code,200)

    def test_disabled_mode_preserves_existing_behaviour(self):
        pilot.install(self.app,self.connect,{'SCOREMAX_INVITE_ONLY_PILOT':'0'})
        self.assertEqual(self.client(2).get('/assessment/any/deep/link').status_code,200)

    def test_pilot_cannot_create_or_submit_formal_mastery(self):
        self.enable()
        client = self.client(1)
        self.assertEqual(client.get('/student/mastery').status_code,403)
        self.assertEqual(client.post('/student/mastery').status_code,403)
        self.assertEqual(client.post('/test/session/1/submit').status_code,403)
        self.assertEqual(self.writes,0)
        self.assertEqual(client.post('/test/session/2/submit').status_code,200)
        self.assertEqual(self.writes,1)

    def test_malformed_or_unbounded_configuration_fails_before_serving(self):
        for ids in ('[]','not-json','["STU-999901","STU-999901"]','["ADM-SYNTHETIC"]'):
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                pilot._configuration({'SCOREMAX_INVITE_ONLY_PILOT':'1','SCOREMAX_PILOT_STUDENT_IDS_JSON':ids})
        with self.assertRaises(ValueError):
            pilot._configuration({'SCOREMAX_INVITE_ONLY_PILOT':'unexpected'})


if __name__ == '__main__':
    unittest.main()
