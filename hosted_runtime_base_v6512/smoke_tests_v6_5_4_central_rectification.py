"""ScoreMax V6.5.4 central-admission rectification adversarial checks.

Disposable DB only. Covers the three new P1 classes plus adjacent strict-JSON and migration risks.
"""
from __future__ import annotations
from release_compatibility import is_compatible_descendant
import json, os, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib import error as urlerror

TMP=Path(tempfile.mkdtemp(prefix='scoremax_v654_rect_'))
os.environ.update({
    'SCOREMAX_DB':str(TMP/'scoremax.db'),
    'SCOREMAX_SECRET':'V654-Central-Rectification-Disposable-Secret',
    'SCOREMAX_ENV':'test','SCOREMAX_ENFORCE_PAYWALL':'0','SCOREMAX_INTERNAL_FULL_ACCESS':'1',
    'SCOREMAX_GROWTH_ENGINE_BASE_URL':'https://growth.example',
    'SCOREMAX_TO_GROWTH_ENGINE_TOKEN':'v654-growth-token-long-enough',
    'SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET':'v654-growth-secret-long-enough-for-hmac',
    'POWER_HOUSE_TO_SCOREMAX_TOKEN':'v654-ph-token-long-enough',
    'POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET':'v654-ph-secret-long-enough-for-hmac',
    'SCOREMAX_POWER_HOUSE_BASE_URL':'https://powerhouse.example',
    'SCOREMAX_TO_POWER_HOUSE_TOKEN':'v654-sm-ph-token-long-enough',
    'SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET':'v654-sm-ph-secret-long-enough-for-hmac',
})
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import scoremax_integration_v1 as integ
app.init(); c=app.db(); integ.init_schema(c); c.commit()

N=0
def ok(name,cond):
    global N
    if not cond: raise AssertionError(name)
    N+=1; print('PASS:',name)

def counts():
    out={}
    for t in ('integration_outbox','integration_quarantine','integration_receipts','integration_inbound_messages','integration_transport_diagnostics'):
        out[t]=int(c.execute(f'SELECT COUNT(*) n FROM {t}').fetchone()['n'])
    return out

def strict_load(s):
    return json.loads(s,parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))

