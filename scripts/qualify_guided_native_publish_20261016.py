"""Admit actual native publisher artifacts into a disposable production-derived DB."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

p=argparse.ArgumentParser()
p.add_argument('--ph-db',required=True)
p.add_argument('--sm-backup',required=True)
p.add_argument('--work',required=True)
a=p.parse_args()
work=Path(a.work).resolve();work.mkdir(parents=True,exist_ok=True)
target=work/'scoremax_qualification.db'
assert not target.exists(), 'Use a fresh disposable qualification directory'
with sqlite3.connect('file:'+str(Path(a.sm_backup).resolve())+'?mode=ro',uri=True) as src,sqlite3.connect(target) as dst:
    src.backup(dst)
for key in tuple(os.environ):
    if key.startswith(('SCOREMAX_','POWER_HOUSE_','GROWTH_ENGINE_')):del os.environ[key]
os.environ.update(SCOREMAX_ENV='production',SCOREMAX_SECRET='disposable-native-guided-qualification-only',
    SCOREMAX_STAGING_SESSION_SECRET='disposable-native-guided-qualification-only',
    SCOREMAX_DB=str(target),SCOREMAX_PERSISTENT_ROOT=str(work),SCOREMAX_BACKUP_DIR=str(work/'backup'),
    SCOREMAX_CONTENT_INTAKE_DIR=str(work/'intake'),SCOREMAX_PUBLIC_BASE_URL='https://localhost',
    SCOREMAX_SMTP_HOST='smtp.invalid',SCOREMAX_SMTP_FROM='qualification@scoremax.test',
    SCOREMAX_INSTANCE_COUNT='1',WEB_CONCURRENCY='1',SCOREMAX_REQUIRE_EMAIL_VERIFICATION='0',
    SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD='Disposable-Qualification-Only-20261016!')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scoremax_runtime_v669b'))
import scoremax_production
import app as sm
import scoremax_integration_v1 as receiver
import guided_self_assessment as guided

def fingerprint(c,table):
    rows=[tuple(r) for r in c.execute('SELECT * FROM "'+table+'" ORDER BY rowid')]
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),default=str).encode()).hexdigest()

with sm.db() as c:
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    protected=[t for t in tables if t in {'users','questions','attempts','attempt_answers','assessment_sessions','written_marking_runs','written_mastery_evidence','mastery_form_results','integration_ph_product_activation_authorizations'}]
    before={t:fingerprint(c,t) for t in protected}
    releases=[tuple(r) for r in c.execute('SELECT * FROM integration_ph_content_releases ORDER BY id')]
    versions=c.execute('SELECT COUNT(*) FROM integration_ph_question_version_store').fetchone()[0]
    memberships=c.execute('SELECT COUNT(*) FROM integration_ph_release_question_membership').fetchone()[0]
    report=[]
    ph=sqlite3.connect('file:'+str(Path(a.ph_db).resolve())+'?mode=ro',uri=True);ph.row_factory=sqlite3.Row
    for row in ph.execute("SELECT o.id,o.envelope_json,a.archive_blob FROM integration_outbox_v1 o JOIN integration_content_releases_v1 r ON json_extract(o.envelope_json,'$.payload.release.release_id')=r.release_id AND json_extract(o.envelope_json,'$.payload.release.release_version')=r.release_version JOIN integration_content_artifacts_v013c a ON a.release_db_id=r.id WHERE r.release_version='2026.10.14.1' ORDER BY o.id"):
        envelope=json.loads(row['envelope_json']);blob=bytes(row['archive_blob'])
        with patch.object(receiver,'_download_manifest_package',return_value=blob):
            receipt,status=receiver.admit_content_envelope(c,envelope,envelope['payload_checksum_sha256']);c.commit()
            (work/('outbox_'+str(row['id'])+'_receipt.json')).write_text(json.dumps(receipt,indent=2))
            assert status==202,(status,receipt.get('status'),[e.get('code') for e in receipt.get('errors',[])])
            replay,replay_status=receiver.admit_content_envelope(c,envelope,envelope['payload_checksum_sha256']);c.commit()
            assert replay_status in (200,202) and replay['receipt_id']==receipt['receipt_id'],(replay_status,replay.get('status'))
        report.append({'outbox_id':row['id'],'status':status,'receipt_id':receipt['receipt_id'],'replay_same_receipt':True})
    assert len(report)==4,report
    assert c.execute('SELECT COUNT(*) FROM integration_ph_question_version_store').fetchone()[0]-versions==600
    assert c.execute('SELECT COUNT(*) FROM integration_ph_release_question_membership').fetchone()[0]-memberships==1108
    amended=0;checked=0
    for row in c.execute("SELECT v.* FROM integration_ph_question_version_store v WHERE EXISTS (SELECT 1 FROM integration_ph_release_question_membership m WHERE m.question_version_id=v.question_version_id AND m.release_version='2026.10.14.1')"):
        q=receiver.effective_projection(json.loads(row['scoremax_projection_json']),json.loads(row['content_json']))
        contract=guided.from_question(q);assert contract and not q['ph_is_auto_markable']
        assert contract['authority']==guided.AUTHORITY
        amended+=bool(contract.get('learner_amendments'));checked+=1
    assert checked==600 and amended==2,(checked,amended)
    assert before=={t:fingerprint(c,t) for t in protected}
    assert not c.execute("SELECT 1 FROM integration_ph_content_releases WHERE local_status='ACTIVE'").fetchone()
    for row in releases:
        assert row==tuple(c.execute('SELECT * FROM integration_ph_content_releases WHERE id=?',(row[0],)).fetchone())
    ph.close()
result={'passed':True,'unique_questions':checked,'additional_mdcat_placements':508,'memberships':1108,
    'approved_existing_hygiene_amendments':amended,'protected_tables_unchanged':protected,
    'previous_releases_unchanged':len(releases),'learner_activation':False,'production_mutations':False,
    'transport':'actual native MANIFEST_PULL artifacts; network download replaced by exact stored archive bytes',
    'releases':report}
(work/'qualification.json').write_text(json.dumps(result,indent=2))
print('GUIDED_NATIVE_PRODUCTION_DERIVED_PASS',json.dumps(result,sort_keys=True))
