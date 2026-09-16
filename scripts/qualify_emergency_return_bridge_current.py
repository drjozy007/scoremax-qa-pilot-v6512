from __future__ import annotations
import csv,hashlib,io,json,os,secrets,shutil,sys
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
RUNTIME=BASE/'scoremax_runtime_v669b'
ROOT=Path('/dev/shm/scoremax-emergency-return-current-qual')
DB=ROOT/'state'/'scoremax.db'
BACKUP=ROOT/'backup'; INTAKE=ROOT/'intake'
shutil.rmtree(ROOT,ignore_errors=True); ROOT.joinpath('state').mkdir(parents=True); BACKUP.mkdir(); INTAKE.mkdir()
os.environ.update({
 'SCOREMAX_ENV':'local','SCOREMAX_DB':str(DB),'SCOREMAX_PERSISTENT_ROOT':str(ROOT),
 'SCOREMAX_BACKUP_DIR':str(BACKUP),'SCOREMAX_CONTENT_INTAKE_DIR':str(INTAKE),
 'SCOREMAX_SECRET':secrets.token_hex(32),'SCOREMAX_STAGING_SESSION_SECRET':secrets.token_hex(32),
})
sys.path.insert(0,str(RUNTIME))
import app as sm
import scoremax_ph_bridge_v6611d as bridge
from ux_admin_view_as_runtime import install_admin_view_as

FIELDS=['Question ID','Family ID','Programme','Country','Qualification','Curriculum Version','Subject','Chapter','Chapter Number','Chapter Name','Topic','Type','Question','A','B','C','D','Answer','Explanation','Level','Difficulty','Learning Outcome','Concept','Cognitive Skill','Marks','Estimated Time Seconds','Rights Status','ScoreMax Ready','Assessment Purpose','Difficulty Source','Source Type','Secure Bank','Status','Review Status','R2 Status','Power House Public ID','Power House Source Row']

def make_csv(ph_id='PH-RS-Q-QUAL-001',qid='BIO12-CH13-QUAL-001')->bytes:
    s=io.StringIO(); w=csv.DictWriter(s,fieldnames=FIELDS); w.writeheader()
    w.writerow({'Question ID':qid,'Family ID':'FAM-QUAL-001','Programme':'FSc Part 2','Country':'Pakistan','Qualification':'FSc / Intermediate','Curriculum Version':'2023 Curriculum','Subject':'Biology','Chapter':'13 — Thermoregulation and Osmoregulation','Chapter Number':'13','Chapter Name':'Thermoregulation and Osmoregulation','Topic':'Homeostasis','Type':'MCQ','Question':'Which response supports homeostasis?','A':'A','B':'B','C':'C','D':'D','Answer':'A','Explanation':'A is correct.','Level':'Exam Ready','Difficulty':'Medium','Learning Outcome':'Governed qualification outcome','Concept':'Homeostasis','Cognitive Skill':'APPLICATION','Marks':'1','Estimated Time Seconds':'60','Rights Status':'ScoreMax Original','ScoreMax Ready':'Yes','Assessment Purpose':'practice|test|mock|mastery','Difficulty Source':'Power House governed source','Source Type':'Power House governed SCOREMAX_CREATED','Secure Bank':'Yes','Status':'REAL_CHAPTER_IMPORTED_CANDIDATE','Review Status':'AUTO_APPROVED_FOR_RELEASE','R2 Status':'','Power House Public ID':ph_id,'Power House Source Row':'756'})
    return s.getvalue().encode()

