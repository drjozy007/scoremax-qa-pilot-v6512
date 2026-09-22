"""Create-only preview fixtures; existing access/revocation state is authoritative.

The historical admin preview is never created, reactivated or password-reset here.
Its retirement is a separate owner-authenticated operation below, not a startup side effect.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

TEACHER_EMAIL = 'ux-teacher@scoremax.test'
TEACHER_USERNAME = 'ux-teacher'
TEACHER_SYSTEM_ID = 'TCH-900001'
ADMIN_EMAIL = 'ux-admin@scoremax.test'
ADMIN_USERNAME = 'ux-admin'
ADMIN_SYSTEM_ID = 'ADM-900001'


def _db_path() -> Path:
    return Path(os.environ.get('SCOREMAX_DB', '/tmp/scoremax-ux-vnext/state/scoremax.db'))


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def _insert_dynamic(conn: sqlite3.Connection, table: str, values: dict) -> int:
    payload = {k: v for k, v in values.items() if k in _columns(conn, table)}
    cur = conn.execute(f'INSERT INTO {table}({",".join(payload)}) VALUES({",".join("?" for _ in payload)})', tuple(payload.values()))
    return int(cur.lastrowid)


def resolve_preview_identity(conn, email: str, username: str, system_id: str, role: str):
    """All three reserved identifiers must agree on exactly one record, or no record.

    Cross-field login collisions also fail closed. Never turn a matching email on an
    unrelated account into a privileged/fixed test identity.
    """
    identity = (email.lower(), username.lower(), system_id.lower())
    rows = conn.execute('''SELECT * FROM users WHERE
      lower(COALESCE(email,'')) IN (?,?,?) OR
      lower(COALESCE(username,'')) IN (?,?,?) OR
      lower(COALESCE(system_user_id,'')) IN (?,?,?)''', identity * 3).fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        raise RuntimeError('PREVIEW_IDENTITY_AMBIGUOUS')
    row = rows[0]
    actual = tuple(str(row[k] or '').lower() for k in ('email', 'username', 'system_user_id'))
    if actual != identity or str(row['role']) != role:
        raise RuntimeError('PREVIEW_IDENTITY_MISMATCH')
    return row


def _ensure_user(conn, *, email: str, username: str, system_id: str, role: str, name: str) -> int:
    row = resolve_preview_identity(conn, email, username, system_id, role)
    if row:
        # Password, status, role, programme and session-version are NEVER reset by boot.
        return int(row['id'])
    return _insert_dynamic(conn, 'users', {
        'system_user_id': system_id, 'role': role, 'full_name': name,
        'email': email, 'username': username, 'password_hash': '',
        'province': 'Punjab', 'district': 'Lahore', 'board': 'Punjab Board',
        'academic_level': 'FSc Part 1', 'active_programme': 'FSc Part 1',
        'subjects': 'Biology,Chemistry,Physics', 'institution_name': 'ScoreMax Preview College',
        'account_status': 'active', 'login_provider': 'preview', 'session_version': 0,
    })


def _ensure_teacher(conn) -> int:
    return _ensure_user(conn, email=TEACHER_EMAIL, username=TEACHER_USERNAME,
                        system_id=TEACHER_SYSTEM_ID, role='teacher', name='ScoreMax Teacher Preview')


def _ensure_preview_student(conn, suffix: int, name: str) -> int:
    return _ensure_user(conn, email=f'ux-teacher-student-{suffix}@scoremax.test',
                        username=f'ux-teacher-student-{suffix}', system_id=f'STU-91{suffix:04d}',
                        role='student', name=name)


def _ensure_class(conn, teacher_id: int, name: str, subject: str, join_code: str) -> tuple[int, bool]:
    rows = conn.execute('SELECT * FROM classrooms WHERE lower(join_code)=lower(?)', (join_code,)).fetchall()
    if rows:
        if len(rows) != 1 or int(rows[0]['teacher_id']) != teacher_id:
            raise RuntimeError('PREVIEW_CLASS_IDENTITY_CONFLICT')
        return int(rows[0]['id']), False
    return _insert_dynamic(conn, 'classrooms', {
        'teacher_id': teacher_id, 'institution_id': None, 'name': name,
        'level': 'FSc Part 1', 'subject': subject, 'join_code': join_code,
    }), True


def ensure_teacher_preview() -> None:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=5000')
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
            print('SCOREMAX_UX_TEACHER_PREVIEW_DEFERRED schema_ready=false', flush=True)
            return
        conn.execute('BEGIN IMMEDIATE')
        teacher_id = _ensure_teacher(conn)
        names = ('Ayesha Khan', 'Hamza Ali', 'Mariam Noor', 'Usman Raza', 'Zainab Ahmed', 'Bilal Hussain')
        students = [_ensure_preview_student(conn, i, name) for i, name in enumerate(names, 1)]
        for name, subject, code, members in (
            ('FSc Biology A', 'Biology', 'UXBIO26', students[:4]),
            ('FSc Chemistry A', 'Chemistry', 'UXCHEM26', students[2:]),
        ):
            cid, created = _ensure_class(conn, teacher_id, name, subject, code)
            if created:
                for idx, sid in enumerate(members, 1):
                    conn.execute('INSERT INTO classroom_students(classroom_id,student_id,roll_no) VALUES(?,?,?)', (cid, sid, f'UX-{idx:02d}'))
        conn.commit()
        print('SCOREMAX_UX_TEACHER_PREVIEW_READY create_only=true admin_seed=false credentials_embedded=false revocations_preserved=true', flush=True)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def retire_legacy_admin_preview(scoremax, *, owner_identity: str, owner_password: str) -> dict:
    """Explicit maintenance operation, never called by boot or exposed as a new route.

    Verify the existing independent owner credential via the native login resolver before
    changing ONLY the exact legacy preview identity. Never rotate or disable the owner.
    No credentials, hashes, reset tokens, or database rows are returned/logged.
    """
    conn = scoremax.db()
    try:
        conn.execute('BEGIN IMMEDIATE')
        legacy = resolve_preview_identity(conn, ADMIN_EMAIL, ADMIN_USERNAME, ADMIN_SYSTEM_ID, 'admin')
        owner = scoremax.resolve_login_user(conn, owner_identity)
        if (not owner or owner['role'] != 'admin' or owner['account_status'] not in (None, '', 'active')
                or (legacy and int(owner['id']) == int(legacy['id']))
                or not str(owner['password_hash'] or '')
                or not scoremax.check_password_hash(owner['password_hash'], owner_password)):
            raise RuntimeError('INDEPENDENT_OWNER_ACCESS_VERIFICATION_REQUIRED')
        # A second alias with the same credential is not an independent recovery path.
        if legacy and legacy['password_hash'] and scoremax.check_password_hash(legacy['password_hash'], owner_password):
            raise RuntimeError('OWNER_CREDENTIAL_NOT_INDEPENDENT')
        teacher = resolve_preview_identity(conn, TEACHER_EMAIL, TEACHER_USERNAME, TEACHER_SYSTEM_ID, 'teacher')
        if teacher and teacher['password_hash'] and scoremax.check_password_hash(teacher['password_hash'], owner_password):
            raise RuntimeError('OWNER_CREDENTIAL_NOT_INDEPENDENT')
        if not legacy:
            conn.rollback()
            return {'status': 'NOT_PRESENT', 'owner_access_verified': True, 'retired': 0}
        done = legacy['account_status'] == 'disabled' and not legacy['password_hash'] and legacy['login_provider'] == 'preview'
        if done:
            conn.rollback()
            return {'status': 'ALREADY_RETIRED', 'owner_access_verified': True, 'retired': 0}
        conn.execute("""UPDATE users SET account_status='disabled',password_hash='',login_provider='preview',
          session_version=COALESCE(session_version,0)+1 WHERE id=?""", (int(legacy['id']),))
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='password_reset_tokens'").fetchone():
            conn.execute("UPDATE password_reset_tokens SET used_at=? WHERE user_id=? AND COALESCE(used_at,'')=''",
                         (datetime.now().isoformat(timespec='seconds'), int(legacy['id'])))
        conn.commit()
        return {'status': 'RETIRED', 'owner_access_verified': True, 'retired': 1, 'owner_changed': False}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
