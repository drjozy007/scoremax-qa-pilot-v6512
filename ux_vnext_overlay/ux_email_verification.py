from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import flash, redirect, render_template, request, url_for
from werkzeug.security import check_password_hash

TOKEN_TTL_HOURS=24
RESEND_COOLDOWN_SECONDS=60


def _db_path() -> Path:
    return Path(os.environ.get('SCOREMAX_DB','/tmp/scoremax-ux-vnext/state/scoremax.db'))


def _connect() -> sqlite3.Connection:
    conn=sqlite3.connect(_db_path(),timeout=5)
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def _cols(conn,table):
    return {r['name'] for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def _ensure_col(conn,table,name,definition):
    if name not in _cols(conn,table):
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


def _utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _iso(dt):
    return dt.isoformat().replace('+00:00','Z')


def _parse_dt(value):
    if not value:
        return None
    try:
        dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        if dt.tzinfo is None:
            dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _token_hash(token):
    return hashlib.sha256(str(token).encode('utf-8')).hexdigest()


def _required():
    return os.environ.get('SCOREMAX_REQUIRE_EMAIL_VERIFICATION','0').strip()=='1'


def _preview_enabled():
    return os.environ.get('SCOREMAX_STAGING_EMAIL_VERIFICATION_PREVIEW','0').strip()=='1'


def _ensure_schema_and_backfill():
    conn=_connect()
    try:
        _ensure_col(conn,'users','email_verified','INTEGER DEFAULT 1')
        _ensure_col(conn,'users','email_verified_at',"TEXT DEFAULT ''")
        _ensure_col(conn,'users','email_verification_token_hash',"TEXT DEFAULT ''")
        _ensure_col(conn,'users','email_verification_expires_at',"TEXT DEFAULT ''")
        _ensure_col(conn,'users','email_verification_sent_at',"TEXT DEFAULT ''")
        # Existing accounts predate this feature. Never unexpectedly lock them out.
        conn.execute("UPDATE users SET email_verified=1 WHERE email_verified IS NULL")
        # System/demo/reviewer accounts are deliberately pre-verified.
        cols=_cols(conn,'users')
        exempt=["role IN ('admin','qa_student','reviewer')","system_user_id IN ('STU-900001','CRV-900001','REVIEWER-01','REVIEWER-02','REVIEWER-03','REVIEWER-04','REVIEWER-05')"]
        if 'is_demo_account' in cols: exempt.append('COALESCE(is_demo_account,0)=1')
        if 'content_reviewer_enabled' in cols: exempt.append('COALESCE(content_reviewer_enabled,0)=1')
        conn.execute("UPDATE users SET email_verified=1,email_verified_at=COALESCE(NULLIF(email_verified_at,''),?) WHERE "+' OR '.join(exempt),(_iso(_utcnow()),))
        conn.commit()
    finally:
        conn.close()


def _resolve(conn,identity):
    normalized=str(identity or '').strip().lower()
    if not normalized or len(normalized)>320:
        return None
    rows=conn.execute("""SELECT * FROM users WHERE lower(COALESCE(email,''))=? OR lower(COALESCE(username,''))=? OR lower(COALESCE(system_user_id,''))=? ORDER BY id LIMIT 2""",(normalized,normalized,normalized)).fetchall()
    return rows[0] if len(rows)==1 else None


def _mask_email(value):
    email=str(value or '').strip()
    if '@' not in email:
        return 'your registered email'
    local,domain=email.split('@',1)
    return (local[:1] or '*')+'***@'+domain


def _is_exempt(conn,user):
    if not user:
        return False
    if str(user['role'] or '') in {'admin','qa_student','reviewer'}:
        return True
    if str(user['system_user_id'] or '') in {'STU-900001','CRV-900001','REVIEWER-01','REVIEWER-02','REVIEWER-03','REVIEWER-04','REVIEWER-05'}:
        return True
    keys=set(user.keys())
    if 'is_demo_account' in keys and int(user['is_demo_account'] or 0)==1:
        return True
    if 'content_reviewer_enabled' in keys and int(user['content_reviewer_enabled'] or 0)==1:
        return True
    return False


def _make_token(conn,user_id):
    token=secrets.token_urlsafe(32)
    now=_utcnow(); expires=now+timedelta(hours=TOKEN_TTL_HOURS)
    conn.execute("""UPDATE users SET email_verification_token_hash=?,email_verification_expires_at=?,email_verification_sent_at=? WHERE id=?""",(_token_hash(token),_iso(expires),_iso(now),user_id))
    return token


def _verification_link(token):
    return url_for('ux_verify_email',token=token,_external=True)


def _send_verification(send_email,user,token):
    email=str(user['email'] or '').strip()
    if not email:
        return False
    # The UX staging service currently uses localhost as its SMTP placeholder. Do not
    # generate noisy failed SMTP connections while the explicit staging preview is active.
    if _preview_enabled() and os.environ.get('SCOREMAX_SMTP_HOST','').strip().lower() in {'','localhost','127.0.0.1'}:
        return False
    link=_verification_link(token)
    body=(
        f"Hello {user['full_name'] or 'there'},\n\n"
        "Please verify your email address to activate your ScoreMax account.\n\n"
        f"Verify email: {link}\n\n"
        f"This link expires in {TOKEN_TTL_HOURS} hours. If you did not create a ScoreMax account, you can ignore this message.\n\n"
        "ScoreMax"
    )
    return bool(send_email(email,'Verify your ScoreMax email',body))


def install_email_verification(app, send_email) -> None:
    if getattr(app,'_ux_email_verification_installed',False):
        return
    _ensure_schema_and_backfill()

    original_register=app.view_functions.get('register')
    original_login=app.view_functions.get('login')
    if original_register is None or original_login is None:
        raise RuntimeError('UX_EMAIL_VERIFICATION_AUTH_ROUTES_MISSING')

    def register_wrapper(role):
        response=original_register(role)
        if not _required() or request.method!='POST' or role!='student':
            return response
        status=int(getattr(response,'status_code',200) or 200)
        if status not in {301,302,303,307,308}:
            return response
        email=str(request.form.get('email') or '').strip().lower()
        if not email:
            return response
        conn=_connect()
        try:
            user=_resolve(conn,email)
            if not user or _is_exempt(conn,user):
                return response
            token=_make_token(conn,user['id'])
            conn.execute("UPDATE users SET email_verified=0,email_verified_at='',account_status='pending_email_verification' WHERE id=?",(user['id'],))
            conn.commit()
            # Re-read after commit so the email function gets the latest row shape.
            user=conn.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
            sent=_send_verification(send_email,user,token)
        finally:
            conn.close()
        flash('Account created. Verify your email before logging in.','success')
        kwargs={'identity':email,'sent':'1' if sent else '0'}
        if _preview_enabled() and not sent:
            kwargs['preview_token']=token
        return redirect(url_for('ux_verification_pending',**kwargs))

    def login_wrapper():
        if _required() and request.method=='POST':
            identity=request.form.get('identity')
            if identity is None:
                identity=request.form.get('email','')
            password=request.form.get('password','')
            conn=_connect()
            try:
                user=_resolve(conn,identity)
                if user and not _is_exempt(conn,user) and int(user['email_verified'] or 0)!=1 and user['password_hash'] and check_password_hash(user['password_hash'],password):
                    return redirect(url_for('ux_verification_pending',identity=identity,sent='0'))
            finally:
                conn.close()
        return original_login()

    app.view_functions['register']=register_wrapper
    app.view_functions['login']=login_wrapper

    @app.route('/verify-email/<token>',methods=['GET'],endpoint='ux_verify_email')
    def ux_verify_email(token):
        if not _required():
            flash('Email verification is not currently required.','info')
            return redirect(url_for('login'))
        digest=_token_hash(token)
        conn=_connect()
        try:
            user=conn.execute("SELECT * FROM users WHERE email_verification_token_hash=? LIMIT 1",(digest,)).fetchone()
            if not user:
                flash('That verification link is invalid or has already been used.','error')
                return redirect(url_for('login'))
            expires=_parse_dt(user['email_verification_expires_at'])
            if not expires or expires<_utcnow():
                flash('That verification link has expired. Request a new one below.','error')
                return redirect(url_for('ux_verification_pending',identity=user['email'],sent='0'))
            conn.execute("""UPDATE users SET email_verified=1,email_verified_at=?,email_verification_token_hash='',email_verification_expires_at='',account_status='active' WHERE id=?""",(_iso(_utcnow()),user['id']))
            conn.commit()
        finally:
            conn.close()
        flash('Email verified. You can now log in to ScoreMax.','success')
        return redirect(url_for('login'))

    @app.route('/verify-email',methods=['GET'],endpoint='ux_verification_pending')
    def ux_verification_pending():
        identity=str(request.args.get('identity') or '').strip()
        sent=request.args.get('sent')=='1'
        preview_token=str(request.args.get('preview_token') or '').strip() if _preview_enabled() else ''
        masked='your registered email'
        conn=_connect()
        try:
            user=_resolve(conn,identity)
            if user:
                masked=_mask_email(user['email'])
        finally:
            conn.close()
        return render_template('ux_verify_email_pending.html',identity=identity,masked_email=masked,sent=sent,preview_token=preview_token,preview_enabled=_preview_enabled())

    @app.route('/verify-email/resend',methods=['POST'],endpoint='ux_resend_verification')
    def ux_resend_verification():
        identity=str(request.form.get('identity') or '').strip()
        sent=False; preview_token=''
        if _required():
            conn=_connect()
            try:
                user=_resolve(conn,identity)
                if user and not _is_exempt(conn,user) and int(user['email_verified'] or 0)!=1:
                    last=_parse_dt(user['email_verification_sent_at'])
                    if not last or (_utcnow()-last).total_seconds()>=RESEND_COOLDOWN_SECONDS:
                        token=_make_token(conn,user['id']); conn.commit()
                        user=conn.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
                        sent=_send_verification(send_email,user,token)
                        if _preview_enabled() and not sent:
                            preview_token=token
            finally:
                conn.close()
        flash('If that account needs verification, a new verification link is ready.','success')
        kwargs={'identity':identity,'sent':'1' if sent else '0'}
        if preview_token:
            kwargs['preview_token']=preview_token
        return redirect(url_for('ux_verification_pending',**kwargs))

    app._ux_email_verification_installed=True
