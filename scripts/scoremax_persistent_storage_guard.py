from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from pathlib import Path

POLICY='SCOREMAX-PERSISTENT-GUARD-V4-GOVERNED-EMERGENCY-DIRECT-20260915'
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
EMERGENCY_RIGHTS={'scoremax original','licensed','permitted','public domain','approved'}


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
    actual={str(r[0]):(str(r[1] or ''),str(r[2] or ''),r[3],str(r[4] or ''),str(r[5] or '')) for r in rows}
    return {'approved':actual==APPROVED_COVERAGE_PACKAGES,'count':len(rows),'codes':sorted(actual),'rows':actual}


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


def _hex64(value) -> bool:
    v=str(value or '').strip().lower()
    return len(v)==64 and all(ch in '0123456789abcdef' for ch in v)


def _safe_json(value,default):
    try: return json.loads(value or '')
    except Exception: return default


def _verify_backup_row(row,kind: str) -> None:
    if not row: fail(f'emergency_{kind}_backup_missing')
    if str(row['integrity_status'] or '').upper()!='OK': fail(f'emergency_{kind}_backup_not_ok')
    path=Path(str(row['file_path'] or '')).resolve()
    if not path.is_file(): fail(f'emergency_{kind}_backup_file_missing')
    if BACKUP not in path.parents: fail(f'emergency_{kind}_backup_outside_protected_storage')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=str(row['file_sha256'] or '').lower(): fail(f'emergency_{kind}_backup_checksum_mismatch')
    if len(raw)!=int(row['file_size_bytes'] or 0): fail(f'emergency_{kind}_backup_size_mismatch')
    check_sqlite(path)


def _emergency_governance_text(payload: dict) -> tuple[bool,bool,bool]:
    ready=str(payload.get('ScoreMax Ready','') or '').strip().lower() in {'1','yes','true'}
    rights=str(payload.get('Rights Status','') or '').strip().lower() in EMERGENCY_RIGHTS
    governance=' '.join(str(payload.get(k,'') or '') for k in ('Status','Review Status','R2 Status','Readiness','Release Status','Review Requirement','Dual Review Status')).casefold()
    r2=any(str(payload.get(k,'') or '').strip().casefold() in {'1','yes','true','required','y','dual_review_required','r2_required'} for k in ('Reviewer 2 Required','Reviewer2 Required','Dual Review Required'))
    if 'dual_review_required' in str(payload.get('Review Requirement','') or '').strip().casefold(): r2=True
    blocked=r2 or any(term in governance for term in ('hold','blocked','r2_required','dual_review_required','human_review_required','source_check_required'))
    return ready,rights,blocked


