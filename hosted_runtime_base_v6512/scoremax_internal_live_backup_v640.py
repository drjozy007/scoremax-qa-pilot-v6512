"""Backup/restore utility for ScoreMax V6.4.0 local internal-live SQLite database."""
from __future__ import annotations
import argparse, hashlib, json, shutil, sqlite3
from datetime import datetime
from pathlib import Path
BASE=Path(__file__).resolve().parent
DATA=BASE/'internal_live_data'; DB=DATA/'scoremax_v6_4_0_internal_live.db'; BACKUPS=DATA/'backups_v640'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def integrity(path):
    c=None
    try:
        c=sqlite3.connect(path)
        row=c.execute('PRAGMA integrity_check').fetchone()
        return row[0] if row else 'integrity_check_returned_no_result'
    except sqlite3.DatabaseError as exc:
        return 'database_error: '+str(exc)
    finally:
        if c is not None:
            c.close()

def backup():
    if not DB.exists(): raise SystemExit('No V6.4.0 internal-live database exists yet.')
    BACKUPS.mkdir(parents=True,exist_ok=True); stamp=datetime.now().strftime('%Y%m%d_%H%M%S'); out=BACKUPS/f'scoremax_v6_4_0_{stamp}.db'
    src=sqlite3.connect(DB); dst=sqlite3.connect(out)
    try: src.backup(dst)
    finally: dst.close(); src.close()
    check=integrity(out)
    if check!='ok': out.unlink(missing_ok=True); raise SystemExit('Backup integrity check failed: '+check)
    manifest={'created_at':datetime.now().isoformat(timespec='seconds'),'database':DB.name,'backup':out.name,'sha256':sha(out),'integrity_check':check}
    out.with_suffix('.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2)); return out

def restore(path):
    src=Path(path).resolve()
    if not src.exists(): raise SystemExit('Backup file not found.')
    check=integrity(src)
    if check!='ok': raise SystemExit('Restore source failed integrity check: '+check)
    DATA.mkdir(exist_ok=True)
    if DB.exists(): backup()
    tmp=DB.with_suffix('.restore.tmp')
    shutil.copy2(src,tmp)
    check2=integrity(tmp)
    if check2!='ok': tmp.unlink(missing_ok=True); raise SystemExit('Restored copy failed integrity check: '+check2)
    tmp.replace(DB); print('Restored:',DB); print('SHA256:',sha(DB))

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest='cmd',required=True); sub.add_parser('backup'); r=sub.add_parser('restore'); r.add_argument('path'); a=ap.parse_args()
    backup() if a.cmd=='backup' else restore(a.path)
if __name__=='__main__': main()
