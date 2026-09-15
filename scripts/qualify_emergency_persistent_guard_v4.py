from __future__ import annotations

import csv
import io
import json
import os
import secrets
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
RUNTIME=BASE/'scoremax_runtime_v669b'
GUARD=BASE/'scripts'/'scoremax_persistent_storage_guard.py'
ROOT=Path('/dev/shm/scoremax-guard-v4')
DB=ROOT/'state'/'scoremax.db'
BACKUP=ROOT/'backup'
INTAKE=ROOT/'intake'
GOOD=Path('/tmp/scoremax_guard_v4_good.db')

os.environ.update({
    'SCOREMAX_ENV':'local',
    'SCOREMAX_PERSISTENT_ROOT':str(ROOT),
    'SCOREMAX_DB':str(DB),
    'SCOREMAX_BACKUP_DIR':str(BACKUP),
    'SCOREMAX_CONTENT_INTAKE_DIR':str(INTAKE),
    'SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/dev/shm',
    'SCOREMAX_SECRET':secrets.token_hex(32),
    'SCOREMAX_STAGING_SESSION_SECRET':secrets.token_hex(32),
})
shutil.rmtree(ROOT,ignore_errors=True)
ROOT.joinpath('state').mkdir(parents=True)
BACKUP.mkdir()
INTAKE.mkdir()
sys.path.insert(0,str(RUNTIME))
import app as sm