def _qualify_emergency_batches(c) -> dict:
    non_ph=c.execute("SELECT * FROM questions WHERE COALESCE(ph_projection_owner,'')<>'POWER_HOUSE' ORDER BY id").fetchall()
    if not non_ph: return {'questions':0,'batches':0,'released':0,'candidate':0,'batch_codes':[]}
    for t in ('content_import_batches','content_import_batch_rows','pilot_backups'):
        if not _table(c,t): fail('emergency_evidence_table_missing='+t)
    qcols=_cols(c,'questions')
    for col in ('source_import_batch_id','content_environment','scoremax_ready','status','review_status','active'):
        if col not in qcols: fail('emergency_question_column_missing='+col)
    batch_ids=sorted({int(q['source_import_batch_id'] or 0) for q in non_ph})
    if not batch_ids or 0 in batch_ids: fail('postimport_unbound_non_power_house_questions')
    result={'questions':len(non_ph),'batches':0,'released':0,'candidate':0,'batch_codes':[]}
    for bid in batch_ids:
        b=c.execute('SELECT * FROM content_import_batches WHERE id=?',(bid,)).fetchone()
        if not b: fail(f'emergency_batch_missing id={bid}')
        code=str(b['batch_code'] or '')
        if str(b['intake_mode'] or '').upper()!='EMERGENCY_DIRECT': fail(f'emergency_wrong_intake_mode batch={code}')
        if str(b['source_system'] or '').upper()!='POWER_HOUSE_GOVERNED': fail(f'emergency_wrong_source_system batch={code}')
        if str(b['status'] or '').upper()!='IMPORTED': fail(f'emergency_batch_not_imported batch={code}')
        if not str(b['source_prompt_pack_id'] or '').strip(): fail(f'emergency_prompt_pack_id_missing batch={code}')
        if not _hex64(b['source_prompt_pack_version']): fail(f'emergency_prompt_pack_version_not_sha256 batch={code}')
        if not _hex64(b['payload_checksum']): fail(f'emergency_payload_checksum_invalid batch={code}')
        row_count=int(b['row_count'] or 0); valid=int(b['valid_count'] or 0); errors=int(b['error_count'] or 0); warnings=int(b['warning_count'] or 0)
        if row_count<1 or valid!=row_count or errors!=0 or warnings!=0: fail(f'emergency_validation_not_clean batch={code} rows={row_count} valid={valid} errors={errors} warnings={warnings}')
        source=Path(str(b['source_file_path'] or '')).resolve()
        if not source.is_file() or INTAKE not in source.parents: fail(f'emergency_source_file_not_protected batch={code}')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=str(b['payload_checksum']).lower(): fail(f'emergency_source_checksum_mismatch batch={code}')
        stored=c.execute('SELECT * FROM content_import_batch_rows WHERE batch_id=? ORDER BY id',(bid,)).fetchall()
        if len(stored)!=row_count: fail(f'emergency_row_evidence_count_mismatch batch={code}')
        qrows=c.execute('SELECT * FROM questions WHERE source_import_batch_id=? ORDER BY id',(bid,)).fetchall()
        if len(qrows)!=row_count: fail(f'emergency_question_count_mismatch batch={code}')
        by_db={int(q['id']):q for q in qrows}
        for r in stored:
            if str(r['import_status'] or '').upper()!='IMPORTED' or not r['question_db_id']: fail(f'emergency_row_not_imported batch={code}')
            if _safe_json(r['errors_json'],['invalid'])!=[] or _safe_json(r['warnings_json'],['invalid'])!=[]: fail(f'emergency_row_validation_evidence_not_clean batch={code}')
            q=by_db.get(int(r['question_db_id']))
            if not q or str(q['question_id'] or '')!=str(r['question_id'] or ''): fail(f'emergency_row_question_binding_mismatch batch={code}')
            payload=_safe_json(r['row_json'],{})
            ready,rights,blocked=_emergency_governance_text(payload)
            if not ready or not rights or blocked: fail(f'emergency_row_release_governance_invalid batch={code} question={r["question_id"]}')
        pre=c.execute('SELECT * FROM pilot_backups WHERE id=?',(b['backup_record_id'],)).fetchone() if b['backup_record_id'] else None
        _verify_backup_row(pre,'preimport')
        release_status=str(b['release_status'] or '').upper()
        released_count=int(b['released_count'] or 0)
        active=sum(int(q['active'] or 0)==1 for q in qrows)
        if release_status=='NOT_RELEASED':
            if released_count!=0 or active!=0: fail(f'emergency_candidate_release_state_mismatch batch={code}')
            if any(str(q['status'] or '')!='Draft' or str(q['review_status'] or '')!='Draft' or str(q['content_environment'] or '')!='CANDIDATE' for q in qrows): fail(f'emergency_candidate_question_state_mismatch batch={code}')
            result['candidate']+=row_count
        elif release_status=='RELEASED_ELIGIBLE':
            if not str(b['release_attested_at'] or '').strip() or not b['release_attested_by'] or not str(b['released_at'] or '').strip(): fail(f'emergency_release_attestation_missing batch={code}')
            if released_count<1 or released_count>row_count or active!=released_count: fail(f'emergency_released_count_mismatch batch={code}')
            release_backup=c.execute('SELECT * FROM pilot_backups WHERE reason=? ORDER BY id DESC LIMIT 1',(f'Automatic backup before emergency release {code}',)).fetchone()
            _verify_backup_row(release_backup,'prerelease')
            for q in qrows:
                if int(q['active'] or 0)==1:
                    if str(q['status'] or '')!='Approved' or str(q['review_status'] or '')!='Approved' or str(q['content_environment'] or '')!='PRODUCTION' or int(q['scoremax_ready'] or 0)!=1: fail(f'emergency_released_question_state_invalid batch={code}')
                elif str(q['content_environment'] or '')!='CANDIDATE': fail(f'emergency_excluded_question_environment_invalid batch={code}')
            result['released']+=released_count; result['candidate']+=row_count-released_count
        else:
            fail(f'emergency_release_status_invalid batch={code} status={release_status}')
        result['batches']+=1; result['batch_codes'].append(code)
    return result


