"""Account-boundary regressions on native WSGI and disposable SQLite only."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import qualify_assessment_contract_repair as fixture
import ux_email_verification as verification
from werkzeug.datastructures import MultiDict
from werkzeug.security import check_password_hash

sm=fixture.sm
ORIGIN='https://localhost'
PASSWORD='Synthetic-registration-only!'


class RegistrationBoundary(unittest.TestCase):
    def setUp(self):
        self.case=fixture.AssessmentRepair('test_native_eight_response_journeys')
        self.case._testMethodName='registration_'+self._testMethodName
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        self.rate=patch.object(sm,'rate_limit',return_value=True)
        self.rate.start();self.addCleanup(self.rate.stop)
        self.flags=patch.dict(os.environ,{'SCOREMAX_SEND_EMAIL_VERIFICATION':'0','SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'0'})
        self.flags.start();self.addCleanup(self.flags.stop)

    def post(self,path,data,client=None):
        client=client or sm.app.test_client()
        client.get('/login',base_url=ORIGIN)
        with client.session_transaction() as session:csrf=session['_csrf_token']
        data=MultiDict(data);data.add('_csrf_token',csrf)
        return client.post(path,data=data,base_url=ORIGIN)

    def signup(self,email,password=PASSWORD,programme='',role='student',client=None):
        return self.post('/register/'+role,{'full_name':'Synthetic Registration','email':email,
                         'password':password,'academic_level':programme},client)

    def account(self,email):
        row=self.case.c.execute('SELECT * FROM users WHERE lower(email)=?',(email.strip().lower(),)).fetchone()
        return dict(row) if row else None

    def writer_available(self):
        conn=sqlite3.connect(self.case.db,timeout=0)
        try:conn.execute('BEGIN IMMEDIATE');conn.rollback()
        finally:conn.close()

    def test_two_simultaneous_duplicate_registrations(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(lambda _:self.signup('same@example.invalid'),range(2)))
        self.assertEqual([r.status_code for r in responses],[302,302])
        self.assertEqual(self.case.c.execute("SELECT count(*) FROM users WHERE email='same@example.invalid'").fetchone()[0],1)
        self.writer_available()

    def test_ten_concurrent_duplicate_and_distinct_identities(self):
        emails=['shared@example.invalid']*5+[f'distinct-{i}@example.invalid' for i in range(5)]
        with ThreadPoolExecutor(max_workers=10) as pool:responses=list(pool.map(self.signup,emails))
        self.assertTrue(all(r.status_code==302 for r in responses))
        for email in set(emails):
            self.assertEqual(self.case.c.execute('SELECT count(*) FROM users WHERE email=?',(email,)).fetchone()[0],1)
        self.writer_available()

    def test_duplicate_with_different_password_preserves_account_and_session(self):
        self.signup('preserve@example.invalid')
        before=self.account('preserve@example.invalid')
        with patch.dict(os.environ,{'SCOREMAX_SEND_EMAIL_VERIFICATION':'1'}),patch.object(verification,'_send_verification') as send:
            response=self.signup('PRESERVE@EXAMPLE.INVALID','Synthetic-wrong-duplicate!')
        self.assertEqual(response.status_code,302);send.assert_not_called()
        self.assertEqual(before,self.account('preserve@example.invalid'))
        self.assertTrue(check_password_hash(before['password_hash'],PASSWORD))
        self.assertEqual(self.case.client.get('/student',base_url=ORIGIN).status_code,200)
        self.writer_available()

    def test_constraint_failure_rolls_back_and_next_signup_succeeds(self):
        self.case.c.execute("CREATE TRIGGER synthetic_registration_failure BEFORE INSERT ON users WHEN NEW.email='constraint@example.invalid' BEGIN SELECT RAISE(ABORT,'synthetic constraint'); END")
        self.case.c.commit()
        for role in ['student','teacher','parent']:
            self.assertEqual(self.signup('constraint@example.invalid',role=role).status_code,302)
            self.assertIsNone(self.account('constraint@example.invalid'));self.writer_available()
            self.assertEqual(self.signup('after-'+role+'@example.invalid',role=role).status_code,302)
            self.assertIsNotNone(self.account('after-'+role+'@example.invalid'));self.writer_available()

    def test_downstream_exception_rolls_back_complete_registration(self):
        before=self.case.c.execute('SELECT count(*) FROM users').fetchone()[0]
        with patch.object(sm.universal_mastery,'emit_growth_event',side_effect=RuntimeError('synthetic downstream fault')):
            response=self.signup('downstream@example.invalid')
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.case.c.execute('SELECT count(*) FROM users').fetchone()[0],before)
        self.assertIsNone(self.account('downstream@example.invalid'));self.writer_available()
        self.signup('after-fault@example.invalid');self.assertIsNotNone(self.account('after-fault@example.invalid'))

    def test_repeated_failures_never_accumulate_locks(self):
        for i in range(6):
            with patch.object(sm,'apply_referral_attribution',side_effect=RuntimeError('synthetic attribution fault')):
                self.assertEqual(self.signup(f'failure-{i}@example.invalid').status_code,302)
            self.assertIsNone(self.account(f'failure-{i}@example.invalid'));self.writer_available()
        self.signup('usable@example.invalid');self.assertIsNotNone(self.account('usable@example.invalid'))

    def test_password_hashing_does_not_hold_writer_reservation(self):
        original=sm.generate_password_hash
        def checked(password):
            self.writer_available()
            return original(password)
        with patch.object(sm,'generate_password_hash',side_effect=checked):
            self.signup('hash@example.invalid')
        self.assertIsNotNone(self.account('hash@example.invalid'))

    def test_registration_after_fresh_application_process(self):
        code='''import socket,sys
def deny(*a,**k):raise RuntimeError('NETWORK_DISABLED')
socket.socket.connect=deny;socket.socket.connect_ex=deny
import scoremax_production as production
import app as sm
client=sm.app.test_client();client.get('/login',base_url='https://localhost')
with client.session_transaction() as s:csrf=s['_csrf_token']
r=client.post('/register/student',base_url='https://localhost',data={'_csrf_token':csrf,'full_name':'Synthetic Restart','email':'restart@example.invalid','password':'Synthetic-registration-only!'})
assert r.status_code==302
with sm.db() as c:assert c.execute("SELECT count(*) FROM users WHERE email='restart@example.invalid'").fetchone()[0]==1
print('REGISTRATION_RESTART_PASS')
'''
        result=subprocess.run([sys.executable,'-c',code],cwd=fixture.ROOT,env=dict(os.environ),capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr[-3000:])
        self.assertIn('REGISTRATION_RESTART_PASS',result.stdout);self.writer_available()

    def test_programme_aliases_share_deferred_decision(self):
        for i,programme in enumerate(['MDCAT','mdcat','  MdCaT  ','FSc Part 2','FSC_PART_II','fsc   part 2']):
            email=f'deferred-{i}@example.invalid';response=self.signup(email,programme=programme)
            self.assertEqual(response.status_code,302);self.assertIn('/interest/programme_',response.location)
            self.assertIsNone(self.account(email));self.writer_available()

    def test_unknown_and_conflicting_programmes_do_not_persist(self):
        for i,programme in enumerate(['unknown','FSc Part 1,MDCAT','FSc / Intermediate','ECAT']):
            email=f'invalid-programme-{i}@example.invalid';self.signup(email,programme=programme)
            self.assertIsNone(self.account(email))
        response=self.post('/register/student',MultiDict([('full_name','Synthetic'),('email','conflict@example.invalid'),
            ('password',PASSWORD),('academic_level','FSc Part 1'),('academic_level','MDCAT')]))
        self.assertEqual(response.status_code,302);self.assertIsNone(self.account('conflict@example.invalid'))

    def test_empty_and_live_programme_registration(self):
        for i,programme in enumerate(['','FSc Part 1','FSC_PART_I',' fsc   part 1 ']):
            email=f'live-{i}@example.invalid';response=self.signup(email,programme=programme)
            self.assertEqual(response.status_code,302)
            row=self.account(email);self.assertIsNotNone(row)
            self.assertEqual(row['active_programme'],'' if not programme else 'FSc Part 1')

    def test_invalid_email_shapes_and_lengths_cannot_persist(self):
        for email in ['no-at-sign','name@','@invalid.example','a@@b.example','a..b@example.invalid',
                      '.a@example.invalid','a.@example.invalid','name\r\nbcc@example.invalid',
                      'x'*65+'@example.invalid','x@'+('a'*64)+'.example',('x'*64)+'@'+('a.'*100)+'example']:
            response=self.signup(email);self.assertEqual(response.status_code,302)
            self.assertIsNone(self.account(email));self.writer_available()

    def test_personal_mailboxes_padding_and_duplicate_case(self):
        for i,email in enumerate(['personal+score@gmail.com','personal@outlook.com','personal@yahoo.co.uk',"o'connor@example.pk"]):
            self.assertEqual(self.signup('  '+email.upper()+'  ').status_code,302)
            self.assertIsNotNone(self.account(email));before=self.account(email)
            self.signup(email);self.assertEqual(self.account(email),before)

    def test_notification_fault_preserves_account_and_required_gate(self):
        for required in ['0','1']:
            email='delivery-'+required+'@example.invalid'
            with patch.dict(os.environ,{'SCOREMAX_SEND_EMAIL_VERIFICATION':'1','SCOREMAX_REQUIRE_EMAIL_VERIFICATION':required}),patch.object(verification,'_make_token',side_effect=RuntimeError('synthetic token storage fault')):
                response=self.signup(email)
            self.assertEqual(response.status_code,302)
            row=self.account(email);self.assertIsNotNone(row);self.assertEqual(row['email_verified'],0)
            self.assertEqual(row['account_status'],'pending_email_verification' if required=='1' else 'active')
            self.writer_available()

    def test_simultaneous_resend_and_password_reset(self):
        self.signup('lifecycle@example.invalid')
        self.case.c.execute("UPDATE users SET email_verified=0,email_verification_sent_at='' WHERE email='lifecycle@example.invalid'");self.case.c.commit()
        paths=['/verify-email/resend','/forgot-password']*3
        with patch.dict(os.environ,{'SCOREMAX_SEND_EMAIL_VERIFICATION':'1'}),patch.object(verification,'_send_verification',return_value=False),patch.object(sm,'send_transactional_email',return_value=False):
            with ThreadPoolExecutor(max_workers=6) as pool:
                responses=list(pool.map(lambda path:self.post(path,{'identity':'lifecycle@example.invalid','email':'lifecycle@example.invalid'}),paths))
        self.assertTrue(all(r.status_code==302 for r in responses))
        self.assertEqual(self.account('lifecycle@example.invalid')['account_status'],'active');self.writer_available()

    def test_reset_issue_exception_releases_writer_and_rolls_back_token(self):
        self.signup('reset-issue@example.invalid')
        original=sm.account_security.issue_password_reset_token
        def fail(conn,**kwargs):
            original(conn,**kwargs)
            raise RuntimeError('synthetic reset issuance fault')
        with patch.object(sm.account_security,'issue_password_reset_token',side_effect=fail):
            response=self.post('/forgot-password',{'email':'reset-issue@example.invalid'})
        self.writer_available()
        self.assertEqual(response.status_code,302)
        uid=self.account('reset-issue@example.invalid')['id']
        self.assertEqual(self.case.c.execute('SELECT count(*) FROM password_reset_tokens WHERE user_id=?',(uid,)).fetchone()[0],0)

    def test_reset_claim_exception_releases_writer_and_preserves_password(self):
        self.signup('reset-claim@example.invalid');before=self.account('reset-claim@example.invalid')
        digest=hashlib.sha256(b'synthetic-reset-token').hexdigest()
        sm.account_security.issue_password_reset_token(self.case.c,user_id=before['id'],token_hash=digest,
            expires_at='2099-01-01T00:00:00',issued_at='2026-10-17T00:00:00');self.case.c.commit()
        original=sm.account_security.claim_password_reset_token
        def fail(conn,**kwargs):
            original(conn,**kwargs)
            raise RuntimeError('synthetic reset claim fault')
        with patch.object(sm.account_security,'claim_password_reset_token',side_effect=fail):
            response=self.post('/reset-password/synthetic-reset-token',{'password':'Synthetic-new-reset-only!'})
        self.writer_available();self.assertEqual(response.status_code,302)
        self.assertEqual(self.account('reset-claim@example.invalid')['password_hash'],before['password_hash'])
        self.assertFalse(self.case.c.execute('SELECT used_at FROM password_reset_tokens WHERE token_hash=?',(digest,)).fetchone()[0])


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--report');args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RegistrationBoundary))
    report={'tests':result.testsRun,'failures':len(result.failures),'passed':result.wasSuccessful(),
          'errors':len(result.errors),'network_disabled':True,'production_database_used':False,'fixture_rate_limit_stubbed':True,
          'source_hashes':{name:hashlib.sha256((fixture.ROOT/name).read_bytes()).hexdigest()
                           for name in ('app.py','account_security_engine.py','ux_email_verification.py')}}
    if args.report:Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    print('REGISTRATION_BOUNDARY_QUALIFICATION',json.dumps(report))
    raise SystemExit(0 if result.wasSuccessful() else 1)