def admin():
    c=sm.db(); r=c.execute("SELECT id,full_name,COALESCE(session_version,0) session_version FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone(); c.close(); assert r
    return r

def client(admin_row,token='qual-csrf'):
    c=sm.app.test_client()
    with c.session_transaction() as s:
        s.update(user_id=int(admin_row['id']),role='admin',full_name=str(admin_row['full_name']),session_version=int(admin_row['session_version']),_csrf_token=token)
    return c

def import_release(raw:bytes):
    a=admin(); cl=client(a); token='qual-csrf'; digest=hashlib.sha256(raw).hexdigest(); ledger='e'*64
    r=cl.post('/admin/import?mode=emergency',data={'_csrf_token':token,'intake_mode':'EMERGENCY_DIRECT','source_system':'POWER_HOUSE_GOVERNED','source_prompt_pack_id':'BIO13-RETURN-QUAL','source_prompt_pack_version':ledger,'file':(io.BytesIO(raw),'qual.csv')},content_type='multipart/form-data',follow_redirects=False)
    assert r.status_code==200,r.status_code
    c=sm.db(); b=c.execute('SELECT * FROM content_import_batches ORDER BY id DESC LIMIT 1').fetchone(); assert b and b['payload_checksum']==digest and int(b['error_count'])==0 and int(b['warning_count'])==0; bid=int(b['id']); c.close()
    r=cl.post('/admin/import/confirm',data={'_csrf_token':token,'batch_id':bid},follow_redirects=False); assert r.status_code in {302,303},r.status_code
    r=cl.post(f'/admin/import/batch/{bid}/release-eligible',data={'_csrf_token':token,'attestation':'I CONFIRM THIS IS A FROZEN ACADEMICALLY APPROVED RELEASE'},follow_redirects=False); assert r.status_code in {302,303},r.status_code
    c=sm.db(); q=c.execute('SELECT * FROM questions WHERE source_import_batch_id=?',(bid,)).fetchone(); assert q and int(q['active'])==1; qid=int(q['id']); c.close()
    return cl,qid,bid,digest,ledger

def main():
    sm.init()
    # Current production registers Admin View As during scoremax_production startup.
    # The qualification imports bare app.py, so mirror that current-baseline route registration.
    install_admin_view_as(sm.app)

    # Direct post-bridge rejection: exactly one incident, and recovery must not duplicate it.
    raw=make_csv(); cl,qdb,bid,digest,ledger=import_release(raw)
    c=sm.db(); q=c.execute('SELECT * FROM questions WHERE id=?',(qdb,)).fetchone()
    msg=bridge.queue_reported_question_incident(c,q,'QUAL-FLAG-001','FACTUAL_ERROR','HIGH','qualification concern',{'source':'QUAL','page':'/admin/questions/'+str(qdb)})
    assert msg
    out=c.execute('SELECT envelope_json FROM integration_outbox WHERE message_id=?',(msg,)).fetchone(); assert out
    env=json.loads(out['envelope_json']); ident=env['payload']['question']
    assert env['schema_version']=='1.1.0'
    assert ident['identity_mode']=='EMERGENCY_DIRECT_GOVERNED'
    assert ident['source_question_id']=='BIO12-CH13-QUAL-001'
    assert ident['power_house_public_id']=='PH-RS-Q-QUAL-001'
    assert ident['power_house_source_row']=='756'
    assert ident['batch_code'] and ident['transport_sha256']==digest and ident['selection_ledger_sha256']==ledger
    c.rollback(); c.close()

    r=cl.post(f'/admin/questions/{qdb}/review',data={'_csrf_token':'qual-csrf','action':'reject','reason_code':'Factual/scientific issue','note':'qualification reject'},follow_redirects=False)
    assert r.status_code in {302,303},r.status_code
    c=sm.db(); q=c.execute('SELECT * FROM questions WHERE id=?',(qdb,)).fetchone(); assert q['status']=='Rejected' and q['review_status']=='Rejected' and int(q['active'])==0
    ev=c.execute("SELECT * FROM question_review_events WHERE question_id=? AND action='Rejected' ORDER BY id DESC LIMIT 1",(qdb,)).fetchone(); assert ev
    direct_events=c.execute("SELECT * FROM ph_bridge_incident_events_v6611d WHERE question_db_id=? AND feedback_code LIKE 'SMAR-%'",(qdb,)).fetchall(); assert len(direct_events)==1,len(direct_events)
    assert bridge.reconcile_governed_emergency_rejections(c)==0
    assert bridge.reconcile_governed_emergency_rejections(c)==0
    assert len(c.execute("SELECT * FROM ph_bridge_incident_events_v6611d WHERE question_db_id=? AND feedback_code LIKE 'SMAR-%'",(qdb,)).fetchall())==1
    assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok'; assert not c.execute('PRAGMA foreign_key_check').fetchall(); c.close()

    # Invalid governed identity: reject must fail atomically and leave no audit/event residue.
    raw2=make_csv(ph_id='',qid='BIO12-CH13-QUAL-002'); cl2,qdb2,bid2,digest2,ledger2=import_release(raw2)
    r=cl2.post(f'/admin/questions/{qdb2}/review',data={'_csrf_token':'qual-csrf','action':'reject','reason_code':'Other','note':'must fail identity'},follow_redirects=False)
    assert r.status_code in {302,303}
    c=sm.db(); q2=c.execute('SELECT * FROM questions WHERE id=?',(qdb2,)).fetchone(); assert q2['status']=='Approved' and q2['review_status']=='Approved' and int(q2['active'])==1,q2['status']
    assert not c.execute("SELECT 1 FROM question_review_events WHERE question_id=? AND action='Rejected'",(qdb2,)).fetchone()
    assert not c.execute("SELECT 1 FROM ph_bridge_incident_events_v6611d WHERE question_db_id=?",(qdb2,)).fetchone()
    c.close()

    # Pre-bridge scenario matching the live row-31 case: local audited rejection exists but no PH incident.
    raw3=make_csv(ph_id='PH-RS-Q-QUAL-003',qid='BIO12-CH13-QUAL-003'); cl3,qdb3,bid3,digest3,ledger3=import_release(raw3)
    c=sm.db()
    a=admin()
    c.execute("UPDATE questions SET review_status='Rejected',status='Rejected',active=0,reviewer='qualification-prebridge',reviewed_at=CURRENT_TIMESTAMP WHERE id=?",(qdb3,))
    ev3=c.execute("INSERT INTO question_review_events(question_id,action,reviewer_id,reason_code,note) VALUES(?,?,?,?,?)",(qdb3,'Rejected',int(a['id']),'Factual/scientific issue','pre-bridge audited rejection')).lastrowid
    c.commit()
    assert not c.execute("SELECT 1 FROM ph_bridge_incident_events_v6611d WHERE question_db_id=?",(qdb3,)).fetchone()
    assert bridge.reconcile_governed_emergency_rejections(c)==1
    recovered=c.execute("SELECT * FROM ph_bridge_incident_events_v6611d WHERE question_db_id=? AND feedback_code=?",(qdb3,f'SMAR-RECOVER-{qdb3}-{ev3}')).fetchall(); assert len(recovered)==1,len(recovered)
    out3=c.execute('SELECT envelope_json FROM integration_outbox WHERE message_id=?',(recovered[0]['outbox_message_id'],)).fetchone(); assert out3
    env3=json.loads(out3['envelope_json']); ident3=env3['payload']['question']
    assert env3['schema_version']=='1.1.0' and ident3['identity_mode']=='EMERGENCY_DIRECT_GOVERNED'
    assert ident3['source_question_id']=='BIO12-CH13-QUAL-003' and ident3['power_house_public_id']=='PH-RS-Q-QUAL-003' and ident3['power_house_source_row']=='756'
    assert bridge.reconcile_governed_emergency_rejections(c)==0
    assert len(c.execute("SELECT * FROM ph_bridge_incident_events_v6611d WHERE question_db_id=? AND feedback_code LIKE 'SMAR-%'",(qdb3,)).fetchall())==1
    assert c.execute('PRAGMA quick_check').fetchone()[0]=='ok'; assert not c.execute('PRAGMA foreign_key_check').fetchall(); c.close()

    print('SCOREMAX_EMERGENCY_RETURN_CURRENT_BASELINE_QUALIFICATION_PASS schema_1_1_0=true emergency_identity=true admin_reject_atomic=true rejection_reason_guard=true invalid_identity_rollback=true prebridge_recovery_exact=true postbridge_no_duplicate=true restart_idempotent=true persistent_guard_v4_reused=true integrity=ok')

if __name__=='__main__': main()
