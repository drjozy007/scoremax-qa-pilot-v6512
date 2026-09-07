from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

RUNTIME=Path(os.environ.get('V6611D_RUNTIME','scoremax_runtime_v669b')).resolve()
if str(RUNTIME) not in sys.path:
    sys.path.insert(0,str(RUNTIME))

integration=importlib.import_module('scoremax_integration_v1')
bridge=importlib.import_module('scoremax_ph_bridge_v6611d')
bridge.install(integration)


def _bootstrap_core_scoremax_schema(c):
    """Minimal real-app core tables that integration.init_schema() additively extends."""
    c.executescript('''
      CREATE TABLE IF NOT EXISTS assessment_sessions(id INTEGER PRIMARY KEY);
      CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,student_id INTEGER);
      CREATE TABLE IF NOT EXISTS attempt_answers(id INTEGER PRIMARY KEY,attempt_id INTEGER,question_db_id INTEGER,selected_answer TEXT,is_correct INTEGER);
      CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY,question_id TEXT UNIQUE,question TEXT DEFAULT '',active INTEGER DEFAULT 1,status TEXT DEFAULT 'Approved');
    ''')


def conn(tmp_path):
    c=sqlite3.connect(tmp_path/'bridge.db')
    c.row_factory=sqlite3.Row
    _bootstrap_core_scoremax_schema(c)
    integration.init_schema(c)
    bridge.init_schema(c)
    return c


def envelope(contract,source,destination,payload,*,mid='MSG-1',idem='IDEM-1'):
    now='2026-09-07T12:00:00Z'
    return {'message_id':mid,'contract_name':contract,'contract_version':'1','schema_version':'1.0.0','source_system':source,'destination_system':destination,'occurred_at':now,'sent_at':now,'correlation_id':'CORR-1','idempotency_key':idem,'producer_version':'TEST','retry_of_message_id':None,'payload_checksum_sha256':integration.payload_checksum(payload),'data_classification':'INTERNAL','payload':payload}


def ensure_question_table(c):
    assert c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='questions'").fetchone()


def insert_release(c,rid='REL-1',ver='1',checksum='a'*64):
    cols={r['name'] for r in c.execute('PRAGMA table_info(integration_ph_content_releases)').fetchall()}
    values={
      'release_id':rid,'release_version':ver,'package_checksum_sha256':checksum,
      'manifest_checksum_sha256':'9'*64,'payload_checksum_sha256':'b'*64,
      'release_status':'ACADEMICALLY_READY','local_status':'STAGED',
      'market_id':'PK','programme_id':'FSC2','subject_id':'BIOLOGY','chapter_id':'CH19',
      'immutable_payload_json':'{}','admitted_at':'2026-09-07T12:00:00Z','release_operation':'PUBLISH_SNAPSHOT',
      'schema_version':'1.0.0','semantic_checksum_sha256':'c'*64,
    }
    use=[k for k in values if k in cols]
    c.execute(f"INSERT INTO integration_ph_content_releases({','.join(use)}) VALUES({','.join('?' for _ in use)})",[values[k] for k in use])
    c.execute('INSERT INTO integration_ph_release_question_membership(release_id,release_version,question_id,question_version_id,ordinal,admitted_at) VALUES(?,?,?,?,?,?)',(rid,ver,'Q-1','QV-1',1,'2026-09-07T12:00:00Z'))


def test_marker_and_release_identity():
    assert bridge.MARKER=='SM-PH-BRIDGE-V6611D-1'
    assert bridge.RELEASE=='6.6.11D'
    assert integration.SCOREMAX_INTEGRATION_RELEASE=='6.6.11D'
    marker=json.loads((RUNTIME/'V6611D_PH_BRIDGE_MARKER.json').read_text())
    assert marker['parent_runtime_tree_sha256']=='0d2d399dcb6a23591a00b05d827a00804094cc17f94a676494b285eca4c79e5a'
    assert marker['release_authority_changed'] is False
    assert marker['cross_system_calls_on_learner_request'] is False


