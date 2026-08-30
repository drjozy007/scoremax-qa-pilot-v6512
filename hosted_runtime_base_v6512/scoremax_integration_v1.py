"""ScoreMax V6.5.6 — governed three-system integration adapter (frozen contract v1).

This module implements ScoreMax's side only:
- Power House -> ScoreMax approved content and blueprint admission
- ScoreMax -> Power House aggregate delivery evidence / content requirements
- ScoreMax -> Growth Engine product/payment/referral events
- scoped service authentication, HMAC integrity, idempotency, retry/outbox, quarantine and health

V6.5.3 closes the admission defects by compiling frozen contract payloads into the existing
ScoreMax runtime, while retaining immutable source payloads and explicit quarantine/rejection
when a governed capability cannot be delivered safely.
"""
from __future__ import annotations
import copy, hashlib, hmac, json, os, sqlite3, time, uuid, logging, io, zipfile, re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib import request as urlrequest, error as urlerror
from urllib.parse import urlparse
from jsonschema import Draft202012Validator, FormatChecker

CONTRACT_VERSION='1'
SCHEMA_VERSION='1.0.0'
RECTIFIED_SCHEMA_VERSION='1.1.0'
SCOREMAX_INTEGRATION_RELEASE='6.5.10'
RECEIVER='SCOREMAX'
RETRY_DELAYS=[0,60,300,1800,7200,43200]
MIN_EVIDENCE_N=int(os.environ.get('SCOREMAX_INTEGRATION_MIN_EVIDENCE_N','10') or 10)
SUPPORTED_LIVE_KEY_TYPES={'SINGLE_OPTION','MULTIPLE_OPTIONS','TEXT','NUMERIC','BOOLEAN'}
SUPPORTED_BLUEPRINT_QUESTION_TYPES={
    'SINGLE_BEST_ANSWER':'single_choice','MCQ':'single_choice','SINGLE_CHOICE':'single_choice',
    'TRUE_FALSE':'true_false','TRUE/FALSE':'true_false','BOOLEAN':'true_false',
    'MULTIPLE_SELECT':'multiple_select','MULTIPLE_OPTIONS':'multiple_select',
    'NUMERIC_RESPONSE':'numerical','NUMERICAL':'numerical','NUMERIC':'numerical',
    'TEXT':'fill_blank','FILL_BLANK':'fill_blank','FILL_IN_THE_BLANK':'fill_blank',
}


def utcnow():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def parse_dt(v):
    if not v: return None
    try:
        return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except Exception:
        return None

def canonical_json(value):
    """Standards-compliant canonical JSON for every integration hash/store/send boundary."""
    try:
        return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
    except (ValueError,TypeError) as exc:
        raise ValueError('Integration JSON must contain only standards-compliant finite JSON values') from exc

def strict_json_loads(value):
    """Parse peer JSON while rejecting NaN/+Infinity/-Infinity tokens recursively."""
    def reject_constant(token):
        raise ValueError('Non-finite JSON numeric token is not permitted: '+str(token))
    return json.loads(value,parse_constant=reject_constant)