def qualify_database():
    if not DB.exists(): return {'state':'absent','policy':POLICY}
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
    try:
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; fk=len(c.execute('PRAGMA foreign_key_check').fetchall()); counts=_counts(c); reviewers=_reviewer_state(c)
        if integrity!='ok' or fk: fail(f'db_integrity_failed integrity={integrity} fk={fk}')
        if not reviewers['approved']: fail('unapproved_reviewer_state='+json.dumps(reviewers,sort_keys=True))
        commercial=_commercial_catalogue_state(c)
        if not commercial['approved']: fail('commercial_catalogue_mismatch='+json.dumps(commercial,sort_keys=True,default=str))
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
        ph_count=int(c.execute("SELECT COUNT(*) FROM questions WHERE ph_projection_owner='POWER_HOUSE'").fetchone()[0])
        if ph_count:
            incomplete=int(c.execute("SELECT COUNT(*) FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND (COALESCE(ph_question_id,'')='' OR COALESCE(ph_question_version_id,'')='' OR COALESCE(ph_question_checksum_sha256,'')='' OR COALESCE(ph_release_id,'')='' OR COALESCE(ph_release_version,'')='' OR COALESCE(ph_release_checksum_sha256,'')='')").fetchone()[0])
            if incomplete: fail(f'postimport_incomplete_lineage count={incomplete}')
            dup=int(c.execute("SELECT COUNT(*) FROM (SELECT ph_question_id FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND COALESCE(active,0)=1 GROUP BY ph_question_id HAVING COUNT(*)>1)").fetchone()[0])
            if dup: fail(f'postimport_duplicate_active_external_identity groups={dup}')
            for t in ('integration_ph_content_releases','integration_ph_release_question_membership','integration_ph_question_version_store'):
                if not _table(c,t): fail('postimport_integration_table_missing='+t)
            releases=_count(c,'integration_ph_content_releases'); membership=_count(c,'integration_ph_release_question_membership')
            if releases<1 or membership<ph_count: fail(f'postimport_release_lineage_incomplete releases={releases} membership={membership} ph_questions={ph_count}')
            unbound=int(c.execute("""SELECT COUNT(*) FROM questions q WHERE q.ph_projection_owner='POWER_HOUSE' AND NOT EXISTS (SELECT 1 FROM integration_ph_release_question_membership m WHERE m.release_id=q.ph_release_id AND m.release_version=q.ph_release_version AND m.question_id=q.ph_question_id AND m.question_version_id=q.ph_question_version_id)""").fetchone()[0])
            if unbound: fail(f'postimport_question_not_bound_to_release count={unbound}')
        else:
            releases=0; membership=0; unbound=0
        emergency=_qualify_emergency_batches(c)
        if ph_count+int(emergency['questions'])!=counts['questions']: fail('postimport_question_classification_mismatch')
        sha,bi,bfk=_backup_and_verify(c,OPERATIONAL_BACKUP); _restore_semantic_check(OPERATIONAL_BACKUP,counts,reviewers)
        return {'state':'postimport_qualified','policy':POLICY,'integrity':integrity,'fk':fk,'counts':counts,'priced_plans':priced,'commercial_catalogue':{'approved':True,'count':commercial['count'],'codes':commercial['codes']},'reviewer_state':reviewers,'native_power_house_questions':ph_count,'release_rows':releases,'membership_rows':membership,'unbound_questions':unbound,'governed_emergency':emergency,'backup':str(OPERATIONAL_BACKUP),'backup_sha256':sha,'backup_integrity':bi,'backup_fk':bfk,'preimport_baseline_preserved':BASELINE_BACKUP.exists()}
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
        ident=str(uuid.uuid4()); payload={'storage_id':ident,'purpose':'ScoreMax governed persistent storage','schema':4,'policy':POLICY}; tmp=SENTINEL.with_suffix('.tmp')
        with tmp.open('w',encoding='utf-8') as f: json.dump(payload,f,sort_keys=True); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,SENTINEL); state='created'
    digest=hashlib.sha256(ident.encode()).hexdigest(); probe=ROOT/'.write_probe'
    with probe.open('w',encoding='utf-8') as f: f.write(digest+'\n'); f.flush(); os.fsync(f.fileno())
    if probe.read_text(encoding='utf-8').strip()!=digest: fail('write_read_probe_failed')
    runs=durability_probe(); db_state='absent'; db_integrity='n/a'; db_fk='n/a'
    if DB.exists(): db_integrity,fk=check_sqlite(DB); db_state='existing'; db_fk=str(fk)
    qualification=qualify_database()
    # SCOREMAX_SAFE98_RETURN_PROBE_HOOK_V1: bounded one-shot against an already STAGED, non-activated SAFE98 release.
    # OFF by default; never materialises or activates learner content.
    if False and os.environ.get('SCOREMAX_SAFE98_RETURN_PROBE','OFF').strip().upper()=='RUN':
        import subprocess,sys
        probe_script=Path(__file__).with_name('safe98_return_loop_probe.py')
        if not probe_script.is_file(): fail('safe98_return_probe_script_missing')
        cp=subprocess.run([sys.executable,str(probe_script)],check=False,env=dict(os.environ))
        if cp.returncode: fail(f'safe98_return_probe_failed rc={cp.returncode}')
    # SCOREMAX_SAFE98_LINEAGE_EXPORT_HOOK_V1: read-only immutable lineage export for the already STAGED SAFE98 release.
    if os.environ.get('SCOREMAX_SAFE98_LINEAGE_EXPORT','OFF').strip().upper()=='RUN':
        import subprocess,sys
        export_script=Path(__file__).with_name('safe98_lineage_export.py')
        if not export_script.is_file(): fail('safe98_lineage_export_script_missing')
        cp=subprocess.run([sys.executable,str(export_script)],check=False,env=dict(os.environ))
        if cp.returncode: fail(f'safe98_lineage_export_failed rc={cp.returncode}')
    # SCOREMAX_SAFE98_DEADLETTER_INTROSPECT_HOOK_V1: disabled after read-only qualification PASS.
    if False:
        import subprocess,sys
        diag_script=Path(__file__).with_name('safe98_deadletter_introspect.py')
        if not diag_script.is_file(): fail('safe98_deadletter_introspect_script_missing')
        cp=subprocess.run([sys.executable,str(diag_script)],check=False,env=dict(os.environ))
        if cp.returncode: fail(f'safe98_deadletter_introspect_failed rc={cp.returncode}')
    # SCOREMAX_SAFE98_DEADLETTER_REQUEUE_HOOK_V1: one bounded governed replay of the same immutable SAFE98 incident.
    if False:
        import subprocess,sys
        rq_script=Path(__file__).with_name('safe98_deadletter_requeue.py')
        if not rq_script.is_file(): fail('safe98_deadletter_requeue_script_missing')
        cp=subprocess.run([sys.executable,str(rq_script)],check=False,env=dict(os.environ))
        if cp.returncode: fail(f'safe98_deadletter_requeue_failed rc={cp.returncode}')
    # SCOREMAX_SAFE98_WITHDRAWAL_INTROSPECT_HOOK_V1: read-only inspection of the generic PH withdrawal receiver and SAFE98 staged state.
    if os.environ.get('SCOREMAX_SAFE98_WITHDRAWAL_INTROSPECT','OFF').strip().upper()=='RUN':
        import subprocess,sys
        wi_script=Path(__file__).with_name('safe98_withdrawal_receiver_introspect.py')
        if not wi_script.is_file(): fail('safe98_withdrawal_introspect_script_missing')
        cp=subprocess.run([sys.executable,str(wi_script)],check=False,env=dict(os.environ))
        if cp.returncode: fail(f'safe98_withdrawal_introspect_failed rc={cp.returncode}')
    # SCOREMAX_SAFE98_ACTIVATION_SOURCE_PROBE_V1: read-only source inspection only.
    if os.environ.get('SCOREMAX_SAFE98_ACTIVATION_SOURCE_PROBE','OFF').strip().upper()=='RUN':
        import subprocess,sys
        ap_script=Path(__file__).with_name('safe98_activation_source_probe.py')
        if not ap_script.is_file(): fail('safe98_activation_source_probe_missing')
        cp=subprocess.run([sys.executable,str(ap_script)],check=False,env=dict(os.environ))
        if cp.returncode: fail(f'safe98_activation_source_probe_failed rc={cp.returncode}')
    # SCOREMAX_SAFE98_WITHDRAWAL_CLOSE_V1: prove one staged exclusion/97 eligible; optionally flush its sole ACK.
    if os.environ.get('SCOREMAX_SAFE98_WITHDRAWAL_CLOSE','OFF').strip().upper() in {'CHECK','FLUSH_ACK'}:
        import subprocess,sys
        close_script=Path(__file__).with_name('safe98_withdrawal_close.py')
        if not close_script.is_file(): fail('safe98_withdrawal_close_script_missing')
        cp=subprocess.run([sys.executable,str(close_script)],check=False,env=dict(os.environ))
        if cp.returncode: fail(f'safe98_withdrawal_close_failed rc={cp.returncode}')
    # SCOREMAX_SAFE98_WITHDRAWAL_AUTH_DIAG_V1: read-only auth failure evidence; never prints secret values.
    if os.environ.get('SCOREMAX_SAFE98_WITHDRAWAL_AUTH_DIAG','OFF').strip().upper()=='RUN':
        import subprocess,sys
        ad_script=Path(__file__).with_name('safe98_withdrawal_auth_diag.py')
        if not ad_script.is_file(): fail('safe98_withdrawal_auth_diag_missing')
        cp=subprocess.run([sys.executable,str(ad_script)],check=False,env=dict(os.environ))
        if cp.returncode: fail(f'safe98_withdrawal_auth_diag_failed rc={cp.returncode}')
    print(f'SCOREMAX_PERSISTENT_STORAGE_PASS policy={POLICY} mount={MOUNT} state={state} storage_id_sha256={digest} probe_runs={runs} db_state={db_state} db_integrity={db_integrity} db_fk={db_fk} db={DB} backup={BACKUP} intake={INTAKE}',flush=True)
    print('SCOREMAX_PERSISTENT_QUALIFICATION='+json.dumps(qualification,sort_keys=True),flush=True)

if __name__=='__main__': main()
