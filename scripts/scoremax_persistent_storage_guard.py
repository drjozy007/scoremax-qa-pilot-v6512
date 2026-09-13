from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from pathlib import Path

POLICY='SCOREMAX-PERSISTENT-GUARD-V3-COMMERCIAL-CATALOGUE-20260913'
ROOT=Path(os.environ.get('SCOREMAX_PERSISTENT_ROOT','/data/scoremax')).resolve()
DB=Path(os.environ.get('SCOREMAX_DB',str(ROOT/'state'/'scoremax.db'))).resolve()
BACKUP=Path(os.environ.get('SCOREMAX_BACKUP_DIR',str(ROOT/'backup'))).resolve()
INTAKE=Path(os.environ.get('SCOREMAX_CONTENT_INTAKE_DIR',str(ROOT/'intake'))).resolve()
MOUNT=Path(os.environ.get('SCOREMAX_EXPECTED_PERSISTENT_MOUNT','/data')).resolve()
SENTINEL=MOUNT/'.scoremax_persistent_storage_identity.json'
PROBE_DB=ROOT/'state'/'storage_durability_probe.sqlite3'
BASELINE_BACKUP=BACKUP/'scoremax_preimport_empty_baseline.sqlite3'
OPERATIONAL_BACKUP=BACKUP/'scoremax_operational_latest.sqlite3'
APPROVED_REVIEWERS={f'REVIEWER-{i:02d}' for i in range(1,6)}
APPROVED_COVERAGE_PACKAGES={
    'fsc1_biology': ('FSc Part 1','ACTIVE',79900,'PKR','monthly'),
    'fsc1_two_subjects': ('FSc Part 1','ACTIVE',129900,'PKR','monthly'),
    'fsc1_science_bundle': ('FSc Part 1','ACTIVE',169900,'PKR','monthly'),
    'fsc1_full': ('FSc Part 1','ACTIVE',199900,'PKR','monthly'),
    'grade9_full': ('Grade 9','COMING_SOON',None,'PKR','monthly'),
    'grade10_full': ('Grade 10','COMING_SOON',None,'PKR','monthly'),
    'fsc2_full': ('FSc Part 2','COMING_SOON',None,'PKR','monthly'),
    'mdcat_full': ('MDCAT','COMING_SOON',None,'PKR','monthly'),
}


def fail(msg: str) -> None:
    print('SCOREMAX_PERSISTENT_STORAGE_FAIL '+msg,flush=True)
    raise SystemExit(78)


def is_mount(path: Path) -> bool:
    try:
        if path.is_mount(): return True
    except Exception:
        pass
    try:
        target=str(path)
        for line in Path('/proc/mounts').read_text(encoding='utf-8',errors='replace').splitlines():
            parts=line.split()
            if len(parts)>=2 and parts[1].replace('\\040',' ')==target: return True
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
        runs=1; c.execute('INSERT INTO durability_probe(id,runs) VALUES(1,1)')
    else:
        runs=int(row[0])+1; c.execute('UPDATE durability_probe SET runs=?,updated_at=CURRENT_TIMESTAMP WHERE id=1',(runs,))
    c.commit(); integ=c.execute('PRAGMA integrity_check').fetchone()[0]; fk=len(c.execute('PRAGMA foreign_key_check').fetchall()); c.close()
    if integ!='ok' or fk: fail(f'durability_probe_integrity_failed integrity={integ} fk={fk}')
    return runs


def _table(c,name): return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())
def _cols(c,name): return {r[1] for r in c.execute(f'PRAGMA table_info({name})').fetchall()} if _table(c,name) else set()
def _count(c,name): return int(c.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]) if _table(c,name) else 0

def _counts(c):
    return {n:_count(c,n) for n in ('questions','curriculum','question_families','chapter_catalogue','coverage_packages')}


def _commercial_catalogue_state(c):
    if not _table(c,'coverage_packages'):
        return {'approved':False,'reason':'table_missing','rows':[]}
    rows=c.execute("SELECT code,programme,status,price_minor,currency,billing_period FROM coverage_packages ORDER BY code").fetchall()
    actual={
        str(r[0]): (str(r[1] or ''),str(r[2] or ''),r[3],str(r[4] or ''),str(r[5] or ''))
        for r in rows
    }
    approved=(actual==APPROVED_COVERAGE_PACKAGES)
    return {'approved':approved,'count':len(rows),'codes':sorted(actual),'rows':actual}