def test_new_dispatch_targets(monkeypatch):
    monkeypatch.setenv('SCOREMAX_POWER_HOUSE_BASE_URL','https://powerhouse.example.test')
    expected={bridge.DELIVERY_ACK:'/api/integration/v1/scoremax/content-delivery-acks',bridge.INCIDENT:'/api/integration/v1/scoremax/content-incidents',bridge.WITHDRAWAL_ACK:'/api/integration/v1/scoremax/question-withdrawal-acks'}
    for contract,path in expected.items():
        url,got,direction=integration._dispatch_target(contract)
        assert got==path and url=='https://powerhouse.example.test'+path and direction=='SCOREMAX_TO_POWER_HOUSE'


def test_delivery_ack_idempotent(tmp_path):
    c=conn(tmp_path); ensure_question_table(c); insert_release(c)
    m1=bridge._queue_delivery_state(c,'REL-1','1','IMPORTED_STAGED')
    m2=bridge._queue_delivery_state(c,'REL-1','1','IMPORTED_STAGED')
    m3=bridge._queue_delivery_state(c,'REL-1','1','ACTIVATED_LEARNER_LIVE')
    assert m1==m2 and m1 and m3 and m3!=m1
    assert c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name=?",(bridge.DELIVERY_ACK,)).fetchone()['n']==2
    rows=c.execute("SELECT envelope_json FROM integration_outbox WHERE contract_name=? ORDER BY id",(bridge.DELIVERY_ACK,)).fetchall()
    payloads=[json.loads(r['envelope_json'])['payload'] for r in rows]
    assert {p['delivery_state'] for p in payloads}=={'IMPORTED_STAGED','ACTIVATED_LEARNER_LIVE'}
    assert all(p['release_authority_conferred'] is False for p in payloads)
    assert all(p['package_checksum_sha256']=='a'*64 for p in payloads)
    c.close()


