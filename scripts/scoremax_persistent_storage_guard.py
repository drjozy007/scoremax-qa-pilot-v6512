from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from pathlib import Path

ROOT=Path(os.environ.get('SCOREMAX_PERSISTENT_ROOT','/data/scoremax')).resolve()
DB=Path(os.environ.get('SCOREMAX_DB',str(ROOT/'state'/'scoremax.db'))).resolve()
BACKUP=Path(os.environ.get('SCOREMAX_BACKUP_DIR',str(ROOT/'backup'))).resolve()
INTAKE=Path(os.environ.get('SCOREMAX_CONTENT_INTAKE_DIR',str(ROOT/'intake'))).resolve()
MOUNT=Path(os.environ.get('SCOREMAX_EXPECTED_PERSISTENT_MOUNT','/data')).resolve()
SENTINEL=MOUNT/'.scoremax_persistent_storage_identity.json'
PROBE_DB=ROOT/'state'/'storage_durability_probe.sqlite3'


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
    db_state='absent'
    db_integrity='n/a'
    db_fk='n/a'
    if DB.exists():
        integ,fk=check_sqlite(DB)
        db_state='existing'
        db_integrity=integ
        db_fk=str(fk)

    print(
        f'SCOREMAX_PERSISTENT_STORAGE_PASS mount={MOUNT} state={state} '
        f'storage_id_sha256={digest} probe_runs={probe_runs} '
        f'db_state={db_state} db_integrity={db_integrity} db_fk={db_fk} '
        f'db={DB} backup={BACKUP} intake={INTAKE}',
        flush=True,
    )

if __name__=='__main__': main()