def sha256_text(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()

def payload_checksum(payload):
    return hashlib.sha256(canonical_json(payload).encode('utf-8')).hexdigest()

def semantic_checksum(value, excluded_fields=()):
    """Canonical checksum owned by ScoreMax, independent of caller-supplied checksum fields."""
    excluded=set(excluded_fields or ())
    def clean(v):
        if isinstance(v,dict):
            return {k:clean(x) for k,x in v.items() if k not in excluded}
        if isinstance(v,list):
            return [clean(x) for x in v]
        return v
    return hashlib.sha256(canonical_json(clean(value)).encode('utf-8')).hexdigest()

def release_semantic_checksum(release,questions,stimuli,operation='PUBLISH_SNAPSHOT'):
    value={
        'operation':str(operation or ''),
        'release':dict(release or {}),
        'questions':list(questions or []),
        'stimuli':list(stimuli or []),
    }
    return semantic_checksum(value,{
        'package_checksum_sha256','manifest_checksum_sha256','question_checksum_sha256',
        'stimulus_checksum_sha256','payload_checksum_sha256'
    })

def blueprint_semantic_checksum(payload):
    return semantic_checksum(payload,{'blueprint_checksum_sha256','payload_checksum_sha256'})

_SCHEMA_CACHE={}
_FORMAT_CHECKER=FormatChecker()
RIGHTS_ELIGIBLE={'OWNED','COMMISSIONED_IP_ASSIGNED','LICENSED_COMMERCIAL','OPEN_COMMERCIAL','PUBLIC_DOMAIN'}

def normalize_rfc3339_utc(value, *, field='timestamp', allow_none=False):
    if value is None or str(value).strip()=='':
        if allow_none:
            return None
        raise ValueError(f'{field} is required')
    raw=str(value).strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',raw):
        raw += 'T00:00:00Z'
    elif re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?',raw):
        raw=raw.replace(' ','T')+'Z'
    elif raw.endswith('z'):
        raw=raw[:-1]+'Z'
    try:
        dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
    except Exception as exc:
        raise ValueError(f'{field} must be RFC3339 date-time') from exc
    if dt.tzinfo is None:
        dt=dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def _contract_schema_path(contract, schema_version='1.0.0'):
    base=Path(__file__).resolve().parent/'integration_contracts'
    if contract=='PH_SM_APPROVED_CONTENT_V1' and str(schema_version)=='1.1.0':
        return base/'v1_1_0'/'PH_SM_APPROVED_CONTENT_V1.schema.json'
    if contract=='PH_SM_APPROVED_CONTENT_MANIFEST_V1':
        return base/'v1_1_0'/'PH_SM_APPROVED_CONTENT_MANIFEST_V1.schema.json'
    if contract=='PH_SM_APPROVED_CONTENT_PACKAGE_V1':
        return base/'v1_1_0'/'PH_SM_APPROVED_CONTENT_PACKAGE_V1.schema.json'
    return base/(contract+'.schema.json')

def _validator(contract,schema_version='1.0.0'):
    key=(contract,str(schema_version))
    v=_SCHEMA_CACHE.get(key)
    if v:
        return v
    path=_contract_schema_path(contract,schema_version)
    schema=json.loads(path.read_text(encoding='utf-8'))
    v=Draft202012Validator(schema,format_checker=_FORMAT_CHECKER)
    _SCHEMA_CACHE[key]=v
    return v

def _schema_errors(value,contract,schema_version='1.0.0'):
    try:
        errs=sorted(_validator(contract,schema_version).iter_errors(value),key=lambda e:list(e.path))
    except Exception as exc:
        return [{'code':'SCHEMA_GATEWAY_ERROR','path':'','message':str(exc),'retryable':False}]
    out=[]
    for e in errs:
        out.append({'code':'SCHEMA_VALIDATION','path':'.'.join(str(x) for x in e.path),'message':e.message,'retryable':False})
    return out

def _strict_envelope_errors(envelope,contract,source,destination):
    sv=str(envelope.get('schema_version') or '') if isinstance(envelope,dict) else ''
    supported={'1.0.0','1.1.0'} if contract=='PH_SM_APPROVED_CONTENT_V1' else {'1.0.0'}
    if sv not in supported:
        return [{'code':'SCHEMA_VERSION','path':'schema_version','message':'Unsupported schema version','retryable':False}]
    errors=_schema_errors(envelope,contract,sv)
    if not errors:
        if envelope.get('contract_name')!=contract:
            errors.append({'code':'CONTRACT_MISMATCH','path':'contract_name','message':'Unexpected contract','retryable':False})
        if envelope.get('source_system')!=source:
            errors.append({'code':'SOURCE_SYSTEM','path':'source_system','message':'Unexpected source system','retryable':False})
        if envelope.get('destination_system')!=destination:
            errors.append({'code':'DESTINATION_SYSTEM','path':'destination_system','message':'Unexpected destination system','retryable':False})
        if str(envelope.get('payload_checksum_sha256') or '')!=payload_checksum(envelope.get('payload')):
            errors.append({'code':'PAYLOAD_CHECKSUM','path':'payload_checksum_sha256','message':'Payload checksum does not match canonical payload','retryable':False})
    return errors

def _object_checksum(obj, checksum_field):
    clean={k:v for k,v in obj.items() if k!=checksum_field}
    return hashlib.sha256(canonical_json(clean).encode('utf-8')).hexdigest()

def _verify_question_stimulus_checksums(payload):
    errors=[]
    for i,q in enumerate(payload.get('questions') or []):
        if str(q.get('question_checksum_sha256') or '')!=_object_checksum(q,'question_checksum_sha256'):
            errors.append({'code':'QUESTION_CHECKSUM','path':f'payload.questions[{i}].question_checksum_sha256','message':'Question checksum mismatch','retryable':False})
    for i,st in enumerate(payload.get('stimuli') or []):
        if str(st.get('stimulus_checksum_sha256') or '')!=_object_checksum(st,'stimulus_checksum_sha256'):
            errors.append({'code':'STIMULUS_CHECKSUM','path':f'payload.stimuli[{i}].stimulus_checksum_sha256','message':'Stimulus checksum mismatch','retryable':False})
    return errors


def _cols(c,table):
    return {r['name'] for r in c.execute(f'PRAGMA table_info({table})').fetchall()}

def _ensure_col(c,table,name,definition):
    if name not in _cols(c,table):
        c.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


def init_schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS integration_inbound_messages(
      message_id TEXT PRIMARY KEY, contract_name TEXT NOT NULL, source_system TEXT NOT NULL,
      idempotency_key TEXT NOT NULL, payload_checksum_sha256 TEXT NOT NULL,
      first_received_at TEXT NOT NULL, last_received_at TEXT NOT NULL, receive_count INTEGER DEFAULT 1,
      receipt_id TEXT, status TEXT NOT NULL, UNIQUE(contract_name,idempotency_key,payload_checksum_sha256));

    CREATE TABLE IF NOT EXISTS integration_receipts(
      receipt_id TEXT PRIMARY KEY, message_id TEXT NOT NULL, contract_name TEXT NOT NULL,
      receiver_system TEXT NOT NULL, received_at TEXT NOT NULL, status TEXT NOT NULL,
      duplicate_of_receipt_id TEXT, accepted_schema_version TEXT, payload_checksum_sha256 TEXT NOT NULL,
      errors_json TEXT DEFAULT '[]');

    CREATE TABLE IF NOT EXISTS integration_quarantine(
      id INTEGER PRIMARY KEY, contract_name TEXT NOT NULL, identity_key TEXT NOT NULL,
      incoming_checksum TEXT NOT NULL, existing_checksum TEXT DEFAULT '', reason_code TEXT NOT NULL,
      message_id TEXT DEFAULT '', payload_json TEXT DEFAULT '{}', status TEXT DEFAULT 'OPEN',
      created_at TEXT NOT NULL, resolved_at TEXT DEFAULT '', resolution_note TEXT DEFAULT '');
    CREATE INDEX IF NOT EXISTS idx_integration_quarantine_open
      ON integration_quarantine(status,contract_name,created_at);

    CREATE TABLE IF NOT EXISTS integration_ph_content_releases(
      id INTEGER PRIMARY KEY, release_id TEXT NOT NULL, release_version TEXT NOT NULL,
      package_checksum_sha256 TEXT NOT NULL, manifest_checksum_sha256 TEXT NOT NULL,
      payload_checksum_sha256 TEXT NOT NULL, semantic_checksum_sha256 TEXT DEFAULT '', release_status TEXT NOT NULL,
      local_status TEXT NOT NULL DEFAULT 'STAGED', effective_at TEXT, generated_at TEXT,
      market_id TEXT NOT NULL, programme_id TEXT NOT NULL, subject_id TEXT NOT NULL,
      chapter_id TEXT NOT NULL, question_count INTEGER DEFAULT 0, stimulus_count INTEGER DEFAULT 0,
      readiness_policy_version TEXT DEFAULT '', supersedes_release_version TEXT,
      source_system_version TEXT DEFAULT '', immutable_payload_json TEXT NOT NULL,
      admitted_at TEXT NOT NULL, activated_at TEXT DEFAULT '', superseded_at TEXT DEFAULT '',
      schema_version TEXT DEFAULT '1.0.0', release_operation TEXT DEFAULT 'PUBLISH_SNAPSHOT',
      withdrawn_at TEXT DEFAULT '', withdrawal_reason TEXT DEFAULT '',
      UNIQUE(release_id,release_version));
    CREATE INDEX IF NOT EXISTS idx_integration_ph_release_state
      ON integration_ph_content_releases(local_status,effective_at,release_id);

    CREATE TABLE IF NOT EXISTS integration_ph_product_activation_authorizations(
      id INTEGER PRIMARY KEY, release_id TEXT NOT NULL, release_version TEXT NOT NULL,
      package_checksum_sha256 TEXT NOT NULL, authorized_by TEXT NOT NULL,
      authorized_at TEXT NOT NULL, reason TEXT NOT NULL,
      activation_status TEXT NOT NULL DEFAULT 'AUTHORIZED', activated_at TEXT DEFAULT '',
      UNIQUE(release_id,release_version,package_checksum_sha256));
    CREATE INDEX IF NOT EXISTS idx_ph_product_activation_state
      ON integration_ph_product_activation_authorizations(activation_status,authorized_at,release_id);

    -- Historical V6.5.0 table retained for compatibility evidence only.
    CREATE TABLE IF NOT EXISTS integration_ph_question_versions(
      id INTEGER PRIMARY KEY, release_id TEXT NOT NULL, release_version TEXT NOT NULL,
      question_id TEXT NOT NULL, question_version_id TEXT NOT NULL, question_version_number INTEGER NOT NULL,
      question_checksum_sha256 TEXT NOT NULL, supersedes_question_version_id TEXT,
      effective_from TEXT, curriculum_json TEXT NOT NULL, content_json TEXT NOT NULL,
      architecture_json TEXT NOT NULL, governance_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
      scoremax_projection_json TEXT NOT NULL, local_question_db_id INTEGER,
      admitted_at TEXT NOT NULL, UNIQUE(question_id,question_version_id));
    CREATE INDEX IF NOT EXISTS idx_integration_ph_qv_release
      ON integration_ph_question_versions(release_id,release_version,question_id);

    -- V6.5.1 corrected model: immutable question version is separate from release membership.
    CREATE TABLE IF NOT EXISTS integration_ph_question_version_store(
      id INTEGER PRIMARY KEY, question_id TEXT NOT NULL, question_version_id TEXT NOT NULL,
      question_version_number INTEGER NOT NULL, question_checksum_sha256 TEXT NOT NULL,
      supersedes_question_version_id TEXT, effective_from TEXT,
      curriculum_json TEXT NOT NULL, content_json TEXT NOT NULL, architecture_json TEXT NOT NULL,
      governance_json TEXT NOT NULL, provenance_json TEXT NOT NULL,
      scoremax_projection_json TEXT NOT NULL, local_question_db_id INTEGER,
      first_admitted_at TEXT NOT NULL, UNIQUE(question_id,question_version_id));

    CREATE TABLE IF NOT EXISTS integration_ph_release_question_membership(
      id INTEGER PRIMARY KEY, release_id TEXT NOT NULL, release_version TEXT NOT NULL,
      question_id TEXT NOT NULL, question_version_id TEXT NOT NULL,
      ordinal INTEGER NOT NULL DEFAULT 0, admitted_at TEXT NOT NULL,
      UNIQUE(release_id,release_version,question_id,question_version_id));
    CREATE INDEX IF NOT EXISTS idx_ph_release_q_membership
      ON integration_ph_release_question_membership(release_id,release_version,ordinal);

    CREATE TABLE IF NOT EXISTS integration_ph_stimulus_versions(
      id INTEGER PRIMARY KEY, release_id TEXT NOT NULL, release_version TEXT NOT NULL,
      stimulus_id TEXT NOT NULL, stimulus_version_id TEXT NOT NULL,
      stimulus_checksum_sha256 TEXT NOT NULL, immutable_payload_json TEXT NOT NULL,
      admitted_at TEXT NOT NULL, UNIQUE(stimulus_id,stimulus_version_id));

    CREATE TABLE IF NOT EXISTS integration_ph_stimulus_version_store(
      id INTEGER PRIMARY KEY, stimulus_id TEXT NOT NULL, stimulus_version_id TEXT NOT NULL,
      stimulus_checksum_sha256 TEXT NOT NULL, immutable_payload_json TEXT NOT NULL,
      first_admitted_at TEXT NOT NULL, UNIQUE(stimulus_id,stimulus_version_id));

    CREATE TABLE IF NOT EXISTS integration_ph_release_stimulus_membership(
      id INTEGER PRIMARY KEY, release_id TEXT NOT NULL, release_version TEXT NOT NULL,
      stimulus_id TEXT NOT NULL, stimulus_version_id TEXT NOT NULL,
      ordinal INTEGER NOT NULL DEFAULT 0, admitted_at TEXT NOT NULL,
      UNIQUE(release_id,release_version,stimulus_id,stimulus_version_id));

    CREATE TABLE IF NOT EXISTS integration_ph_blueprints(
      id INTEGER PRIMARY KEY, blueprint_id TEXT NOT NULL, blueprint_version TEXT NOT NULL,
      blueprint_checksum_sha256 TEXT NOT NULL, payload_checksum_sha256 TEXT NOT NULL,
      semantic_checksum_sha256 TEXT DEFAULT '', release_state TEXT NOT NULL, market_id TEXT NOT NULL, programme_id TEXT NOT NULL,
      subject_id TEXT NOT NULL, effective_from TEXT, effective_to TEXT,
      immutable_payload_json TEXT NOT NULL, local_status TEXT NOT NULL DEFAULT 'IMPORTED',
      projection_status TEXT DEFAULT 'IMMUTABLE_ONLY', projected_blueprint_id INTEGER,
      admitted_at TEXT NOT NULL, UNIQUE(blueprint_id,blueprint_version));

    CREATE TABLE IF NOT EXISTS integration_outbox(
      id INTEGER PRIMARY KEY, message_id TEXT UNIQUE NOT NULL, contract_name TEXT NOT NULL,
      destination_system TEXT NOT NULL, idempotency_key TEXT NOT NULL,
      business_identity TEXT NOT NULL, payload_checksum_sha256 TEXT NOT NULL,
      envelope_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PENDING',
      attempt_count INTEGER DEFAULT 0, retry_cycle INTEGER DEFAULT 0, next_attempt_at TEXT, last_attempt_at TEXT,
      last_error_code TEXT DEFAULT '', last_error TEXT DEFAULT '', receipt_json TEXT DEFAULT '',
      source_record_type TEXT DEFAULT '', source_record_id TEXT DEFAULT '',
      claim_token TEXT DEFAULT '', claim_expires_at TEXT DEFAULT '',
      created_at TEXT NOT NULL, dispatched_at TEXT DEFAULT '',
      UNIQUE(contract_name,idempotency_key));
    CREATE INDEX IF NOT EXISTS idx_integration_outbox_due
      ON integration_outbox(status,next_attempt_at,created_at);

    CREATE TABLE IF NOT EXISTS integration_dispatch_attempts(
      id INTEGER PRIMARY KEY, outbox_id INTEGER NOT NULL, attempted_at TEXT NOT NULL,
      retry_cycle INTEGER DEFAULT 0, http_status INTEGER, result_status TEXT DEFAULT '', error_code TEXT DEFAULT '',
      error_text TEXT DEFAULT '', response_json TEXT DEFAULT '');

    CREATE TABLE IF NOT EXISTS integration_service_replay_log(
      source_system TEXT NOT NULL, message_id TEXT NOT NULL, seen_at TEXT NOT NULL,
      PRIMARY KEY(source_system,message_id));

    CREATE TABLE IF NOT EXISTS integration_source_change_queue(
      id INTEGER PRIMARY KEY AUTOINCREMENT, source_table TEXT NOT NULL, source_pk TEXT NOT NULL,
      change_kind TEXT NOT NULL DEFAULT 'UPSERT', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      projected_at TEXT DEFAULT '');
    CREATE INDEX IF NOT EXISTS idx_integration_source_change_pending
      ON integration_source_change_queue(projected_at,id);

    CREATE TABLE IF NOT EXISTS integration_projection_watermarks(
      projection_name TEXT PRIMARY KEY, last_source_id INTEGER DEFAULT 0,
      updated_at TEXT NOT NULL);

    CREATE TABLE IF NOT EXISTS integration_worker_state(
      worker_name TEXT PRIMARY KEY, heartbeat_at TEXT NOT NULL, last_cycle_at TEXT DEFAULT '',
      last_result_json TEXT DEFAULT '{}', process_id TEXT DEFAULT '');

    CREATE TABLE IF NOT EXISTS integration_requeue_audit(
      id INTEGER PRIMARY KEY, outbox_id INTEGER NOT NULL, from_status TEXT NOT NULL,
      to_status TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT DEFAULT '', created_at TEXT NOT NULL,
      prior_attempt_count INTEGER DEFAULT 0, new_retry_cycle INTEGER DEFAULT 0);

    CREATE TABLE IF NOT EXISTS integration_transport_diagnostics(
      id INTEGER PRIMARY KEY, contract_name TEXT NOT NULL, direction TEXT NOT NULL,
      event_code TEXT NOT NULL, occurred_at TEXT NOT NULL, details_json TEXT DEFAULT '{}');
    CREATE INDEX IF NOT EXISTS idx_integration_transport_diag_contract
      ON integration_transport_diagnostics(contract_name,occurred_at);
    ''')

    # Additive upgrade of the V6.5.0 release table. CREATE TABLE IF NOT EXISTS does not
    # add columns to an existing database, so these must be ensured before any V6.5.1
    # activation/migration logic reads them.
    for n,d in {
        'schema_version':"TEXT DEFAULT '1.0.0'",
        'release_operation':"TEXT DEFAULT 'PUBLISH_SNAPSHOT'",
        'withdrawn_at':"TEXT DEFAULT ''",
        'withdrawal_reason':"TEXT DEFAULT ''",
        'semantic_checksum_sha256':"TEXT DEFAULT ''"
    }.items():
        _ensure_col(c,'integration_ph_content_releases',n,d)
    _ensure_col(c,'integration_ph_blueprints','semantic_checksum_sha256',"TEXT DEFAULT ''")
    _ensure_col(c,'integration_outbox','claim_token',"TEXT DEFAULT ''")
    _ensure_col(c,'integration_outbox','claim_expires_at',"TEXT DEFAULT ''")
    _ensure_col(c,'integration_outbox','retry_cycle',"INTEGER DEFAULT 0")
    _ensure_col(c,'integration_dispatch_attempts','retry_cycle',"INTEGER DEFAULT 0")
    _ensure_col(c,'integration_requeue_audit','prior_attempt_count',"INTEGER DEFAULT 0")
    _ensure_col(c,'integration_requeue_audit','new_retry_cycle',"INTEGER DEFAULT 0")

    # Migration: copy V6.5.0 data into the corrected immutable-store + membership model.
    c.execute('''INSERT OR IGNORE INTO integration_ph_question_version_store(
      question_id,question_version_id,question_version_number,question_checksum_sha256,
      supersedes_question_version_id,effective_from,curriculum_json,content_json,architecture_json,
      governance_json,provenance_json,scoremax_projection_json,local_question_db_id,first_admitted_at)
      SELECT question_id,question_version_id,question_version_number,question_checksum_sha256,
      supersedes_question_version_id,effective_from,curriculum_json,content_json,architecture_json,
      governance_json,provenance_json,scoremax_projection_json,local_question_db_id,admitted_at
      FROM integration_ph_question_versions''')
    c.execute('''INSERT OR IGNORE INTO integration_ph_release_question_membership(
      release_id,release_version,question_id,question_version_id,ordinal,admitted_at)
      SELECT release_id,release_version,question_id,question_version_id,id,admitted_at
      FROM integration_ph_question_versions''')
    c.execute('''INSERT OR IGNORE INTO integration_ph_stimulus_version_store(
      stimulus_id,stimulus_version_id,stimulus_checksum_sha256,immutable_payload_json,first_admitted_at)
      SELECT stimulus_id,stimulus_version_id,stimulus_checksum_sha256,immutable_payload_json,admitted_at
      FROM integration_ph_stimulus_versions''')
    c.execute('''INSERT OR IGNORE INTO integration_ph_release_stimulus_membership(
      release_id,release_version,stimulus_id,stimulus_version_id,ordinal,admitted_at)
      SELECT release_id,release_version,stimulus_id,stimulus_version_id,id,admitted_at
      FROM integration_ph_stimulus_versions''')

    for table in ('assessment_sessions','attempts'):
        _ensure_col(c,table,'ph_release_pins_json',"TEXT DEFAULT '{}'")
        _ensure_col(c,table,'ph_question_pins_json',"TEXT DEFAULT '{}'")
    for name,definition in {
        'ph_question_id':"TEXT DEFAULT ''", 'ph_question_version_id':"TEXT DEFAULT ''",
        'ph_question_checksum_sha256':"TEXT DEFAULT ''", 'ph_release_id':"TEXT DEFAULT ''",
        'ph_release_version':"TEXT DEFAULT ''", 'ph_release_checksum_sha256':"TEXT DEFAULT ''",
        'ph_question_snapshot_json':"TEXT DEFAULT '{}'"
    }.items():
        _ensure_col(c,'attempt_answers',name,definition)
    qcols={
        'ph_question_id':"TEXT DEFAULT ''", 'ph_question_version_id':"TEXT DEFAULT ''",
        'ph_question_checksum_sha256':"TEXT DEFAULT ''", 'ph_release_id':"TEXT DEFAULT ''",
        'ph_release_version':"TEXT DEFAULT ''", 'ph_release_checksum_sha256':"TEXT DEFAULT ''",
        'ph_market_id':"TEXT DEFAULT ''", 'ph_programme_id':"TEXT DEFAULT ''",
        'ph_subject_id':"TEXT DEFAULT ''", 'ph_chapter_id':"TEXT DEFAULT ''",
        'ph_claim_family_id':"TEXT DEFAULT ''", 'ph_reasoning_seed_id':"TEXT DEFAULT ''",
        'ph_dependency_group_id':"TEXT DEFAULT ''", 'ph_dependency_type':"TEXT DEFAULT ''",
        'ph_evidence_role':"TEXT DEFAULT ''", 'ph_independent_mastery_weight':"REAL DEFAULT 0",
        'ph_knowledge_node_ids_json':"TEXT DEFAULT '[]'", 'ph_mastery_ceiling':"TEXT DEFAULT ''",
        'ph_cognitive_demand':"TEXT DEFAULT ''", 'ph_curriculum_snapshot_json':"TEXT DEFAULT '{}'",
        'ph_governance_snapshot_json':"TEXT DEFAULT '{}'", 'ph_provenance_snapshot_json':"TEXT DEFAULT '{}'",
        'ph_is_auto_markable':"INTEGER DEFAULT 1", 'ph_projection_owner':"TEXT DEFAULT ''"
    }
    for n,d in qcols.items():
        _ensure_col(c,'questions',n,d)
    c.execute("UPDATE questions SET ph_projection_owner='POWER_HOUSE' WHERE COALESCE(ph_question_id,'')<>'' AND COALESCE(ph_projection_owner,'')=''")

    # Incremental local source hooks. Cross-system calls never run in these triggers.
    for trig in (
        'trg_int_ref_attr_ins','trg_int_ref_attr_upd','trg_int_payment_ins','trg_int_payment_upd',
        'trg_int_reward_ins','trg_int_reward_upd','trg_int_req_ins','trg_int_req_upd','trg_int_um_growth_ins'
    ):
        c.execute(f'DROP TRIGGER IF EXISTS {trig}')

    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='referral_attributions'").fetchone():
        c.executescript('''
        CREATE TRIGGER trg_int_ref_attr_ins AFTER INSERT ON referral_attributions
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('referral_attributions',NEW.id,'INSERT'); END;
        CREATE TRIGGER trg_int_ref_attr_upd AFTER UPDATE ON referral_attributions
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('referral_attributions',NEW.id,'UPDATE'); END;
        ''')
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='payment_transactions'").fetchone():
        c.executescript('''
        CREATE TRIGGER trg_int_payment_ins AFTER INSERT ON payment_transactions
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('payment_transactions',NEW.id,'INSERT'); END;
        CREATE TRIGGER trg_int_payment_upd AFTER UPDATE ON payment_transactions
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('payment_transactions',NEW.id,'UPDATE'); END;
        ''')
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='referral_rewards'").fetchone():
        c.executescript('''
        CREATE TRIGGER trg_int_reward_ins AFTER INSERT ON referral_rewards
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('referral_rewards',NEW.id,'INSERT'); END;
        CREATE TRIGGER trg_int_reward_upd AFTER UPDATE ON referral_rewards
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('referral_rewards',NEW.id,'UPDATE'); END;
        ''')
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='content_requirement_requests'").fetchone():
        c.executescript('''
        CREATE TRIGGER trg_int_req_ins AFTER INSERT ON content_requirement_requests
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('content_requirement_requests',NEW.id,'INSERT'); END;
        CREATE TRIGGER trg_int_req_upd AFTER UPDATE ON content_requirement_requests
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('content_requirement_requests',NEW.id,'UPDATE'); END;
        ''')
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='universal_growth_event_outbox'").fetchone():
        c.executescript('''
        CREATE TRIGGER trg_int_um_growth_ins AFTER INSERT ON universal_growth_event_outbox
        BEGIN INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) VALUES('universal_growth_event_outbox',NEW.event_id,'INSERT'); END;
        CREATE INDEX IF NOT EXISTS idx_um_growth_created_event ON universal_growth_event_outbox(created_at,event_id);
        ''')

    # One-time migration backfill; it is not a learner request-path scan.
    if c.execute("SELECT COUNT(*) n FROM integration_source_change_queue").fetchone()['n']==0:
        for table,pk in (
            ('referral_attributions','id'),('payment_transactions','id'),
            ('referral_rewards','id'),('content_requirement_requests','id')
        ):
            if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():
                c.execute(f"INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) SELECT ?,CAST({pk} AS TEXT),'BACKFILL' FROM {table}",(table,))
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='universal_growth_event_outbox'").fetchone():
            c.execute("INSERT INTO integration_source_change_queue(source_table,source_pk,change_kind) SELECT 'universal_growth_event_outbox',event_id,'BACKFILL' FROM universal_growth_event_outbox")

    # Revalidate pre-V6.5.3 integration state once instead of inheriting rejected semantics.
    _reconcile_legacy_integration_state(c)

def _begin_immediate(c):
    # Serialise integration identity decisions across concurrent HTTP workers.
    if not getattr(c,'in_transaction',False):
        c.execute('BEGIN IMMEDIATE')


def _receipt(c,envelope,status,errors=None,duplicate_of=None):
    rid='RCPT::SCOREMAX::'+uuid.uuid4().hex
    norm_errors=[]
    for err in list(errors or []):
        e=dict(err or {})
        e.setdefault('code','INTEGRATION_ERROR'); e.setdefault('path',''); e.setdefault('message','')
        e['retryable']=bool(e.get('retryable',False))
        norm_errors.append({k:e[k] for k in ('code','path','message','retryable')})
    rec={'receipt_id':rid,'message_id':str(envelope.get('message_id') or ''),'contract_name':str(envelope.get('contract_name') or ''),
         'receiver_system':'SCOREMAX','received_at':utcnow(),'status':status,'duplicate_of_receipt_id':duplicate_of,
         'accepted_schema_version':str(envelope.get('schema_version') or '') if status in {'ACCEPTED','DUPLICATE'} else None,
         'payload_checksum_sha256':str(envelope.get('payload_checksum_sha256') or '0'*64),'errors':norm_errors}
    receipt_errors=_schema_errors(rec,'INTEGRATION_RECEIPT_V1','1.0.0')
    if receipt_errors:
        raise ValueError('Internal integration receipt failed frozen schema: '+canonical_json(receipt_errors))
    c.execute('''INSERT INTO integration_receipts(receipt_id,message_id,contract_name,receiver_system,received_at,status,
      duplicate_of_receipt_id,accepted_schema_version,payload_checksum_sha256,errors_json) VALUES(?,?,?,?,?,?,?,?,?,?)''',
      (rid,rec['message_id'],rec['contract_name'],'SCOREMAX',rec['received_at'],status,duplicate_of,rec['accepted_schema_version'],rec['payload_checksum_sha256'],canonical_json(rec['errors'])))
    return rec


def _receipt_from_id(c,receipt_id):
    if not receipt_id:
        return None
    row=c.execute('SELECT * FROM integration_receipts WHERE receipt_id=?',(receipt_id,)).fetchone()
    if not row:
        return None
    try: errors=json.loads(row['errors_json'] or '[]')
    except Exception: errors=[]
    return {
      'receipt_id':row['receipt_id'],'message_id':row['message_id'],'contract_name':row['contract_name'],
      'receiver_system':row['receiver_system'],'received_at':row['received_at'],'status':row['status'],
      'duplicate_of_receipt_id':row['duplicate_of_receipt_id'],'accepted_schema_version':row['accepted_schema_version'],
      'payload_checksum_sha256':row['payload_checksum_sha256'],'errors':errors}


def _durable_replay_receipt(c,row):
    """Return the original receiver receipt for an exact inbound replay.

    Integration replay is byte/identity idempotence, not a second durable event.
    """
    rec=_receipt_from_id(c,row['receipt_id'] if row else None)
    return rec


def _basic_validate(envelope,contract,source,destination='SCOREMAX'):
    return _strict_envelope_errors(envelope,contract,source,destination)



def _quarantine(c,envelope,identity,incoming,existing,reason):
    c.execute('''INSERT INTO integration_quarantine(contract_name,identity_key,incoming_checksum,existing_checksum,reason_code,
      message_id,payload_json,status,created_at) VALUES(?,?,?,?,?,?,?,'OPEN',?)''',
      (envelope.get('contract_name',''),identity,incoming,existing or '',reason,envelope.get('message_id',''),canonical_json(envelope),utcnow()))
    return _receipt(c,envelope,'QUARANTINED',[{'code':reason,'path':'payload','message':'Identity/version/checksum conflict requires governed resolution.'}])


def _register_inbound(c,envelope):
    contract=envelope.get('contract_name',''); idem=envelope.get('idempotency_key',''); chk=envelope.get('payload_checksum_sha256','')
    row=c.execute('SELECT * FROM integration_inbound_messages WHERE contract_name=? AND idempotency_key=? ORDER BY first_received_at LIMIT 1',(contract,idem)).fetchone()
    if row:
        if row['payload_checksum_sha256']!=chk:
            return 'CONFLICT',row
        c.execute('UPDATE integration_inbound_messages SET receive_count=receive_count+1,last_received_at=? WHERE message_id=?',(utcnow(),row['message_id']))
        return 'DUPLICATE',row
    # message-id reuse with another business identity is also a conflict.
    m=c.execute('SELECT * FROM integration_inbound_messages WHERE message_id=?',(envelope.get('message_id',''),)).fetchone()
    if m and (m['contract_name']!=contract or m['idempotency_key']!=idem or m['payload_checksum_sha256']!=chk):
        return 'CONFLICT',m
    return 'NEW',None


def _record_inbound(c,envelope,receipt,status):
    now=utcnow()
    c.execute('''INSERT INTO integration_inbound_messages(message_id,contract_name,source_system,idempotency_key,payload_checksum_sha256,
      first_received_at,last_received_at,receive_count,receipt_id,status) VALUES(?,?,?,?,?,?,?,?,?,?)''',
      (envelope['message_id'],envelope['contract_name'],envelope['source_system'],envelope['idempotency_key'],envelope['payload_checksum_sha256'],now,now,1,receipt['receipt_id'],status))


def _governance_ready(q):
    g=q.get('governance') or {}; a=q.get('architecture') or {}
    required={'academic_review_state':'APPROVED','hold_status':'CLEAR','release_readiness':'READY'}
    for k,v in required.items():
        if str(g.get(k) or '').upper()!=v: return False,f'{k}_NOT_{v}'
    if str(g.get('source_check_status') or '').upper() not in {'CLEAR','NOT_REQUIRED'}:
        return False,'SOURCE_CHECK_NOT_CLEAR_OR_NOT_REQUIRED'
    if str(g.get('r2_status') or '').upper() not in {'NOT_REQUIRED','CLEARED','PASSED','COMPLETE'}:
        return False,'R2_NOT_CLEARED'
    generated=g.get('generated_clearance_status')
    if generated not in (None,'') and str(generated).upper() not in {'CLEARED','NOT_REQUIRED'}:
        return False,'GENERATED_CLEARANCE_NOT_CLEARED'
    if str(g.get('rights_status') or '').upper() not in RIGHTS_ELIGIBLE:
        return False,'RIGHTS_NOT_ELIGIBLE'
    role=str(a.get('evidence_role') or '').upper(); dep=str(a.get('dependency_type') or '').upper()
    eligible=bool(a.get('independent_mastery_eligible')); weight=float(a.get('independent_mastery_weight') or 0)
    dependent=role!='INDEPENDENT' or dep in {'VARIANT','TRUE_VARIANT','SCAFFOLD','RECOVERY','RECONFIRMATION','DEPENDENT','SHARED_STIMULUS_DEPENDENT'}
    if dependent and (eligible or abs(weight)>1e-9): return False,'DEPENDENT_INDEPENDENCE_INFLATION'
    if role=='INDEPENDENT' and weight<0: return False,'NEGATIVE_INDEPENDENT_WEIGHT'
    return True,''



def _legacy_level(v):
    m={'FOUNDATION':'Foundation','EXAM_READY':'Exam Ready','ADVANCED':'Advanced','DISTINCTION':'Distinction','EXPERT':'Expert','ELITE':'Elite'}
    return m.get(str(v or '').upper(),str(v or '').replace('_',' ').title() or 'Foundation')

def _qtype(content):
    key=str((content.get('marking') or {}).get('key_type') or '').upper(); exam=str(content.get('exam_question_type') or '').upper(); fam=str(content.get('question_family_type') or '').upper()
    if key=='RUBRIC_ONLY': return 'Extended Response',False
    if key=='NUMERIC' or 'NUMERIC' in exam: return 'Numerical',True
    if key=='BOOLEAN' or 'TRUE' in exam: return 'True/False',True
    if key=='MULTIPLE_OPTIONS': return 'Multiple Select',True
    if key in {'TEXT'}: return 'Fill Blank',True
    return 'MCQ',True

def _family_key(q):
    c=q.get('curriculum') or {}; a=q.get('architecture') or {}
    raw='|'.join(str(x or '').lower() for x in [c.get('market_id'),c.get('qualification_id'),c.get('board_exam_id'),c.get('programme_id'),c.get('subject_id'),a.get('claim_family_id')])
    return 'PHFAM-'+hashlib.sha256(raw.encode()).hexdigest()[:24]

def _stimulus_lookup(payload):
    out={}
    for s in payload.get('stimuli') or []:
        sid=str(s.get('stimulus_id') or '')
        if sid: out[sid]=s
    return out

def _finite_number(value):
    try:
        n=float(value)
        return n if n==n and abs(n)!=float('inf') else None
    except (TypeError,ValueError,OverflowError):
        return None

def _learner_stimulus_text(stimulus):
    """Deterministic learner-safe stimulus projection; immutable source JSON remains internal."""
    if stimulus in (None,'',{}):
        return ''
    if isinstance(stimulus,str):
        return stimulus.strip()
    if isinstance(stimulus,(int,float,bool)):
        return str(stimulus)
    if isinstance(stimulus,list):
        safe=[_learner_stimulus_text(x) for x in stimulus]
        return '\n'.join(x for x in safe if x)
    if not isinstance(stimulus,dict):
        return ''
    # Governed stimulus records wrap learner material under content. Provenance and review
    # metadata are deliberately not traversed.
    if isinstance(stimulus.get('content'),(dict,list,str)):
        return _learner_stimulus_text(stimulus.get('content'))
    parts=[]
    for key in ('title','heading','prompt','instructions','text','caption'):
        value=stimulus.get(key)
        if isinstance(value,str) and value.strip():
            parts.append(value.strip())
    # Structured learner data may be shown, but only through explicit learner-facing keys.
    for key in ('table','rows','columns','dataset','data','values'):
        value=stimulus.get(key)
        if isinstance(value,(list,dict)) and value:
            parts.append(canonical_json(value))
    return '\n'.join(parts)

def _semantic_question_errors(q,stimuli,index=0):
    errors=[]; path=f'payload.questions[{index}]'
    content=q.get('content') or {}; marking=content.get('marking') or {}; options=content.get('options') or []
    key_type=str(marking.get('key_type') or '').upper(); key=marking.get('key')
    option_ids=[]; seen=set()
    for oi,opt in enumerate(options):
        oid=str((opt or {}).get('option_id') or '').strip()
        if not oid:
            errors.append({'code':'OPTION_ID_REQUIRED','path':f'{path}.content.options[{oi}].option_id','message':'Each learner option requires an opaque option_id','retryable':False})
        elif oid in seen:
            errors.append({'code':'DUPLICATE_OPTION_ID','path':f'{path}.content.options[{oi}].option_id','message':'Option IDs must be unique within a question','retryable':False})
        seen.add(oid); option_ids.append(oid)
    stimulus_ref=str(content.get('stimulus_ref') or '').strip()
    if stimulus_ref and stimulus_ref not in stimuli:
        errors.append({'code':'UNRESOLVED_STIMULUS_REFERENCE','path':f'{path}.content.stimulus_ref','message':'Referenced stimulus is not present in this release snapshot','retryable':False})
    if key_type not in SUPPORTED_LIVE_KEY_TYPES:
        code='UNSUPPORTED_RUBRIC_ONLY_DELIVERY' if key_type=='RUBRIC_ONLY' else 'UNSUPPORTED_MARKING_KEY_TYPE'
        errors.append({'code':code,'path':f'{path}.content.marking.key_type','message':'This governed marking mode is not safely deliverable by the current ScoreMax assessment runtime','retryable':False})
        return errors
    if _finite_number(marking.get('marks')) is None or float(marking.get('marks') or 0)<0:
        errors.append({'code':'INVALID_MARKS','path':f'{path}.content.marking.marks','message':'Marks must be a finite non-negative number','retryable':False})
    neg=_finite_number(marking.get('negative_marks'))
    if neg is None or neg>0:
        errors.append({'code':'INVALID_NEGATIVE_MARKS','path':f'{path}.content.marking.negative_marks','message':'negative_marks must be a finite value less than or equal to zero','retryable':False})
    if key_type in {'SINGLE_OPTION','MULTIPLE_OPTIONS'}:
        if len(option_ids)<2:
            errors.append({'code':'OPTIONS_REQUIRED','path':f'{path}.content.options','message':'Option-keyed questions require at least two learner options','retryable':False})
        keys=key if isinstance(key,list) else [key]
        keys=[str(x) for x in keys if x is not None and str(x)!='']
        if key_type=='SINGLE_OPTION' and len(keys)!=1:
            errors.append({'code':'SINGLE_KEY_CARDINALITY','path':f'{path}.content.marking.key','message':'SINGLE_OPTION requires exactly one key','retryable':False})
        if key_type=='MULTIPLE_OPTIONS' and (not isinstance(key,list) or not keys or len(keys)!=len(set(keys))):
            errors.append({'code':'MULTIPLE_KEY_CARDINALITY','path':f'{path}.content.marking.key','message':'MULTIPLE_OPTIONS requires a non-empty unique key list','retryable':False})
        missing=[x for x in keys if x not in option_ids]
        if missing:
            errors.append({'code':'KEY_NOT_IN_OPTIONS','path':f'{path}.content.marking.key','message':'Every keyed option must exist in the learner option set','retryable':False})
    elif key_type=='NUMERIC':
        if _finite_number(key) is None:
            errors.append({'code':'NUMERIC_KEY_REQUIRED','path':f'{path}.content.marking.key','message':'NUMERIC requires a finite numeric key','retryable':False})
        tol=marking.get('numeric_tolerance')
        if tol is not None and (_finite_number(tol) is None or float(tol)<0):
            errors.append({'code':'NUMERIC_TOLERANCE','path':f'{path}.content.marking.numeric_tolerance','message':'Numeric tolerance must be null or a finite non-negative number','retryable':False})
        if options:
            errors.append({'code':'NUMERIC_OPTIONS_INCOHERENT','path':f'{path}.content.options','message':'NUMERIC questions must not depend on option IDs','retryable':False})
    elif key_type=='TEXT':
        accepted=[str(x).strip() for x in (marking.get('accepted_answers') or []) if str(x).strip()]
        if not str(key if key is not None else '').strip() and not accepted:
            errors.append({'code':'TEXT_KEY_REQUIRED','path':f'{path}.content.marking','message':'TEXT requires a key or at least one accepted answer','retryable':False})
        if options:
            errors.append({'code':'TEXT_OPTIONS_INCOHERENT','path':f'{path}.content.options','message':'TEXT questions must not depend on option IDs','retryable':False})
    elif key_type=='BOOLEAN':
        if isinstance(key,bool):
            pass
        elif str(key or '').strip().upper() not in {'TRUE','FALSE','T','F','1','0'} and str(key or '') not in option_ids:
            errors.append({'code':'BOOLEAN_KEY_REQUIRED','path':f'{path}.content.marking.key','message':'BOOLEAN requires a true/false value or a valid option ID','retryable':False})
        if options and len(option_ids)!=2:
            errors.append({'code':'BOOLEAN_OPTION_CARDINALITY','path':f'{path}.content.options','message':'BOOLEAN options, when supplied, must contain exactly two unique options','retryable':False})
    if key_type!='NUMERIC' and marking.get('numeric_tolerance') not in (None,0,0.0):
        errors.append({'code':'MARKING_MODE_INCOHERENT','path':f'{path}.content.marking.numeric_tolerance','message':'numeric_tolerance is only valid for NUMERIC marking','retryable':False})
    if marking.get('rubric') not in (None,{}) and key_type!='RUBRIC_ONLY':
        errors.append({'code':'MARKING_MODE_INCOHERENT','path':f'{path}.content.marking.rubric','message':'A rubric cannot silently replace an auto-markable key','retryable':False})
    return errors

def _semantic_content_errors(questions,stimuli):
    errors=[]; stim_lookup={}; seen_stim=set()
    for i,s in enumerate(stimuli or []):
        sid=str((s or {}).get('stimulus_id') or '')
        if sid in seen_stim:
            errors.append({'code':'DUPLICATE_STIMULUS_ID','path':f'payload.stimuli[{i}].stimulus_id','message':'Only one stimulus version per stimulus ID may appear in a release snapshot','retryable':False})
        seen_stim.add(sid); stim_lookup[sid]=s
    seen_qids=set(); seen_qvids=set()
    for i,q in enumerate(questions or []):
        qid=str((q or {}).get('question_id') or ''); qvid=str((q or {}).get('question_version_id') or '')
        if qid in seen_qids:
            errors.append({'code':'MULTIPLE_QUESTION_VERSIONS_IN_SNAPSHOT','path':f'payload.questions[{i}].question_id','message':'A release snapshot may contain only one version of each question ID','retryable':False})
        if qvid in seen_qvids:
            errors.append({'code':'DUPLICATE_QUESTION_VERSION_ID','path':f'payload.questions[{i}].question_version_id','message':'question_version_id must be unique within a release snapshot','retryable':False})
        seen_qids.add(qid); seen_qvids.add(qvid)
        errors.extend(_semantic_question_errors(q,stim_lookup,i))
    return errors

def _projection(q,stimuli):
    curr=q.get('curriculum') or {}; disp=curr.get('display') or {}; content=q.get('content') or {}; marking=content.get('marking') or {}; arch=q.get('architecture') or {}; gov=q.get('governance') or {}; prov=q.get('provenance') or {}
    options=content.get('options') or []
    opt={x.get('option_id'):x.get('text','') for x in options if isinstance(x,dict)}
    key=marking.get('key')
    if isinstance(key,list): answer=','.join(str(x) for x in key)
    elif key is None: answer=''
    elif isinstance(key,bool): answer='TRUE' if key else 'FALSE'
    else: answer=str(key)
    qtype,auto=_qtype(content)
    answer_cfg={'options':[{'id':str(x.get('option_id') or ''),'text':str(x.get('text') or '')} for x in options]}
    key_type=str(marking.get('key_type') or '').upper()
    if key_type=='TEXT':
        accepted=[str(x) for x in (marking.get('accepted_answers') or [])]
        if key is not None and str(key) not in accepted: accepted.insert(0,str(key))
        answer_cfg['accepted_answers']=accepted
    elif marking.get('accepted_answers'):
        answer_cfg['accepted_answers']=list(marking.get('accepted_answers') or [])
    marking_cfg={'marks':float(marking.get('marks') or 0),'negative_marks':float(marking.get('negative_marks') or 0),'auto_markable':bool(auto),'key_type':key_type}
    if key_type in {'SINGLE_OPTION','MULTIPLE_OPTIONS'}: marking_cfg['correct_option_ids']=key if isinstance(key,list) else ([str(key)] if key is not None else [])
    if key_type=='BOOLEAN': marking_cfg['correct_option_ids']=[answer]
    if key_type=='NUMERIC':
        marking_cfg['correct_value']=float(key)
        marking_cfg['tolerance']=float(marking.get('numeric_tolerance') or 0)
    if marking.get('rubric') is not None: marking_cfg['rubric']=marking.get('rubric')
    stim=content.get('inline_stimulus')
    if not stim and content.get('stimulus_ref'): stim=stimuli.get(str(content.get('stimulus_ref')))
    source=prov.get('primary_source') or {}
    return {
      'question_id':str(q.get('question_id') or ''),'family_id':str(arch.get('claim_family_id') or ''),'variant':str(arch.get('evidence_role') or ''),
      'programme':str(disp.get('programme') or curr.get('programme_id') or ''),'subject':str(disp.get('subject') or curr.get('subject_id') or ''),
      'chapter':str(disp.get('chapter') or curr.get('chapter_id') or ''),'topic':str(disp.get('topic') or curr.get('topic_id') or ''),
      'subtopic':str(disp.get('subtopic') or curr.get('subtopic_id') or ''),'qtype':qtype,'level':_legacy_level(arch.get('mastery_level')),
      'question':str(content.get('stem') or ''),'option_a':opt.get('A',''),'option_b':opt.get('B',''),'option_c':opt.get('C',''),'option_d':opt.get('D',''),
      'answer':answer,'explanation':str(marking.get('explanation') or ''),'status':'Approved','country':str(curr.get('market_id') or ''),
      'qualification':str(curr.get('qualification_id') or ''),'exam_board':str(curr.get('board_exam_id') or ''),'curriculum_version':'',
      'learning_outcome':str(disp.get('outcome_text') or ''),'concept':str(disp.get('topic') or ''),'difficulty':_legacy_level(arch.get('mastery_level')),
      'cognitive_skill':str(arch.get('cognitive_demand') or ''),'command_word':str(content.get('command_word') or ''),'marks':float(marking.get('marks') or 0),
      'estimated_time_seconds':content.get('estimated_time_seconds') or 60,'stimulus_type':'POWER_HOUSE' if stim else '',
      'stimulus_data':_learner_stimulus_text(stim),'answer_config':canonical_json(answer_cfg),'marking_config':canonical_json(marking_cfg),
      'feedback_config':'{}','misconception_tags':canonical_json(arch.get('misconception_ids') or []),'prerequisite_tags':'[]',
      'question_version':int(q.get('question_version_number') or 1),'review_status':'Approved','source_type':'Power House Approved Content','secure_bank':1,
      'language':str(content.get('language') or 'en'),'family_key':_family_key(q),'active':1,'rights_status':str(gov.get('rights_status') or ''),
      'scoremax_ready':1,'content_environment':'PRODUCTION','ph_question_id':str(q.get('question_id') or ''),'ph_question_version_id':str(q.get('question_version_id') or ''),
      'ph_question_checksum_sha256':str(q.get('question_checksum_sha256') or ''),'ph_market_id':str(curr.get('market_id') or ''),'ph_programme_id':str(curr.get('programme_id') or ''),
      'ph_subject_id':str(curr.get('subject_id') or ''),'ph_chapter_id':str(curr.get('chapter_id') or ''),'ph_claim_family_id':str(arch.get('claim_family_id') or ''),
      'ph_reasoning_seed_id':str(arch.get('reasoning_seed_id') or ''),'ph_dependency_group_id':str(arch.get('dependency_group_id') or ''),'ph_dependency_type':str(arch.get('dependency_type') or ''),
      'ph_evidence_role':str(arch.get('evidence_role') or ''),'ph_independent_mastery_weight':float(arch.get('independent_mastery_weight') or 0),
      'ph_knowledge_node_ids_json':canonical_json(arch.get('knowledge_node_ids') or []),'ph_mastery_ceiling':str(arch.get('mastery_ceiling') or ''),
      'ph_cognitive_demand':str(arch.get('cognitive_demand') or ''),'ph_curriculum_snapshot_json':canonical_json(curr),'ph_governance_snapshot_json':canonical_json(gov),
      'ph_provenance_snapshot_json':canonical_json(prov),'ph_is_auto_markable':1 if auto else 0,
      '_display_chapter_number':str(disp.get('chapter_number') or ''),'_display_chapter_name':str(disp.get('chapter') or ''),
      '_source_locator':str(source.get('locator') or ''),'_source_id':str(source.get('source_id') or '')
    }


def _manifest_pull_credentials():
    return os.environ.get('SCOREMAX_TO_POWER_HOUSE_TOKEN','')


def _https_origin(value, *, label):
    """Return a canonical HTTPS origin tuple; reject ambiguous authority syntax.

    This validator deliberately runs before ScoreMax reads any Power House credential.
    Host comparison is exact after IDNA/lower-case normalization, so suffix-host and
    userinfo confusion cannot satisfy the deployment-controlled origin boundary.
    """
    raw=str(value or '').strip()
    try:
        parsed=urlparse(raw)
        port=parsed.port
    except Exception as exc:
        raise ValueError(f'{label} is not a valid URL authority') from exc
    if parsed.scheme.lower()!='https':
        raise ValueError(f'{label} must use HTTPS')
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f'{label} must not contain userinfo')
    host=parsed.hostname
    if not host:
        raise ValueError(f'{label} must include a hostname')
    try:
        host=host.rstrip('.').encode('idna').decode('ascii').lower()
    except Exception as exc:
        raise ValueError(f'{label} hostname is invalid') from exc
    # An absent port means the HTTPS default. An explicit port is never treated as
    # absent: in particular, :0 / :00 / :000 must fail closed rather than normalize
    # to 443. urlparse().port already rejects non-numeric and >65535 values.
    canonical_port=443 if port is None else int(port)
    if canonical_port<1 or canonical_port>65535:
        raise ValueError(f'{label} port is outside the valid range 1..65535')
    return ('https',host,canonical_port)


def _trusted_power_house_origin():
    return _https_origin(os.environ.get('SCOREMAX_POWER_HOUSE_BASE_URL',''),label='SCOREMAX_POWER_HOUSE_BASE_URL')


def _validate_power_house_package_url(url):
    trusted=_trusted_power_house_origin()
    candidate=_https_origin(url,label='Power House package URL')
    if candidate!=trusted:
        raise ValueError('Power House package URL origin does not match configured Power House origin')
    return str(url or '').strip(),trusted


class _PowerHouseSameOriginRedirectHandler(urlrequest.HTTPRedirectHandler):
    """Permit redirects only inside the already-validated Power House origin."""
    def __init__(self,trusted_origin):
        super().__init__()
        self.trusted_origin=trusted_origin

    def redirect_request(self,req,fp,code,msg,headers,newurl):
        candidate=_https_origin(newurl,label='Power House redirect URL')
        if candidate!=self.trusted_origin:
            # Raise before urllib can construct or send a redirected request carrying auth.
            raise ValueError('Cross-origin Power House package redirect blocked')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def _download_manifest_package(url,timeout=20):
    # P0 security boundary: validate the caller-supplied URL against deployment-controlled
    # Power House origin BEFORE reading the bearer token or opening any network request.
    package_url,trusted_origin=_validate_power_house_package_url(url)
    headers={'Accept':'application/zip'}
    token=_manifest_pull_credentials()
    if token: headers['Authorization']='Bearer '+token
    req=urlrequest.Request(package_url,headers=headers,method='GET')
    opener=urlrequest.build_opener(_PowerHouseSameOriginRedirectHandler(trusted_origin))
    with opener.open(req,timeout=timeout) as rr:
        return rr.read()


def _safe_zip_member(name):
    n=str(name or '').replace('\\','/')
    return bool(n) and not n.startswith('/') and '..' not in Path(n).parts


def _load_manifest_package(package_bytes,release):
    pkg_sha=hashlib.sha256(package_bytes).hexdigest()
    if pkg_sha!=str(release.get('package_checksum_sha256') or ''):
        raise ValueError('Package SHA-256 mismatch')
    with zipfile.ZipFile(io.BytesIO(package_bytes)) as z:
        bad=z.testzip()
        if bad: raise ValueError('ZIP integrity failure: '+str(bad))
        names=z.namelist()
        if 'manifest.json' not in names: raise ValueError('manifest.json missing')
        if any(not _safe_zip_member(n) for n in names): raise ValueError('Unsafe package member path')
        manifest_bytes=z.read('manifest.json')
        if hashlib.sha256(manifest_bytes).hexdigest()!=str(release.get('manifest_checksum_sha256') or ''):
            raise ValueError('Manifest SHA-256 mismatch')
        manifest=json.loads(manifest_bytes.decode('utf-8'))
        serr=_schema_errors(manifest,'PH_SM_APPROVED_CONTENT_MANIFEST_V1','1.1.0')
        if serr: raise ValueError('Manifest schema invalid: '+canonical_json(serr))
        if manifest['release_id']!=release.get('release_id') or manifest['release_version']!=release.get('release_version'):
            raise ValueError('Manifest release identity mismatch')
        listed={f['path']:f for f in manifest['files']}
        for path,meta in listed.items():
            if path not in names: raise ValueError('Manifest file missing: '+path)
            data=z.read(path)
            if len(data)!=int(meta['size_bytes']) or hashlib.sha256(data).hexdigest()!=meta['sha256']:
                raise ValueError('Manifest member integrity mismatch: '+path)
        content_file=manifest['content_file']
        if content_file not in listed: raise ValueError('Content file is not governed by manifest files list')
        content_bytes=z.read(content_file)
        if hashlib.sha256(content_bytes).hexdigest()!=manifest['content_file_sha256']:
            raise ValueError('Content file SHA-256 mismatch')
        package=json.loads(content_bytes.decode('utf-8'))
        serr=_schema_errors(package,'PH_SM_APPROVED_CONTENT_PACKAGE_V1','1.1.0')
        if serr: raise ValueError('Content package schema invalid: '+canonical_json(serr))
        if package['release_id']!=release.get('release_id') or package['release_version']!=release.get('release_version'):
            raise ValueError('Content package release identity mismatch')
        if int(manifest['question_count'])!=len(package['questions']) or int(manifest['stimulus_count'])!=len(package['stimuli']):
            raise ValueError('Manifest count mismatch')
        return package,manifest


def _stage_question_version(c,q,release_id,release_version,stim_lookup,ordinal,now):
    qid=str(q['question_id']); qvid=str(q['question_version_id']); qchk=str(q['question_checksum_sha256'])
    existing=c.execute('SELECT * FROM integration_ph_question_version_store WHERE question_id=? AND question_version_id=?',(qid,qvid)).fetchone()
    if existing and existing['question_checksum_sha256']!=qchk:
        raise ValueError(f'QUESTION_VERSION_CHECKSUM_CONFLICT::{qid}::{qvid}')
    proj=_projection(q,stim_lookup)
    if not existing:
        c.execute('''INSERT INTO integration_ph_question_version_store(question_id,question_version_id,question_version_number,question_checksum_sha256,
          supersedes_question_version_id,effective_from,curriculum_json,content_json,architecture_json,governance_json,provenance_json,
          scoremax_projection_json,first_admitted_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (qid,qvid,int(q['question_version_number']),qchk,q.get('supersedes_question_version_id'),q.get('effective_from'),
           canonical_json(q.get('curriculum') or {}),canonical_json(q.get('content') or {}),canonical_json(q.get('architecture') or {}),
           canonical_json(q.get('governance') or {}),canonical_json(q.get('provenance') or {}),canonical_json(proj),now))
        c.execute('''INSERT OR IGNORE INTO integration_ph_question_versions(release_id,release_version,question_id,question_version_id,question_version_number,
          question_checksum_sha256,supersedes_question_version_id,effective_from,curriculum_json,content_json,architecture_json,governance_json,provenance_json,scoremax_projection_json,admitted_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',(release_id,release_version,qid,qvid,int(q['question_version_number']),qchk,q.get('supersedes_question_version_id'),q.get('effective_from'),
          canonical_json(q.get('curriculum') or {}),canonical_json(q.get('content') or {}),canonical_json(q.get('architecture') or {}),canonical_json(q.get('governance') or {}),canonical_json(q.get('provenance') or {}),canonical_json(proj),now))
    c.execute('''INSERT OR IGNORE INTO integration_ph_release_question_membership(release_id,release_version,question_id,question_version_id,ordinal,admitted_at)
      VALUES(?,?,?,?,?,?)''',(release_id,release_version,qid,qvid,int(ordinal),now))


def _stage_stimulus_version(c,s,release_id,release_version,ordinal,now):
    sid=str(s['stimulus_id']); svid=str(s['stimulus_version_id']); schk=str(s['stimulus_checksum_sha256'])
    existing=c.execute('SELECT * FROM integration_ph_stimulus_version_store WHERE stimulus_id=? AND stimulus_version_id=?',(sid,svid)).fetchone()
    if existing and existing['stimulus_checksum_sha256']!=schk:
        raise ValueError(f'STIMULUS_VERSION_CHECKSUM_CONFLICT::{sid}::{svid}')
    if not existing:
        c.execute('''INSERT INTO integration_ph_stimulus_version_store(stimulus_id,stimulus_version_id,stimulus_checksum_sha256,immutable_payload_json,first_admitted_at)
          VALUES(?,?,?,?,?)''',(sid,svid,schk,canonical_json(s),now))
        c.execute('''INSERT OR IGNORE INTO integration_ph_stimulus_versions(release_id,release_version,stimulus_id,stimulus_version_id,stimulus_checksum_sha256,immutable_payload_json,admitted_at)
          VALUES(?,?,?,?,?,?,?)''',(release_id,release_version,sid,svid,schk,canonical_json(s),now))
    c.execute('''INSERT OR IGNORE INTO integration_ph_release_stimulus_membership(release_id,release_version,stimulus_id,stimulus_version_id,ordinal,admitted_at)
      VALUES(?,?,?,?,?,?)''',(release_id,release_version,sid,svid,int(ordinal),now))


def _withdraw_release(c,envelope,semantic_checksum_sha256=''):
    p=envelope['payload']; rel=p['release']; rid=rel['release_id']; target=str(rel.get('supersedes_release_version') or '')
    now=utcnow()
    c.execute('''INSERT INTO integration_ph_content_releases(release_id,release_version,package_checksum_sha256,manifest_checksum_sha256,payload_checksum_sha256,semantic_checksum_sha256,
      release_status,local_status,effective_at,generated_at,market_id,programme_id,subject_id,chapter_id,question_count,stimulus_count,readiness_policy_version,
      supersedes_release_version,source_system_version,immutable_payload_json,admitted_at,schema_version,release_operation,withdrawn_at,withdrawal_reason)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (rid,rel['release_version'],rel['package_checksum_sha256'],rel['manifest_checksum_sha256'],envelope['payload_checksum_sha256'],semantic_checksum_sha256,rel['release_status'],'WITHDRAWN',
       rel.get('effective_at'),rel.get('generated_at'),rel['market_id'],rel['programme_id'],rel['subject_id'],rel['chapter_id'],0,0,rel.get('readiness_policy_version',''),
       target,envelope.get('producer_version',''),canonical_json(p),now,envelope.get('schema_version','1.1.0'),'WITHDRAW_RELEASE',rel.get('withdrawn_at') or now,rel.get('withdrawal_reason','')))
    if target:
        c.execute("UPDATE integration_ph_content_releases SET local_status='WITHDRAWN',withdrawn_at=?,withdrawal_reason=? WHERE release_id=? AND release_version=?",
                  (rel.get('withdrawn_at') or now,rel.get('withdrawal_reason',''),rid,target))
        c.execute("UPDATE questions SET active=0,status='Withdrawn' WHERE ph_projection_owner='POWER_HOUSE' AND ph_release_id=? AND ph_release_version=?",(rid,target))
    else:
        c.execute("UPDATE questions SET active=0,status='Withdrawn' WHERE ph_projection_owner='POWER_HOUSE' AND ph_release_id=?",(rid,))
    queue_product_event(c,event_type='CONTENT_AVAILABILITY_CHANGED',event_id=f'CONTENT::{rid}::{rel["release_version"]}::WITHDRAWN',actor_type='SYSTEM',actor_id='SCOREMAX',
      context={'market_id':rel['market_id'],'programme_id':rel['programme_id'],'subject_id':rel['subject_id'],'chapter_id':rel['chapter_id']},
      event_data={'power_house_release_id':rid,'power_house_release_version':rel['release_version'],'power_house_release_checksum_sha256':rel['package_checksum_sha256'],'live_status':'WITHDRAWN'},producer_version=SCOREMAX_INTEGRATION_RELEASE)

