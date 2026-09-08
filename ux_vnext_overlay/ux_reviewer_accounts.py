from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

REVIEWER_ACCOUNTS = (
    {'n':1,'system_user_id':'REVIEWER-01','username':'reviewer01','email':'reviewer01@scoremax.test','name':'ScoreMax Content Reviewer 01','env':'SCOREMAX_STAGING_REVIEWER_01_PASSWORD'},
    {'n':2,'system_user_id':'REVIEWER-02','username':'reviewer02','email':'reviewer02@scoremax.test','name':'ScoreMax Content Reviewer 02','env':'SCOREMAX_STAGING_REVIEWER_02_PASSWORD'},
    {'n':3,'system_user_id':'REVIEWER-03','username':'reviewer03','email':'reviewer03@scoremax.test','name':'ScoreMax Content Reviewer 03','env':'SCOREMAX_STAGING_REVIEWER_03_PASSWORD'},
    {'n':4,'system_user_id':'REVIEWER-04','username':'reviewer04','email':'reviewer04@scoremax.test','name':'ScoreMax Content Reviewer 04','env':'SCOREMAX_STAGING_REVIEWER_04_PASSWORD'},
    {'n':5,'system_user_id':'REVIEWER-05','username':'reviewer05','email':'reviewer05@scoremax.test','name':'ScoreMax Content Reviewer 05','env':'SCOREMAX_STAGING_REVIEWER_05_PASSWORD'},
)


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


def ensure_reviewer_accounts() -> None:
    conn=_connect()
    try:
        if 'users' not in {r['name'] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}:
            raise RuntimeError('SCOREMAX_USERS_TABLE_MISSING_BEFORE_REVIEWER_SEED')
        if 'content_reviewer_enabled' not in _cols(conn,'users'):
            conn.execute('ALTER TABLE users ADD COLUMN content_reviewer_enabled INTEGER DEFAULT 0')
        for account in REVIEWER_ACCOUNTS:
            password=os.environ.get(account['env'],'').strip()
            if not password:
                continue
            identity=(account['email'].lower(),account['username'].lower(),account['system_user_id'].lower())
            row=conn.execute("""SELECT id FROM users
              WHERE lower(COALESCE(email,''))=? OR lower(COALESCE(username,''))=? OR lower(COALESCE(system_user_id,''))=?
              ORDER BY id LIMIT 1""",identity).fetchone()
            ph=generate_password_hash(password)
            values=(account['system_user_id'],account['username'],account['email'],account['name'],ph)
            if row:
                conn.execute("""UPDATE users SET system_user_id=?,username=?,email=?,full_name=?,password_hash=?,role='student',
                  province='Punjab',board='Punjab Board',academic_level='FSc Part 1',subjects='Biology,Chemistry,Physics',
                  account_status='active',active_programme='FSc Part 1',login_provider='password',content_reviewer_enabled=1
                  WHERE id=?""",values+(row['id'],))
            else:
                conn.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,province,board,academic_level,subjects,
                  account_status,active_programme,login_provider,content_reviewer_enabled)
                  VALUES(?,'student',?,?,?,?,?,?,?,'Biology,Chemistry,Physics','active','FSc Part 1','password',1)""",
                  (account['system_user_id'],account['name'],account['email'],account['username'],ph,'Punjab','Punjab Board','FSc Part 1'))
        conn.commit()
    finally:
        conn.close()
