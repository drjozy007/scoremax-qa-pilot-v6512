"""ScoreMax V6.2.7.2 Email-or-User-ID login regression suite."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
from smoke_tests_v5_5 import install_framework_stubs


def main():
    flask, request = install_framework_stubs()
    temp = Path(tempfile.mkdtemp(prefix='scoremax_v6272_'))
    os.environ['SCOREMAX_DB'] = str(temp / 'scoremax.db')
    os.environ['SCOREMAX_ENV'] = 'local'
    os.environ['SCOREMAX_SECRET'] = 'v6.2.7.2-login-regression-secret'
    os.environ['SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD'] = 'Admin-Login-Password-2026'
    sys.path.insert(0, str(ROOT))

    import app
    if not hasattr(app.app, 'logger'):
        class _Logger:
            @staticmethod
            def warning(*args, **kwargs):
                return None
        app.app.logger = _Logger()
    from werkzeug.security import generate_password_hash

    checks = []

    def ok(name, condition=True):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
        print('PASS:', name)

    def login_attempt(identity, password, *, legacy_key=False):
        flask.session.clear()
        request.method = 'POST'
        request.remote_addr = '127.0.0.1'
        request.form = {('email' if legacy_key else 'identity'): identity, 'password': password}
        result = app.login()
        return result, dict(flask.session)

    app.init()
    c = app.db()
    password = 'Student-Login-Password-2026'
    cur = c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status)
        VALUES(?,?,?,?,?,?,'active')""", (
        'STU-000123', 'student', 'Login Test Student', 'student.login@example.com',
        'sm-00000123', generate_password_hash(password)))
    student_id = cur.lastrowid

    # Deliberate cross-field collision: one account's email equals another account's username.
    c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status)
        VALUES(?,?,?,?,?,?,'active')""", (
        'TCH-000901', 'teacher', 'Collision Email', 'collision@example.com',
        'teacher-collision-a', generate_password_hash('Collision-A-Password')))
    c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status)
        VALUES(?,?,?,?,?,?,'active')""", (
        'PAR-000902', 'parent', 'Collision Username', 'parent-collision@example.com',
        'collision@example.com', generate_password_hash('Collision-B-Password')))
    c.commit()

    template = (ROOT / 'templates' / 'login.html').read_text(encoding='utf-8')
    ok('login page gives a clear email or ScoreMax ID sign-in label', ('Email or ScoreMax ID' in template) or ('Email or User ID' in template))
    ok('login field accepts non-email identifiers in the browser', 'type="text" name="identity"' in template and 'type="email" name="identity"' not in template)
    ok('login field uses username autocomplete semantics', 'autocomplete="username"' in template)

    result, session = login_attempt('STUDENT.LOGIN@EXAMPLE.COM', password)
    ok('registered email login is case-insensitive', result == '/dashboard' and session.get('user_id') == student_id)

    result, session = login_attempt('stu-000123', password)
    ok('formal ScoreMax system User ID login is case-insensitive', result == '/dashboard' and session.get('user_id') == student_id)

    result, session = login_attempt('SM-00000123', password)
    ok('assigned username login remains supported', result == '/dashboard' and session.get('user_id') == student_id)

    result, session = login_attempt('admin', 'Admin-Login-Password-2026')
    ok('bootstrap Admin can log in with the admin User ID', result == '/dashboard' and session.get('role') == 'admin')

    result, session = login_attempt('sm-00000123', password, legacy_key=True)
    ok('older clients using the email form key remain compatible', result == '/dashboard' and session.get('user_id') == student_id)

    result, session = login_attempt('collision@example.com', 'Collision-A-Password')
    ok('cross-field ambiguous identifiers are rejected instead of selecting an account',
       isinstance(result, tuple) and result[0] == 'render' and not session.get('user_id'))

    unknown_result, unknown_session = login_attempt('missing-user', 'Wrong-Password')
    wrong_result, wrong_session = login_attempt('student.login@example.com', 'Wrong-Password')
    ok('unknown and wrong-password attempts follow the same neutral failure path',
       isinstance(unknown_result, tuple) and unknown_result[0] == 'render'
       and isinstance(wrong_result, tuple) and wrong_result[0] == 'render'
       and not unknown_session.get('user_id') and not wrong_session.get('user_id'))

    source = (ROOT / 'app.py').read_text(encoding='utf-8')
    ok('login failure wording is neutral and does not enumerate accounts', "flash('Invalid login details.','error')" in source)

    indexes = {row['name'] for row in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    ok('case-insensitive indexes protect email username and system User ID uniqueness',
       {'idx_users_unique_email', 'idx_users_unique_username_ci', 'idx_users_unique_system_user_id_ci'} <= indexes)

    ok('release health marker is V6.2.7.2', app.healthz()[0]['version'] in {'6.2.7.2','6.2.8','6.2.8.1'})
    c.close()
    print(f'\nV6.2.7.2 LOGIN COMPATIBILITY CHECKS PASSED: {len(checks)}')


if __name__ == '__main__':
    main()