def ph_question_row(c,*,ph=True):
    ensure_question_table(c); owner='POWER_HOUSE' if ph else ''
    c.execute('''INSERT INTO questions(question_id,question,active,status,ph_projection_owner,ph_question_id,ph_question_version_id,ph_question_checksum_sha256,ph_release_id,ph_release_version,ph_release_checksum_sha256,ph_market_id,ph_programme_id,ph_subject_id,ph_chapter_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',('LOCAL-1','What is immunity?',1,'Approved',owner,'PH-Q-1' if ph else '','PH-QV-1' if ph else '','d'*64 if ph else '','PH-REL-1' if ph else '','1' if ph else '','e'*64 if ph else '','PK' if ph else '','FSC2' if ph else '','BIOLOGY' if ph else '','CH19' if ph else ''))
    return c.execute('SELECT * FROM questions WHERE question_id=?',('LOCAL-1',)).fetchone()


def test_non_ph_report_does_not_queue_incident(tmp_path):
    c=conn(tmp_path); q=ph_question_row(c,ph=False)
    out=bridge.queue_reported_question_incident(c,q,'FDB-LOCAL','Incorrect question','HIGH','This question is incorrect.',{'page':'/test/1'})
    assert out==''
    assert c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name=?",(bridge.INCIDENT,)).fetchone()['n']==0
    c.close()


def test_ph_incident_exact_lineage_idempotent_and_privacy_minimised(tmp_path):
    c=conn(tmp_path); q=ph_question_row(c,ph=True)
    description='Wrong answer. Contact me at learner@example.com or +44 7700 900123 please.'
    context={'source':'assessment_question','page':'https://scoremax.example/test/42?student=SECRET#anchor'}
    m1=bridge.queue_reported_question_incident(c,q,'FDB-PH-1','Wrong answer','CRITICAL',description,context)
    m2=bridge.queue_reported_question_incident(c,q,'FDB-PH-1','Wrong answer','CRITICAL',description,context)
    assert m1==m2 and m1
    assert c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name=?",(bridge.INCIDENT,)).fetchone()['n']==1
    env=json.loads(c.execute("SELECT envelope_json FROM integration_outbox WHERE contract_name=?",(bridge.INCIDENT,)).fetchone()['envelope_json']); p=env['payload']; qp=p['question']
    assert qp['question_id']=='PH-Q-1' and qp['question_version_id']=='PH-QV-1' and qp['question_checksum_sha256']=='d'*64
    assert qp['release_id']=='PH-REL-1' and qp['release_checksum_sha256']=='e'*64
    assert p['reporter_identity_included'] is False and p['student_pii_included'] is False and p['release_authority_conferred'] is False
    assert 'learner@example.com' not in p['description'] and '[redacted-email]' in p['description']
    assert '7700' not in p['description'] and '[redacted-phone]' in p['description']
    assert p['page_path']=='/test/42' and 'SECRET' not in json.dumps(env)
    c.close()


def withdrawal_payload(qid='PH-Q-1',item='ITEM-1',export='EXP-1'):
    row={'item_public_id':item,'withdrawal_queue_id':1,'question_public_id':qid,'question_version_fingerprint':'PH-QV-1','hold_id':2,'defect_code':'SCOREMAX_LEARNER_REPORTED_CONTENT_INCIDENT','reason':'Governed fail-close test','requested_action':'STOP_FUTURE_DELIVERY_PRESERVE_HISTORICAL_ATTEMPTS','historical_attempts_must_be_preserved':True,'item_sha256':'f'*64}
    return {'export_public_id':export,'population_sha256':'1'*64,'items':[row],'release_authority_conferred':False}


def test_withdrawal_stops_future_delivery_and_preserves_history(tmp_path):
    c=conn(tmp_path); q=ph_question_row(c,ph=True)
    c.execute("INSERT INTO attempts(id,student_id) VALUES(1,77)")
    c.execute("INSERT INTO attempt_answers(id,attempt_id,question_db_id,selected_answer,is_correct) VALUES(1,1,?,?,?)",(q['id'],'A',1))
    before_attempts=c.execute('SELECT COUNT(*) n FROM attempts').fetchone()['n']; before_answers=c.execute('SELECT COUNT(*) n FROM attempt_answers').fetchone()['n']
    p=withdrawal_payload(); env=envelope(bridge.WITHDRAWAL,'POWER_HOUSE','SCOREMAX',p,mid='WD-1',idem='WD-IDEM-1')
    rec,status=bridge.admit_withdrawal_envelope(c,env,env['payload_checksum_sha256'])
    assert status==202 and rec['status']=='ACCEPTED'
    q2=c.execute("SELECT active,status FROM questions WHERE id=?",(q['id'],)).fetchone(); assert q2['active']==0 and q2['status']=='Withdrawn'
    assert c.execute('SELECT COUNT(*) n FROM attempts').fetchone()['n']==before_attempts and c.execute('SELECT COUNT(*) n FROM attempt_answers').fetchone()['n']==before_answers
    ack=json.loads(c.execute("SELECT envelope_json FROM integration_outbox WHERE contract_name=?",(bridge.WITHDRAWAL_ACK,)).fetchone()['envelope_json'])['payload']
    assert ack['items'][0]['state']=='WITHDRAWN' and ack['items'][0]['historical_attempts_preserved'] is True and ack['release_authority_conferred'] is False
    c.close()


def test_withdrawal_exact_export_replay_is_duplicate_without_mutation(tmp_path):
    c=conn(tmp_path); q=ph_question_row(c,ph=True); p=withdrawal_payload(); env=envelope(bridge.WITHDRAWAL,'POWER_HOUSE','SCOREMAX',p,mid='WD-1',idem='WD-IDEM-1')
    r1,s1=bridge.admit_withdrawal_envelope(c,env,env['payload_checksum_sha256']); r2,s2=bridge.admit_withdrawal_envelope(c,env,env['payload_checksum_sha256'])
    assert (s1,r1['status'])==(202,'ACCEPTED') and (s2,r2['status'])==(200,'DUPLICATE')
    assert c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name=?",(bridge.WITHDRAWAL_ACK,)).fetchone()['n']==1
    assert c.execute("SELECT active FROM questions WHERE id=?",(q['id'],)).fetchone()['active']==0
    c.close()


def test_unknown_withdrawal_returns_not_present(tmp_path):
    c=conn(tmp_path); ensure_question_table(c); p=withdrawal_payload(qid='PH-Q-NOT-HERE',item='ITEM-X',export='EXP-X'); env=envelope(bridge.WITHDRAWAL,'POWER_HOUSE','SCOREMAX',p,mid='WD-X',idem='WD-X')
    rec,status=bridge.admit_withdrawal_envelope(c,env,env['payload_checksum_sha256'])
    assert status==202 and rec['status']=='ACCEPTED'
    out=json.loads(c.execute("SELECT envelope_json FROM integration_outbox WHERE contract_name=?",(bridge.WITHDRAWAL_ACK,)).fetchone()['envelope_json'])
    assert out['payload']['items'][0]['state']=='NOT_PRESENT'
    c.close()