def _reviewer_state(c):
    if not _table(c,'users'): return {'count':0,'ids':[],'approved':True}
    cols=_cols(c,'users'); enabled="COALESCE(content_reviewer_enabled,0)" if 'content_reviewer_enabled' in cols else '0'; email="lower(COALESCE(email,'')) LIKE '%reviewer%' OR " if 'email' in cols else ''
    rows=c.execute(f"SELECT COALESCE(system_user_id,''),COALESCE(role,''),COALESCE(username,''),{enabled} FROM users WHERE lower(COALESCE(username,'')) LIKE '%reviewer%' OR {email}COALESCE(system_user_id,'') LIKE 'REVIEWER-%' OR COALESCE(system_user_id,'')='CRV-900001' ORDER BY system_user_id").fetchall()
    ids=[str(r[0]) for r in rows]
    if not rows: return {'count':0,'ids':[],'approved':True}
    approved=(set(ids)==APPROVED_REVIEWERS and len(rows)==5 and 'content_reviewer_enabled' in cols and all(str(r[1])=='student' and int(r[3] or 0)==1 for r in rows))
    return {'count':len(rows),'ids':ids,'approved':approved}


def _backup_and_verify(c,target: Path) -> tuple[str,str,int]:
    tmp=target.with_suffix('.tmp'); tmp.unlink(missing_ok=True)
    dest=sqlite3.connect(tmp)
    try: c.backup(dest); dest.commit()
    finally: dest.close()
    os.replace(tmp,target)
    integ,fk=check_sqlite(target)
    return hashlib.sha256(target.read_bytes()).hexdigest(),integ,fk


def _restore_semantic_check(source: Path, expected_counts: dict, expected_reviewers: dict) -> None:
    with tempfile.TemporaryDirectory(prefix='scoremax-guard-restore-') as td:
        restored=Path(td)/'restored.sqlite3'; src=sqlite3.connect(source,timeout=30); dst=sqlite3.connect(restored,timeout=30)
        try: src.backup(dst); dst.commit()
        finally: dst.close(); src.close()
        check_sqlite(restored); rc=sqlite3.connect(restored,timeout=30)
        try: got=_counts(rc); reviewers=_reviewer_state(rc)
        finally: rc.close()
        if got!=expected_counts or reviewers!=expected_reviewers: fail('restore_semantic_mismatch')


def qualify_database():
    if not DB.exists(): return {'state':'absent','policy':POLICY}
    c=sqlite3.connect(DB,timeout=30)
    try:
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; fk=len(c.execute('PRAGMA foreign_key_check').fetchall()); counts=_counts(c); reviewers=_reviewer_state(c)
        if integrity!='ok' or fk: fail(f'db_integrity_failed integrity={integrity} fk={fk}')
        if not reviewers['approved']: fail('unapproved_reviewer_state='+json.dumps(reviewers,sort_keys=True))
        commercial=_commercial_catalogue_state(c)
        if not commercial['approved']:
            fail('commercial_catalogue_mismatch='+json.dumps(commercial,sort_keys=True,default=str))
        priced=int(c.execute('SELECT COUNT(*) FROM plans WHERE COALESCE(price_minor,0)>0').fetchone()[0]) if _table(c,'plans') else 0
        if priced!=0: fail(f'seeded_plan_prices_present count={priced}')

        if counts['questions']==0:
            governed={k:counts[k] for k in ('questions','curriculum','question_families','chapter_catalogue')}
            if any(governed.values()): fail('preimport_governed_substrate_not_empty='+json.dumps(governed,sort_keys=True))
            sha,bi,bfk=_backup_and_verify(c,BASELINE_BACKUP); _restore_semantic_check(BASELINE_BACKUP,counts,reviewers)
            return {'state':'preimport_qualified','policy':POLICY,'integrity':integrity,'fk':fk,'counts':counts,'priced_plans':priced,'commercial_catalogue':{'approved':True,'count':commercial['count'],'codes':commercial['codes']},'reviewer_state':reviewers,'backup':str(BASELINE_BACKUP),'backup_sha256':sha,'backup_integrity':bi,'backup_fk':bfk}

        qcols=_cols(c,'questions')
        required={'ph_projection_owner','ph_question_id','ph_question_version_id','ph_question_checksum_sha256','ph_release_id','ph_release_version','ph_release_checksum_sha256','active'}
        missing=sorted(required-qcols)
        if missing: fail('postimport_lineage_columns_missing='+','.join(missing))
        non_ph=int(c.execute("SELECT COUNT(*) FROM questions WHERE COALESCE(ph_projection_owner,'')<>'POWER_HOUSE'").fetchone()[0])
        if non_ph: fail(f'postimport_non_power_house_questions count={non_ph}')
        incomplete=int(c.execute("SELECT COUNT(*) FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND (COALESCE(ph_question_id,'')='' OR COALESCE(ph_question_version_id,'')='' OR COALESCE(ph_question_checksum_sha256,'')='' OR COALESCE(ph_release_id,'')='' OR COALESCE(ph_release_version,'')='' OR COALESCE(ph_release_checksum_sha256,'')='')").fetchone()[0])
        if incomplete: fail(f'postimport_incomplete_lineage count={incomplete}')
        dup=int(c.execute("SELECT COUNT(*) FROM (SELECT ph_question_id FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND COALESCE(active,0)=1 GROUP BY ph_question_id HAVING COUNT(*)>1)").fetchone()[0])
        if dup: fail(f'postimport_duplicate_active_external_identity groups={dup}')
        for t in ('integration_ph_content_releases','integration_ph_release_question_membership','integration_ph_question_version_store'):
            if not _table(c,t): fail('postimport_integration_table_missing='+t)
        releases=_count(c,'integration_ph_content_releases'); membership=_count(c,'integration_ph_release_question_membership')
        if releases<1 or membership<counts['questions']: fail(f'postimport_release_lineage_incomplete releases={releases} membership={membership} questions={counts["questions"]}')
        unbound=int(c.execute("""SELECT COUNT(*) FROM questions q WHERE q.ph_projection_owner='POWER_HOUSE' AND NOT EXISTS (SELECT 1 FROM integration_ph_release_question_membership m WHERE m.release_id=q.ph_release_id AND m.release_version=q.ph_release_version AND m.question_id=q.ph_question_id AND m.question_version_id=q.ph_question_version_id)""").fetchone()[0])
        if unbound: fail(f'postimport_question_not_bound_to_release count={unbound}')
        sha,bi,bfk=_backup_and_verify(c,OPERATIONAL_BACKUP); _restore_semantic_check(OPERATIONAL_BACKUP,counts,reviewers)
        return {'state':'postimport_qualified','policy':POLICY,'integrity':integrity,'fk':fk,'counts':counts,'priced_plans':priced,'commercial_catalogue':{'approved':True,'count':commercial['count'],'codes':commercial['codes']},'reviewer_state':reviewers,'release_rows':releases,'membership_rows':membership,'unbound_questions':unbound,'backup':str(OPERATIONAL_BACKUP),'backup_sha256':sha,'backup_integrity':bi,'backup_fk':bfk,'preimport_baseline_preserved':BASELINE_BACKUP.exists()}
    finally: c.close()


