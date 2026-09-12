from __future__ import annotations

import os
import sqlite3
from pathlib import Path

TEACHER_EMAIL='ux-teacher@scoremax.test'
TEACHER_USERNAME='ux-teacher'
TEACHER_SYSTEM_ID='TCH-900001'
TEACHER_PREVIEW_PASSWORD_HASH='pbkdf2:sha256:1000000$UOgOHDs3iDJFLDMJ$dec7ff77a321e0cc78508a14190e5f26f184ebfa010a86bd85532cdac61ed4a3'


def _db_path() -> Path:
    return Path(os.environ.get('SCOREMAX_DB','/tmp/scoremax-ux-vnext/state/scoremax.db'))


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(r[1]) for r in conn.execute(f'PRAGMA table_info({table})').fetchall()}


def _insert_dynamic(conn: sqlite3.Connection, table: str, values: dict) -> int:
    cols=_columns(conn,table)
    payload={k:v for k,v in values.items() if k in cols}
    names=','.join(payload)
    marks=','.join('?' for _ in payload)
    cur=conn.execute(f'INSERT INTO {table}({names}) VALUES({marks})',tuple(payload.values()))
    return int(cur.lastrowid)


def _update_dynamic(conn: sqlite3.Connection, table: str, row_id: int, values: dict) -> None:
    cols=_columns(conn,table)
    payload={k:v for k,v in values.items() if k in cols}
    if not payload:
        return
    clause=','.join(f'{k}=?' for k in payload)
    conn.execute(f'UPDATE {table} SET {clause} WHERE id=?',tuple(payload.values())+(row_id,))


def _ensure_teacher(conn: sqlite3.Connection) -> int:
    row=conn.execute("SELECT id FROM users WHERE lower(COALESCE(email,''))=?",(TEACHER_EMAIL,)).fetchone()
    values={
        'system_user_id':TEACHER_SYSTEM_ID,
        'role':'teacher',
        'full_name':'ScoreMax Teacher Preview',
        'email':TEACHER_EMAIL,
        'username':TEACHER_USERNAME,
        'password_hash':TEACHER_PREVIEW_PASSWORD_HASH,
        'province':'Punjab',
        'district':'Lahore',
        'board':'Punjab Board',
        'academic_level':'FSc Part 1',
        'subjects':'Biology,Chemistry,Physics',
        'institution_name':'ScoreMax Preview College',
        'account_status':'active',
        'login_provider':'password',
        'session_version':0,
        'own_referral_code':'TCH900001',
    }
    if row:
        teacher_id=int(row['id'])
        _update_dynamic(conn,'users',teacher_id,values)
        return teacher_id
    return _insert_dynamic(conn,'users',values)


def _ensure_preview_student(conn: sqlite3.Connection, suffix: int, full_name: str) -> int:
    email=f'ux-teacher-student-{suffix}@scoremax.test'
    row=conn.execute("SELECT id FROM users WHERE lower(COALESCE(email,''))=?",(email,)).fetchone()
    values={
        'system_user_id':f'STU-91{suffix:04d}',
        'role':'student',
        'full_name':full_name,
        'email':email,
        'username':f'ux-teacher-student-{suffix}',
        'province':'Punjab',
        'board':'Punjab Board',
        'academic_level':'FSc Part 1',
        'subjects':'Biology,Chemistry,Physics',
        'account_status':'active',
        'login_provider':'password',
        'session_version':0,
    }
    if row:
        student_id=int(row['id'])
        _update_dynamic(conn,'users',student_id,values)
        return student_id
    return _insert_dynamic(conn,'users',values)


def _ensure_class(conn: sqlite3.Connection, teacher_id: int, name: str, subject: str, join_code: str) -> int:
    row=conn.execute("SELECT id FROM classrooms WHERE teacher_id=? AND join_code=?",(teacher_id,join_code)).fetchone()
    values={'teacher_id':teacher_id,'institution_id':None,'name':name,'level':'FSc Part 1','subject':subject,'join_code':join_code}
    if row:
        cid=int(row['id']); _update_dynamic(conn,'classrooms',cid,values); return cid
    return _insert_dynamic(conn,'classrooms',values)


def ensure_teacher_preview() -> None:
    path=_db_path(); path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path); conn.row_factory=sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON'); conn.execute('PRAGMA busy_timeout=5000')
    try:
        # Safe on a genuinely fresh hosted database. scoremax_production calls this again after init().
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
            print('SCOREMAX_UX_TEACHER_PREVIEW_DEFERRED schema_ready=false',flush=True)
            return
        teacher_id=_ensure_teacher(conn)
        biology=_ensure_class(conn,teacher_id,'FSc Biology A','Biology','UXBIO26')
        chemistry=_ensure_class(conn,teacher_id,'FSc Chemistry A','Chemistry','UXCHEM26')
        students=[_ensure_preview_student(conn,1,'Ayesha Khan'),_ensure_preview_student(conn,2,'Hamza Ali'),_ensure_preview_student(conn,3,'Mariam Noor'),_ensure_preview_student(conn,4,'Usman Raza'),_ensure_preview_student(conn,5,'Zainab Ahmed'),_ensure_preview_student(conn,6,'Bilal Hussain')]
        for cid,members in ((biology,students[:4]),(chemistry,students[2:])):
            for idx,sid in enumerate(members,1):
                conn.execute('INSERT OR IGNORE INTO classroom_students(classroom_id,student_id,roll_no) VALUES(?,?,?)',(cid,sid,f'UX-{idx:02d}'))
        conn.commit()
        print('SCOREMAX_UX_TEACHER_PREVIEW_READY teacher=TCH-900001 classes=2 representative_students=6 staging_only=true',flush=True)
    finally:
        conn.close()
