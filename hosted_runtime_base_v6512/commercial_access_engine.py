"""Programme/subject package entitlements for ScoreMax V6.2.8.

Coverage (which subjects) and access tier (how deep) are deliberately separate.
This module is provider-neutral and does not process card payments.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


def _text(v: Any) -> str:
    return str(v or '').strip()


def _json(v: Any, default):
    try:
        parsed=json.loads(v) if isinstance(v,str) else v
        return parsed if isinstance(parsed,type(default)) else default
    except Exception:
        return default


def init_schema(c) -> None:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS coverage_packages(
      id INTEGER PRIMARY KEY,code TEXT UNIQUE NOT NULL,name TEXT NOT NULL,programme TEXT NOT NULL,
      description TEXT DEFAULT '',coverage_type TEXT NOT NULL DEFAULT 'SUBJECTS',subjects_json TEXT DEFAULT '[]',
      price_minor INTEGER,currency TEXT DEFAULT 'PKR',billing_period TEXT DEFAULT 'monthly',status TEXT DEFAULT 'ACTIVE',
      sort_order INTEGER DEFAULT 0,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS student_package_entitlements(
      id INTEGER PRIMARY KEY,student_id INTEGER NOT NULL,coverage_package_id INTEGER NOT NULL,access_plan_code TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'ACTIVE',starts_at TEXT NOT NULL,ends_at TEXT,source TEXT DEFAULT 'manual',notes TEXT DEFAULT '',
      created_by INTEGER,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS package_entitlement_history(
      id INTEGER PRIMARY KEY,student_id INTEGER NOT NULL,entitlement_id INTEGER,event_type TEXT NOT NULL,
      previous_json TEXT DEFAULT '{}',new_json TEXT DEFAULT '{}',actor_user_id INTEGER,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS checkout_requests(
      id INTEGER PRIMARY KEY,student_id INTEGER NOT NULL,coverage_package_id INTEGER NOT NULL,access_plan_code TEXT NOT NULL,
      status TEXT DEFAULT 'PENDING_GATEWAY',requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,notes TEXT DEFAULT '');
    CREATE INDEX IF NOT EXISTS idx_student_package_entitlements ON student_package_entitlements(student_id,status,ends_at);
    CREATE INDEX IF NOT EXISTS idx_coverage_packages_programme ON coverage_packages(programme,status,sort_order);
    ''')
    columns={r['name'] for r in c.execute('PRAGMA table_info(subscriptions)').fetchall()}
    if 'coverage_package_id' not in columns:
        c.execute('ALTER TABLE subscriptions ADD COLUMN coverage_package_id INTEGER')
    seeds=[
      ('fsc1_biology','Biology only','FSc Part 1','Full access to Biology within the selected access level.','SUBJECTS',['Biology'],79900,'PKR','monthly','ACTIVE',10),
      ('fsc1_two_subjects','Choose two FSc Part 1 subjects','FSc Part 1','A flexible two-subject package.','SELECT_N',[],129900,'PKR','monthly','ACTIVE',20),
      ('fsc1_science_bundle','Biology, Chemistry and Physics','FSc Part 1','The core science bundle.','SUBJECTS',['Biology','Chemistry','Physics'],169900,'PKR','monthly','ACTIVE',30),
      ('fsc1_full','All currently available FSc Part 1 subjects','FSc Part 1','Every subject released for this programme.','ALL_AVAILABLE',[],199900,'PKR','monthly','ACTIVE',40),
      ('grade9_full','Grade 9 — all available subjects','Grade 9','All Grade 9 subjects as they become available.','ALL_AVAILABLE',[],None,'PKR','monthly','COMING_SOON',50),
      ('grade10_full','Grade 10 — all available subjects','Grade 10','All Grade 10 subjects as they become available.','ALL_AVAILABLE',[],None,'PKR','monthly','COMING_SOON',60),
      ('fsc2_full','FSc Part 2 — all available subjects','FSc Part 2','All FSc Part 2 subjects as they become available.','ALL_AVAILABLE',[],None,'PKR','monthly','COMING_SOON',70),
      ('mdcat_full','MDCAT — complete curriculum','MDCAT','Complete released MDCAT curriculum.','ALL_AVAILABLE',[],None,'PKR','monthly','COMING_SOON',80),
    ]
    for row in seeds:
        c.execute('''INSERT INTO coverage_packages(code,name,programme,description,coverage_type,subjects_json,price_minor,currency,billing_period,status,sort_order)
          VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET name=excluded.name,programme=excluded.programme,
          description=excluded.description,coverage_type=excluded.coverage_type,subjects_json=excluded.subjects_json,
          status=excluded.status,sort_order=excluded.sort_order''',
          (row[0],row[1],row[2],row[3],row[4],json.dumps(row[5]),row[6],row[7],row[8],row[9],row[10]))


def package_rows(c, programme: str='', include_coming: bool=True):
    clauses=[]; params=[]
    if programme:
        clauses.append('lower(programme)=lower(?)'); params.append(programme)
    if not include_coming:
        clauses.append("status='ACTIVE'")
    where=(' WHERE '+ ' AND '.join(clauses)) if clauses else ''
    rows=c.execute(f'SELECT * FROM coverage_packages{where} ORDER BY sort_order,name',params).fetchall()
    out=[]
    for r in rows:
        d=dict(r); d['subjects']=_json(r['subjects_json'],[]); out.append(d)
    return out


def active_entitlement(c, student_id: int):
    today=date.today().isoformat()
    row=c.execute('''SELECT spe.*,cp.code coverage_code,cp.name coverage_name,cp.programme,cp.coverage_type,cp.subjects_json
      FROM student_package_entitlements spe JOIN coverage_packages cp ON cp.id=spe.coverage_package_id
      WHERE spe.student_id=? AND spe.status='ACTIVE' AND (spe.ends_at IS NULL OR spe.ends_at='' OR spe.ends_at>=?)
      ORDER BY spe.id DESC LIMIT 1''',(student_id,today)).fetchone()
    if not row: return None
    d=dict(row); d['subjects']=_json(row['subjects_json'],[]); return d


def programme_subjects(c, programme: str) -> list[str]:
    rows=c.execute("""SELECT DISTINCT subject FROM questions WHERE COALESCE(subject,'')<>'' AND
      (lower(COALESCE(programme,''))=lower(?) OR lower(COALESCE(qualification,''))=lower(?))
      ORDER BY subject""",(programme,programme)).fetchall()
    return [r['subject'] for r in rows]


def effective_coverage(c, student_id: int, programme: str, *, commercial_gates_enabled: bool=False) -> dict:
    ent=active_entitlement(c,student_id)
    available=programme_subjects(c,programme)
    if ent and _text(ent.get('programme')).casefold()==_text(programme).casefold():
        if ent['coverage_type']=='ALL_AVAILABLE': included=available
        else: included=list(ent.get('subjects') or [])
        return {'source':'ENTITLEMENT','entitlement':ent,'included_subjects':included,'access_plan_code':ent['access_plan_code']}
    # Preserve safe local-pilot access while keeping the package architecture visible.
    if not commercial_gates_enabled:
        return {'source':'PILOT_ALL_AVAILABLE','entitlement':None,'included_subjects':available,'access_plan_code':''}
    # Commercial default: the first currently available subject is the free starter subject.
    return {'source':'FREE_STARTER','entitlement':None,'included_subjects':available[:1],'access_plan_code':'free_access'}


def subject_state(c, student_id: int, programme: str, subject: str, *, available: bool,
                  commercial_gates_enabled: bool=False) -> str:
    if not available: return 'COMING_SOON'
    coverage=effective_coverage(c,student_id,programme,commercial_gates_enabled=commercial_gates_enabled)
    included={_text(x).casefold() for x in coverage['included_subjects']}
    return 'INCLUDED' if _text(subject).casefold() in included else 'LOCKED'


def assign_entitlement(c, *, student_id: int, coverage_package_id: int, access_plan_code: str,
                       starts_at: str, ends_at: str='', source: str='manual', notes: str='', actor_user_id: int|None=None) -> int:
    package=c.execute('SELECT * FROM coverage_packages WHERE id=?',(coverage_package_id,)).fetchone()
    if not package: raise ValueError('Coverage package not found.')
    if package['status']!='ACTIVE': raise ValueError('Only an active package can be assigned.')
    plan=c.execute('SELECT * FROM plans WHERE code=? AND audience=\'student\' AND active=1',(access_plan_code,)).fetchone()
    if not plan: raise ValueError('Student access level not found.')
    previous=active_entitlement(c,student_id)
    c.execute("UPDATE student_package_entitlements SET status='REPLACED',updated_at=CURRENT_TIMESTAMP WHERE student_id=? AND status='ACTIVE'",(student_id,))
    cur=c.execute('''INSERT INTO student_package_entitlements(student_id,coverage_package_id,access_plan_code,status,starts_at,ends_at,source,notes,created_by)
      VALUES(?,?,?,'ACTIVE',?,?,?,?,?)''',(student_id,coverage_package_id,access_plan_code,starts_at,ends_at,source,notes,actor_user_id))
    new={'coverage_package_id':coverage_package_id,'access_plan_code':access_plan_code,'starts_at':starts_at,'ends_at':ends_at,'source':source}
    c.execute('''INSERT INTO package_entitlement_history(student_id,entitlement_id,event_type,previous_json,new_json,actor_user_id)
      VALUES(?,?, 'ENTITLEMENT_ASSIGNED',?,?,?)''',(student_id,cur.lastrowid,json.dumps(previous or {}),json.dumps(new),actor_user_id))
    return cur.lastrowid


def request_checkout(c, *, student_id: int, coverage_package_id: int, access_plan_code: str) -> int:
    package=c.execute("SELECT id FROM coverage_packages WHERE id=? AND status='ACTIVE'",(coverage_package_id,)).fetchone()
    plan=c.execute("SELECT code FROM plans WHERE code=? AND audience='student' AND active=1",(access_plan_code,)).fetchone()
    if not package or not plan: raise ValueError('Choose an available package and access level.')
    cur=c.execute('INSERT INTO checkout_requests(student_id,coverage_package_id,access_plan_code,status) VALUES(?,?,?,\'PENDING_GATEWAY\')',
                  (student_id,coverage_package_id,access_plan_code))
    return cur.lastrowid
