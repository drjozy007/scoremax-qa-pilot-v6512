"""Isolated WA-01/WA-09 regression qualification; never uses configured/live storage.

Run after the canonical build: python scripts/qualify_account_startup_repair.py
Only synthetic credentials are used, and all outbound connections are blocked.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'scoremax_runtime_v669b'
STATE = tempfile.TemporaryDirectory(prefix='scoremax-account-startup-')
BASE = Path(STATE.name)
# These are synthetic regression credentials, never product credentials.
OWNER_PASSWORD = 'Synthetic-Owner-Only-2026!'
LEGACY_PASSWORD = 'Synthetic-Old-Preview-2026!'
for key in tuple(os.environ):
    if key.startswith(('SCOREMAX_', 'POWER_HOUSE_', 'GROWTH_ENGINE_')):
        del os.environ[key]
os.environ.update({
    'SCOREMAX_ENV':'production', 'SCOREMAX_SECRET':'isolated-account-startup-regression-secret-20260922',
    'SCOREMAX_STAGING_SESSION_SECRET':'isolated-account-startup-regression-secret-20260922',
    'SCOREMAX_DB':str(BASE/'initial.db'), 'SCOREMAX_PERSISTENT_ROOT':str(BASE),
    'SCOREMAX_BACKUP_DIR':str(BASE/'backup'), 'SCOREMAX_CONTENT_INTAKE_DIR':str(BASE/'intake'),
    'SCOREMAX_SMTP_HOST':'smtp.invalid', 'SCOREMAX_SMTP_FROM':'qualification@scoremax.test',
    'SCOREMAX_PUBLIC_BASE_URL':'https://localhost', 'WEB_CONCURRENCY':'1',
    'SCOREMAX_INSTANCE_COUNT':'1', 'SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'0',
    'SCOREMAX_ENFORCE_PAYWALL':'0', 'SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':OWNER_PASSWORD,
})
def deny_network(*args, **kwargs):
    raise RuntimeError('QUALIFICATION_NETWORK_DISABLED')
socket.socket.connect = deny_network
socket.socket.connect_ex = deny_network
sys.path.insert(0, str(ROOT))
# This must succeed. No fallback to partially initialized app.py is permitted.
import scoremax_production as production
import app as sm
import ux_teacher_preview as preview
import ux_reviewer_accounts as reviewers
import ux_admin_view_as_runtime as view_as
import ux_bio13_failed_pilot_retirement_runtime as retirement

SNAPSHOT = BASE/'snapshot.db'
with sm.db() as src, sqlite3.connect(SNAPSHOT) as dst:
    src.backup(dst)


def rows(table):
    with sm.db() as conn:
        return [dict(r) for r in conn.execute(f'SELECT * FROM {table} ORDER BY 1')]


def user(username):
    with sm.db() as conn:
        return dict(conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone())


def insert_user(username, role='admin', password=LEGACY_PASSWORD, **extra):
    with sm.db() as conn:
        values = {'system_user_id':'SYN-'+username,'username':username,'email':username+'@scoremax.test',
                  'role':role,'full_name':'Synthetic '+username,'password_hash':sm.generate_password_hash(password),
                  'account_status':'active','session_version':0,'login_provider':'password', **extra}
        uid = preview._insert_dynamic(conn, 'users', values)
        conn.commit()
        return uid


def legacy_admin():
    return insert_user(preview.ADMIN_USERNAME, email=preview.ADMIN_EMAIL, system_user_id=preview.ADMIN_SYSTEM_ID)


def authenticated(username='admin'):
    row = user(username)
    client = sm.app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=row['id'], role=row['role'], full_name=row['full_name'],
                       session_version=int(row['session_version'] or 0), _csrf_token='synthetic-csrf')
    return client


def enter_preview(client, profile='student:fsc1'):
    return client.post('/admin/view-as/start',data={'profile':profile,'_csrf_token':'synthetic-csrf'},base_url='https://localhost')


class AccountStartupRepair(unittest.TestCase):
    def setUp(self):
        self.state = BASE/self._testMethodName
        self.state.mkdir()
        self.db = self.state/'case.db'
        with sqlite3.connect(SNAPSHOT) as src, sqlite3.connect(self.db) as dst:
            src.backup(dst)
        sm.DB = self.db
        os.environ['SCOREMAX_DB'] = str(self.db)
        os.environ.pop('SCOREMAX_RETIRE_FAILED_BIO13_PILOT', None)
        for account in reviewers.REVIEWER_ACCOUNTS:
            os.environ.pop(account['env'], None)

    def test_cold_boot_uses_actual_entrypoint_without_admin_preview(self):
        self.assertIs(production.application, sm.app)
        self.assertEqual(len(rows('questions')), 0)
        with sm.db() as conn:
            self.assertIsNone(conn.execute("SELECT id FROM users WHERE username='ux-admin'").fetchone())
        for name in ('ux-teacher','ux-teacher-student-1'):
            self.assertEqual(user(name)['password_hash'], '')
            self.assertEqual(user(name)['login_provider'], 'preview')
        for endpoint in ('admin_view_as', 'admin_mastery_rigor', 'ux_content_review_staged', 'ux_catalogue_subject'):
            self.assertIn(endpoint, sm.app.view_functions)

    def test_startup_replays_preserve_all_existing_identities(self):
        before = {t:rows(t) for t in ('users','classrooms','classroom_students')}
        for _ in range(3):
            preview.ensure_teacher_preview()
            reviewers.ensure_reviewer_accounts()
        self.assertEqual(before, {t:rows(t) for t in before})

    def test_teacher_password_disable_version_and_context_survive(self):
        with sm.db() as conn:
            conn.execute("UPDATE users SET password_hash=?,account_status='disabled',session_version=9,active_programme='MDCAT' WHERE username='ux-teacher'", (sm.generate_password_hash('Synthetic-New-Password!'),))
            conn.commit()
        before = user('ux-teacher')
        preview.ensure_teacher_preview()
        self.assertEqual(user('ux-teacher'), before)

    def test_legacy_admin_is_not_resurrected_or_rotated(self):
        uid = legacy_admin()
        with sm.db() as conn:
            conn.execute("UPDATE users SET account_status='disabled',session_version=9 WHERE id=?", (uid,));conn.commit()
        before = user('ux-admin')
        preview.ensure_teacher_preview()
        self.assertEqual(user('ux-admin'), before)

    def test_existing_owner_not_changed_by_seeders(self):
        before=user('admin')
        preview.ensure_teacher_preview();reviewers.ensure_reviewer_accounts()
        self.assertEqual(user('admin'),before)

    def test_class_configuration_and_removed_members_not_recreated(self):
        with sm.db() as conn:
            conn.execute("UPDATE classrooms SET name='Changed by owner',level='MDCAT' WHERE join_code='UXBIO26'")
            conn.execute('DELETE FROM classroom_students WHERE rowid=(SELECT MIN(rowid) FROM classroom_students)');conn.commit()
        before={t:rows(t) for t in ('classrooms','classroom_students')}
        preview.ensure_teacher_preview()
        self.assertEqual(before,{t:rows(t) for t in before})

    def test_preview_cross_field_collision_is_atomic(self):
        insert_user('TCH-900001')
        before=rows('users')
        with self.assertRaisesRegex(RuntimeError,'PREVIEW_IDENTITY_AMBIGUOUS'):
            preview.ensure_teacher_preview()
        self.assertEqual(rows('users'),before)

    def test_preview_role_mismatch_does_not_reassign_role(self):
        with sm.db() as conn:
            conn.execute("UPDATE users SET role='admin' WHERE username='ux-teacher'");conn.commit()
        before=rows('users')
        with self.assertRaisesRegex(RuntimeError,'PREVIEW_IDENTITY_MISMATCH'):
            preview.ensure_teacher_preview()
        self.assertEqual(rows('users'),before)

    def test_reviewer_password_access_revocation_and_context_survive(self):
        os.environ[reviewers.REVIEWER_ACCOUNTS[0]['env']]='Synthetic-Reviewer-Initial!'
        reviewers.ensure_reviewer_accounts()
        with sm.db() as conn:
            conn.execute("UPDATE users SET account_status='disabled',content_reviewer_enabled=0,session_version=12,password_hash=?,active_programme='MDCAT' WHERE username='reviewer01'", (sm.generate_password_hash('Synthetic-Reviewer-Changed!'),));conn.commit()
        before=user('reviewer01')
        os.environ[reviewers.REVIEWER_ACCOUNTS[0]['env']]='Synthetic-Env-Rotation!'
        reviewers.ensure_reviewer_accounts()
        self.assertEqual(user('reviewer01'),before)

    def test_reviewer_identity_collision_rolls_back_earlier_insert(self):
        for account in reviewers.REVIEWER_ACCOUNTS[:2]:
            os.environ[account['env']]='Synthetic-Reviewer-Only!'
        insert_user('other-owner',email='reviewer02@scoremax.test')
        before=rows('users')
        with self.assertRaisesRegex(RuntimeError,'PREVIEW_IDENTITY_MISMATCH'):
            reviewers.ensure_reviewer_accounts()
        self.assertEqual(rows('users'),before)

    def test_reviewer_without_configured_password_not_created(self):
        before=rows('users');reviewers.ensure_reviewer_accounts()
        self.assertEqual(rows('users'),before)

    def test_explicit_retirement_requires_correct_independent_owner(self):
        legacy_admin();before=rows('users')
        for identity,password in [('admin','wrong'),('ux-admin',LEGACY_PASSWORD),('missing',OWNER_PASSWORD)]:
            with self.assertRaisesRegex(RuntimeError,'INDEPENDENT_OWNER_ACCESS_VERIFICATION_REQUIRED'):
                preview.retire_legacy_admin_preview(sm,owner_identity=identity,owner_password=password)
            self.assertEqual(rows('users'),before)

    def test_explicit_retirement_rejects_shared_owner_credential(self):
        legacy_admin();insert_user('second-admin')
        before=rows('users')
        with self.assertRaisesRegex(RuntimeError,'OWNER_CREDENTIAL_NOT_INDEPENDENT'):
            preview.retire_legacy_admin_preview(sm,owner_identity='second-admin',owner_password=LEGACY_PASSWORD)
        self.assertEqual(rows('users'),before)

    def test_explicit_retirement_only_changes_exact_legacy_identity(self):
        uid=legacy_admin();owner_before=user('admin')
        other_before=[u for u in rows('users') if u['id']!=uid]
        with sm.db() as conn:
            conn.execute("UPDATE users SET session_version=9 WHERE id=?",(uid,))
            conn.execute("INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) VALUES(?,?,?)",(uid,'synthetic-reset-hash','2099-01-01'));conn.commit()
        stale=authenticated('ux-admin')
        result=preview.retire_legacy_admin_preview(sm,owner_identity='admin',owner_password=OWNER_PASSWORD)
        self.assertEqual(result['status'],'RETIRED')
        after=user('ux-admin')
        self.assertEqual((after['account_status'],after['password_hash'],after['session_version']),('disabled','',10))
        self.assertEqual(user('admin'),owner_before)
        self.assertEqual([u for u in rows('users') if u['id']!=uid],other_before)
        self.assertTrue(rows('password_reset_tokens')[0]['used_at'])
        response=stale.get('/admin',base_url='https://localhost')
        self.assertEqual(response.status_code,302)
        with stale.session_transaction() as session:self.assertNotIn('user_id',session)
        self.assertFalse(sm.check_password_hash(after['password_hash'],LEGACY_PASSWORD))

    def test_retirement_replay_is_idempotent_and_stays_retired_on_boot(self):
        legacy_admin()
        preview.retire_legacy_admin_preview(sm,owner_identity='admin',owner_password=OWNER_PASSWORD)
        before=rows('users')
        again=preview.retire_legacy_admin_preview(sm,owner_identity='admin',owner_password=OWNER_PASSWORD)
        self.assertEqual(again['status'],'ALREADY_RETIRED')
        preview.ensure_teacher_preview()
        self.assertEqual(rows('users'),before)

    def test_retirement_native_owner_login_stays_working(self):
        legacy_admin()
        for i in range(2):
            client=sm.app.test_client();client.get('/login',base_url='https://localhost')
            with client.session_transaction() as session:token=session['_csrf_token']
            response=client.post('/login',data={'identity':'admin','password':OWNER_PASSWORD,'_csrf_token':token},base_url='https://localhost')
            self.assertEqual(response.status_code,302)
            with client.session_transaction() as session:self.assertEqual(session.get('role'),'admin')
            if i==0:preview.retire_legacy_admin_preview(sm,owner_identity='admin',owner_password=OWNER_PASSWORD)

    def test_retirement_ambiguous_login_cannot_authorize(self):
        legacy_admin();insert_user('ambiguous-admin',email='admin')
        before=rows('users')
        with self.assertRaisesRegex(RuntimeError,'INDEPENDENT_OWNER_ACCESS_VERIFICATION_REQUIRED'):
            preview.retire_legacy_admin_preview(sm,owner_identity='admin',owner_password=OWNER_PASSWORD)
        self.assertEqual(rows('users'),before)

    def test_retirement_no_legacy_record_has_no_side_effect(self):
        before=rows('users')
        result=preview.retire_legacy_admin_preview(sm,owner_identity='admin',owner_password=OWNER_PASSWORD)
        self.assertEqual(result['status'],'NOT_PRESENT');self.assertEqual(rows('users'),before)

    def test_view_as_all_six_profiles_exit_to_same_owner(self):
        for role in ('student','teacher'):
            for programme in ('fsc1','fsc2','mdcat'):
                with self.subTest(role=role,programme=programme):
                    client=authenticated();self.assertEqual(enter_preview(client,f'{role}:{programme}').status_code,302)
                    with client.session_transaction() as session:
                        self.assertEqual(session.get('role'),role)
                        self.assertEqual(session.get('admin_view_as_origin_session_version'),0)
                    self.assertEqual(client.get('/admin/view-as/exit',base_url='https://localhost').status_code,302)
                    with client.session_transaction() as session:
                        self.assertEqual(session.get('user_id'),user('admin')['id'])
                        self.assertEqual(session.get('role'),'admin')

    def test_view_as_owner_revocation_blocks_next_request_and_exit(self):
        for destination in ('/student/catalogue','/admin/view-as/exit'):
            with self.subTest(destination=destination):
                client=authenticated();self.assertEqual(enter_preview(client).status_code,302)
                with sm.db() as conn:
                    conn.execute("UPDATE users SET session_version=session_version+1 WHERE username='admin'");conn.commit()
                response=client.get(destination,base_url='https://localhost')
                self.assertEqual(response.status_code,302)
                self.assertTrue(response.location.endswith('/login'))
                with client.session_transaction() as session:self.assertNotIn('user_id',session)

    def test_view_as_disabled_origin_cannot_restore(self):
        client=authenticated();enter_preview(client)
        with sm.db() as conn:
            conn.execute("UPDATE users SET account_status='disabled' WHERE username='admin'");conn.commit()
        response=client.get('/admin/view-as/exit',base_url='https://localhost')
        self.assertTrue(response.location.endswith('/login'))
        with client.session_transaction() as session:self.assertNotIn('user_id',session)

    def test_view_as_old_cookie_without_origin_version_fails_closed(self):
        client=authenticated();enter_preview(client)
        with client.session_transaction() as session:session.pop('admin_view_as_origin_session_version')
        response=client.get('/admin/view-as/exit',base_url='https://localhost')
        self.assertTrue(response.location.endswith('/login'))
        with client.session_transaction() as session:self.assertNotIn('user_id',session)

    def test_view_as_disabled_teacher_not_reenabled(self):
        with sm.db() as conn:
            conn.execute("UPDATE users SET account_status='disabled' WHERE username='ux-teacher'");conn.commit()
        before=user('ux-teacher')
        self.assertEqual(enter_preview(authenticated(),'teacher:fsc1').status_code,409)
        self.assertEqual(user('ux-teacher'),before)

    def test_view_as_teacher_does_not_reenable_disabled_students(self):
        with sm.db() as conn:
            conn.execute("UPDATE users SET account_status='disabled',session_version=7 WHERE username='ux-teacher-student-2'");conn.commit()
        before=user('ux-teacher-student-2')
        self.assertEqual(enter_preview(authenticated(),'teacher:mdcat').status_code,302)
        self.assertEqual(user('ux-teacher-student-2'),before)

    def test_view_as_readonly_and_csrf_fences_remain(self):
        client=authenticated();before=rows('assessment_sessions')
        self.assertEqual(client.post('/admin/view-as/start',data={'profile':'student:fsc1'},base_url='https://localhost').status_code,400)
        self.assertEqual(enter_preview(client).status_code,302)
        response=client.post('/test/start',data={'subject':'Physics','_csrf_token':'synthetic-csrf'},base_url='https://localhost')
        self.assertIn(response.status_code,(302,403))
        self.assertEqual(rows('assessment_sessions'),before)

    def test_view_as_non_admin_denied(self):
        for name in ('ux-teacher','ux-teacher-student-1'):
            self.assertEqual(enter_preview(authenticated(name)).status_code,403)

    def test_historical_retirement_disabled_does_not_open_database(self):
        with patch.object(sm,'db',side_effect=AssertionError('Disabled operation accessed database')):
            for value in ('OFF','0','','1','unrecognized'):
                with patch.dict(os.environ,{'SCOREMAX_RETIRE_FAILED_BIO13_PILOT':value}):
                    retirement.run(sm)

    def test_historical_retirement_armed_missing_batch_rolls_back(self):
        before=rows('users')
        with patch.dict(os.environ,{'SCOREMAX_RETIRE_FAILED_BIO13_PILOT':'ARMED'}):
            with self.assertRaisesRegex(RuntimeError,'BIO13_RETIRE_BATCH_COUNT:0'):
                retirement.run(sm)
        with sm.db() as conn:
            self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='bio13_failed_pilot_retirement_v1'").fetchone())
            self.assertEqual(conn.execute('PRAGMA quick_check').fetchone()[0],'ok')
            self.assertEqual(conn.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertEqual(rows('users'),before)

    def test_full_restarted_process_preserves_owner_and_revocations(self):
        legacy_admin()
        # Prepare a fully initialized restored-state fixture before freezing it.
        # Core init assigns ancillary referral identifiers to newly inserted users.
        sm.init()
        with sm.db() as conn:
            conn.execute("UPDATE users SET account_status='disabled',session_version=9 WHERE username IN ('ux-admin','ux-teacher')");conn.commit()
        before=rows('users')
        script="""import socket
socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('NETWORK_DISABLED'))
socket.socket.connect_ex=socket.socket.connect
import scoremax_production
print('ACTUAL_RESTART_PASSED')
"""
        completed=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=dict(os.environ),capture_output=True,text=True,timeout=40)
        self.assertEqual(completed.returncode,0,completed.stderr[-1200:])
        self.assertIn('ACTUAL_RESTART_PASSED',completed.stdout)
        # Native boot may add ancillary referral/email-verification metadata to a legacy
        # synthetic fixture. This gate freezes identity, auth, role and selected context.
        protected=('id','system_user_id','username','email','role','password_hash','account_status',
                   'login_provider','session_version','content_reviewer_enabled','active_programme')
        selected=lambda data:[{k:r.get(k) for k in protected} for r in data]
        self.assertEqual(selected(rows('users')),selected(before))
        self.assertEqual(user('admin'),next(r for r in before if r['username']=='admin'))

    def test_no_embedded_preview_credential_or_startup_admin_seed(self):
        source=(ROOT/'ux_teacher_preview.py').read_text()
        self.assertNotRegex(source,r'(pbkdf2:|scrypt:)[^\s]+\$')
        self.assertNotIn('TEACHER_PREVIEW_PASSWORD_HASH',source)
        self.assertNotIn('def _ensure_admin_preview',source)

    def test_native_admin_password_reset_revokes_sessions_and_reset_links(self):
        uid=insert_user('target-student',role='student')
        stale=authenticated('target-student')
        with sm.db() as conn:
            conn.execute('INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) VALUES(?,?,?)',(uid,'unused-link','2099-01-01'));conn.commit()
        response=authenticated().post(f'/admin/users/{uid}/reset-password',data={'new_password':'Synthetic-Changed-2026!','_csrf_token':'synthetic-csrf'},base_url='https://localhost')
        self.assertEqual(response.status_code,302)
        target=user('target-student')
        self.assertEqual(target['session_version'],1)
        self.assertTrue(sm.check_password_hash(target['password_hash'],'Synthetic-Changed-2026!'))
        self.assertTrue(rows('password_reset_tokens')[0]['used_at'])
        stale.get('/student',base_url='https://localhost')
        with stale.session_transaction() as session:self.assertNotIn('user_id',session)

    def test_native_disable_reenable_does_not_revive_old_session(self):
        uid=insert_user('target-student',role='student')
        stale=authenticated('target-student');admin=authenticated()
        for status in ('disabled','active'):
            response=admin.post(f'/admin/users/{uid}/status',data={'status':status,'_csrf_token':'synthetic-csrf'},base_url='https://localhost')
            self.assertEqual(response.status_code,302)
        self.assertEqual(user('target-student')['session_version'],2)
        stale.get('/student',base_url='https://localhost')
        with stale.session_transaction() as session:self.assertNotIn('user_id',session)
        before=user('target-student')
        admin.post(f'/admin/users/{uid}/status',data={'status':'active','_csrf_token':'synthetic-csrf'},base_url='https://localhost')
        self.assertEqual(user('target-student'),before)

    def test_native_reset_of_owner_invalidates_open_preview(self):
        insert_user('maintenance-admin',password='Synthetic-Independent-2026!')
        client=authenticated();enter_preview(client)
        uid=user('admin')['id']
        response=authenticated('maintenance-admin').post(f'/admin/users/{uid}/reset-password',data={'new_password':'Synthetic-New-Owner-2026!','_csrf_token':'synthetic-csrf'},base_url='https://localhost')
        self.assertEqual(response.status_code,302)
        response=client.get('/admin/view-as/exit',base_url='https://localhost')
        self.assertTrue(response.location.endswith('/login'))
        with client.session_transaction() as session:self.assertNotIn('user_id',session)

    def test_native_status_invalid_input_and_missing_users_fail_closed(self):
        admin=authenticated();before=rows('users');uid=user('admin')['id']
        response=admin.post(f'/admin/users/{uid}/status',data={'status':'unexpected','_csrf_token':'synthetic-csrf'},base_url='https://localhost')
        self.assertEqual(response.status_code,400)
        for suffix,data in [('status',{'status':'disabled'}),('reset-password',{'new_password':'Synthetic-Changed-2026!'})]:
            response=admin.post(f'/admin/users/999999/{suffix}',data={**data,'_csrf_token':'synthetic-csrf'},base_url='https://localhost')
            self.assertEqual(response.status_code,404)
        self.assertEqual(rows('users'),before)

    def test_native_self_service_reset_retains_single_use_and_revocation(self):
        uid=insert_user('target-student',role='student')
        token='synthetic-reset-token-only'
        token_hash=hashlib.sha256(token.encode()).hexdigest()
        with sm.db() as conn:
            conn.execute('INSERT INTO password_reset_tokens(user_id,token_hash,expires_at) VALUES(?,?,?)',(uid,token_hash,'2099-01-01'));conn.commit()
        client=sm.app.test_client();client.get('/login',base_url='https://localhost')
        with client.session_transaction() as session:csrf=session['_csrf_token']
        response=client.post('/reset-password/'+token,data={'password':'Synthetic-New-Self-2026!','_csrf_token':csrf},base_url='https://localhost')
        self.assertEqual(response.status_code,302)
        self.assertEqual(user('target-student')['session_version'],1)
        after=user('target-student')
        client.get('/login',base_url='https://localhost')
        with client.session_transaction() as session:csrf=session['_csrf_token']
        client.post('/reset-password/'+token,data={'password':'Synthetic-Unwanted-Replay!','_csrf_token':csrf},base_url='https://localhost')
        self.assertEqual(user('target-student'),after)

    def test_historical_retirement_valid_exact100_and_replay(self):
        # Minimal synthetic component fixture; full native schema/startup is exercised above.
        path=self.state/'historical.db'
        def connect():
            c=sqlite3.connect(path);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');return c
        with connect() as c:
            c.executescript('''CREATE TABLE content_import_batches(id INTEGER PRIMARY KEY,batch_code,row_count,valid_count,error_count,warning_count,source_prompt_pack_id,source_prompt_pack_version,payload_checksum);
CREATE TABLE questions(id INTEGER PRIMARY KEY,question_id,active,status,review_status,scoremax_ready,content_environment);
CREATE TABLE content_import_batch_rows(batch_id,question_db_id,row_json,import_status);
CREATE TABLE attempts(id INTEGER PRIMARY KEY,original_payload TEXT);
''')
            c.execute('INSERT INTO content_import_batches VALUES(1,?,100,100,0,0,?,?,?)',('SYN-HIST',retirement.PROMPT_PACK_ID,retirement.PROMPT_PACK_VERSION,retirement.TRANSPORT_SHA))
            for n in range(100):
                qid=f'SYN-Q{n}';active=int(n<98)
                c.execute('INSERT INTO questions VALUES(?,?,?,?,?,?,?)',(n+1,qid,active,'Approved' if active else 'Rejected','Approved' if active else 'Rejected',active,'PRODUCTION'))
                payload=json.dumps({'Question ID':qid,'Power House Public ID':f'SYN-PH{n}','Power House Source Row':str(n+1)})
                c.execute('INSERT INTO content_import_batch_rows VALUES(1,?,?,?)',(n+1,payload,'IMPORTED'))
            c.execute("INSERT INTO attempts VALUES(1,'immutable synthetic history')");c.commit()
        with patch.dict(os.environ,{'SCOREMAX_RETIRE_FAILED_BIO13_PILOT':'ARMED'}),patch.object(sm,'db',side_effect=connect):
            retirement.run(sm);retirement.run(sm)
        with connect() as c:
            self.assertEqual(c.execute('SELECT SUM(active) FROM questions').fetchone()[0],0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM bio13_failed_pilot_retirement_v1').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT original_payload FROM attempts').fetchone()[0],'immutable synthetic history')
            before=[tuple(r) for r in c.execute('SELECT * FROM questions ORDER BY id')]
        with patch.object(sm,'db',side_effect=connect):retirement.run(sm)
        with connect() as c:self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM questions ORDER BY id')],before)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='account_startup_repair_results.json')
    options=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(AccountStartupRepair)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'ux_teacher_preview.py',ROOT/'ux_reviewer_accounts.py',ROOT/'ux_admin_view_as_runtime.py',ROOT/'ux_bio13_failed_pilot_retirement_runtime.py',ROOT/'account_security_engine.py',ROOT/'app.py']}
    report={'suite':'WA01_WA09_ACCOUNT_STARTUP_REPAIR','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),'source_hashes':source_hashes,'production_data_modified':False,'render_deployment_triggered':False,'live_legacy_admin_retired':False,'scope':'Synthetic, isolated cold and restarted native WSGI, account seeding, explicit owner-verified retirement, View As session revocation. Not whole-platform clearance.'}
    Path(options.report).write_text(json.dumps(report,indent=2)+'\n')
    print('ACCOUNT_STARTUP_REPAIR_RESULT='+json.dumps(report,sort_keys=True))
    STATE.cleanup()
    raise SystemExit(0 if result.wasSuccessful() else 1)
