from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from pathlib import Path

ROOT=Path(os.environ.get('SCOREMAX_PERSISTENT_ROOT','/data/scoremax')).resolve()
DB=Path(os.environ.get('SCOREMAX_DB',str(ROOT/'state'/'scoremax.db'))).resolve()
BACKUP=Path(os.environ.get('SCOREMAX_BACKUP_DIR',str(ROOT/'backup'))).resolve()
INTAKE=Path(os.environ.get('SCOREMAX_CONTENT_INTAKE_DIR',str(ROOT/'intake'))).resolve()
MOUNT=Path(os.environ.get('SCOREMAX_EXPECTED_PERSISTENT_MOUNT','/data')).resolve()
SENTINEL=MOUNT/'.scoremax_persistent_storage_identity.json'
PROBE_DB=ROOT/'state'/'storage_durability_probe.sqlite3'
BASELINE_BACKUP=BACKUP/'scoremax_preimport_empty_baseline.sqlite3'
APPROVED_REVIEWERS={f'REVIEWER-{i:02d}' for i in range(1,6)}


def fail(msg: str) -> None:
    print('SCOREMAX_PERSISTENT_STORAGE_FAIL '+msg,flush=True)
    raise SystemExit(78)


def is_mount(path: Path) -> bool:
    try:
        if path.is_mount(): return True
    except Exception:
        pass
    try:
        mounts=Path('/proc/mounts').read_text(encoding='utf-8',errors='replace').splitlines()
        target=str(path)
        for line in mounts:
            parts=line.split()
            if len(parts)>=2 and parts[1].replace('\\040',' ')==target:
                return True
    except Exception:
        pass
    return False


def check_sqlite(path: Path) -> tuple[str,int]:
    try:
        c=sqlite3.connect(path,timeout=30)
        integ=c.execute('PRAGMA integrity_check').fetchone()[0]
        fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
        c.close()
    except Exception as exc:
        fail(f'sqlite_check_failed path={path} error={type(exc).__name__}')
    if integ!='ok': fail(f'sqlite_integrity_failed path={path} result={integ}')
    if fk: fail(f'sqlite_foreign_key_failed path={path} count={fk}')
    return integ,fk


def durability_probe() -> int:
    c=sqlite3.connect(PROBE_DB,timeout=30)
    c.execute('CREATE TABLE IF NOT EXISTS durability_probe(id INTEGER PRIMARY KEY CHECK(id=1), runs INTEGER NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)')
    row=c.execute('SELECT runs FROM durability_probe WHERE id=1').fetchone()
    if row is None:
        runs=1
        c.execute('INSERT INTO durability_probe(id,runs) VALUES(1,1)')
    else:
        runs=int(row[0])+1
        c.execute('UPDATE durability_probe SET runs=?,updated_at=CURRENT_TIMESTAMP WHERE id=1',(runs,))
    c.commit()
    integ=c.execute('PRAGMA integrity_check').fetchone()[0]
    fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
    c.close()
    if integ!='ok' or fk: fail(f'durability_probe_integrity_failed integrity={integ} fk={fk}')
    return runs


def _table(c: sqlite3.Connection, name: str) -> bool:
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())


def _cols(c: sqlite3.Connection, name: str) -> set[str]:
    return {r[1] for r in c.execute(f'PRAGMA table_info({name})').fetchall()} if _table(c,name) else set()


def _count(c: sqlite3.Connection, name: str) -> int:
    return int(c.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]) if _table(c,name) else 0


def _preimport_counts(c: sqlite3.Connection) -> dict[str,int]:
    names=('questions','curriculum','question_families','chapter_catalogue','coverage_packages')
    return {name:_count(c,name) for name in names}


def _reviewer_state(c: sqlite3.Connection) -> dict[str,object]:
    if not _table(c,'users'):
        return {'count':0,'ids':[],'approved':True}
    rows=c.execute("""SELECT COALESCE(system_user_id,'') system_user_id,COALESCE(role,'') role,
        COALESCE(username,'') username,COALESCE(content_reviewer_enabled,0) enabled
        FROM users WHERE lower(COALESCE(username,'')) LIKE '%reviewer%'
        OR lower(COALESCE(email,'')) LIKE '%reviewer%'
        OR COALESCE(system_user_id,'') LIKE 'REVIEWER-%'
        OR COALESCE(system_user_id,'')='CRV-900001' ORDER BY system_user_id""").fetchall()
    ids=[str(r[0]) for r in rows]
    if not rows:
        return {'count':0,'ids':[],'approved':True}
    approved=(set(ids)==APPROVED_REVIEWERS and len(rows)==5 and all(str(r[1])=='student' and int(r[3] or 0)==1 for r in rows))
    return {'count':len(rows),'ids':ids,'approved':approved}


