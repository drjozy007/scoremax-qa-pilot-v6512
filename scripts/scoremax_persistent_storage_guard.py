from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from pathlib import Path

ROOT=Path(os.environ.get('SCOREMAX_PERSISTENT_ROOT','/data/scoremax')).resolve()
DB=Path(os.environ.get('SCOREMAX_DB',str(ROOT/'state'/'scoremax.db'))).resolve()
BACKUP=Path(os.environ.get('SCOREMAX_BACKUP_DIR',str(ROOT/'backup'))).resolve()
INTAKE=Path(os.environ.get('SCOREMAX_CONTENT_INTAKE_DIR',str(ROOT/'intake'))).resolve()
MOUNT=Path(os.environ.get('SCOREMAX_EXPECTED_PERSISTENT_MOUNT','/data')).resolve()
SENTINEL=MOUNT/'.scoremax_persistent_storage_identity.json'


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


def main() -> None:
    if not MOUNT.exists() or not MOUNT.is_dir(): fail(f'mount_missing={MOUNT}')
    if not is_mount(MOUNT): fail(f'not_a_real_mount={MOUNT}')
    for p in (ROOT,DB.parent,BACKUP,INTAKE): p.mkdir(parents=True,exist_ok=True)
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
    print(f'SCOREMAX_PERSISTENT_STORAGE_PASS mount={MOUNT} state={state} storage_id_sha256={digest} db={DB} backup={BACKUP} intake={INTAKE}',flush=True)

if __name__=='__main__': main()
