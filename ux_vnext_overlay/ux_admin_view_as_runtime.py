from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from flask import abort, flash, redirect, render_template, request, session, url_for

POLICY='SCOREMAX-ADMIN-VIEW-AS-V1'
PREVIEW_STUDENT_EMAIL='ux-teacher-student-1@scoremax.test'
PREVIEW_TEACHER_EMAIL='ux-teacher@scoremax.test'
PREVIEW_STUDENT_GROUP='ux-teacher-student-%@scoremax.test'

PROGRAMMES={
    'fsc1':{
        'label':'FSc Year 1',
        'academic_level':'FSc Part 1',
        'active_programme':'FSc Part 1',
        'class_level':'FSc Part 1',
        'subjects':'Biology,Chemistry,Physics',
    },
    'fsc2':{
        'label':'FSc Year 2',
        'academic_level':'FSc Part 2',
        'active_programme':'FSc Part 2',
        'class_level':'FSc Part 2',
        'subjects':'Biology,Chemistry,Physics',
    },
    'mdcat':{
        'label':'MDCAT',
        # Keep the learner's underlying school year distinct from the active admission route.
        'academic_level':'FSc Part 2',
        'active_programme':'MDCAT',
        'class_level':'MDCAT',
        'subjects':'Biology,Chemistry,Physics,English,Logical Reasoning',
    },
}


def _db_path() -> Path:
    return Path(os.environ.get('SCOREMAX_DB','/tmp/scoremax-ux-vnext/state/scoremax.db'))


def _connect() -> sqlite3.Connection:
    conn=sqlite3.connect(_db_path())
    conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def _update_user(conn: sqlite3.Connection, user_id: int, values: dict) -> None:
    cols=_columns(conn,'users')
    payload={k:v for k,v in values.items() if k in cols}
    if not payload:
        return
    conn.execute(
        'UPDATE users SET '+','.join(f'{k}=?' for k in payload)+' WHERE id=?',
        tuple(payload.values())+(int(user_id),),
    )


def _preview_user(conn: sqlite3.Connection, role: str):
    email=PREVIEW_STUDENT_EMAIL if role=='student' else PREVIEW_TEACHER_EMAIL
    row=conn.execute(
        "SELECT * FROM users WHERE lower(COALESCE(email,''))=lower(?) AND role=?",
        (email,role),
    ).fetchone()
    if not row:
        raise RuntimeError(f'{role}_preview_fixture_missing')
    return row


def _configure_preview_fixture(conn: sqlite3.Connection, role: str, programme_code: str):
    profile=PROGRAMMES.get(programme_code)
    if not profile:
        raise ValueError('unsupported_programme')
    preview=_preview_user(conn,role)
    common={
        'province':'Punjab',
        'board':'Punjab Board',
        'academic_level':profile['academic_level'],
        'subjects':profile['subjects'],
        'active_programme':profile['active_programme'],
        'account_status':'active',
    }
    _update_user(conn,int(preview['id']),common)

    if role=='teacher':
        # Existing synthetic teacher classes are presentation fixtures. Re-contextualise
        # those fixtures rather than creating more accounts/classes in the live database.
        class_cols=_columns(conn,'classrooms')
        rows=conn.execute('SELECT id,subject FROM classrooms WHERE teacher_id=? ORDER BY id',(int(preview['id']),)).fetchall()
        for row in rows:
            subject=str(row['subject'] or 'Class')
            values={
                'level':profile['class_level'],
                'name':f"{profile['label']} {subject} A",
            }
            payload={k:v for k,v in values.items() if k in class_cols}
            if payload:
                conn.execute(
                    'UPDATE classrooms SET '+','.join(f'{k}=?' for k in payload)+' WHERE id=?',
                    tuple(payload.values())+(int(row['id']),),
                )
        # Keep the existing representative synthetic students coherent with the teacher fixture.
        synthetic=conn.execute(
            "SELECT id FROM users WHERE lower(COALESCE(email,'')) LIKE 'ux-teacher-student-%@scoremax.test'"
        ).fetchall()
        for s in synthetic:
            _update_user(conn,int(s['id']),common)

    conn.commit()
    return conn.execute('SELECT * FROM users WHERE id=?',(int(preview['id']),)).fetchone()


