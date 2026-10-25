"""A bounded invitation gate around existing student routes; grants no release authority."""
import json
import os
import re

from flask import Response, request, session

_ACCOUNT_ID = re.compile(r'STU-[0-9]{6}')
_PUBLIC_ENDPOINTS = frozenset({
    'index','login','register','logout','forgot_password','reset_password',
    'about_page','how_it_works','faq_page','updates_page','contact_page',
    'healthz','readyz','static','knowledge_home','knowledge_article','connect_page',
    'sustainability_page','teacher_of_year_page','science_genius_home',
    'science_genius_leaderboard','feature_interest','referral_redirect',
    'reviewer_invite','ux_register_interest','ux_nominate_school','ux_verify_email',
    'ux_verification_pending','ux_resend_verification',
})
_NOTICE = ('<aside role="status" data-scoremax-invite-only-pilot="1">'
           'Invitation-only pilot. Public student registration is closed. '
           'Results are pilot practice feedback; no examination-readiness '
           'certificate is conferred by pilot access.</aside>')


def _configuration(environ):
    mode = str(environ.get('SCOREMAX_INVITE_ONLY_PILOT', '0')).strip()
    if mode not in {'0', '1'}:
        raise ValueError('INVITE_ONLY_PILOT_MODE_INVALID')
    if mode == '0':
        return False, frozenset()
    try:
        raw = json.loads(environ.get('SCOREMAX_PILOT_STUDENT_IDS_JSON', '[]'))
    except (TypeError, ValueError):
        raise ValueError('INVITE_ONLY_PILOT_ALLOWLIST_INVALID') from None
    if (not isinstance(raw, list) or not 1 <= len(raw) <= 20
            or any(not isinstance(value, str) or not _ACCOUNT_ID.fullmatch(value) for value in raw)
            or len(raw) != len(set(raw))):
        raise ValueError('INVITE_ONLY_PILOT_ALLOWLIST_INVALID')
    return True, frozenset(raw)


def _restricted():
    return Response(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>ScoreMax pilot access</title></head><body><main>'
        '<h1>ScoreMax pilot access is by invitation</h1>'
        '<p>Use an invited, verified student account. Your account and saved '
        'records have not been changed.</p><a href="/login">Log in</a> '
        '<a href="/logout">Log out</a></main></body></html>',
        status=403, mimetype='text/html',
        headers={'Cache-Control': 'no-store, private'},
    )


def _practice_only():
    return Response(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<title>ScoreMax pilot practice</title></head><body><main>'
        '<h1>Pilot practice feedback only</h1>'
        '<p>Formal mastery checks are unavailable during this pilot.</p>'
        '<a href="/test/setup">Open practice</a></main></body></html>',
        status=403, mimetype='text/html',
        headers={'Cache-Control': 'no-store, private'},
    )


def install(app, database_factory, environ=None):
    """Install after native account-security hooks; retain every native role/release check.

    The factory must return a new caller-owned connection, as app.db already does.
    Private account IDs live only in deployment configuration, never in source/logs.
    """
    enabled, allowed = _configuration(os.environ if environ is None else environ)
    marker = 'scoremax_invite_only_pilot'
    if marker in app.extensions:
        raise RuntimeError('INVITE_ONLY_PILOT_ALREADY_INSTALLED')
    app.extensions[marker] = {'enabled': enabled, 'allowed_count': len(allowed)}
    if not enabled:
        return

    @app.before_request
    def _invitation_boundary():
        if request.path.startswith(('/api/integration/v1/','/api/payments/v1/provider/')):
            return None  # Native machine credentials/HMAC still govern these routes.
        # Cover both methods and the native parameterised registration endpoint.
        if (request.endpoint == 'register' and (request.view_args or {}).get('role') == 'student'
                or request.path.rstrip('/') == '/register/student'):
            return _restricted()
        user_id = session.get('user_id')
        if user_id is None or request.endpoint in _PUBLIC_ENDPOINTS:
            return None
        connection = database_factory()
        try:
            connection.execute('PRAGMA query_only=ON')
            row = connection.execute(
                'SELECT role,system_user_id,account_status,email_verified,is_demo_account '
                'FROM users WHERE id=?', (user_id,),
            ).fetchone()
            user = dict(row) if row is not None else None
            if (user is not None and user['role'] == 'student'
                    and user['system_user_id'] in allowed):
                if request.endpoint == 'mastery_page' or request.path.rstrip('/') == '/student/mastery':
                    return _practice_only()
                assessment_id = (request.view_args or {}).get('assessment_id')
                if assessment_id is not None:
                    assessment = connection.execute(
                        'SELECT meta_json FROM assessment_sessions WHERE id=? AND student_id=?',
                        (assessment_id, user_id),
                    ).fetchone()
                    if assessment is not None:
                        try:
                            metadata = json.loads(assessment['meta_json'] or '{}')
                        except (TypeError, ValueError):
                            return _restricted()
                        if not isinstance(metadata, dict):
                            return _restricted()
                        if metadata.get('assessment_kind') == 'mastery':
                            return _practice_only()
        finally:
            connection.close()
        if user is None:
            return _restricted()
        if user['role'] != 'student':
            return None  # Existing admin/reviewer/QA boundaries remain authoritative.
        if (user['system_user_id'] not in allowed or user['account_status'] != 'active'
                or not user['email_verified'] or user['is_demo_account']):
            return _restricted()
        return None  # Invitation never replaces the native route's authorisation.

    @app.after_request
    def _pilot_label(response):
        if (response.mimetype == 'text/html' and not response.is_streamed
                and response.status_code < 300 and session.get('role') not in {'admin','reviewer','teacher'}):
            text = response.get_data(as_text=True)
            if '</body>' in text and 'data-scoremax-invite-only-pilot=' not in text:
                response.set_data(text.replace('</body>', _NOTICE + '</body>', 1))
        return response
