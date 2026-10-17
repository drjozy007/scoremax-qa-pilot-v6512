"""Exercise the assembled email workflow on a disposable DB with network denied.

SMTP is captured in memory. No production account, inbox, key, or DB is used.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts import qualify_mastery_launch_freeze as fixture
import ux_email_verification as ev

sm = fixture.sm
ORIGIN = 'https://scoremax.pk'
PASSWORD = 'Synthetic-email-qualification-only!'
TABLES = ('questions', 'attempts', 'assessment_sessions', 'mastery_policies',
          'mastery_records', 'integration_ph_content_releases',
          'integration_ph_question_version_store',
          'integration_ph_release_question_membership',
          'integration_ph_product_activation_authorizations')


def protected_fingerprint():
    with sqlite3.connect(os.environ['SCOREMAX_DB']) as c:
        existing = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        result = {}
        for table in TABLES:
            if table in existing:
                rows = c.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
                result[table] = hashlib.sha256(json.dumps(rows, default=str, separators=(',', ':')).encode()).hexdigest()
        return result


class CapturedSMTP:
    messages = []
    lock = threading.Lock()
    fail = False

    def __init__(self, *args, **kwargs):
        if self.fail:
            raise RuntimeError('synthetic SMTP unavailable')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def login(self, *args):
        return None

    def send_message(self, message):
        with self.lock:
            self.messages.append(message)


class OptionalEmailVerification(unittest.TestCase):
    serial = 0

    @classmethod
    def setUpClass(cls):
        cls.protected_before = protected_fingerprint()

    @classmethod
    def tearDownClass(cls):
        if protected_fingerprint() != cls.protected_before:
            raise AssertionError('Protected academic data changed during email qualification')

    def setUp(self):
        type(self).serial += 1
        self.email = f'qualification-{self.serial}@example.invalid'
        self.client = sm.app.test_client()
        self.stack = []
        for context in (
            patch.dict(os.environ, {
                'SCOREMAX_REQUIRE_EMAIL_VERIFICATION': '0',
                'SCOREMAX_SEND_EMAIL_VERIFICATION': '1',
                'SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW': '0',
                'SCOREMAX_PUBLIC_BASE_URL': ORIGIN,
                'SCOREMAX_SMTP_PORT': '465', 'SCOREMAX_SMTP_SSL': '1',
            }),
            patch.object(sm, '_configured_public_origin', ORIGIN),
            patch.object(sm, 'rate_limit', return_value=True),
            patch.object(sm.smtplib, 'SMTP_SSL', CapturedSMTP),
        ):
            context.start()
            self.stack.append(context)
        self.addCleanup(lambda: [context.stop() for context in reversed(self.stack)])
        CapturedSMTP.messages = []
        CapturedSMTP.fail = False

    def post(self, path, data, client=None):
        client = client or self.client
        client.get('/login', base_url=ORIGIN)
        with client.session_transaction(base_url=ORIGIN) as session:
            csrf = session['_csrf_token']
        return client.post(path, base_url=ORIGIN, data={**data, '_csrf_token': csrf})

    def register(self, email=None):
        return self.post('/register/student', {'full_name': 'Synthetic Qualification',
                         'email': email or self.email, 'password': PASSWORD})

    def user(self):
        with ev._connect() as c:
            row = c.execute('SELECT * FROM users WHERE email=?', (self.email,)).fetchone()
            return dict(row) if row else None

    def change(self, **values):
        with ev._connect() as c:
            c.execute('UPDATE users SET '+','.join(f'{key}=?' for key in values)+' WHERE email=?',
                      (*values.values(), self.email))
            c.commit()

    def link(self, kind='verify-email'):
        links = re.findall(r'https://[^\s]+', CapturedSMTP.messages[-1].get_content())
        link = next(value for value in links if f'/{kind}/' in value)
        self.assertEqual(urlsplit(link).netloc, 'scoremax.pk')
        return urlsplit(link).path

    def flashes(self, client=None):
        with (client or self.client).session_transaction(base_url=ORIGIN) as session:
            return [message for category, message in session.get('_flashes', [])]

    def login(self, client=None, password=PASSWORD):
        return self.post('/login', {'identity': self.email, 'password': password}, client)

    def test_01_default_off_preserves_registration(self):
        os.environ['SCOREMAX_SEND_EMAIL_VERIFICATION'] = '0'
        self.assertEqual(self.register().status_code, 302)
        self.assertEqual(CapturedSMTP.messages, [])
        self.assertEqual(self.user()['email_verified'], 1)
        self.assertEqual(self.login().status_code, 302)

    def test_02_optional_send_allows_login_and_one_time_verification(self):
        self.assertEqual(self.register().location, '/login')
        self.assertEqual(len(CapturedSMTP.messages), 1)
        user = self.user()
        self.assertEqual(user['email_verified'], 0)
        self.assertEqual(user['account_status'], 'active')
        link = self.link()
        self.assertNotIn(link.rsplit('/', 1)[-1], json.dumps(user))
        self.assertEqual(self.login().status_code, 302)
        os.environ['SCOREMAX_SEND_EMAIL_VERIFICATION'] = '0'
        self.client.get(link, base_url=ORIGIN)
        self.assertEqual(self.user()['email_verified'], 1)
        self.assertEqual(self.user()['email_verification_token_hash'], '')
        self.assertIn('Email verified.', ' '.join(self.flashes()))
        before = self.user()
        self.client.get(link, base_url=ORIGIN)
        self.assertIn('invalid or has already been used', self.flashes()[-1])
        self.assertEqual(before, self.user())

    def test_03_expiry_boundary_and_invalid_token_are_closed(self):
        self.register()
        link = self.link()
        now = ev._utcnow()
        self.change(email_verification_expires_at=ev._iso(now))
        before = self.user()
        with patch.object(ev, '_utcnow', return_value=now):
            self.client.get(link, base_url=ORIGIN)
        self.assertIn('expired', self.flashes()[-1])
        self.client.get('/verify-email/synthetic-invalid-token', base_url=ORIGIN)
        self.assertEqual(before, self.user())

    def test_04_duplicate_email_never_resets_existing_account(self):
        self.register()
        self.client.get(self.link(), base_url=ORIGIN)
        before = self.user()
        for password in ('Synthetic-wrong-password!', PASSWORD):
            response = self.post('/register/student', {'full_name': 'Duplicate',
                                  'email': self.email.upper(), 'password': password})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(before, self.user())
        self.assertEqual(len(CapturedSMTP.messages), 1)

    def test_05_resend_cooldown_rotates_and_invalidates_old_link(self):
        self.register()
        old = self.link()
        response = self.post('/verify-email/resend', {'identity': self.email})
        self.assertNotIn('preview_token', response.location)
        self.assertEqual(len(CapturedSMTP.messages), 1)
        self.change(email_verification_sent_at=ev._iso(ev._utcnow()-timedelta(seconds=61)))
        self.post('/verify-email/resend', {'identity': self.email})
        self.assertEqual(len(CapturedSMTP.messages), 2)
        fresh = self.link()
        self.assertNotEqual(old, fresh)
        self.client.get(old, base_url=ORIGIN)
        self.assertEqual(self.user()['email_verified'], 0)
        self.client.get(fresh, base_url=ORIGIN)
        self.assertEqual(self.user()['email_verified'], 1)

    def test_06_required_mode_remains_compatible_in_disposable_db_only(self):
        os.environ['SCOREMAX_REQUIRE_EMAIL_VERIFICATION'] = '1'
        os.environ['SCOREMAX_SEND_EMAIL_VERIFICATION'] = '0'
        self.assertIn('/verify-email?', self.register().location)
        self.assertEqual(self.user()['account_status'], 'pending_email_verification')
        self.assertIn('/verify-email?', self.login().location)
        self.client.get(self.link(), base_url=ORIGIN)
        self.assertEqual(self.login().location, '/dashboard')

    def test_07_disabled_accounts_are_not_reactivated_or_emailed(self):
        self.register()
        link = self.link()
        for status in ('disabled', 'suspended'):
            self.change(account_status=status,
                        email_verification_sent_at=ev._iso(ev._utcnow()-timedelta(seconds=61)))
            before = self.user()
            self.client.get(link, base_url=ORIGIN)
            self.post('/verify-email/resend', {'identity': self.email})
            self.assertEqual(before, self.user())
        self.assertEqual(len(CapturedSMTP.messages), 1)

    def test_08_failed_transport_does_not_block_optional_login(self):
        CapturedSMTP.fail = True
        with self.assertLogs(sm.app.logger, level='ERROR') as logs:
            self.assertEqual(self.register().location, '/login')
        self.assertEqual(CapturedSMTP.messages, [])
        self.assertNotIn('/verify-email/', '\n'.join(logs.output))
        self.assertEqual(self.user()['account_status'], 'active')
        self.assertEqual(self.login().location, '/dashboard')

    def test_09_links_ignore_untrusted_request_host(self):
        self.register()
        with sm.app.test_request_context('/', base_url='https://untrusted.invalid'):
            self.assertTrue(ev._verification_link('synthetic-token').startswith(ORIGIN+'/verify-email/'))

    def test_10_concurrent_verification_claims_exactly_once(self):
        self.register()
        link = self.link()
        barrier = threading.Barrier(2)
        parse = ev._parse_dt

        def synchronized_parse(value):
            result = parse(value)
            barrier.wait(timeout=5)
            return result

        def claim(_):
            client = sm.app.test_client()
            response = client.get(link, base_url=ORIGIN)
            self.assertEqual(response.status_code, 302)
            return self.flashes(client)[-1]

        with patch.object(ev, '_parse_dt', side_effect=synchronized_parse):
            with ThreadPoolExecutor(max_workers=2) as pool:
                messages = list(pool.map(claim, range(2)))
        self.assertEqual(sum(message.startswith('Email verified.') for message in messages), 1)
        self.assertEqual(sum('invalid or has already been used' in message for message in messages), 1)

    def test_11_concurrent_resends_send_once(self):
        self.register()
        self.change(email_verification_sent_at=ev._iso(ev._utcnow()-timedelta(seconds=61)))
        clients = [sm.app.test_client(), sm.app.test_client()]
        barrier = threading.Barrier(2)

        def resend(client):
            client.get('/login', base_url=ORIGIN)
            barrier.wait(timeout=5)
            return self.post('/verify-email/resend', {'identity': self.email}, client).status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(resend, clients)), [302, 302])
        self.assertEqual(len(CapturedSMTP.messages), 2)

    def test_12_token_and_session_survive_fresh_process(self):
        self.register()
        link = self.link()
        self.login()
        cookie = self.client.get_cookie(sm.app.config['SESSION_COOKIE_NAME'], domain='scoremax.pk')
        code = '''import json, os, socket, sys
socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('network disabled'))
sys.path.insert(0,sys.argv[1])
import scoremax_production
import app
data=json.load(sys.stdin)
c=app.app.test_client()
c.set_cookie(app.app.config['SESSION_COOKIE_NAME'],data['cookie'],domain='scoremax.pk')
assert c.get('/dashboard',base_url='https://scoremax.pk').location != '/login'
c.get(data['link'],base_url='https://scoremax.pk')
with app.db() as db:
 assert db.execute('SELECT email_verified FROM users WHERE email=?',(data['email'],)).fetchone()[0]==1
print('FRESH_PROCESS_EMAIL_SESSION_PASS')
'''
        result = subprocess.run([sys.executable, '-c', code, str(fixture.ROOT)],
                                input=json.dumps({'cookie': cookie.value, 'link': link, 'email': self.email}),
                                text=True, capture_output=True, env=os.environ.copy(), timeout=30)
        self.assertEqual(result.returncode, 0, 'Fresh-process session/token qualification failed')
        self.assertIn('FRESH_PROCESS_EMAIL_SESSION_PASS', result.stdout)

    def test_13_password_reset_rotation_and_old_session_revocation(self):
        self.register()
        self.login()
        other = sm.app.test_client()
        self.login(other)
        self.post('/forgot-password', {'email': self.email})
        old = self.link('reset-password')
        self.post('/forgot-password', {'email': self.email})
        fresh = self.link('reset-password')
        self.assertNotEqual(old, fresh)
        self.assertIn(b'invalid', self.client.get(old, base_url=ORIGIN).data.lower())
        version = self.user()['session_version']
        new_password = 'Synthetic-replacement-password-only!'
        self.assertEqual(self.post(fresh, {'password': new_password}).location, '/login')
        self.assertEqual(self.user()['session_version'], version+1)
        self.assertEqual(other.get('/dashboard', base_url=ORIGIN).location, '/login')
        self.assertEqual(self.post(fresh, {'password': PASSWORD}).location, '/forgot-password')
        self.assertEqual(self.login(password=new_password).location, '/dashboard')

    def test_14_access_log_contains_route_template_only(self):
        from gunicorn.config import Config
        from gunicorn.glogging import Logger, SafeAtoms
        from types import SimpleNamespace
        marker = 'SYNTHETIC_TOKEN_MUST_NOT_BE_LOGGED'
        response = self.client.get('/verify-email/'+marker, base_url=ORIGIN)
        self.assertEqual(response.status_code, 302)
        with sm.app.test_request_context('/verify-email/'+marker):
            result = sm.app.process_response(sm.app.response_class())
            from flask import request
            safe_path = request.environ['scoremax.safe_path']
        self.assertEqual(safe_path, '/verify-email/<token>')
        environ = {'REQUEST_METHOD': 'GET', 'RAW_URI': '/verify-email/'+marker+'?token='+marker,
                   'PATH_INFO': '/verify-email/'+marker, 'QUERY_STRING': 'token='+marker,
                   'SERVER_PROTOCOL': 'HTTP/1.1', 'HTTP_REFERER': ORIGIN+'/'+marker,
                   'scoremax.safe_path': safe_path}
        logger = Logger(Config())
        atoms = SafeAtoms(logger.atoms(SimpleNamespace(status='302 Found', sent=0, headers=[]),
                                      SimpleNamespace(headers=[]), environ, timedelta(milliseconds=5)))
        line = '%(h)s %(l)s %(u)s %(t)s "%(m)s %({scoremax.safe_path}e)s %(H)s" %(s)s %(b)s %(L)s' % atoms
        self.assertIn('/verify-email/<token>', line)
        self.assertNotIn(marker, line)


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(OptionalEmailVerification))
    print('OPTIONAL_EMAIL_QUALIFICATION '+json.dumps({
        'status': 'PASS' if result.wasSuccessful() else 'FAIL', 'tests': result.testsRun,
        'failures': len(result.failures), 'errors': len(result.errors),
        'network_disabled': True, 'production_db_used': False, 'real_email_sent': False,
        'protected_data_unchanged': protected_fingerprint() == OptionalEmailVerification.protected_before,
    }, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