def admit_content_envelope(c,envelope,content_sha_header=''):
    """Validate, semantically compile, and atomically admit a governed PH content snapshot."""
    p=envelope.get('payload') if isinstance(envelope.get('payload'),dict) else {}
    # Frozen v1.0 MANIFEST_PULL has a known contradictory schema; v1.1.0 is the governed executable form.
    if str(envelope.get('schema_version') or '')=='1.0.0' and str(p.get('delivery_mode') or '').upper()=='MANIFEST_PULL':
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',[{'code':'FROZEN_MANIFEST_PULL_SCHEMA_CONFLICT','path':'payload.delivery_mode','message':'Frozen v1.0 MANIFEST_PULL contradiction is resolved only by schema 1.1.0.','retryable':False}]); c.commit(); return rec,422
    errors=_basic_validate(envelope,'PH_SM_APPROVED_CONTENT_V1','POWER_HOUSE')
    if errors:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',errors); c.commit(); return rec,422
    if content_sha_header and content_sha_header!=envelope['payload_checksum_sha256']:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',[{'code':'HEADER_CHECKSUM','path':'X-Content-SHA256','message':'Header checksum mismatch','retryable':False}]); c.commit(); return rec,400

    schema_version=str(envelope.get('schema_version') or SCHEMA_VERSION)
    delivery=str(p.get('delivery_mode') or '').upper()
    operation=str(p.get('release_operation') or ('PUBLISH_SNAPSHOT' if schema_version=='1.0.0' else '')).upper()
    rel=p.get('release') or {}

    if operation=='WITHDRAW_RELEASE':
        semantic=release_semantic_checksum(rel,[],[],operation)
        _begin_immediate(c)
        state,row=_register_inbound(c,envelope)
        identity=f"{rel.get('release_id')}|{rel.get('release_version')}"
        existing=c.execute('SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(rel.get('release_id'),rel.get('release_version'))).fetchone()
        if state=='DUPLICATE':
            rec=_durable_replay_receipt(c,row)
            if rec: c.commit(); return rec,200
        if state=='CONFLICT':
            rec=_quarantine(c,envelope,identity,semantic,row['payload_checksum_sha256'] if row else '','INBOUND_IDEMPOTENCY_CONFLICT'); c.commit(); return rec,409
        if existing:
            old_sem=str(existing['semantic_checksum_sha256'] or '') if 'semantic_checksum_sha256' in existing.keys() else ''
            if old_sem and old_sem!=semantic:
                rec=_quarantine(c,envelope,identity,semantic,old_sem,'SEMANTIC_IDENTITY_VERSION_CONFLICT'); c.commit(); return rec,409
            rec=_receipt(c,envelope,'DUPLICATE'); _record_inbound(c,envelope,rec,'DUPLICATE'); c.commit(); return rec,200
        _withdraw_release(c,envelope,semantic_checksum_sha256=semantic)
        rec=_receipt(c,envelope,'ACCEPTED'); _record_inbound(c,envelope,rec,'ACCEPTED'); c.commit(); return rec,202

    if operation!='PUBLISH_SNAPSHOT' or delivery not in {'INLINE','MANIFEST_PULL'}:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',[{'code':'DELIVERY_OPERATION','path':'payload','message':'Unsupported delivery mode or release operation','retryable':False}]); c.commit(); return rec,422

    questions=list(p.get('questions') or []); stimuli=list(p.get('stimuli') or []); manifest=None
    if delivery=='MANIFEST_PULL':
        try:
            package_bytes=_download_manifest_package(p.get('package_download_url'))
            package,manifest=_load_manifest_package(package_bytes,rel)
            questions=list(package.get('questions') or []); stimuli=list(package.get('stimuli') or [])
        except Exception as exc:
            retryable=isinstance(exc,(TimeoutError,ConnectionError,urlerror.URLError)) or (isinstance(exc,urlerror.HTTPError) and int(getattr(exc,'code',0) or 0) in {408,425,429,500,502,503,504})
            code='MANIFEST_PULL_TRANSPORT' if retryable else 'MANIFEST_PULL_INTEGRITY'
            status_code=503 if retryable else 422
            _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',[{'code':code,'path':'payload.package_download_url','message':str(exc),'retryable':retryable}]); c.commit(); return rec,status_code

    # Academic/content compiler: all checks complete before release/version/question/stimulus writes.
    errors=[]
    if str(rel.get('release_status') or '').upper()!='ACADEMICALLY_READY':
        errors.append({'code':'RELEASE_STATUS','path':'payload.release.release_status','message':'Only ACADEMICALLY_READY releases may be admitted','retryable':False})
    if int(rel.get('question_count') or 0)!=len(questions):
        errors.append({'code':'QUESTION_COUNT','path':'payload.release.question_count','message':'Question count mismatch','retryable':False})
    if int(rel.get('stimulus_count') or 0)!=len(stimuli):
        errors.append({'code':'STIMULUS_COUNT','path':'payload.release.stimulus_count','message':'Stimulus count mismatch','retryable':False})
    checksum_errors=_verify_question_stimulus_checksums({'questions':questions,'stimuli':stimuli})
    if checksum_errors:
        _begin_immediate(c)
        ident=f"{rel.get('release_id','')}|{rel.get('release_version','')}"
        rec=_quarantine(c,envelope,ident,envelope.get('payload_checksum_sha256',''),'', 'CONTENT_OBJECT_CHECKSUM_MISMATCH')
        c.commit(); return rec,409
    seen=set()
    for i,q in enumerate(questions):
        qid=str(q.get('question_id') or ''); qvid=str(q.get('question_version_id') or '')
        if (qid,qvid) in seen:
            errors.append({'code':'DUPLICATE_QUESTION_VERSION','path':f'payload.questions[{i}]','message':'Duplicate question version in package','retryable':False})
        seen.add((qid,qvid))
        ok,why=_governance_ready(q)
        if not ok:
            errors.append({'code':why,'path':f'payload.questions[{i}].governance','message':'Question is not learner-release-ready','retryable':False})
        curr=q.get('curriculum') or {}
        for rk in ('market_id','programme_id','subject_id','chapter_id'):
            if str(curr.get(rk) or '')!=str(rel.get(rk) or ''):
                errors.append({'code':'SCOPE_MISMATCH','path':f'payload.questions[{i}].curriculum.{rk}','message':'Question scope differs from release scope','retryable':False})
    errors.extend(_semantic_content_errors(questions,stimuli))
    if errors:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',errors); c.commit(); return rec,422

    semantic=release_semantic_checksum(rel,questions,stimuli,operation)
    _begin_immediate(c)
    state,row=_register_inbound(c,envelope)
    identity=f"{rel.get('release_id')}|{rel.get('release_version')}"
    existing=c.execute('SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(rel.get('release_id'),rel.get('release_version'))).fetchone()
    if state=='DUPLICATE':
        rec=_durable_replay_receipt(c,row)
        if rec: c.commit(); return rec,200
    if state=='CONFLICT':
        rec=_quarantine(c,envelope,identity,semantic,row['payload_checksum_sha256'] if row else '','INBOUND_IDEMPOTENCY_CONFLICT'); c.commit(); return rec,409
    if existing:
        if str(existing['local_status'] or '').upper()=='QUARANTINED':
            rec=_receipt(c,envelope,'QUARANTINED',[{'code':'MIGRATION_SEMANTIC_REVALIDATION_FAILED','path':'payload','message':'This legacy identity failed V6.5.3 semantic revalidation and requires governed replacement under a new version.','retryable':False}]); c.commit(); return rec,409
        old_sem=str(existing['semantic_checksum_sha256'] or '') if 'semantic_checksum_sha256' in existing.keys() else ''
        # Legacy rows without this V6.5.3 checksum are never silently redefined.
        if not old_sem:
            old_payload={}
            try: old_payload=json.loads(existing['immutable_payload_json'] or '{}')
            except Exception: old_payload={}
            if old_payload and str((old_payload.get('release') or {}).get('release_id') or '')==str(rel.get('release_id') or ''):
                old_sem=release_semantic_checksum(old_payload.get('release') or {},old_payload.get('questions') or [],old_payload.get('stimuli') or [],old_payload.get('release_operation') or 'PUBLISH_SNAPSHOT')
        if old_sem!=semantic:
            rec=_quarantine(c,envelope,identity,semantic,old_sem or 'LEGACY_IDENTITY_ALREADY_EXISTS','SEMANTIC_IDENTITY_VERSION_CONFLICT'); c.commit(); return rec,409
        rec=_receipt(c,envelope,'DUPLICATE'); _record_inbound(c,envelope,rec,'DUPLICATE'); c.commit(); return rec,200

    # Immutable object identity preflight.
    for q in questions:
        old=c.execute('SELECT question_checksum_sha256 FROM integration_ph_question_version_store WHERE question_id=? AND question_version_id=?',(q['question_id'],q['question_version_id'])).fetchone()
        if old and old['question_checksum_sha256']!=q['question_checksum_sha256']:
            rec=_quarantine(c,envelope,f"{q['question_id']}|{q['question_version_id']}",q['question_checksum_sha256'],old['question_checksum_sha256'],'QUESTION_VERSION_CHECKSUM_CONFLICT'); c.commit(); return rec,409
    for st in stimuli:
        old=c.execute('SELECT stimulus_checksum_sha256 FROM integration_ph_stimulus_version_store WHERE stimulus_id=? AND stimulus_version_id=?',(st['stimulus_id'],st['stimulus_version_id'])).fetchone()
        if old and old['stimulus_checksum_sha256']!=st['stimulus_checksum_sha256']:
            rec=_quarantine(c,envelope,f"{st['stimulus_id']}|{st['stimulus_version_id']}",st['stimulus_checksum_sha256'],old['stimulus_checksum_sha256'],'STIMULUS_VERSION_CHECKSUM_CONFLICT'); c.commit(); return rec,409

    now=utcnow(); effective=rel.get('effective_at'); eff=parse_dt(effective) if effective else None
    c.execute('''INSERT INTO integration_ph_content_releases(release_id,release_version,package_checksum_sha256,manifest_checksum_sha256,
      payload_checksum_sha256,semantic_checksum_sha256,release_status,local_status,effective_at,generated_at,market_id,programme_id,subject_id,chapter_id,
      question_count,stimulus_count,readiness_policy_version,supersedes_release_version,source_system_version,immutable_payload_json,admitted_at,
      schema_version,release_operation) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],rel['manifest_checksum_sha256'],envelope['payload_checksum_sha256'],semantic,rel['release_status'],
       'STAGED',effective,rel.get('generated_at'),rel['market_id'],rel['programme_id'],rel['subject_id'],rel['chapter_id'],len(questions),len(stimuli),
       rel.get('readiness_policy_version',''),rel.get('supersedes_release_version'),envelope.get('producer_version',''),canonical_json(p),now,schema_version,'PUBLISH_SNAPSHOT'))
    stim_lookup={str(st.get('stimulus_id')):st for st in stimuli if st.get('stimulus_id')}
    for i,st in enumerate(stimuli): _stage_stimulus_version(c,st,rel['release_id'],rel['release_version'],i,now)
    for i,q in enumerate(questions): _stage_question_version(c,q,rel['release_id'],rel['release_version'],stim_lookup,i,now)
    rec=_receipt(c,envelope,'ACCEPTED'); _record_inbound(c,envelope,rec,'ACCEPTED')
    # Academic/content admission ends at immutable STAGED state. Power House effective_at
    # is retained as source metadata only; it is never product-activation authority.
    c.commit(); return rec,202


def _activation_authorization(c,rel):
    return c.execute('''SELECT * FROM integration_ph_product_activation_authorizations
      WHERE release_id=? AND release_version=? AND package_checksum_sha256=?
        AND activation_status IN ('AUTHORIZED','ACTIVATED')
      ORDER BY id LIMIT 1''',(rel['release_id'],rel['release_version'],rel['package_checksum_sha256'])).fetchone()


def _activate_release(c,release_id,release_version):
    rel=c.execute('SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(release_id,release_version)).fetchone()
    if not rel or rel['local_status'] in {'ACTIVE','WITHDRAWN','SUPERSEDED','QUARANTINED'}: return 0
    # Structural authority fence: no internal/startup/health caller can make staged
    # Power House content learner-live without an exact ScoreMax-owned authorization.
    auth=_activation_authorization(c,rel)
    if not auth: return 0
    qvs=c.execute('''SELECT v.*,m.ordinal FROM integration_ph_release_question_membership m
      JOIN integration_ph_question_version_store v ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
      WHERE m.release_id=? AND m.release_version=? ORDER BY m.ordinal,m.id''',(release_id,release_version)).fetchall()
    new_external_ids={r['question_id'] for r in qvs}
    # Remove only prior Power House projections omitted by the new full snapshot; never touch legacy local questions.
    old=c.execute("SELECT id,ph_question_id FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND ph_release_id=? AND COALESCE(active,0)=1",(release_id,)).fetchall()
    for r in old:
        if r['ph_question_id'] not in new_external_ids:
            c.execute("UPDATE questions SET active=0,status='Withdrawn' WHERE id=?",(r['id'],))
    c.execute("UPDATE integration_ph_content_releases SET local_status='SUPERSEDED',superseded_at=? WHERE release_id=? AND release_version<>? AND local_status='ACTIVE'",(utcnow(),release_id,release_version))
    qcols=_cols(c,'questions')
    for rv in qvs:
        proj=json.loads(rv['scoremax_projection_json']); proj['ph_release_id']=release_id; proj['ph_release_version']=release_version; proj['ph_release_checksum_sha256']=rel['package_checksum_sha256']
        external_qid=rv['question_id']
        # local question identity is namespaced and stable across PH versions, so an opaque external ID can never overwrite a legacy row.
        local_qid='PHQ::'+hashlib.sha256(external_qid.encode('utf-8')).hexdigest()[:32]
        proj['question_id']=local_qid; proj['ph_question_id']=external_qid; proj['ph_projection_owner']='POWER_HOUSE'
        family_key=proj['family_key']; family_id=proj['family_id']
        c.execute('''INSERT INTO question_families(family_key,family_id,country,qualification,exam_board,curriculum_version,programme,subject,
          learning_outcome,concept,construct_signature,invariants_json,review_status,active,source_type)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(family_key) DO UPDATE SET family_id=excluded.family_id,
          programme=excluded.programme,subject=excluded.subject,learning_outcome=excluded.learning_outcome,concept=excluded.concept,
          review_status='Approved',active=1,source_type=excluded.source_type,updated_at=CURRENT_TIMESTAMP''',
          (family_key,family_id,proj.get('country',''),proj.get('qualification',''),proj.get('exam_board',''),proj.get('curriculum_version',''),proj['programme'],proj['subject'],
           proj.get('learning_outcome',''),proj.get('concept',''),family_id,'[]','Approved',1,'Power House Approved Content'))
        existing=c.execute("SELECT * FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND ph_question_id=? ORDER BY id LIMIT 1",(external_qid,)).fetchone()
        clean={k:v for k,v in proj.items() if not k.startswith('_')}
        allowed=[k for k in clean if k in qcols and k!='id']
        if existing:
            sets=','.join(f'{k}=?' for k in allowed); vals=[clean[k] for k in allowed]+[existing['id']]
            c.execute(f'UPDATE questions SET {sets} WHERE id=?',vals); qdb=existing['id']
        else:
            names=allowed; vals=[clean[k] for k in names]; marks=','.join('?' for _ in names)
            cur=c.execute(f"INSERT INTO questions({','.join(names)}) VALUES({marks})",vals); qdb=cur.lastrowid
        c.execute('UPDATE integration_ph_question_version_store SET local_question_db_id=? WHERE id=?',(qdb,rv['id']))
        c.execute('UPDATE integration_ph_question_versions SET local_question_db_id=? WHERE question_id=? AND question_version_id=?',(qdb,external_qid,rv['question_version_id']))
        curr=json.loads(rv['curriculum_json']); disp=curr.get('display') or {}
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='chapter_catalogue'").fetchone():
            source=str(proj.get('chapter') or '')
            row=c.execute('SELECT id FROM chapter_catalogue WHERE programme=? AND subject=? AND source_chapter=?',(proj['programme'],proj['subject'],source)).fetchone()
            label=(f"Chapter {disp.get('chapter_number')} — {disp.get('chapter')}" if disp.get('chapter_number') and disp.get('chapter') else str(disp.get('chapter') or source))
            vals=(str(disp.get('chapter_number') or ''),str(disp.get('chapter') or ''),label,'COMPLETE_GOVERNED_METADATA','POWER_HOUSE','Approved')
            if row: c.execute('''UPDATE chapter_catalogue SET chapter_number=?,chapter_name=?,display_label=?,identity_status=?,metadata_source=?,review_status=?,active=1,updated_at=CURRENT_TIMESTAMP WHERE id=?''',vals+(row['id'],))
            else: c.execute('''INSERT INTO chapter_catalogue(programme,subject,source_chapter,chapter_number,chapter_name,display_label,identity_status,metadata_source,review_status,active) VALUES(?,?,?,?,?,?,?,?,?,1)''',(proj['programme'],proj['subject'],source)+vals)
    c.execute("UPDATE integration_ph_content_releases SET local_status='ACTIVE',activated_at=? WHERE release_id=? AND release_version=?",(utcnow(),release_id,release_version))
    queue_product_event(c,event_type='CONTENT_AVAILABILITY_CHANGED',event_id=f'CONTENT::{release_id}::{release_version}::LIVE',actor_type='SYSTEM',actor_id='SCOREMAX',context={'market_id':rel['market_id'],'programme_id':rel['programme_id'],'subject_id':rel['subject_id'],'chapter_id':rel['chapter_id']},event_data={'power_house_release_id':release_id,'power_house_release_version':release_version,'power_house_release_checksum_sha256':rel['package_checksum_sha256'],'live_status':'LIVE_TO_LEARNERS'},producer_version=SCOREMAX_INTEGRATION_RELEASE)
    c.execute("""UPDATE integration_ph_product_activation_authorizations
      SET activation_status='ACTIVATED',activated_at=?
      WHERE id=? AND activation_status IN ('AUTHORIZED','ACTIVATED')""",(utcnow(),auth['id']))
    return len(qvs)


def authorize_product_activation(c,release_id,release_version,package_checksum_sha256,actor,reason):
    """Authorize and activate one exact immutable staged Power House release.

    This is ScoreMax product authority. Power House effective_at is deliberately not
    consulted. The first authorization record is durable evidence; exact replay is
    idempotent and cannot change its actor/reason/time.
    """
    rid=str(release_id or '').strip(); ver=str(release_version or '').strip()
    chk=str(package_checksum_sha256 or '').strip().lower(); who=str(actor or '').strip(); why=str(reason or '').strip()
    if not rid or not ver or not chk:
        return {'status':'REJECTED','code':'ACTIVATION_IDENTITY_REQUIRED','activated_count':0}
    if not who or not why:
        return {'status':'REJECTED','code':'ACTIVATION_EVIDENCE_REQUIRED','activated_count':0}
    rel=c.execute('SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(rid,ver)).fetchone()
    if not rel:
        return {'status':'REJECTED','code':'RELEASE_NOT_FOUND','activated_count':0}
    if str(rel['package_checksum_sha256'] or '').lower()!=chk:
        return {'status':'REJECTED','code':'RELEASE_CHECKSUM_MISMATCH','activated_count':0}
    existing=_activation_authorization(c,rel)
    if rel['local_status']=='ACTIVE':
        if existing:
            return {'status':'ACTIVE','code':'IDEMPOTENT_REPLAY','activated_count':0,'authorization_id':existing['id']}
        return {'status':'REJECTED','code':'ACTIVE_WITHOUT_AUTHORIZATION','activated_count':0}
    if rel['local_status']!='STAGED' or str(rel['release_operation'] or '').upper()!='PUBLISH_SNAPSHOT':
        return {'status':'REJECTED','code':'RELEASE_NOT_ACTIVATABLE','activated_count':0}
    if not existing:
        now=utcnow()
        c.execute('''INSERT INTO integration_ph_product_activation_authorizations(
          release_id,release_version,package_checksum_sha256,authorized_by,authorized_at,reason,activation_status)
          VALUES(?,?,?,?,?,?,'AUTHORIZED')''',(rid,ver,chk,who,now,why))
        existing=_activation_authorization(c,rel)
    count=_activate_release(c,rid,ver)
    final=c.execute('SELECT local_status FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(rid,ver)).fetchone()
    if not final or final['local_status']!='ACTIVE':
        return {'status':'REJECTED','code':'ACTIVATION_DID_NOT_COMPLETE','activated_count':0,'authorization_id':existing['id'] if existing else None}
    return {'status':'ACTIVE','code':'ACTIVATED' if count else 'IDEMPOTENT_REPLAY','activated_count':int(count),'authorization_id':existing['id'] if existing else None}


def activate_due_releases(c,limit=100):
    """Crash-recovery activation for *already authorized* staged releases only.

    Kept under the historical name for compatibility. Source effective_at is not an
    authorization signal and is intentionally absent from this query.
    """
    rows=c.execute("""SELECT r.release_id,r.release_version FROM integration_ph_content_releases r
      JOIN integration_ph_product_activation_authorizations a
        ON a.release_id=r.release_id AND a.release_version=r.release_version
       AND a.package_checksum_sha256=r.package_checksum_sha256
       AND a.activation_status='AUTHORIZED'
      WHERE r.local_status='STAGED' AND r.release_operation='PUBLISH_SNAPSHOT'
      ORDER BY a.authorized_at,a.id LIMIT ?""",(int(limit),)).fetchall()
    total=0
    for r in rows: total+=_activate_release(c,r['release_id'],r['release_version'])
    return total



def _semantic_blueprint_errors(p):
    errors=[]; sections=list(p.get('sections') or [])
    if not sections:
        errors.append({'code':'BLUEPRINT_SECTIONS_REQUIRED','path':'payload.sections','message':'A released blueprint requires at least one section','retryable':False})
        return errors
    orders=set()
    for i,sec in enumerate(sections):
        path=f'payload.sections[{i}]'; order=sec.get('order')
        if order in orders:
            errors.append({'code':'DUPLICATE_SECTION_ORDER','path':path+'.order','message':'Section order must be unique','retryable':False})
        orders.add(order)
        try: count=int(sec.get('question_count') or 0)
        except Exception: count=0
        if count<=0:
            errors.append({'code':'INVALID_SECTION_QUESTION_COUNT','path':path+'.question_count','message':'Each section must require at least one question','retryable':False})
        qmin=0; qmax=0
        rules=list(sec.get('question_type_rules') or [])
        for j,rule in enumerate(rules):
            qt=str(rule.get('question_type') or '').upper()
            if qt not in SUPPORTED_BLUEPRINT_QUESTION_TYPES:
                errors.append({'code':'UNSUPPORTED_BLUEPRINT_QUESTION_TYPE','path':f'{path}.question_type_rules[{j}].question_type','message':'Blueprint requests a question type the current governed runtime cannot execute','retryable':False})
            try: mn=int(rule.get('minimum') or 0); mx=int(rule.get('maximum') if rule.get('maximum') is not None else count)
            except Exception: mn=-1; mx=-1
            if mn<0 or mx<mn:
                errors.append({'code':'INVALID_BLUEPRINT_TYPE_BOUNDS','path':f'{path}.question_type_rules[{j}]','message':'Question-type minimum/maximum bounds are invalid','retryable':False})
            else: qmin+=mn; qmax+=mx
        if rules and (qmin>count or qmax<count):
            errors.append({'code':'BLUEPRINT_TYPE_COUNTS_INCOHERENT','path':path+'.question_type_rules','message':'Question-type bounds cannot satisfy the section question_count','retryable':False})
        cmin=0; cmax=0
        coverage=list(sec.get('coverage_rules') or [])
        for j,rule in enumerate(coverage):
            try: mn=int(rule.get('minimum_questions') or 0); mx=int(rule.get('maximum_questions') if rule.get('maximum_questions') is not None else count)
            except Exception: mn=-1; mx=-1
            if mn<0 or mx<mn:
                errors.append({'code':'INVALID_BLUEPRINT_COVERAGE_BOUNDS','path':f'{path}.coverage_rules[{j}]','message':'Coverage minimum/maximum bounds are invalid','retryable':False})
            else: cmin+=mn; cmax+=mx
        if coverage and (cmin>count or cmax<count):
            errors.append({'code':'BLUEPRINT_COVERAGE_COUNTS_INCOHERENT','path':path+'.coverage_rules','message':'Coverage bounds cannot satisfy the section question_count','retryable':False})
    mr=p.get('marking_rules') or {}
    for field in ('correct_marks','incorrect_marks','unanswered_marks'):
        if _finite_number(mr.get(field)) is None:
            errors.append({'code':'INVALID_BLUEPRINT_MARKING_RULE','path':'payload.marking_rules.'+field,'message':'Blueprint marking values must be finite numbers','retryable':False})
    return errors


def _legacy_release_snapshot(c,row):
    """Reconstruct the governed snapshot retained by pre-V6.5.3 integration rows."""
    try: stored=json.loads(row['immutable_payload_json'] or '{}')
    except Exception: stored={}
    rel=dict(stored.get('release') or {}) if isinstance(stored,dict) else {}
    if not rel:
        rel={k:row[k] for k in (
            'release_id','release_version','package_checksum_sha256','manifest_checksum_sha256','release_status',
            'effective_at','generated_at','market_id','programme_id','subject_id','chapter_id','question_count',
            'stimulus_count','readiness_policy_version','supersedes_release_version'
        ) if k in row.keys()}
    questions=list(stored.get('questions') or []) if isinstance(stored,dict) else []
    stimuli=list(stored.get('stimuli') or []) if isinstance(stored,dict) else []
    if len(questions)!=int(row['question_count'] or 0):
        questions=[]
        rows=c.execute("""SELECT v.* FROM integration_ph_release_question_membership m
          JOIN integration_ph_question_version_store v ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
          WHERE m.release_id=? AND m.release_version=? ORDER BY m.ordinal,m.id""",(row['release_id'],row['release_version'])).fetchall()
        for q in rows:
            def j(name):
                try: return json.loads(q[name] or '{}')
                except Exception: return {}
            questions.append({
                'question_id':q['question_id'],'question_version_id':q['question_version_id'],
                'question_version_number':int(q['question_version_number'] or 1),
                'question_checksum_sha256':q['question_checksum_sha256'],
                'supersedes_question_version_id':q['supersedes_question_version_id'],'effective_from':q['effective_from'],
                'curriculum':j('curriculum_json'),'content':j('content_json'),'architecture':j('architecture_json'),
                'governance':j('governance_json'),'provenance':j('provenance_json')})
    if len(stimuli)!=int(row['stimulus_count'] or 0):
        stimuli=[]
        rows=c.execute("""SELECT v.immutable_payload_json FROM integration_ph_release_stimulus_membership m
          JOIN integration_ph_stimulus_version_store v ON v.stimulus_id=m.stimulus_id AND v.stimulus_version_id=m.stimulus_version_id
          WHERE m.release_id=? AND m.release_version=? ORDER BY m.ordinal,m.id""",(row['release_id'],row['release_version'])).fetchall()
        for st in rows:
            try: stimuli.append(json.loads(st['immutable_payload_json'] or '{}'))
            except Exception: stimuli.append({})
    return rel,questions,stimuli


def _migration_quarantine_once(c,contract,identity,incoming,existing,reason,payload):
    row=c.execute("SELECT 1 FROM integration_quarantine WHERE contract_name=? AND identity_key=? AND reason_code=? AND status='OPEN' LIMIT 1",(contract,identity,reason)).fetchone()
    if row: return
    c.execute("""INSERT INTO integration_quarantine(contract_name,identity_key,incoming_checksum,existing_checksum,reason_code,message_id,payload_json,status,created_at)
      VALUES(?,?,?,?,?,'',?,'OPEN',?)""",(contract,identity,incoming or '',existing or '',reason,canonical_json(payload),utcnow()))


def _reconcile_legacy_integration_state(c):
    """Fail-safe reconciliation for pre-V6.5.4 databases without rewriting immutable evidence."""
    # V6.5.3 used Python's permissive JSON encoder. Any historical outbox row containing
    # NaN/Infinity is retained byte-for-byte for audit but is made non-dispatchable.
    for row in c.execute("SELECT * FROM integration_outbox WHERE status NOT IN ('DELIVERED','QUARANTINED') ORDER BY id").fetchall():
        try:
            env=strict_json_loads(row['envelope_json'] or '{}'); canonical_json(env)
        except Exception:
            c.execute("UPDATE integration_outbox SET status='QUARANTINED',last_error_code='MIGRATION_NON_STANDARD_JSON',last_error='Legacy V6.5.3 outbox envelope is not standards-compliant JSON',claim_token='',claim_expires_at='' WHERE id=?",(row['id'],))
            _migration_quarantine_once(c,row['contract_name'],str(row['business_identity'] or row['message_id']),str(row['payload_checksum_sha256'] or ''),'','MIGRATION_NON_STANDARD_JSON',{'outbox_id':row['id'],'message_id':row['message_id']})
    legacy=c.execute("SELECT * FROM integration_ph_content_releases WHERE COALESCE(semantic_checksum_sha256,'')='' ORDER BY id").fetchall()
    for row in legacy:
        operation=str(row['release_operation'] or 'PUBLISH_SNAPSHOT').upper()
        rel,questions,stimuli=_legacy_release_snapshot(c,row)
        semantic=release_semantic_checksum(rel,questions,stimuli,operation)
        errors=[]
        if operation=='PUBLISH_SNAPSHOT':
            if str(row['release_status'] or '').upper()!='ACADEMICALLY_READY':
                errors.append({'code':'RELEASE_STATUS','path':'release.release_status','message':'Legacy release is not ACADEMICALLY_READY','retryable':False})
            if len(questions)!=int(row['question_count'] or 0) or len(stimuli)!=int(row['stimulus_count'] or 0):
                errors.append({'code':'MIGRATION_SNAPSHOT_INCOMPLETE','path':'release','message':'Legacy immutable snapshot cannot be reconstructed completely','retryable':False})
            for i,q in enumerate(questions):
                ok,why=_governance_ready(q)
                if not ok: errors.append({'code':why,'path':f'questions[{i}].governance','message':'Legacy question is not learner-release-ready','retryable':False})
                curr=q.get('curriculum') or {}
                for rk in ('market_id','programme_id','subject_id','chapter_id'):
                    if str(curr.get(rk) or '')!=str(row[rk] or ''):
                        errors.append({'code':'SCOPE_MISMATCH','path':f'questions[{i}].curriculum.{rk}','message':'Legacy question scope differs from release scope','retryable':False})
            errors.extend(_semantic_content_errors(questions,stimuli))
        if errors:
            c.execute("UPDATE integration_ph_content_releases SET semantic_checksum_sha256=?,local_status='QUARANTINED' WHERE id=?",(semantic,row['id']))
            c.execute("UPDATE questions SET active=0,status='Withdrawn' WHERE ph_projection_owner='POWER_HOUSE' AND ph_release_id=? AND ph_release_version=?",(row['release_id'],row['release_version']))
            _migration_quarantine_once(c,'PH_SM_APPROVED_CONTENT_V1',f"{row['release_id']}|{row['release_version']}",semantic,str(row['payload_checksum_sha256'] or ''),'MIGRATION_SEMANTIC_REVALIDATION_FAILED',{'errors':errors})
            continue
        c.execute('UPDATE integration_ph_content_releases SET semantic_checksum_sha256=? WHERE id=?',(semantic,row['id']))
        if operation=='PUBLISH_SNAPSHOT':
            stim_lookup={str(x.get('stimulus_id') or ''):x for x in stimuli if isinstance(x,dict)}
            for q in questions:
                proj=canonical_json(_projection(q,stim_lookup))
                c.execute('UPDATE integration_ph_question_version_store SET scoremax_projection_json=? WHERE question_id=? AND question_version_id=?',(proj,q.get('question_id'),q.get('question_version_id')))
                c.execute('UPDATE integration_ph_question_versions SET scoremax_projection_json=? WHERE question_id=? AND question_version_id=?',(proj,q.get('question_id'),q.get('question_version_id')))
            if str(row['local_status'] or '').upper()=='ACTIVE':
                c.execute("UPDATE integration_ph_content_releases SET local_status='STAGED' WHERE id=?",(row['id'],))
                _activate_release(c,row['release_id'],row['release_version'])

    blueprints=c.execute("SELECT * FROM integration_ph_blueprints WHERE COALESCE(semantic_checksum_sha256,'')='' OR COALESCE(projection_status,'IMMUTABLE_ONLY')='IMMUTABLE_ONLY' ORDER BY id").fetchall()
    for row in blueprints:
        try: payload=json.loads(row['immutable_payload_json'] or '{}')
        except Exception: payload={}
        semantic=blueprint_semantic_checksum(payload)
        errors=[] if str(payload.get('release_state') or '').upper()=='RELEASED' else [{'code':'BLUEPRINT_NOT_RELEASED','path':'release_state','message':'Legacy blueprint is not RELEASED','retryable':False}]
        errors.extend(_semantic_blueprint_errors(payload))
        if errors:
            c.execute("UPDATE integration_ph_blueprints SET semantic_checksum_sha256=?,local_status='QUARANTINED',projection_status='MIGRATION_REJECTED' WHERE id=?",(semantic,row['id']))
            _migration_quarantine_once(c,'PH_SM_ASSESSMENT_BLUEPRINT_V1',f"{row['blueprint_id']}|{row['blueprint_version']}",semantic,str(row['payload_checksum_sha256'] or ''),'MIGRATION_BLUEPRINT_REVALIDATION_FAILED',{'errors':errors})
            continue
        try:
            local_bp_id=_project_blueprint_runtime(c,payload,semantic)
        except Exception as exc:
            c.execute("UPDATE integration_ph_blueprints SET semantic_checksum_sha256=?,local_status='QUARANTINED',projection_status='MIGRATION_REJECTED' WHERE id=?",(semantic,row['id']))
            _migration_quarantine_once(c,'PH_SM_ASSESSMENT_BLUEPRINT_V1',f"{row['blueprint_id']}|{row['blueprint_version']}",semantic,str(row['payload_checksum_sha256'] or ''),'MIGRATION_BLUEPRINT_RUNTIME_FAILED',{'error':str(exc)})
            continue
        c.execute("UPDATE integration_ph_blueprints SET semantic_checksum_sha256=?,local_status='IMPORTED',projection_status='ACTIVE_RUNTIME',projected_blueprint_id=? WHERE id=?",(semantic,local_bp_id,row['id']))

def _project_blueprint_runtime(c,p,semantic):
    """Extend the accepted V5.5 blueprint engine; no parallel assessment engine is created."""
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='assessment_blueprints'").fetchone():
        raise ValueError('Existing ScoreMax assessment blueprint engine is unavailable')
    market=str(p.get('market_id') or ''); programme=str(p.get('programme_id') or '')
    framework_external=f'PH_SCOPE::{market}::{programme}'
    row=c.execute('SELECT * FROM assessment_frameworks WHERE powerhouse_framework_id=?',(framework_external,)).fetchone()
    if row: framework_id=row['id']
    else:
        framework_id=c.execute('''INSERT INTO assessment_frameworks(powerhouse_framework_id,name,country,authority,active)
          VALUES(?,?,?,?,1)''',(framework_external,programme,market,'POWER_HOUSE')).lastrowid
    framework_version_external=f'PH_BLUEPRINT_SCOPE::{p["blueprint_id"]}::{p["blueprint_version"]}'
    fv=c.execute('SELECT * FROM assessment_framework_versions WHERE framework_id=? AND powerhouse_framework_version_id=?',(framework_id,framework_version_external)).fetchone()
    if fv: framework_version_id=fv['id']
    else:
        framework_version_id=c.execute('''INSERT INTO assessment_framework_versions(framework_id,powerhouse_framework_version_id,version_name,effective_from,effective_to,status)
          VALUES(?,?,?,?,?,'ACTIVE')''',(framework_id,framework_version_external,str(p['blueprint_version']),str(p.get('effective_from') or ''),str(p.get('effective_to') or ''))).lastrowid
    existing=c.execute('SELECT * FROM assessment_blueprints WHERE powerhouse_blueprint_id=? AND blueprint_version=?',(p['blueprint_id'],p['blueprint_version'])).fetchone()
    sections=list(p.get('sections') or []); total_questions=sum(int(x.get('question_count') or 0) for x in sections)
    duration_seconds=int(p.get('total_duration_seconds') or 0); duration_minutes=max(1,(duration_seconds+59)//60) if duration_seconds else None
    immutable=canonical_json(p); refs=p.get('source_authority_refs') or []
    if existing:
        if str(existing['payload_checksum'] or '')!=semantic:
            raise ValueError('LOCAL_BLUEPRINT_SEMANTIC_CONFLICT')
        bp_id=existing['id']
        c.execute("UPDATE assessment_blueprints SET local_status='ACTIVE',source_status='RELEASED',sync_status='ACTIVE_RUNTIME',activated_at=COALESCE(NULLIF(activated_at,''),?) WHERE id=?",(utcnow(),bp_id))
    else:
        bp_id=c.execute('''INSERT INTO assessment_blueprints(powerhouse_blueprint_id,framework_id,framework_version_id,blueprint_version,source_status,local_status,
          authority,source_reference,governance_note,total_questions,duration_minutes,difficulty_distribution_json,activation_date,superseded_date,
          source_created_at,source_approved_at,source_approved_by,source_policy_version,payload_checksum,signature_status,sync_status,
          validation_report_json,immutable_payload_json,activated_at)
          VALUES(?,?,?,?,?,'ACTIVE',?,?,?,?,?,'{}',?,'','','','','',?,'FROZEN_CONTRACT_VALIDATED','ACTIVE_RUNTIME','{}',?,?)''',
          (p['blueprint_id'],framework_id,framework_version_id,str(p['blueprint_version']),'RELEASED','POWER_HOUSE',canonical_json(refs),
           'Governed Power House blueprint projected into the existing ScoreMax runtime.',total_questions,duration_minutes,str(p.get('effective_from') or ''),semantic,immutable,utcnow())).lastrowid
        # The frozen PH contract is subject-scoped. Preserve all governed section/rule detail in rules_json
        # while using the accepted local engine's one-row-per-subject storage shape.
        rules={'power_house_sections':sections,'marking_rules':p.get('marking_rules') or {},'permitted_release_ids':p.get('permitted_release_ids') or []}
        c.execute('''INSERT INTO assessment_blueprint_sections(blueprint_id,section_order,section_code,section_title,subject,question_count,weight_percent,duration_minutes,difficulty_distribution_json,rules_json)
          VALUES(?,?,?,?,?,?,?,?,?,?)''',(bp_id,1,'PH_GOVERNED','Power House governed sections',str(p['subject_id']),total_questions,100.0,duration_minutes,'{}',canonical_json(rules)))
    return int(bp_id)


def admit_blueprint_envelope(c,envelope,content_sha_header=''):
    errors=_basic_validate(envelope,'PH_SM_ASSESSMENT_BLUEPRINT_V1','POWER_HOUSE')
    p=envelope.get('payload') if isinstance(envelope.get('payload'),dict) else {}
    if errors:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',errors); c.commit(); return rec,422
    if content_sha_header and content_sha_header!=envelope['payload_checksum_sha256']:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',[{'code':'HEADER_CHECKSUM','path':'X-Content-SHA256','message':'Header checksum mismatch','retryable':False}]); c.commit(); return rec,400
    if str(p.get('release_state') or '').upper()!='RELEASED':
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',[{'code':'BLUEPRINT_NOT_RELEASED','path':'payload.release_state','message':'Only RELEASED blueprints may be admitted','retryable':False}]); c.commit(); return rec,422
    semantic_errors=_semantic_blueprint_errors(p)
    if semantic_errors:
        _begin_immediate(c); rec=_receipt(c,envelope,'REJECTED',semantic_errors); c.commit(); return rec,422
    semantic=blueprint_semantic_checksum(p)
    _begin_immediate(c)
    state,row=_register_inbound(c,envelope); identity=f"{p.get('blueprint_id')}|{p.get('blueprint_version')}"
    existing=c.execute('SELECT * FROM integration_ph_blueprints WHERE blueprint_id=? AND blueprint_version=?',(p['blueprint_id'],p['blueprint_version'])).fetchone()
    if state=='DUPLICATE':
        rec=_durable_replay_receipt(c,row)
        if rec: c.commit(); return rec,200
    if state=='CONFLICT':
        rec=_quarantine(c,envelope,identity,semantic,row['payload_checksum_sha256'] if row else '','INBOUND_IDEMPOTENCY_CONFLICT'); c.commit(); return rec,409
    if existing:
        if str(existing['local_status'] or '').upper()=='QUARANTINED' or str(existing['projection_status'] or '').upper()=='MIGRATION_REJECTED':
            rec=_receipt(c,envelope,'QUARANTINED',[{'code':'MIGRATION_BLUEPRINT_REVALIDATION_FAILED','path':'payload','message':'This legacy blueprint failed V6.5.3 runtime revalidation and requires governed replacement under a new version.','retryable':False}]); c.commit(); return rec,409
        old_sem=str(existing['semantic_checksum_sha256'] or '') if 'semantic_checksum_sha256' in existing.keys() else ''
        if not old_sem:
            try: old_sem=blueprint_semantic_checksum(json.loads(existing['immutable_payload_json'] or '{}'))
            except Exception: old_sem=''
        if old_sem!=semantic:
            rec=_quarantine(c,envelope,identity,semantic,old_sem or 'LEGACY_IDENTITY_ALREADY_EXISTS','SEMANTIC_IDENTITY_VERSION_CONFLICT'); c.commit(); return rec,409
        rec=_receipt(c,envelope,'DUPLICATE'); _record_inbound(c,envelope,rec,'DUPLICATE'); c.commit(); return rec,200
    try:
        local_bp_id=_project_blueprint_runtime(c,p,semantic)
    except Exception as exc:
        c.rollback(); _begin_immediate(c)
        rec=_receipt(c,envelope,'REJECTED',[{'code':'BLUEPRINT_RUNTIME_PROJECTION_FAILED','path':'payload','message':str(exc),'retryable':False}]); c.commit(); return rec,422
    c.execute('''INSERT INTO integration_ph_blueprints(blueprint_id,blueprint_version,blueprint_checksum_sha256,payload_checksum_sha256,semantic_checksum_sha256,release_state,
      market_id,programme_id,subject_id,effective_from,effective_to,immutable_payload_json,local_status,projection_status,projected_blueprint_id,admitted_at)
      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'ACTIVE_RUNTIME',?,?)''',(p['blueprint_id'],p['blueprint_version'],p['blueprint_checksum_sha256'],envelope['payload_checksum_sha256'],semantic,p['release_state'],p['market_id'],p['programme_id'],p['subject_id'],p.get('effective_from'),p.get('effective_to'),canonical_json(p),'IMPORTED',local_bp_id,utcnow()))
    rec=_receipt(c,envelope,'ACCEPTED'); _record_inbound(c,envelope,rec,'ACCEPTED'); c.commit(); return rec,202


def build_session_content_pins(c,question_ids):
    releases={}; questions={}
    for qid in question_ids:
        r=c.execute('''SELECT q.id,q.ph_question_id,q.ph_question_version_id,q.ph_question_checksum_sha256,q.ph_release_id,q.ph_release_version,q.ph_release_checksum_sha256,
          q.ph_market_id,q.ph_programme_id,q.ph_subject_id,q.ph_chapter_id,v.scoremax_projection_json
          FROM questions q LEFT JOIN integration_ph_question_version_store v ON v.question_id=q.ph_question_id AND v.question_version_id=q.ph_question_version_id WHERE q.id=?''',(qid,)).fetchone()
        if not r or not r['ph_question_version_id']: continue
        projection=json.loads(r['scoremax_projection_json'] or '{}') if r['scoremax_projection_json'] else {}
        scope={'market_id':r['ph_market_id'],'programme_id':r['ph_programme_id'],'subject_id':r['ph_subject_id'],'chapter_id':r['ph_chapter_id']}
        pin={'question_db_id':int(r['id']),'question_id':r['ph_question_id'],'question_version_id':r['ph_question_version_id'],'question_checksum_sha256':r['ph_question_checksum_sha256'],'release_id':r['ph_release_id'],'release_version':r['ph_release_version'],'release_checksum_sha256':r['ph_release_checksum_sha256'],**scope,'projection':projection}
        questions[str(qid)]=pin
        if r['ph_release_id']:
            releases[r['ph_release_id']]={'release_id':r['ph_release_id'],'release_version':r['ph_release_version'],'package_checksum_sha256':r['ph_release_checksum_sha256'],**scope}
    return releases,questions



def _load_json_field(row,name):
    try: return json.loads(row[name] or '{}') if name in row.keys() else {}
    except Exception: return {}

def pinned_question(session_row,qid,current_row):
    pins=_load_json_field(session_row,'ph_question_pins_json'); pin=pins.get(str(qid))
    if not pin: return current_row
    base=dict(current_row); base.update(pin.get('projection') or {})
    return base

def answer_pin(session_row,qid):
    return _load_json_field(session_row,'ph_question_pins_json').get(str(qid)) or {}

def overlay_attempt_question(row):
    d=dict(row)
    try: snap=json.loads(d.get('ph_question_snapshot_json') or '{}')
    except Exception: snap={}
    if snap: d.update(snap)
    return d


def _envelope(contract,destination,idempotency,business,payload,producer_version,data_classification='INTERNAL'):
    now=utcnow(); msg='msg::'+contract+'::'+hashlib.sha256((idempotency+'|'+payload_checksum(payload)).encode()).hexdigest()[:28]
    env={'message_id':msg,'contract_name':contract,'contract_version':'1','schema_version':SCHEMA_VERSION,'source_system':'SCOREMAX','destination_system':destination,
         'occurred_at':now,'sent_at':now,'correlation_id':'corr::'+hashlib.sha256(str(business).encode()).hexdigest()[:20],'idempotency_key':str(idempotency),
         'producer_version':str(producer_version or SCOREMAX_INTEGRATION_RELEASE),'retry_of_message_id':None,'payload_checksum_sha256':payload_checksum(payload),'data_classification':data_classification,'payload':payload}
    errors=_strict_envelope_errors(env,contract,'SCOREMAX',destination)
    if errors: raise ValueError('Outbound contract validation failed: '+canonical_json(errors))
    return env


def _queue(c,envelope,business_identity,source_record_type='',source_record_id=''):
    contract=str(envelope.get('contract_name') or ''); destination=str(envelope.get('destination_system') or '')
    errors=_strict_envelope_errors(envelope,contract,'SCOREMAX',destination)
    if errors: raise ValueError('Outbound message rejected before outbox persistence: '+canonical_json(errors))
    _begin_immediate(c)
    idem=envelope['idempotency_key']; chk=envelope['payload_checksum_sha256']
    existing=c.execute('SELECT * FROM integration_outbox WHERE contract_name=? AND idempotency_key=?',(contract,idem)).fetchone()
    if existing:
        if existing['payload_checksum_sha256']!=chk:
            c.execute('''INSERT INTO integration_quarantine(contract_name,identity_key,incoming_checksum,existing_checksum,reason_code,message_id,payload_json,status,created_at)
              VALUES(?,?,?,?,?,?,?,'OPEN',?)''',(contract,business_identity,chk,existing['payload_checksum_sha256'],'OUTBOX_IDEMPOTENCY_CHECKSUM_CONFLICT',envelope['message_id'],canonical_json(envelope),utcnow()))
        return existing['message_id']
    c.execute('''INSERT OR IGNORE INTO integration_outbox(message_id,contract_name,destination_system,idempotency_key,business_identity,payload_checksum_sha256,envelope_json,status,
      attempt_count,next_attempt_at,source_record_type,source_record_id,created_at) VALUES(?,?,?,?,?,?,?,'PENDING',0,?,?,?,?)''',
      (envelope['message_id'],contract,envelope['destination_system'],idem,business_identity,chk,canonical_json(envelope),utcnow(),source_record_type,str(source_record_id or ''),utcnow()))
    row=c.execute('SELECT * FROM integration_outbox WHERE contract_name=? AND idempotency_key=?',(contract,idem)).fetchone()
    if row and row['payload_checksum_sha256']!=chk:
        c.execute('''INSERT INTO integration_quarantine(contract_name,identity_key,incoming_checksum,existing_checksum,reason_code,message_id,payload_json,status,created_at)
          VALUES(?,?,?,?,?,?,?,'OPEN',?)''',(contract,business_identity,chk,row['payload_checksum_sha256'],'OUTBOX_IDEMPOTENCY_CHECKSUM_CONFLICT',envelope['message_id'],canonical_json(envelope),utcnow()))
    return row['message_id'] if row else envelope['message_id']



def _pseudo_user(c,user_id):
    if not user_id: return 'USR::PSEUDO::SYSTEM'
    r=c.execute('SELECT system_user_id FROM users WHERE id=?',(user_id,)).fetchone(); raw=(r['system_user_id'] if r and r['system_user_id'] else f'USER:{user_id}')
    return 'USR::PSEUDO::'+hashlib.sha256(str(raw).encode()).hexdigest()[:16]

def _teacher_external(c,user_id):
    if not user_id: return None
    r=c.execute('SELECT system_user_id FROM users WHERE id=?',(user_id,)).fetchone(); return str(r['system_user_id'] if r and r['system_user_id'] else f'TEACHER::{user_id}')


def queue_product_event(c,*,event_type,event_id,actor_type='SYSTEM',actor_id='SCOREMAX',context=None,event_data=None,occurred_at=None,producer_version=SCOREMAX_INTEGRATION_RELEASE):
    allowed={'LEARNER_REGISTERED','ATTRIBUTION_RECORDED','PROGRAMME_SELECTED','DIAGNOSTIC_STARTED','DIAGNOSTIC_COMPLETED','FIRST_MEANINGFUL_ACTIVITY','ASSESSMENT_STARTED','ASSESSMENT_COMPLETED','STUDY_PLAN_ACTIVITY','RETENTION_MILESTONE','ACCESS_TIER_CHANGED','PACKAGE_PURCHASED','PAYMENT_CLEARED','PAYMENT_FAILED','PAYMENT_REFUNDED','PAYMENT_REVERSED','SUBSCRIPTION_RENEWED','TEACHER_REGISTERED','TEACHER_REFERRAL_RECORDED','STUDENT_REFERRAL_RECORDED','REFERRAL_REWARD_ELIGIBILITY_CHANGED','INSTITUTION_ACTIVITY','CLASS_CREATED','LEARNER_INVITED','CONTENT_AVAILABILITY_CHANGED'}
    if event_type not in allowed: return ''
    p={'event_id':str(event_id),'event_type':event_type,'event_version':'1','occurred_at':normalize_rfc3339_utc(occurred_at or utcnow(),field='occurred_at'),
       'actor':{'actor_type':actor_type,'actor_id':str(actor_id)},'context':dict(context or {}),'event_data':dict(event_data or {})}
    env=_envelope('SM_GE_PRODUCT_EVENT_V1','GROWTH_ENGINE','product-event::'+str(event_id),str(event_id),p,producer_version,'PSEUDONYMOUS')
    return _queue(c,env,str(event_id),'PRODUCT_EVENT',str(event_id))



def _referral_attribution_for_user(c,user_id):
    if not user_id: return None
    return c.execute('SELECT * FROM referral_attributions WHERE user_id=?',(user_id,)).fetchone()


def _stable_referral_id(attr):
    return f"REF::ATTR::{attr['id']}" if attr else None


def _teacher_network_ids(c,attr):
    direct=None; upstream=None
    if attr and str(attr['referrer_type'] or '')=='user' and attr['referrer_id']:
        ru=c.execute('SELECT role FROM users WHERE id=?',(attr['referrer_id'],)).fetchone()
        if ru and ru['role']=='teacher':
            direct=_teacher_external(c,attr['referrer_id'])
            up=_referral_attribution_for_user(c,attr['referrer_id'])
            if up and str(up['referrer_type'] or '')=='user' and up['referrer_id']:
                uru=c.execute('SELECT role FROM users WHERE id=?',(up['referrer_id'],)).fetchone()
                if uru and uru['role']=='teacher': upstream=_teacher_external(c,up['referrer_id'])
    return direct,upstream

def sync_growth_outbox(c,producer_version=SCOREMAX_INTEGRATION_RELEASE,limit=200):
    """Project a bounded incremental change queue; never rescan full product histories on learner requests."""
    before=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
    changes=c.execute("SELECT * FROM integration_source_change_queue WHERE projected_at='' AND source_table IN ('universal_growth_event_outbox','referral_attributions','payment_transactions','referral_rewards') ORDER BY id LIMIT ?",(int(limit),)).fetchall()
    for ch in changes:
        table=str(ch['source_table']); pk=str(ch['source_pk']); handled=True
        if table=='universal_growth_event_outbox':
            r=c.execute('SELECT event_id,event_type,payload_json,user_key,occurred_at FROM universal_growth_event_outbox WHERE event_id=?',(pk,)).fetchone()
            if r:
                mapping={'PROGRAMME_SWITCHED':'PROGRAMME_SELECTED','ASSESSMENT_COMPLETED':'ASSESSMENT_COMPLETED','STUDY_PLAN_CREATED':'STUDY_PLAN_ACTIVITY'}
                old=str(r['event_type'] or '').upper(); data=json.loads(r['payload_json'] or '{}'); user_id=None
                if str(r['user_key'] or '').startswith('USER:'):
                    try:user_id=int(str(r['user_key']).split(':',1)[1])
                    except Exception:user_id=None
                u=c.execute('SELECT role,active_programme,academic_level FROM users WHERE id=?',(user_id,)).fetchone() if user_id else None
                if old=='REGISTERED': et='TEACHER_REGISTERED' if u and u['role']=='teacher' else 'LEARNER_REGISTERED'
                elif old in mapping: et=mapping[old]
                else: et=None
                if et:
                    actor_type='TEACHER' if u and u['role']=='teacher' else 'LEARNER'; context={'programme_id':(u['active_programme'] or u['academic_level']) if u else None}; ed={}
                    if et=='ASSESSMENT_COMPLETED': ed={'attempt_id':data.get('attempt_id'),'assessment_type':data.get('assessment_kind') or data.get('scope'),'completion_status':'COMPLETED'}
                    if et=='STUDY_PLAN_ACTIVITY': ed={'study_plan_action':'CREATED'}
                    queue_product_event(c,event_type=et,event_id='UE::'+r['event_id'],actor_type=actor_type,actor_id=_pseudo_user(c,user_id),context=context,event_data=ed,occurred_at=r['occurred_at'],producer_version=producer_version)
        elif table=='referral_attributions':
            a=c.execute('SELECT ra.*,u.role referred_role,ru.role referrer_role FROM referral_attributions ra LEFT JOIN users u ON u.id=ra.user_id LEFT JOIN users ru ON ru.id=ra.referrer_id WHERE ra.id=?',(pk,)).fetchone()
            if a and a['referrer_type']=='user' and a['referrer_id'] and a['referrer_role']=='teacher':
                et='TEACHER_REFERRAL_RECORDED' if a['referred_role']=='teacher' else 'STUDENT_REFERRAL_RECORDED'
                direct,upstream=_teacher_network_ids(c,a)
                queue_product_event(c,event_type=et,event_id=f"REF::{a['id']}::{et}",actor_type='TEACHER',actor_id=direct or _teacher_external(c,a['referrer_id']),
                  context={'referral_id':_stable_referral_id(a)},event_data={'direct_referrer_teacher_id':direct,'upstream_referrer_teacher_id':upstream},occurred_at=a['created_at'],producer_version=producer_version)
        elif table=='payment_transactions':
            tx=c.execute('SELECT id,user_id,plan_id,status,refund_amount_minor,refund_status,currency,gross_amount_minor,net_amount_minor,paid_at,created_at,provider FROM payment_transactions WHERE id=?',(pk,)).fetchone()
            if tx:
                plan=c.execute('SELECT code FROM plans WHERE id=?',(tx['plan_id'],)).fetchone() if tx['plan_id'] else None
                rr=c.execute('SELECT * FROM referral_rewards WHERE payment_transaction_id=?',(tx['id'],)).fetchone()
                attr=_referral_attribution_for_user(c,tx['user_id']); direct,upstream=_teacher_network_ids(c,attr)
                status=str(tx['status'] or '').strip().lower()
                refund_status=str(tx['refund_status'] or '').strip().lower()
                refund=int(tx['refund_amount_minor'] or 0)
                net=int(tx['net_amount_minor'] or 0)
                empty_refund_status=refund_status in {'','none','not_refunded'}
                coherent=True
                if status in {'successful','cleared','paid'} and refund==0 and empty_refund_status:
                    et='PAYMENT_CLEARED'; state='CLEARED'
                elif status in {'failed','declined'} and refund==0 and empty_refund_status:
                    et='PAYMENT_FAILED'; state='FAILED'
                elif status=='refunded' and net>0 and refund==net and refund_status=='refunded':
                    et='PAYMENT_REFUNDED'; state=f'REFUNDED::{refund}'
                elif status in {'reversed','voided'} and refund==0 and refund_status in {'reversed','voided'}:
                    et='PAYMENT_REVERSED'; state='REVERSED'
                elif status in {'pending','processing','authorised','authorized'} and refund==0 and empty_refund_status:
                    et=None
                else:
                    et=None; coherent=False
                if not coherent:
                    # Contradictory/unsupported lifecycle tuples are not projected and are not
                    # marked complete. They remain pending for governed remediation.
                    handled=False
                if et:
                    # The Growth contract deliberately applies a semantic metadata allowlist.
                    # `payment_provider` is the governed public key; provider refs/payment methods
                    # and all credentials stay in ScoreMax.
                    negative_reward_states={'reversed','ineligible','cancelled','voided'}
                    direct_positive=bool(rr and int(rr['reward_amount_minor'] or 0)>0)
                    upstream_positive=bool(rr and int(rr['override_reward_amount_minor'] or 0)>0)
                    direct_status=str(rr['status'] or '').lower() if rr else ''
                    upstream_status=str(rr['override_status'] or '').lower() if rr else ''
                    terminal_payment=et in {'PAYMENT_REFUNDED','PAYMENT_REVERSED'}
                    partial_refund=bool(et=='PAYMENT_REFUNDED' and 0<refund<net)
                    incoherent_reward=bool(terminal_payment and rr and (
                        (direct_positive and direct_status not in negative_reward_states) or
                        (upstream_positive and upstream_status not in negative_reward_states)
                    ))
                    failed_with_positive_reward=bool(et=='PAYMENT_FAILED' and rr and (
                        (direct_positive and direct_status not in negative_reward_states) or
                        (upstream_positive and upstream_status not in negative_reward_states)
                    ))
                    if partial_refund or incoherent_reward or failed_with_positive_reward:
                        # No governed partial-refund reward rule exists, and ScoreMax must never
                        # manufacture a negative reward merely to make the receiver accept it.
                        # Leave the source change pending until authoritative ScoreMax payment /
                        # reward logic has produced a coherent state.
                        handled=False
                    else:
                        ed={'payment_transaction_id':tx['id'],'payment_status':state.split('::')[0],'currency':str(tx['currency'] or 'PKR')[:3].upper(),'gross_amount_minor':int(tx['gross_amount_minor'] or 0),'eligible_amount_minor':int(tx['net_amount_minor'] or 0),'refund_amount_minor':refund,
                            'direct_referrer_teacher_id':direct,'upstream_referrer_teacher_id':upstream,'direct_reward_id':rr['id'] if rr else None,'upstream_reward_id':(f"UPSTREAM::{rr['id']}" if rr and rr['override_referrer_user_id'] else None),
                            'direct_reward_amount_minor':int(rr['reward_amount_minor'] or 0) if rr else None,'upstream_reward_amount_minor':int(rr['override_reward_amount_minor'] or 0) if rr else None,'reward_status':rr['status'] if rr else None,'metadata':{'payment_provider':tx['provider'] or 'manual'}}
                        queue_product_event(c,event_type=et,event_id=f"PAYMENT::{tx['id']}::{state}",actor_type='LEARNER',actor_id=_pseudo_user(c,tx['user_id']),context={'package_id':plan['code'] if plan else None,'referral_id':_stable_referral_id(attr)},event_data=ed,occurred_at=tx['paid_at'] or tx['created_at'],producer_version=producer_version)
        elif table=='referral_rewards':
            rr=c.execute('SELECT * FROM referral_rewards WHERE id=?',(pk,)).fetchone()
            if rr:
                tx=c.execute('SELECT id,user_id,plan_id,status,refund_amount_minor,currency,gross_amount_minor,net_amount_minor,paid_at,created_at,provider FROM payment_transactions WHERE id=?',(rr['payment_transaction_id'],)).fetchone(); attr=_referral_attribution_for_user(c,rr['referred_user_id'])
                queue_product_event(c,event_type='REFERRAL_REWARD_ELIGIBILITY_CHANGED',event_id=f"REWARD::{rr['id']}::{rr['status']}::{rr['override_status']}",actor_type='SYSTEM',actor_id='SCOREMAX',context={'referral_id':_stable_referral_id(attr)},
                  event_data={'payment_transaction_id':rr['payment_transaction_id'],'direct_referrer_teacher_id':_teacher_external(c,rr['referrer_user_id']),'upstream_referrer_teacher_id':_teacher_external(c,rr['override_referrer_user_id']) if rr['override_referrer_user_id'] else None,'direct_reward_id':rr['id'],'upstream_reward_id':f"UPSTREAM::{rr['id']}" if rr['override_referrer_user_id'] else None,'direct_reward_amount_minor':int(rr['reward_amount_minor'] or 0),'upstream_reward_amount_minor':int(rr['override_reward_amount_minor'] or 0),'reward_status':rr['status']},occurred_at=(tx['paid_at'] if tx else None) or rr['created_at'],producer_version=producer_version)
        elif table=='content_requirement_requests':
            # handled by bounded sync_content_requirements so a single change can feed PH without full-table scans
            handled=False
        else:
            handled=True
        if handled:
            c.execute('UPDATE integration_source_change_queue SET projected_at=? WHERE id=?',(utcnow(),ch['id']))
    after=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_GE_PRODUCT_EVENT_V1'").fetchone()['n']
    return int(after-before)



def queue_content_requirement(c,payload,producer_version=SCOREMAX_INTEGRATION_RELEASE):
    payload=copy.deepcopy(payload)
    batch=str(payload.get('request_batch_id') or '')
    if not batch: raise ValueError('request_batch_id required')
    for item in payload.get('requirements') or []:
        if item.get('created_at') is not None:
            item['created_at']=normalize_rfc3339_utc(item['created_at'],field='requirements.created_at')
    env=_envelope('SM_PH_CONTENT_REQUIREMENT_V1','POWER_HOUSE','requirements::'+batch,batch,payload,producer_version,'INTERNAL')
    return _queue(c,env,batch,'CONTENT_REQUIREMENT',batch)



def queue_delivery_evidence(c,*,market_id,programme_id,subject_id,chapter_id,period_start,period_end,minimum_n=None,blueprint_id=None,blueprint_version=None,producer_version=SCOREMAX_INTEGRATION_RELEASE):
    """Aggregate only immutable attempt pins; mutable current question rows never rescope historical evidence."""
    minimum_n=int(minimum_n or MIN_EVIDENCE_N)
    out_start=normalize_rfc3339_utc(period_start,field='period_start'); out_end=normalize_rfc3339_utc(period_end,field='period_end')
    qstart=out_start.replace('T',' ').replace('Z',''); qend=out_end.replace('T',' ').replace('Z','')
    rows=c.execute('''SELECT aa.ph_question_id question_id,aa.ph_question_version_id question_version_id,aa.ph_question_checksum_sha256 question_checksum,
      aa.ph_release_id release_id,aa.ph_release_version release_version,aa.ph_release_checksum_sha256 release_checksum,
      aa.ph_question_snapshot_json,aa.selected_answer,aa.is_correct,aa.response_time_seconds,a.created_at,a.assessment_kind,
      a.blueprint_source_id,a.blueprint_version,a.blueprint_snapshot_json
      FROM attempt_answers aa JOIN attempts a ON a.id=aa.attempt_id
      WHERE COALESCE(aa.ph_question_version_id,'')<>'' AND a.created_at>=? AND a.created_at<=?
      ORDER BY aa.ph_question_version_id,aa.id''',(qstart,qend)).fetchall()
    scoped=[]
    for r in rows:
        try: snap=json.loads(r['ph_question_snapshot_json'] or '{}')
        except Exception: snap={}
        scope=(str(snap.get('ph_market_id') or ''),str(snap.get('ph_programme_id') or ''),str(snap.get('ph_subject_id') or ''),str(snap.get('ph_chapter_id') or ''))
        wanted=(str(market_id),str(programme_id),str(subject_id),str(chapter_id))
        if scope!=wanted: continue
        if blueprint_id and str(r['blueprint_source_id'] or '')!=str(blueprint_id): continue
        if blueprint_version and str(r['blueprint_version'] or '')!=str(blueprint_version): continue
        scoped.append(r)
    groups={}
    for r in scoped: groups.setdefault((r['question_id'],r['question_version_id'],r['question_checksum']),[]).append(r)
    items=[]
    for (qid,qvid,qchk),rs in groups.items():
        delivered=len(rs); suppressed=delivered<minimum_n
        answered=[x for x in rs if str(x['selected_answer'] or '').strip()!='']; skipped=delivered-len(answered)
        correct=sum(1 for x in answered if int(x['is_correct'] or 0)); incorrect=sum(1 for x in answered if not int(x['is_correct'] or 0))
        times=sorted([int(x['response_time_seconds'] or 0) for x in answered if int(x['response_time_seconds'] or 0)>0])
        def pct(p):
            if not times:return None
            idx=min(len(times)-1,max(0,int(round((len(times)-1)*p)))); return float(times[idx])
        dcounts={}
        for x in answered:
            if not int(x['is_correct'] or 0): dcounts[str(x['selected_answer'])]=dcounts.get(str(x['selected_answer']),0)+1
        # Recovery/reconfirmation telemetry must be derived from immutable attempt pins + owning attempt kind.
        # Suppressed item aggregates retain the contract-safe zero representation so sub-threshold cohorts do not leak.
        recovery=[x for x in answered if str(x['assessment_kind'] or '').strip().lower()=='recovery']
        reconfirm=[x for x in answered if str(x['assessment_kind'] or '').strip().lower() in ('recall','reconfirmation')]
        recovery_attempts=len(recovery); recovery_successes=sum(1 for x in recovery if int(x['is_correct'] or 0))
        reconfirmation_attempts=len(reconfirm); reconfirmation_successes=sum(1 for x in reconfirm if int(x['is_correct'] or 0))
        items.append({'question_id':qid,'question_version_id':qvid,'question_checksum_sha256':qchk,'delivered_count':delivered,'submitted_count':len(answered),
          'correct_count':0 if suppressed else correct,'incorrect_count':0 if suppressed else incorrect,'skipped_count':0 if suppressed else skipped,
          'timing_seconds':{'median':None if suppressed else pct(.5),'p90':None if suppressed else pct(.9)},'assistance_counts':{},'distractor_counts':{} if suppressed else dcounts,'confidence_counts':{},'flag_counts':{},
          'recovery_attempts':0 if suppressed else recovery_attempts,'recovery_successes':0 if suppressed else recovery_successes,
          'reconfirmation_attempts':0 if suppressed else reconfirmation_attempts,'reconfirmation_successes':0 if suppressed else reconfirmation_successes,
          'item_difficulty':None if suppressed or not answered else round(correct/len(answered),4),'discrimination':None,'sample_suppressed':suppressed,'ambiguity_signal_count':0})
    if not items: return ''
    batch='EVB::'+hashlib.sha256(f'{market_id}|{programme_id}|{subject_id}|{chapter_id}|{out_start}|{out_end}|{blueprint_id or ""}|{blueprint_version or ""}'.encode()).hexdigest()[:20]
    payload={'evidence_batch_id':batch,'environment':'LIVE','aggregation_level':'QUESTION_VERSION','period_start':out_start,'period_end':out_end,'minimum_sample_policy':{'minimum_n':minimum_n,'suppression_applied':any(x['sample_suppressed'] for x in items)},'market_id':market_id,'programme_id':programme_id,'subject_id':subject_id,'chapter_id':chapter_id,'blueprint_id':blueprint_id,'blueprint_version':blueprint_version,'items':items}
    env=_envelope('SM_PH_DELIVERY_EVIDENCE_V1','POWER_HOUSE','evidence::'+batch,batch,payload,producer_version,'PSEUDONYMOUS')
    return _queue(c,env,batch,'DELIVERY_EVIDENCE',batch)


def _credentials(direction):
    if direction=='POWER_HOUSE_TO_SCOREMAX':
        return [(os.environ.get('POWER_HOUSE_TO_SCOREMAX_TOKEN',''),os.environ.get('POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET','')),(os.environ.get('POWER_HOUSE_TO_SCOREMAX_PREVIOUS_TOKEN',''),os.environ.get('POWER_HOUSE_TO_SCOREMAX_PREVIOUS_HMAC_SECRET',''))]
    if direction=='GROWTH_ENGINE_TO_SCOREMAX':
        return [(os.environ.get('GROWTH_ENGINE_TO_SCOREMAX_TOKEN',''),os.environ.get('GROWTH_ENGINE_TO_SCOREMAX_HMAC_SECRET','')),(os.environ.get('GROWTH_ENGINE_TO_SCOREMAX_PREVIOUS_TOKEN',''),os.environ.get('GROWTH_ENGINE_TO_SCOREMAX_PREVIOUS_HMAC_SECRET',''))]
    if direction=='SCOREMAX_TO_POWER_HOUSE': return [(os.environ.get('SCOREMAX_TO_POWER_HOUSE_TOKEN',''),os.environ.get('SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET',''))]
    if direction=='SCOREMAX_TO_GROWTH_ENGINE': return [(os.environ.get('SCOREMAX_TO_GROWTH_ENGINE_TOKEN',''),os.environ.get('SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET',''))]
    return []

def signature(method,path,message_id,sent_at,content_sha,secret):
    raw='\n'.join([method.upper(),path,message_id,sent_at,content_sha])
    return hmac.new(secret.encode(),raw.encode(),hashlib.sha256).hexdigest()

def verify_inbound_http(req,expected_source='POWER_HOUSE'):
    direction='POWER_HOUSE_TO_SCOREMAX' if expected_source=='POWER_HOUSE' else 'GROWTH_ENGINE_TO_SCOREMAX'
    auth=str(req.headers.get('Authorization') or ''); token=auth[7:] if auth.startswith('Bearer ') else ''
    mid=str(req.headers.get('X-Message-Id') or ''); sent=str(req.headers.get('X-Sent-At') or ''); chk=str(req.headers.get('X-Content-SHA256') or ''); sig=str(req.headers.get('X-Signature') or '')
    if sig.startswith('hmac-sha256='): sig=sig.split('=',1)[1]
    dt=parse_dt(sent); max_skew=int(os.environ.get('SCOREMAX_INTEGRATION_MAX_CLOCK_SKEW_SECONDS','300') or 300)
    if not dt or abs((datetime.now(timezone.utc)-dt).total_seconds())>max_skew: return False,401,'STALE_OR_INVALID_SENT_AT'
    for t,s in _credentials(direction):
        if t and s and secrets_compare(token,t) and secrets_compare(sig,signature(req.method,req.path,mid,sent,chk,s)):
            return True,200,'OK'
    return False,401,'AUTH_OR_SIGNATURE_FAILED'

def secrets_compare(a,b):
    try:return hmac.compare_digest(str(a),str(b))
    except:return False


def _dispatch_target(contract):
    if contract in {'SM_PH_DELIVERY_EVIDENCE_V1','SM_PH_CONTENT_REQUIREMENT_V1'}:
        base=os.environ.get('SCOREMAX_POWER_HOUSE_BASE_URL','').rstrip('/'); path='/api/integration/v1/scoremax/delivery-evidence' if contract=='SM_PH_DELIVERY_EVIDENCE_V1' else '/api/integration/v1/scoremax/content-requirements'; direction='SCOREMAX_TO_POWER_HOUSE'
    elif contract=='SM_GE_PRODUCT_EVENT_V1':
        base=os.environ.get('SCOREMAX_GROWTH_ENGINE_BASE_URL','').rstrip('/'); path='/api/integration/v1/scoremax/product-events'; direction='SCOREMAX_TO_GROWTH_ENGINE'
    else: return '', '', ''
    return (base+path if base else ''),path,direction

def _dispatch_receipt_errors(receipt,envelope):
    errors=_schema_errors(receipt,'INTEGRATION_RECEIPT_V1','1.0.0')
    if not errors:
        if receipt.get('message_id')!=envelope.get('message_id'):
            errors.append({'code':'RECEIPT_MESSAGE_MISMATCH','path':'message_id','message':'Receipt message_id does not match dispatched message','retryable':True})
        if receipt.get('contract_name')!=envelope.get('contract_name'):
            errors.append({'code':'RECEIPT_CONTRACT_MISMATCH','path':'contract_name','message':'Receipt contract does not match dispatched contract','retryable':True})
        if receipt.get('receiver_system')!=envelope.get('destination_system'):
            errors.append({'code':'RECEIPT_RECEIVER_MISMATCH','path':'receiver_system','message':'Receipt receiver_system does not match the destination that processed the message','retryable':True})
        if receipt.get('payload_checksum_sha256')!=envelope.get('payload_checksum_sha256'):
            errors.append({'code':'RECEIPT_CHECKSUM_MISMATCH','path':'payload_checksum_sha256','message':'Receipt checksum does not match dispatched payload','retryable':True})
    return errors

def record_transport_diagnostic(c,contract_name,direction,event_code,details=None):
    """Persist only redacted transport/auth evidence for the existing health surface."""
    contract=str(contract_name or '').strip()
    if not contract:
        return
    code=str(event_code or 'INTEGRATION_TRANSPORT_ERROR').strip()[:120]
    safe={}
    if isinstance(details,dict):
        for key in ('http_status','peer','note'):
            if key in details and details[key] not in (None,''):
                safe[key]=str(details[key])[:160]
    c.execute('INSERT INTO integration_transport_diagnostics(contract_name,direction,event_code,occurred_at,details_json) VALUES(?,?,?,?,?)',
      (contract,str(direction or ''),code,utcnow(),canonical_json(safe)))


def _credential_expiry_warning(contract):
    env_by_contract={
      'PH_SM_APPROVED_CONTENT_V1':'POWER_HOUSE_TO_SCOREMAX_CREDENTIAL_EXPIRES_AT',
      'PH_SM_ASSESSMENT_BLUEPRINT_V1':'POWER_HOUSE_TO_SCOREMAX_CREDENTIAL_EXPIRES_AT',
      'SM_PH_DELIVERY_EVIDENCE_V1':'SCOREMAX_TO_POWER_HOUSE_CREDENTIAL_EXPIRES_AT',
      'SM_PH_CONTENT_REQUIREMENT_V1':'SCOREMAX_TO_POWER_HOUSE_CREDENTIAL_EXPIRES_AT',
      'SM_GE_PRODUCT_EVENT_V1':'SCOREMAX_TO_GROWTH_ENGINE_CREDENTIAL_EXPIRES_AT',
    }
    env_name=env_by_contract.get(contract)
    raw=os.environ.get(env_name,'').strip() if env_name else ''
    if not raw:
        return None
    dt=parse_dt(raw)
    if not dt:
        return 'CREDENTIAL_EXPIRY_CONFIGURATION_INVALID'
    seconds=(dt-datetime.now(timezone.utc)).total_seconds()
    if seconds<=0:
        return 'CREDENTIAL_EXPIRED'
    warn_seconds=int(os.environ.get('SCOREMAX_INTEGRATION_CREDENTIAL_EXPIRY_WARNING_SECONDS','604800') or 604800)
    return 'CREDENTIAL_EXPIRES_SOON' if seconds<=warn_seconds else None


def _latest_error_candidate(c,contract):
    candidates=[]
    row=c.execute("SELECT a.error_code code,a.attempted_at at FROM integration_dispatch_attempts a JOIN integration_outbox o ON o.id=a.outbox_id WHERE o.contract_name=? AND COALESCE(a.error_code,'')<>'' ORDER BY a.id DESC LIMIT 1",(contract,)).fetchone()
    if row: candidates.append((str(row['at'] or ''),str(row['code'] or '')))
    row=c.execute("SELECT reason_code code,created_at at FROM integration_quarantine WHERE contract_name=? ORDER BY id DESC LIMIT 1",(contract,)).fetchone()
    if row: candidates.append((str(row['at'] or ''),str(row['code'] or '')))
    row=c.execute("SELECT errors_json,received_at at FROM integration_receipts WHERE contract_name=? AND status IN ('REJECTED','QUARANTINED') ORDER BY received_at DESC LIMIT 1",(contract,)).fetchone()
    if row:
        code='INBOUND_REJECTED'
        try:
            errs=strict_json_loads(row['errors_json'] or '[]')
            if errs and isinstance(errs[0],dict) and errs[0].get('code'):
                code=str(errs[0]['code'])
        except Exception:
            code='INVALID_STORED_RECEIPT_ERROR_JSON'
        candidates.append((str(row['at'] or ''),code))
    row=c.execute("SELECT event_code code,occurred_at at FROM integration_transport_diagnostics WHERE contract_name=? ORDER BY id DESC LIMIT 1",(contract,)).fetchone()
    if row: candidates.append((str(row['at'] or ''),str(row['code'] or '')))
    if not candidates:
        return None,None
    at,code=max(candidates,key=lambda x:x[0])
    return code or None,at or None


def _clock_skew_warning(c,contract,last_error_code=None):
    code=str(last_error_code or '')
    if code in {'STALE_OR_INVALID_SENT_AT','CLOCK_SKEW','PEER_CLOCK_SKEW'}:
        return code
    row=c.execute("SELECT event_code FROM integration_transport_diagnostics WHERE contract_name=? AND event_code IN ('STALE_OR_INVALID_SENT_AT','CLOCK_SKEW','PEER_CLOCK_SKEW') ORDER BY id DESC LIMIT 1",(contract,)).fetchone()
    return str(row['event_code']) if row else None


def worker_heartbeat(c,worker_name='integration-dispatch',result=None,process_id=''):
    now=utcnow()
    c.execute('''INSERT INTO integration_worker_state(worker_name,heartbeat_at,last_cycle_at,last_result_json,process_id)
      VALUES(?,?,?,?,?) ON CONFLICT(worker_name) DO UPDATE SET heartbeat_at=excluded.heartbeat_at,last_cycle_at=excluded.last_cycle_at,last_result_json=excluded.last_result_json,process_id=excluded.process_id''',
      (worker_name,now,now,canonical_json(result or {}),str(process_id or '')))


def _claim_due(c,limit=100,lease_seconds=60):
    """Atomically claim a fair bounded batch across outbound contract queues."""
    now=utcnow(); _begin_immediate(c)
    # Crash recovery: an expired lease may be reclaimed, but terminal rows are monotonic.
    c.execute("UPDATE integration_outbox SET status='RETRY',claim_token='',claim_expires_at='',next_attempt_at=COALESCE(next_attempt_at,?) WHERE status='IN_FLIGHT' AND claim_expires_at<>'' AND claim_expires_at<=?",(now,now))
    contracts=[r['contract_name'] for r in c.execute("SELECT DISTINCT contract_name FROM integration_outbox WHERE status IN ('PENDING','RETRY') AND (next_attempt_at IS NULL OR next_attempt_at='' OR next_attempt_at<=?) ORDER BY contract_name",(now,)).fetchall()]
    buckets={}
    for contract in contracts:
        buckets[contract]=list(c.execute("SELECT id FROM integration_outbox WHERE contract_name=? AND status IN ('PENDING','RETRY') AND (next_attempt_at IS NULL OR next_attempt_at='' OR next_attempt_at<=?) ORDER BY created_at,id LIMIT ?",(contract,now,int(limit))).fetchall())
    selected=[]
    while len(selected)<int(limit) and any(buckets.values()):
        for contract in contracts:
            if buckets.get(contract) and len(selected)<int(limit): selected.append(buckets[contract].pop(0)['id'])
    if not selected:
        c.commit(); return []
    token='CLAIM::'+uuid.uuid4().hex
    expires=(datetime.now(timezone.utc)+timedelta(seconds=max(10,int(lease_seconds)))).replace(microsecond=0).isoformat().replace('+00:00','Z')
    for row_id in selected:
        c.execute("UPDATE integration_outbox SET status='IN_FLIGHT',claim_token=?,claim_expires_at=? WHERE id=? AND status IN ('PENDING','RETRY')",(token,expires,row_id))
    c.commit()
    marks=','.join('?' for _ in selected)
    return c.execute(f"SELECT * FROM integration_outbox WHERE id IN ({marks}) AND status='IN_FLIGHT' AND claim_token=? ORDER BY id",(*selected,token)).fetchall()


def _schedule_retry(c,row_id,attempts,code,text,claim_token=''):
    where="id=? AND status='IN_FLIGHT'"; args=[]
    if claim_token:
        where += ' AND claim_token=?'
    if attempts>=len(RETRY_DELAYS):
        vals=[attempts,utcnow(),code,text,row_id]
        if claim_token: vals.append(claim_token)
        c.execute(f"UPDATE integration_outbox SET status='DEAD_LETTER',attempt_count=?,last_attempt_at=?,last_error_code=?,last_error=?,claim_token='',claim_expires_at='' WHERE {where}",vals); return 'DEAD_LETTER'
    delay=RETRY_DELAYS[min(attempts,len(RETRY_DELAYS)-1)]
    nextdt=(datetime.now(timezone.utc)+timedelta(seconds=delay)).replace(microsecond=0).isoformat().replace('+00:00','Z')
    vals=[attempts,utcnow(),nextdt,code,text,row_id]
    if claim_token: vals.append(claim_token)
    c.execute(f"UPDATE integration_outbox SET status='RETRY',attempt_count=?,last_attempt_at=?,next_attempt_at=?,last_error_code=?,last_error=?,claim_token='',claim_expires_at='' WHERE {where}",vals); return 'RETRY'


def requeue_outbox(c,outbox_id,actor='OPERATOR',reason=''):
    """Start a fresh bounded retry cycle without changing message identity or history.

    Prior dispatch-attempt rows are immutable evidence. attempt_count is the active-cycle
    counter, so an exhausted prior cycle cannot poison the first retry after governance.
    """
    _begin_immediate(c)
    row=c.execute('SELECT * FROM integration_outbox WHERE id=?',(int(outbox_id),)).fetchone()
    if not row or row['status'] not in {'DEAD_LETTER','QUARANTINED'}:
        c.rollback(); return False
    old=row['status']; now=utcnow(); prior_attempts=int(row['attempt_count'] or 0)
    prior_cycle=int(row['retry_cycle'] or 0) if 'retry_cycle' in row.keys() else 0
    new_cycle=prior_cycle+1
    c.execute("UPDATE integration_outbox SET status='PENDING',attempt_count=0,retry_cycle=?,next_attempt_at=?,last_error_code='',last_error='',claim_token='',claim_expires_at='' WHERE id=? AND status=?",(new_cycle,now,int(outbox_id),old))
    c.execute("INSERT INTO integration_requeue_audit(outbox_id,from_status,to_status,actor,reason,created_at,prior_attempt_count,new_retry_cycle) VALUES(?,?,?,?,?,?,?,?)",
      (int(outbox_id),old,'PENDING',str(actor or 'OPERATOR'),str(reason or ''),now,prior_attempts,new_cycle))
    c.commit(); return True

def dispatch_due(c,limit=100,timeout=8):
    rows=_claim_due(c,limit=int(limit),lease_seconds=max(30,int(timeout)*4))
    result={'attempted':0,'delivered':0,'retrying':0,'dead_letter':0,'quarantined':0,'not_configured':0}
    for r in rows:
        claim=str(r['claim_token'] or ''); url,path,direction=_dispatch_target(r['contract_name'])
        parsed=urlparse(str(url or ''))
        # Missing endpoint is an operational NOT_CONFIGURED state.  It must preserve the
        # committed row without reading credentials or making a network call.
        if not url:
            c.execute("UPDATE integration_outbox SET status='PENDING',last_error_code='NOT_CONFIGURED',last_error='Outbound integration endpoint is not configured',claim_token='',claim_expires_at='' WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(r['id'],claim)); result['not_configured']+=1; continue
        # A configured but insecure endpoint is a security boundary violation.  Enforce
        # HTTPS before credentials are read or request headers/body are constructed.
        if parsed.scheme.lower()!='https' or not parsed.netloc:
            c.execute("UPDATE integration_outbox SET status='QUARANTINED',last_attempt_at=?,last_error_code='INSECURE_PEER_URL',last_error=?,claim_token='',claim_expires_at='' WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(utcnow(),str(url)[:1000],r['id'],claim)); result['quarantined']+=1; continue
        creds=_credentials(direction); token,secret=creds[0] if creds else ('','')
        if not token or not secret:
            c.execute("UPDATE integration_outbox SET status='PENDING',last_error_code='NOT_CONFIGURED',last_error='Outbound integration credentials are not configured',claim_token='',claim_expires_at='' WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(r['id'],claim)); result['not_configured']+=1; continue
        try:
            env=strict_json_loads(r['envelope_json'])
            # Re-canonicalise before any send. This also catches legacy bytes that a permissive parser accepted.
            canonical_json(env)
        except Exception:
            c.execute("UPDATE integration_outbox SET status='QUARANTINED',last_attempt_at=?,last_error_code='NON_STANDARD_OUTBOX_ENVELOPE',last_error='Stored envelope is not standards-compliant canonical JSON',claim_token='',claim_expires_at='' WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(utcnow(),r['id'],claim))
            result['quarantined']+=1
            continue
        env['sent_at']=utcnow(); body=canonical_json(env).encode(); chk=env['payload_checksum_sha256']; sent=env['sent_at']; sig=signature('POST',path,env['message_id'],sent,chk,secret)
        headers={'Content-Type':'application/json','Authorization':'Bearer '+token,'X-Message-Id':env['message_id'],'X-Sent-At':sent,'X-Content-SHA256':chk,'X-Signature':'hmac-sha256='+sig}
        result['attempted']+=1; http=0; resp=''; errcode=''; errtext=''; receipt=None; receipt_parse_error=''; response_evidence=''
        try:
            rq=urlrequest.Request(url,data=body,headers=headers,method='POST'); rr=urlrequest.urlopen(rq,timeout=timeout); http=int(rr.status); resp=rr.read().decode('utf-8','replace')
        except urlerror.HTTPError as e:
            http=int(e.code); resp=e.read().decode('utf-8','replace'); errcode='HTTP_'+str(http); errtext=resp[:1000]
        except Exception as e:
            errcode='TRANSPORT_ERROR'; errtext=str(e)[:1000]
        attempts=int(r['attempt_count'] or 0)+1; st=''
        if http in {200,202,409,422,429,503} and resp:
            try:
                receipt=strict_json_loads(resp)
                response_evidence=canonical_json(receipt)
            except Exception:
                receipt=None
                receipt_parse_error='INVALID_PEER_JSON'
                response_evidence=canonical_json({'http_status':http or None,'body_sha256':sha256_text(resp),'body_length':len(resp),'parse_status':'INVALID_OR_NON_STANDARD_JSON'})
        elif resp:
            response_evidence=canonical_json({'http_status':http or None,'body_sha256':sha256_text(resp),'body_length':len(resp),'parse_status':'UNPARSED_RESPONSE'})
        receipt_errors=_dispatch_receipt_errors(receipt if isinstance(receipt,dict) else {},env) if receipt is not None else []
        if receipt is not None and not receipt_errors:
            rs=str(receipt.get('status') or '')
            saved=canonical_json(receipt)
            if rs in {'ACCEPTED','DUPLICATE'}:
                c.execute("UPDATE integration_outbox SET status='DELIVERED',attempt_count=?,last_attempt_at=?,dispatched_at=?,receipt_json=?,last_error_code='',last_error='',claim_token='',claim_expires_at='' WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(attempts,utcnow(),utcnow(),saved,r['id'],claim)); st='DELIVERED'
            elif rs=='QUARANTINED':
                c.execute("UPDATE integration_outbox SET status='QUARANTINED',attempt_count=?,last_attempt_at=?,receipt_json=?,last_error_code='PEER_QUARANTINED',last_error=?,claim_token='',claim_expires_at='' WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(attempts,utcnow(),saved,canonical_json(receipt.get('errors') or [])[:1000],r['id'],claim)); st='QUARANTINED'
            elif rs=='REJECTED':
                retryable=any(bool(e.get('retryable')) for e in receipt.get('errors') or [])
                if retryable:
                    # Preserve the peer receipt while scheduling retry.
                    c.execute("UPDATE integration_outbox SET receipt_json=? WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(saved,r['id'],claim))
                    st=_schedule_retry(c,r['id'],attempts,'PEER_REJECTED_RETRYABLE',canonical_json(receipt.get('errors') or [])[:1000],claim)
                else:
                    c.execute("UPDATE integration_outbox SET status='DEAD_LETTER',attempt_count=?,last_attempt_at=?,receipt_json=?,last_error_code='PEER_REJECTED',last_error=?,claim_token='',claim_expires_at='' WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(attempts,utcnow(),saved,canonical_json(receipt.get('errors') or [])[:1000],r['id'],claim)); st='DEAD_LETTER'
            else:
                st=_schedule_retry(c,r['id'],attempts,'UNKNOWN_RECEIPT_STATUS',rs,claim)
        elif receipt is not None and receipt_errors:
            errcode='INVALID_OR_MISMATCHED_INTEGRATION_RECEIPT_V1'; errtext=canonical_json(receipt_errors)[:1000]
            st=_schedule_retry(c,r['id'],attempts,errcode,errtext,claim)
        elif receipt_parse_error:
            errcode=receipt_parse_error; errtext='Peer response was not standards-compliant JSON'
            st=_schedule_retry(c,r['id'],attempts,errcode,errtext,claim)
        elif http in {400,401,403,409,422}:
            c.execute("UPDATE integration_outbox SET status='DEAD_LETTER',attempt_count=?,last_attempt_at=?,last_error_code=?,last_error=?,claim_token='',claim_expires_at='' WHERE id=? AND status='IN_FLIGHT' AND claim_token=?",(attempts,utcnow(),errcode or 'NON_RETRYABLE',errtext,r['id'],claim)); st='DEAD_LETTER'
        else:
            st=_schedule_retry(c,r['id'],attempts,errcode or ('HTTP_'+str(http) if http else 'TRANSPORT_ERROR'),errtext,claim)
        c.execute('''INSERT INTO integration_dispatch_attempts(outbox_id,attempted_at,retry_cycle,http_status,result_status,error_code,error_text,response_json) VALUES(?,?,?,?,?,?,?,?)''',(r['id'],utcnow(),int(r['retry_cycle'] or 0) if 'retry_cycle' in r.keys() else 0,http or None,st,errcode,errtext,response_evidence[:4000]))
        if st=='DELIVERED': result['delivered']+=1
        elif st=='RETRY': result['retrying']+=1
        elif st=='DEAD_LETTER': result['dead_letter']+=1
        elif st=='QUARANTINED': result['quarantined']+=1
    worker_heartbeat(c,result=result,process_id=str(os.getpid()))
    c.commit()
    return result


def integration_health(c):
    """Frozen per-direction health projected from durable integration evidence."""
    directions=[]
    specs=[
        ('POWER_HOUSE -> SCOREMAX','PH_SM_APPROVED_CONTENT_V1','INBOUND'),
        ('POWER_HOUSE -> SCOREMAX','PH_SM_ASSESSMENT_BLUEPRINT_V1','INBOUND'),
        ('SCOREMAX -> POWER_HOUSE','SM_PH_DELIVERY_EVIDENCE_V1','OUTBOUND'),
        ('SCOREMAX -> POWER_HOUSE','SM_PH_CONTENT_REQUIREMENT_V1','OUTBOUND'),
        ('SCOREMAX -> GROWTH_ENGINE','SM_GE_PRODUCT_EVENT_V1','OUTBOUND'),
    ]
    for direction,contract,flow in specs:
        counts={r['status']:int(r['n']) for r in c.execute('SELECT status,COUNT(*) n FROM integration_outbox WHERE contract_name=? GROUP BY status',(contract,)).fetchall()}
        queued=counts.get('PENDING',0); retry=counts.get('RETRY',0); inflight=counts.get('IN_FLIGHT',0); dead=counts.get('DEAD_LETTER',0); quarantined_out=counts.get('QUARANTINED',0)
        q=int(c.execute("SELECT COUNT(*) n FROM integration_quarantine WHERE contract_name=? AND status='OPEN'",(contract,)).fetchone()['n'])
        source_counts={}
        for r in c.execute('SELECT source_record_type,status,COUNT(*) n FROM integration_outbox WHERE contract_name=? GROUP BY source_record_type,status',(contract,)).fetchall():
            source=str(r['source_record_type'] or 'UNSPECIFIED')
            bucket=source_counts.setdefault(source,{'total':0,'statuses':{}})
            n=int(r['n']); bucket['total']+=n; bucket['statuses'][str(r['status'])]=n

        if flow=='INBOUND':
            last_received=c.execute('SELECT MAX(last_received_at) t FROM integration_inbound_messages WHERE contract_name=?',(contract,)).fetchone()['t']
            last_success=c.execute("SELECT MAX(received_at) t FROM integration_receipts WHERE contract_name=? AND status IN ('ACCEPTED','DUPLICATE')",(contract,)).fetchone()['t']
            last_dispatched=None; oldest=None
            ps=c.execute("SELECT accepted_schema_version v FROM integration_receipts WHERE contract_name=? AND accepted_schema_version IS NOT NULL ORDER BY received_at DESC LIMIT 1",(contract,)).fetchone()
            peer_schema=ps['v'] if ps else None
        else:
            last_success=c.execute("SELECT MAX(dispatched_at) t FROM integration_outbox WHERE contract_name=? AND status='DELIVERED' AND COALESCE(dispatched_at,'')<>''",(contract,)).fetchone()['t']
            last_dispatched=c.execute('SELECT MAX(a.attempted_at) t FROM integration_dispatch_attempts a JOIN integration_outbox o ON o.id=a.outbox_id WHERE o.contract_name=?',(contract,)).fetchone()['t']
            last_received=c.execute("SELECT MAX(a.attempted_at) t FROM integration_dispatch_attempts a JOIN integration_outbox o ON o.id=a.outbox_id WHERE o.contract_name=? AND COALESCE(a.response_json,'')<>''",(contract,)).fetchone()['t']
            oldest=c.execute("SELECT MIN(created_at) t FROM integration_outbox WHERE contract_name=? AND status IN ('PENDING','RETRY','IN_FLIGHT')",(contract,)).fetchone()['t']
            rr=c.execute("SELECT receipt_json FROM integration_outbox WHERE contract_name=? AND COALESCE(receipt_json,'')<>'' ORDER BY id DESC LIMIT 1",(contract,)).fetchone()
            peer_schema=None
            if rr:
                try: peer_schema=(strict_json_loads(rr['receipt_json']) or {}).get('accepted_schema_version')
                except Exception: peer_schema=None

        configured=True
        if direction.startswith('SCOREMAX -> POWER_HOUSE'):
            configured=bool(os.environ.get('SCOREMAX_POWER_HOUSE_BASE_URL') and os.environ.get('SCOREMAX_TO_POWER_HOUSE_TOKEN') and os.environ.get('SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET'))
        elif direction.startswith('SCOREMAX -> GROWTH_ENGINE'):
            configured=bool(os.environ.get('SCOREMAX_GROWTH_ENGINE_BASE_URL') and os.environ.get('SCOREMAX_TO_GROWTH_ENGINE_TOKEN') and os.environ.get('SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET'))
        elif direction.startswith('POWER_HOUSE -> SCOREMAX'):
            configured=bool(os.environ.get('POWER_HOUSE_TO_SCOREMAX_TOKEN') and os.environ.get('POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET'))
        state='NOT_CONFIGURED' if not configured else ('FAILED' if dead or q or quarantined_out else ('DELAYED' if retry or queued or inflight else 'HEALTHY'))
        last_error_code,last_error_at=_latest_error_candidate(c,contract)
        directions.append({
            'direction':direction,'contract':contract,'connection_state':state,
            'last_success_at':last_success,'last_received_at':last_received,'last_dispatched_at':last_dispatched,
            'queued_count':queued,'retrying_count':retry,'in_flight_count':inflight,
            'dead_letter_count':dead,'quarantined_count':q+quarantined_out,
            'oldest_queued_at':oldest,'oldest_backlog_at':oldest,
            'last_error_code':last_error_code,'last_error_at':last_error_at,
            'local_schema_version':RECTIFIED_SCHEMA_VERSION if contract=='PH_SM_APPROVED_CONTENT_V1' else SCHEMA_VERSION,
            'peer_schema_version':peer_schema,'peer_version':None,
            'credential_expiry_warning':_credential_expiry_warning(contract),
            'clock_skew_warning':_clock_skew_warning(c,contract,last_error_code),
            'source_counts':source_counts,
        })
    worker=c.execute("SELECT worker_name,heartbeat_at,last_cycle_at,last_result_json,process_id FROM integration_worker_state WHERE worker_name='integration-dispatch'").fetchone()
    worker_state=None
    if worker:
        worker_state={'worker_name':worker['worker_name'],'heartbeat_at':worker['heartbeat_at'],'last_cycle_at':worker['last_cycle_at'],'process_id':worker['process_id']}
        try: worker_state['last_result']=strict_json_loads(worker['last_result_json'] or '{}')
        except Exception: worker_state['last_result']={}
    return {
        'scoremax_release':SCOREMAX_INTEGRATION_RELEASE,
        'integration_contract_version':'1','integration_schema_version':RECTIFIED_SCHEMA_VERSION,
        'directions':directions,'worker':worker_state,
        'v1_0_manifest_pull_conflict_preserved':True,'v1_1_manifest_pull_supported':True,
    }


def production_preflight(strict=False):
    required=['POWER_HOUSE_TO_SCOREMAX_TOKEN','POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET','SCOREMAX_POWER_HOUSE_BASE_URL','SCOREMAX_TO_POWER_HOUSE_TOKEN','SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET','SCOREMAX_GROWTH_ENGINE_BASE_URL','SCOREMAX_TO_GROWTH_ENGINE_TOKEN','SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET']
    missing=[k for k in required if not str(os.environ.get(k,'')).strip()]
    issues=[]
    if not missing:
        for key in ('SCOREMAX_POWER_HOUSE_BASE_URL','SCOREMAX_GROWTH_ENGINE_BASE_URL'):
            v=str(os.environ.get(key,'')).strip(); u=urlparse(v)
            if u.scheme.lower()!='https' or not u.netloc: issues.append({'code':'INSECURE_PEER_URL','key':key})
        weak={'x','y','secret','password','changeme','change-me','placeholder','test','token'}
        for key in ('POWER_HOUSE_TO_SCOREMAX_TOKEN','POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET','SCOREMAX_TO_POWER_HOUSE_TOKEN','SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET','SCOREMAX_TO_GROWTH_ENGINE_TOKEN','SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET'):
            v=str(os.environ.get(key,'')).strip()
            min_len=24 if key.endswith('TOKEN') else 32
            if len(v)<min_len or v.lower() in weak: issues.append({'code':'WEAK_OR_PLACEHOLDER_SECRET','key':key})
        prev_pairs=(('POWER_HOUSE_TO_SCOREMAX_PREVIOUS_TOKEN','POWER_HOUSE_TO_SCOREMAX_PREVIOUS_HMAC_SECRET'),('GROWTH_ENGINE_TO_SCOREMAX_PREVIOUS_TOKEN','GROWTH_ENGINE_TO_SCOREMAX_PREVIOUS_HMAC_SECRET'))
        for tk,sk in prev_pairs:
            tv=str(os.environ.get(tk,'')).strip(); sv=str(os.environ.get(sk,'')).strip()
            if bool(tv)!=bool(sv): issues.append({'code':'INCOMPLETE_PREVIOUS_CREDENTIAL_PAIR','key':tk})
            if tv and (len(tv)<24 or len(sv)<32): issues.append({'code':'WEAK_PREVIOUS_CREDENTIAL_PAIR','key':tk})
        try:
            skew=int(os.environ.get('SCOREMAX_INTEGRATION_MAX_CLOCK_SKEW_SECONDS','300') or 300)
            if skew<30 or skew>900: issues.append({'code':'UNSAFE_CLOCK_SKEW','key':'SCOREMAX_INTEGRATION_MAX_CLOCK_SKEW_SECONDS'})
        except Exception: issues.append({'code':'INVALID_CLOCK_SKEW','key':'SCOREMAX_INTEGRATION_MAX_CLOCK_SKEW_SECONDS'})
    ready=not missing and not issues
    return {'ready':ready,'strict':bool(strict),'missing':missing,'issues':issues,'status':'READY' if ready else ('BLOCKED' if strict else 'NOT_CONFIGURED')}



def sync_content_requirements(c,producer_version=SCOREMAX_INTEGRATION_RELEASE,limit=100):
    """Project only queued changed coverage requests; no historical request-table scan."""
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='content_requirement_requests'").fetchone(): return 0
    before=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_PH_CONTENT_REQUIREMENT_V1'").fetchone()['n']
    changes=c.execute("SELECT * FROM integration_source_change_queue WHERE projected_at='' AND source_table='content_requirement_requests' ORDER BY id LIMIT ?",(int(limit),)).fetchall()
    for ch in changes:
        r=c.execute('SELECT * FROM content_requirement_requests WHERE id=?',(ch['source_pk'],)).fetchone()
        if not r or str(r['status'] or '').upper() not in {'OPEN','REQUESTED'}:
            c.execute('UPDATE integration_source_change_queue SET projected_at=? WHERE id=?',(utcnow(),ch['id'])); continue
        scopes=c.execute("""SELECT DISTINCT ph_market_id,ph_programme_id,ph_subject_id,ph_chapter_id FROM questions
          WHERE active=1 AND ph_projection_owner='POWER_HOUSE' AND COALESCE(ph_release_id,'')<>'' AND subject=? AND (?='' OR chapter=?)""",(r['subject'],r['chapter'] or '',r['chapter'] or '')).fetchall()
        scopes=[x for x in scopes if all(str(x[k] or '') for k in ('ph_market_id','ph_programme_id','ph_subject_id','ph_chapter_id'))]
        if len(scopes)!=1:
            # ambiguous academic scope remains queued for a later governed resolution rather than inventing identity
            continue
        sc=scopes[0]; priority=str(r['priority'] or '').lower(); pr='P0' if priority in {'critical','p0'} else ('P1' if priority in {'high','p1'} else 'P2')
        typ='BLUEPRINT_SHORTFALL' if r['blueprint_id'] else ('MISSING_MASTERY_LEVEL' if r['mastery_level'] else 'CHAPTER_COVERAGE_GAP')
        minimum=max(1,int(r['assets_required'] or 0),int(r['families_required'] or 0)); reqid=str(r['request_code'] or f'REQ::{r["id"]}')
        item={'requirement_id':reqid,'created_at':normalize_rfc3339_utc(r['created_at'] or utcnow(),field='requirement.created_at'),'requirement_type':typ,'priority':pr,
              'market_id':sc['ph_market_id'],'programme_id':sc['ph_programme_id'],'subject_id':sc['ph_subject_id'],'chapter_id':sc['ph_chapter_id'],'topic_id':None,'blueprint_id':None,'blueprint_version':None,
              'requested_inventory':{'minimum_count':minimum,'mastery_levels':[str(r['mastery_level']).upper().replace(' ','_')] if r['mastery_level'] else [],'evidence_roles':['INDEPENDENT'] if int(r['families_required'] or 0)>0 else [],'question_types':[]},
              'reason':str(r['reason'] or 'ScoreMax detected an inventory requirement.'),'supporting_metrics':{'assets_required':int(r['assets_required'] or 0),'families_required':int(r['families_required'] or 0)},'status':'REQUESTED'}
        batch='REQB::'+hashlib.sha256(reqid.encode()).hexdigest()[:20]; queue_content_requirement(c,{'request_batch_id':batch,'requirements':[item]},producer_version)
        c.execute('UPDATE integration_source_change_queue SET projected_at=? WHERE id=?',(utcnow(),ch['id']))
    after=c.execute("SELECT COUNT(*) n FROM integration_outbox WHERE contract_name='SM_PH_CONTENT_REQUIREMENT_V1'").fetchone()['n']
    return int(after-before)



def sync_delivery_evidence(c,producer_version=SCOREMAX_INTEGRATION_RELEASE,days=7,minimum_n=None):
    """Queue privacy-minimised question-version evidence for active PH releases with actual LIVE attempts."""
    end=datetime.now(timezone.utc).replace(microsecond=0); start=end-timedelta(days=max(1,int(days)))
    start_s=start.isoformat().replace('+00:00','Z'); end_s=end.isoformat().replace('+00:00','Z')
    n=0
    for r in c.execute("SELECT DISTINCT market_id,programme_id,subject_id,chapter_id FROM integration_ph_content_releases WHERE local_status='ACTIVE'").fetchall():
        mid=queue_delivery_evidence(c,market_id=r['market_id'],programme_id=r['programme_id'],subject_id=r['subject_id'],chapter_id=r['chapter_id'],period_start=start_s,period_end=end_s,minimum_n=minimum_n,producer_version=producer_version)
        if mid:n+=1
    return n