def main():
    if not MOUNT.exists() or not MOUNT.is_dir(): fail(f'mount_missing={MOUNT}')
    if not is_mount(MOUNT): fail(f'not_a_real_mount={MOUNT}')
    for p in (ROOT,DB.parent,BACKUP,INTAKE,PROBE_DB.parent): p.mkdir(parents=True,exist_ok=True)
    if MOUNT not in ROOT.parents and ROOT!=MOUNT: fail('persistent_root_outside_mount')
    for name,path in (('db',DB),('backup',BACKUP),('intake',INTAKE)):
        if MOUNT not in path.parents: fail(name+'_outside_mount')
    if SENTINEL.exists():
        payload=json.loads(SENTINEL.read_text(encoding='utf-8')); ident=str(payload.get('storage_id','')).strip()
        if not ident: fail('sentinel_corrupt')
        state='existing'
    else:
        ident=str(uuid.uuid4()); payload={'storage_id':ident,'purpose':'ScoreMax governed persistent storage','schema':3,'policy':POLICY}; tmp=SENTINEL.with_suffix('.tmp')
        with tmp.open('w',encoding='utf-8') as f: json.dump(payload,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,SENTINEL); state='created'
    digest=hashlib.sha256(ident.encode()).hexdigest(); probe=ROOT/'.write_probe'
    with probe.open('w',encoding='utf-8') as f: f.write(digest+'\n'); f.flush(); os.fsync(f.fileno())
    if probe.read_text(encoding='utf-8').strip()!=digest: fail('write_read_probe_failed')
    runs=durability_probe(); db_state='absent'; db_integrity='n/a'; db_fk='n/a'
    if DB.exists(): db_integrity,fk=check_sqlite(DB); db_state='existing'; db_fk=str(fk)
    qualification=qualify_database()
    print(f'SCOREMAX_PERSISTENT_STORAGE_PASS policy={POLICY} mount={MOUNT} state={state} storage_id_sha256={digest} probe_runs={runs} db_state={db_state} db_integrity={db_integrity} db_fk={db_fk} db={DB} backup={BACKUP} intake={INTAKE}',flush=True)
    print('SCOREMAX_PERSISTENT_QUALIFICATION='+json.dumps(qualification,sort_keys=True),flush=True)

if __name__=='__main__': main()