ok('V6.5.4 rectification remains active in V6.5.6',is_compatible_descendant(app.SCOREMAX_RELEASE_VERSION,'6.5.4') and is_compatible_descendant(integ.SCOREMAX_INTEGRATION_RELEASE,'6.5.4'))
cols=lambda t:{r['name'] for r in c.execute(f'PRAGMA table_info({t})')}
ok('retry-cycle lineage columns exist',{'retry_cycle'}<=cols('integration_outbox') and {'retry_cycle'}<=cols('integration_dispatch_attempts') and {'prior_attempt_count','new_retry_cycle'}<=cols('integration_requeue_audit'))
ok('transport diagnostic store exists',bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='integration_transport_diagnostics'").fetchone()))

# Strict recursive JSON: NaN, +Inf and -Inf must fail before durable integration effects.
for label,val in [('NaN',float('nan')),('+Infinity',float('inf')),('-Infinity',float('-inf'))]:
    before=counts(); threw=False
    try:
        integ.queue_product_event(c,event_type='LEARNER_REGISTERED',event_id='STRICT-'+label,
            context={'nested':[{'x':val}]},event_data={'metadata':{'poison':[1,{'v':val}]}})
        c.commit()
    except Exception:
        threw=True; c.rollback()
    ok(f'{label} rejected recursively',threw)
    ok(f'{label} creates zero durable integration side effects',counts()==before)
    for raw in (f'{{"x":{label if label=="NaN" else ("Infinity" if label=="+Infinity" else "-Infinity")}}}',):
        failed=False
        try: integ.strict_json_loads(raw)
        except Exception: failed=True
        ok(f'{label} rejected by strict peer JSON parser',failed)

# Governed requeue starts a new active cycle while preserving immutable prior attempts.
mid=integ.queue_product_event(c,event_type='LEARNER_REGISTERED',event_id='REQUEUE-V654-1',event_data={'metadata':{'case':'cycle'}}); c.commit()
r=c.execute('SELECT * FROM integration_outbox WHERE message_id=?',(mid,)).fetchone(); oid=int(r['id'])
exhausted=len(integ.RETRY_DELAYS)
c.execute("UPDATE integration_outbox SET status='DEAD_LETTER',attempt_count=?,retry_cycle=0,last_error_code='TRANSPORT_ERROR',last_error='prior cycle exhausted' WHERE id=?",(exhausted,oid))
for i in range(exhausted):
    c.execute("INSERT INTO integration_dispatch_attempts(outbox_id,attempted_at,retry_cycle,http_status,result_status,error_code,error_text,response_json) VALUES(?,?,?,?,?,?,?,?)",
      (oid,integ.utcnow(),0,503,'RETRY' if i<exhausted-1 else 'DEAD_LETTER','HTTP_503','prior cycle','{}'))
c.commit()
prior_rows=[dict(x) for x in c.execute('SELECT * FROM integration_dispatch_attempts WHERE outbox_id=? ORDER BY id',(oid,)).fetchall()]
ok('governed requeue accepted',integ.requeue_outbox(c,oid,actor='V654_TEST',reason='fresh cycle'))
after=dict(c.execute('SELECT status,attempt_count,retry_cycle,message_id,idempotency_key,payload_checksum_sha256,envelope_json FROM integration_outbox WHERE id=?',(oid,)).fetchone())
ok('requeue resets active counter only',after['status']=='PENDING' and after['attempt_count']==0 and after['retry_cycle']==1)
aud=dict(c.execute('SELECT * FROM integration_requeue_audit WHERE outbox_id=? ORDER BY id DESC LIMIT 1',(oid,)).fetchone())
ok('requeue audit preserves exhausted prior count and new cycle',aud['prior_attempt_count']==exhausted and aud['new_retry_cycle']==1)
ok('message identity and envelope retained on requeue',after['message_id']==mid and after['envelope_json']==r['envelope_json'] and after['payload_checksum_sha256']==r['payload_checksum_sha256'])

orig=integ.urlrequest.urlopen; integ.urlrequest.urlopen=lambda *a,**k: (_ for _ in ()).throw(urlerror.URLError('simulated outage'))
try: result=integ.dispatch_due(c,limit=1,timeout=1)
finally: integ.urlrequest.urlopen=orig
post=dict(c.execute('SELECT status,attempt_count,retry_cycle,next_attempt_at,last_error_code FROM integration_outbox WHERE id=?',(oid,)).fetchone())
ok('first failure in new cycle is RETRY not terminal',post['status']=='RETRY' and post['attempt_count']==1 and post['retry_cycle']==1 and result['retrying']==1 and result['dead_letter']==0)
new_rows=[dict(x) for x in c.execute('SELECT * FROM integration_dispatch_attempts WHERE outbox_id=? ORDER BY id',(oid,)).fetchall()]
ok('prior dispatch attempt rows remain unchanged',new_rows[:len(prior_rows)]==prior_rows)
ok('new attempt is appended with new cycle lineage',len(new_rows)==len(prior_rows)+1 and int(new_rows[-1]['retry_cycle'])==1)
# Keep it out of the next claim set.
c.execute("UPDATE integration_outbox SET status='DEAD_LETTER' WHERE id=?",(oid,)); c.commit()

# Invalid peer receipt JSON must not be persisted raw; only standards-compliant redacted evidence may be stored.
mid2=integ.queue_product_event(c,event_type='LEARNER_REGISTERED',event_id='BAD-PEER-JSON-V654',event_data={'metadata':{'case':'peer'}}); c.commit()
class FakeResponse:
    status=202
    def read(self): return b'{"status":"ACCEPTED","poison":NaN}'
integ.urlrequest.urlopen=lambda *a,**k: FakeResponse()
try: integ.dispatch_due(c,limit=1,timeout=1)
finally: integ.urlrequest.urlopen=orig
r2=dict(c.execute('SELECT * FROM integration_outbox WHERE message_id=?',(mid2,)).fetchone())
a2=dict(c.execute('SELECT * FROM integration_dispatch_attempts WHERE outbox_id=? ORDER BY id DESC LIMIT 1',(r2['id'],)).fetchone())
ok('invalid peer JSON becomes retryable transport evidence',r2['status']=='RETRY' and r2['last_error_code']=='INVALID_PEER_JSON')
parsed=strict_load(a2['response_json'])
ok('invalid peer JSON body is never persisted as non-standard JSON',parsed.get('parse_status')=='INVALID_OR_NON_STANDARD_JSON' and 'body_sha256' in parsed and 'NaN' not in a2['response_json'])
c.execute("UPDATE integration_outbox SET status='DEAD_LETTER' WHERE id=?",(r2['id'],)); c.commit()

# Exact V6.5.3-style unsafe stored envelope is retained for audit but quarantined on init/reconciliation.
legacy_mid='msg::SM_GE_PRODUCT_EVENT_V1::LEGACY-NAN'
legacy_env='{"message_id":"%s","contract_name":"SM_GE_PRODUCT_EVENT_V1","payload":{"metadata":{"x":NaN}}}'%legacy_mid
c.execute("INSERT INTO integration_outbox(message_id,contract_name,destination_system,idempotency_key,business_identity,payload_checksum_sha256,envelope_json,status,attempt_count,retry_cycle,next_attempt_at,created_at) VALUES(?,?,?,?,?,?,?,'PENDING',0,0,?,?)",
  (legacy_mid,'SM_GE_PRODUCT_EVENT_V1','GROWTH_ENGINE','legacy-nan-v653','legacy-nan-v653','0'*64,legacy_env,integ.utcnow(),integ.utcnow()))
c.commit(); integ.init_schema(c); c.commit()
legacy=dict(c.execute('SELECT status,last_error_code,envelope_json FROM integration_outbox WHERE message_id=?',(legacy_mid,)).fetchone())
ok('legacy permissive-JSON row is quarantined before dispatch',legacy['status']=='QUARANTINED' and legacy['last_error_code']=='MIGRATION_NON_STANDARD_JSON')
ok('legacy invalid envelope bytes remain unchanged for audit',legacy['envelope_json']==legacy_env)
qrow=c.execute("SELECT payload_json FROM integration_quarantine WHERE reason_code='MIGRATION_NON_STANDARD_JSON' AND identity_key='legacy-nan-v653'").fetchone()
ok('migration quarantine evidence itself is strict JSON',bool(qrow) and isinstance(strict_load(qrow['payload_json']),dict))

# Frozen health minimum: fields exist and reconcile to durable receive/error/warning evidence.
REQUIRED={'direction','contract','connection_state','last_success_at','last_received_at','last_dispatched_at','queued_count','retrying_count','dead_letter_count','quarantined_count','oldest_queued_at','last_error_code','last_error_at','local_schema_version','peer_schema_version','peer_version','credential_expiry_warning','clock_skew_warning'}
now=integ.utcnow(); rid='RCPT::V654::HEALTH'; msg='MSG::V654::HEALTH'
c.execute("INSERT OR IGNORE INTO integration_receipts(receipt_id,message_id,contract_name,receiver_system,received_at,status,duplicate_of_receipt_id,accepted_schema_version,payload_checksum_sha256,errors_json) VALUES(?,?,?,?,?,'ACCEPTED',NULL,'1.1.0',?,'[]')",(rid,msg,'PH_SM_APPROVED_CONTENT_V1','SCOREMAX',now,'1'*64))
c.execute("INSERT OR IGNORE INTO integration_inbound_messages(message_id,contract_name,source_system,idempotency_key,payload_checksum_sha256,first_received_at,last_received_at,receive_count,receipt_id,status) VALUES(?,?,?,?,?,?,?,?,?,'ACCEPTED')",(msg,'PH_SM_APPROVED_CONTENT_V1','POWER_HOUSE','health-v654','1'*64,now,now,1,rid))
integ.record_transport_diagnostic(c,'PH_SM_APPROVED_CONTENT_V1','POWER_HOUSE -> SCOREMAX','STALE_OR_INVALID_SENT_AT')
os.environ['POWER_HOUSE_TO_SCOREMAX_CREDENTIAL_EXPIRES_AT']=(datetime.now(timezone.utc)+timedelta(hours=24)).replace(microsecond=0).isoformat().replace('+00:00','Z')
c.commit()
health=integ.integration_health(c); by={d['contract']:d for d in health['directions']}
ok('every frozen health direction has complete minimum field contract',all(REQUIRED<=set(d) for d in health['directions']))
h=by['PH_SM_APPROVED_CONTENT_V1']
ok('health last_received_at reconciles to durable inbox',h['last_received_at']==now)
ok('health peer schema reconciles to durable receipt',h['peer_schema_version']=='1.1.0')
ok('health clock skew warning reconciles to durable diagnostic',h['clock_skew_warning']=='STALE_OR_INVALID_SENT_AT' and h['last_error_code']=='STALE_OR_INVALID_SENT_AT')
ok('health credential expiry warning is truthful when configured',h['credential_expiry_warning']=='CREDENTIAL_EXPIRES_SOON')
ok('health compatibility alias preserves oldest backlog field',all(d.get('oldest_backlog_at')==d.get('oldest_queued_at') for d in health['directions']))

integrity=c.execute('PRAGMA integrity_check').fetchone()[0]; fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
ok('V6.5.4 rectification DB integrity remains clean',integrity=='ok' and fk==0)
print(f'\nSCOREMAX V6.5.4 CENTRAL RECTIFICATION CHECKS PASSED: {N}')
print('Disposable database:',TMP/'scoremax.db')
c.close()