def run_guard(label:str,expect_pass:bool=True,token:str='') -> str:
    p=subprocess.run([sys.executable,str(GUARD)],env=os.environ.copy(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    out=p.stdout
    print(f'--- {label} rc={p.returncode} ---')
    print(out[-4000:])
    if expect_pass:
        assert p.returncode==0,(label,p.returncode,out)
        assert 'SCOREMAX_PERSISTENT_STORAGE_PASS' in out,(label,out)
    else:
        assert p.returncode==78,(label,p.returncode,out)
        assert token in out,(label,token,out)
    return out


def build_csv() -> bytes:
    fields=['Question ID','Family ID','Variant','Programme','Country','Qualification','Exam Board','Curriculum Version','Subject','Chapter','Chapter Number','Chapter Name','Topic','Sub-topic','Type','Question','A','B','C','D','Answer','Explanation','Level','Difficulty','Learning Outcome','Concept','Cognitive Skill','Command Word','Marks','Estimated Time Seconds','Stimulus / Context','Rights Status','ScoreMax Ready','Assessment Purpose','Difficulty Source','Source Type','Secure Bank','Status','Review Status','R2 Status']
    b=io.StringIO(); w=csv.DictWriter(b,fieldnames=fields); w.writeheader()
    for i in range(1,101):
        w.writerow({'Question ID':f'GUARD-Q-{i:03d}','Family ID':f'GUARD-F-{(i-1)//4:03d}','Programme':'FSc Part 2','Country':'Pakistan','Qualification':'FSc / Intermediate','Curriculum Version':'2023 Curriculum','Subject':'Biology','Chapter':'13 — Thermoregulation and Osmoregulation','Chapter Number':'13','Chapter Name':'Thermoregulation and Osmoregulation','Topic':'Homeostasis','Type':'MCQ','Question':f'Which option is correct for governed guard fixture {i}?','A':'Correct','B':'Distractor B','C':'Distractor C','D':'Distractor D','Answer':'A','Explanation':'A is the governed correct option.','Level':'Foundation','Difficulty':'Easy','Learning Outcome':'Governed test outcome','Concept':'Governed family','Cognitive Skill':'Recall','Marks':'1','Estimated Time Seconds':'60','Rights Status':'ScoreMax Original','ScoreMax Ready':'Yes','Assessment Purpose':'practice|test|mock|mastery','Difficulty Source':'Power House governed source','Source Type':'Power House governed SCOREMAX_CREATED','Secure Bank':'Yes','Status':'Ready','Review Status':'AUTO_APPROVED_FOR_RELEASE','R2 Status':''})
    return b.getvalue().encode()


def restore_good():
    shutil.copy2(GOOD,DB)
    Path(str(DB)+'-wal').unlink(missing_ok=True)
    Path(str(DB)+'-shm').unlink(missing_ok=True)


def mutate(sql:str):
    c=sqlite3.connect(DB); c.execute(sql); c.commit(); c.close()


def main():
    sm.init(); c=sm.db(); assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok'; assert not c.execute('PRAGMA foreign_key_check').fetchall(); c.close()
    pre=run_guard('preimport'); assert 'preimport_qualified' in pre

    raw=build_csv(); admin_c=sm.db(); admin=admin_c.execute("SELECT id,full_name,COALESCE(session_version,0) session_version FROM users WHERE role='admin' AND COALESCE(account_status,'active')='active' ORDER BY id LIMIT 1").fetchone(); assert admin; before=int(admin_c.execute('SELECT COALESCE(MAX(id),0) FROM content_import_batches').fetchone()[0]); admin_c.close()
    token='guard-v4'; client=sm.app.test_client()
    with client.session_transaction() as s: s.update(user_id=int(admin['id']),role='admin',full_name=str(admin['full_name']),session_version=int(admin['session_version']),_csrf_token=token)
    r=client.post('/admin/import?mode=emergency',data={'_csrf_token':token,'intake_mode':'EMERGENCY_DIRECT','source_system':'POWER_HOUSE_GOVERNED','source_prompt_pack_id':'GUARD-V4-QUALIFICATION','source_prompt_pack_version':'1'*64,'file':(io.BytesIO(raw),'guard100.csv')},content_type='multipart/form-data',follow_redirects=False); assert r.status_code==200
    c=sm.db(); b=c.execute('SELECT * FROM content_import_batches WHERE id>? ORDER BY id DESC LIMIT 1',(before,)).fetchone(); assert b and int(b['row_count'])==100 and int(b['valid_count'])==100 and int(b['error_count'])==0 and int(b['warning_count'])==0; bid=int(b['id']); c.close()
    r=client.post('/admin/import/confirm',data={'_csrf_token':token,'batch_id':bid},follow_redirects=False); assert r.status_code in {302,303}
    c=sm.db(); qs=c.execute('SELECT * FROM questions WHERE source_import_batch_id=?',(bid,)).fetchall(); assert len(qs)==100 and all(int(q['active'] or 0)==0 and q['status']=='Draft' and q['review_status']=='Draft' and q['content_environment']=='CANDIDATE' for q in qs); c.close()
    cand=run_guard('candidate'); assert '"candidate": 100' in cand and '"released": 0' in cand

    r=client.post(f'/admin/import/batch/{bid}/release-eligible',data={'_csrf_token':token,'attestation':'I CONFIRM THIS IS A FROZEN ACADEMICALLY APPROVED RELEASE','release_note':'Guard V4 qualification fixture.'},follow_redirects=False); assert r.status_code in {302,303}
    c=sm.db(); b=c.execute('SELECT * FROM content_import_batches WHERE id=?',(bid,)).fetchone(); qs=c.execute('SELECT * FROM questions WHERE source_import_batch_id=?',(bid,)).fetchall(); assert b['release_status']=='RELEASED_ELIGIBLE' and int(b['released_count'])==100; assert len(qs)==100 and all(int(q['active'] or 0)==1 and q['status']=='Approved' and q['review_status']=='Approved' and q['content_environment']=='PRODUCTION' for q in qs); dst=sqlite3.connect(GOOD); c.backup(dst); dst.close(); c.close()
    released=run_guard('released'); assert '"released": 100' in released and '"questions": 100' in released

    attacks=[
      ('bad_source',"UPDATE content_import_batches SET source_system='MANUAL_FILE'",'emergency_wrong_source_system'),
      ('bad_checksum',"UPDATE content_import_batches SET payload_checksum=printf('%064d',0)",'emergency_source_checksum_mismatch'),
      ('no_attestation',"UPDATE content_import_batches SET release_attested_at=''",'emergency_release_attestation_missing'),
      ('no_binding',"UPDATE questions SET source_import_batch_id=NULL WHERE id=(SELECT MIN(id) FROM questions)",'postimport_unbound_non_power_house_questions'),
      ('bad_state',"UPDATE questions SET status='Draft' WHERE id=(SELECT MIN(id) FROM questions)",'emergency_released_question_state_invalid'),
    ]
    for name,sql,expected in attacks:
        restore_good(); mutate(sql); run_guard(name,False,expected)
    restore_good(); final=run_guard('final-clean'); assert '"released": 100' in final
    result={'status':'PASS','policy':'SCOREMAX-PERSISTENT-GUARD-V4-GOVERNED-EMERGENCY-DIRECT-20260915','questions':100,'candidate_restart':True,'released_restart':True,'adversarial_fail_closed_cases':len(attacks),'parent_live_commit':'27a0ece04c97cd0bebc0b4fcb592747fa3867c07','production_mutation':False}
    print('SCOREMAX_EMERGENCY_GUARD_V4_QUALIFICATION_PASS '+json.dumps(result,sort_keys=True))


if __name__=='__main__': main()