def qualify_preimport_database() -> dict[str,object]:
    if not DB.exists():
        return {'state':'absent'}
    c=sqlite3.connect(DB,timeout=30)
    try:
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
        fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
        counts=_preimport_counts(c)
        priced_plans=0
        if _table(c,'plans'):
            priced_plans=int(c.execute('SELECT COUNT(*) FROM plans WHERE COALESCE(price_minor,0)>0').fetchone()[0])
        reviewer_state=_reviewer_state(c)
        if integrity!='ok' or fk: fail(f'preimport_db_integrity_failed integrity={integrity} fk={fk}')
        governed={k:counts[k] for k in ('questions','curriculum','question_families','chapter_catalogue')}
        if any(governed.values()): fail('preimport_governed_substrate_not_empty='+json.dumps(governed,sort_keys=True))
        if counts['coverage_packages']!=0: fail(f'preimport_commercial_catalogue_not_empty count={counts["coverage_packages"]}')
        if priced_plans!=0: fail(f'preimport_seeded_plan_prices_present count={priced_plans}')
        if not reviewer_state['approved']: fail('preimport_unapproved_reviewer_state='+json.dumps(reviewer_state,sort_keys=True))

        tmp=BASELINE_BACKUP.with_suffix('.tmp')
        if tmp.exists(): tmp.unlink()
        dest=sqlite3.connect(tmp)
        try:
            c.backup(dest)
            dest.commit()
        finally:
            dest.close()
        os.replace(tmp,BASELINE_BACKUP)
    finally:
        c.close()

    backup_integrity,backup_fk=check_sqlite(BASELINE_BACKUP)
    with tempfile.TemporaryDirectory(prefix='scoremax-preimport-restore-') as td:
        restored=Path(td)/'restored.sqlite3'
        src=sqlite3.connect(BASELINE_BACKUP,timeout=30)
        dst=sqlite3.connect(restored,timeout=30)
        try:
            src.backup(dst); dst.commit()
        finally:
            dst.close(); src.close()
        restore_integrity,restore_fk=check_sqlite(restored)
        rc=sqlite3.connect(restored,timeout=30)
        try:
            restored_counts=_preimport_counts(rc)
            restored_priced=int(rc.execute('SELECT COUNT(*) FROM plans WHERE COALESCE(price_minor,0)>0').fetchone()[0]) if _table(rc,'plans') else 0
            restored_reviewers=_reviewer_state(rc)
        finally:
            rc.close()
        if restored_counts!=counts or restored_priced!=priced_plans or restored_reviewers!=reviewer_state:
            fail('preimport_restore_semantic_mismatch')

    digest=hashlib.sha256(BASELINE_BACKUP.read_bytes()).hexdigest()
    return {
        'state':'qualified','integrity':integrity,'fk':fk,'counts':counts,
        'priced_plans':priced_plans,'reviewer_state':reviewer_state,
        'backup':str(BASELINE_BACKUP),'backup_sha256':digest,
        'backup_integrity':backup_integrity,'backup_fk':backup_fk,
        'restore_integrity':restore_integrity,'restore_fk':restore_fk,
    }


def main() -> None:
    if not MOUNT.exists() or not MOUNT.is_dir(): fail(f'mount_missing={MOUNT}')
    if not is_mount(MOUNT): fail(f'not_a_real_mount={MOUNT}')
    for p in (ROOT,DB.parent,BACKUP,INTAKE,PROBE_DB.parent): p.mkdir(parents=True,exist_ok=True)
    if MOUNT not in ROOT.parents and ROOT!=MOUNT: fail('persistent_root_outside_mount')
    if MOUNT not in DB.parents: fail('db_outside_mount')
    if MOUNT not in BACKUP.parents: fail('backup_outside_mount')
    if MOUNT not in INTAKE.parents: fail('intake_outside_mount')

    if SENTINEL.exists():
        payload=json.loads(SENTINEL.read_text(encoding='utf-8'))
        ident=str(payload.get('storage_id','')).strip()
        if not ident: fail('sentinel_corrupt')
        state='existing'
    else:
        ident=str(uuid.uuid4())
        payload={'storage_id':ident,'purpose':'ScoreMax governed persistent pre-import storage','schema':1}
        tmp=SENTINEL.with_suffix('.tmp')
        with tmp.open('w',encoding='utf-8') as f:
            json.dump(payload,f,sort_keys=True)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp,SENTINEL)
        state='created'

    digest=hashlib.sha256(ident.encode('utf-8')).hexdigest()
    probe=ROOT/'.write_probe'
    with probe.open('w',encoding='utf-8') as f:
        f.write(digest+'\n'); f.flush(); os.fsync(f.fileno())
    if probe.read_text(encoding='utf-8').strip()!=digest: fail('write_read_probe_failed')

    probe_runs=durability_probe()
    db_state='absent';db_integrity='n/a';db_fk='n/a'
    if DB.exists():
        integ,fk=check_sqlite(DB)
        db_state='existing';db_integrity=integ;db_fk=str(fk)

    qualification=qualify_preimport_database()
    print(
        f'SCOREMAX_PERSISTENT_STORAGE_PASS mount={MOUNT} state={state} '
        f'storage_id_sha256={digest} probe_runs={probe_runs} '
        f'db_state={db_state} db_integrity={db_integrity} db_fk={db_fk} '
        f'db={DB} backup={BACKUP} intake={INTAKE}',
        flush=True,
    )
    print('SCOREMAX_PERSISTENT_PREIMPORT_QUALIFICATION='+json.dumps(qualification,sort_keys=True),flush=True)

if __name__=='__main__': main()