def _restore_admin_session():
    origin_id=session.get('admin_view_as_origin_user_id')
    token=session.get('_csrf_token')
    if not origin_id:
        session.clear()
        return redirect(url_for('login'))
    with _connect() as conn:
        admin=conn.execute(
            "SELECT id,role,full_name,COALESCE(session_version,0) session_version,account_status FROM users WHERE id=?",
            (int(origin_id),),
        ).fetchone()
    if not admin or admin['role']!='admin' or (admin['account_status'] and admin['account_status']!='active'):
        session.clear()
        return redirect(url_for('login'))
    session.clear()
    if token:
        session['_csrf_token']=token
    session.update(
        user_id=int(admin['id']),role='admin',full_name=admin['full_name'],
        session_version=int(admin['session_version'] or 0),
    )
    flash('Admin preview ended. You are back in ScoreMax Admin.','success')
    return redirect(url_for('admin_view_as'))


def _view_as_home():
    if session.get('role')!='admin' or session.get('admin_view_as_mode'):
        abort(403)
    profiles=[]
    for role in ('student','teacher'):
        for code,p in PROGRAMMES.items():
            profiles.append({
                'key':f'{role}:{code}',
                'role':role,
                'role_label':'Student' if role=='student' else 'Teacher',
                'programme_code':code,
                'programme_label':p['label'],
            })
    return render_template('ux_admin_view_as.html',profiles=profiles,policy=POLICY)


def _view_as_start():
    if session.get('role')!='admin' or session.get('admin_view_as_mode'):
        abort(403)
    key=str(request.form.get('profile') or '').strip().lower()
    if ':' not in key:
        abort(400,description='Choose a preview role and programme.')
    role,programme_code=key.split(':',1)
    if role not in {'student','teacher'} or programme_code not in PROGRAMMES:
        abort(400,description='Unsupported preview profile.')

    origin_id=int(session['user_id'])
    token=session.get('_csrf_token')
    with _connect() as conn:
        origin=conn.execute(
            "SELECT id,role,account_status FROM users WHERE id=?",
            (origin_id,),
        ).fetchone()
        if not origin or origin['role']!='admin' or (origin['account_status'] and origin['account_status']!='active'):
            abort(403)
        preview=_configure_preview_fixture(conn,role,programme_code)

    label=f"{'Student' if role=='student' else 'Teacher'} · {PROGRAMMES[programme_code]['label']}"
    session.clear()
    if token:
        session['_csrf_token']=token
    session.update(
        user_id=int(preview['id']),role=role,full_name=preview['full_name'],
        session_version=int(preview['session_version'] or 0),
        admin_view_as_mode=1,
        admin_view_as_origin_user_id=origin_id,
        admin_view_as_profile=key,
        admin_view_as_label=label,
        admin_view_as_policy=POLICY,
    )
    print(f'SCOREMAX_ADMIN_VIEW_AS_ENTER role={role} programme={programme_code} preview_user_id={int(preview["id"])}',flush=True)
    return redirect(url_for('student_dashboard' if role=='student' else 'teacher_dashboard'))


def _view_as_exit():
    if not session.get('admin_view_as_mode'):
        if session.get('role')=='admin':
            return redirect(url_for('admin_view_as'))
        abort(403)
    print('SCOREMAX_ADMIN_VIEW_AS_EXIT',flush=True)
    return _restore_admin_session()


def install_admin_view_as(app) -> None:
    # The preview fixtures must already exist from ux_teacher_preview startup.
    with _connect() as conn:
        student=_preview_user(conn,'student')
        teacher=_preview_user(conn,'teacher')
        if int(student['id'])==int(teacher['id']):
            raise RuntimeError('preview_role_identity_collision')

    app.add_url_rule('/admin/view-as','admin_view_as',_view_as_home,methods=['GET'])
    app.add_url_rule('/admin/view-as/start','admin_view_as_start',_view_as_start,methods=['POST'])
    app.add_url_rule('/admin/view-as/exit','admin_view_as_exit',_view_as_exit,methods=['GET','POST'])

    @app.before_request
    def _admin_view_as_safety_fence():
        if not session.get('admin_view_as_mode'):
            return None
        # Exit always remains available. Treat Logout as Exit so the admin cannot
        # accidentally lose the originating admin session while inspecting a persona.
        if request.endpoint=='admin_view_as_exit':
            return None
        if request.endpoint=='logout':
            return _restore_admin_session()
        # Navigation preview is intentionally read-only. GET rendering may use the
        # dedicated synthetic fixture, but no learner/teacher production action is written.
        if request.method not in {'GET','HEAD','OPTIONS'}:
            flash('Admin View As is read-only. Exit preview to perform real actions.','info')
            return redirect(url_for('dashboard'))
        return None

    print(
        'SCOREMAX_ADMIN_VIEW_AS_RUNTIME_PASS roles=student,teacher '
        'programmes=fsc1,fsc2,mdcat synthetic_fixtures_reused=true '
        'real_user_impersonation=false read_only=true reversible=true',
        flush=True,
    )
