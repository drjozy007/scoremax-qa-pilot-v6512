"""ScoreMax V6.6.11D — governed Power House delivery/incident bridge.

Additive compatibility layer over the SHA-verified V6.6.11C integration runtime.
It does not confer release authority. Cross-system work is outbox-only.
"""
from __future__ import annotations

import hashlib
import json

MARKER='SM-PH-BRIDGE-V6611D-1'
RELEASE='6.6.11D'
DELIVERY_ACK='SM_PH_CONTENT_DELIVERY_ACK_V1'
INCIDENT='SM_PH_CONTENT_INCIDENT_V1'
WITHDRAWAL='PH_SM_QUESTION_WITHDRAWAL_V1'
WITHDRAWAL_ACK='SM_PH_QUESTION_WITHDRAWAL_ACK_V1'

_INSTALLED=False
_INTEGRATION=None
_ORIGINALS={}


def init_schema(c):
    c.executescript('''
    CREATE TABLE IF NOT EXISTS ph_bridge_delivery_events_v6611d(
      id INTEGER PRIMARY KEY,
      event_key TEXT NOT NULL UNIQUE,
      release_id TEXT NOT NULL,
      release_version TEXT NOT NULL,
      package_checksum_sha256 TEXT NOT NULL,
      delivery_state TEXT NOT NULL,
      question_count INTEGER NOT NULL DEFAULT 0,
      outbox_message_id TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ph_bridge_incident_events_v6611d(
      id INTEGER PRIMARY KEY,
      feedback_code TEXT NOT NULL UNIQUE,
      question_db_id INTEGER NOT NULL,
      ph_question_id TEXT NOT NULL,
      ph_question_version_id TEXT NOT NULL,
      ph_question_checksum_sha256 TEXT NOT NULL,
      ph_release_id TEXT NOT NULL,
      ph_release_version TEXT NOT NULL,
      outbox_message_id TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ph_bridge_withdrawal_receipts_v6611d(
      id INTEGER PRIMARY KEY,
      export_public_id TEXT NOT NULL UNIQUE,
      population_sha256 TEXT NOT NULL,
      inbound_message_id TEXT NOT NULL,
      item_count INTEGER NOT NULL,
      ack_message_id TEXT NOT NULL DEFAULT '',
      receipt_sha256 TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    ''')


def _sha_text(value):
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()


def _event_key(release_id, release_version, state):
    return f'{release_id}|{release_version}|{state}'


def _queue_delivery_state(c, release_id, release_version, state):
    i=_INTEGRATION
    if not i: return ''
    rel=c.execute('SELECT * FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(release_id,release_version)).fetchone()
    if not rel: return ''
    count=int(c.execute('SELECT COUNT(*) n FROM integration_ph_release_question_membership WHERE release_id=? AND release_version=?',(release_id,release_version)).fetchone()['n'] or 0)
    key=_event_key(release_id,release_version,state)
    payload={
      'event_id':'SMDEL::'+_sha_text(key)[:32],
      'delivery_state':state,
      'release_id':str(release_id),
      'release_version':str(release_version),
      'package_checksum_sha256':str(rel['package_checksum_sha256'] or '').lower(),
      'question_count':count,
      'scoremax_release':RELEASE,
      'release_authority_conferred':False,
    }
    env=i._envelope(DELIVERY_ACK,'POWER_HOUSE','delivery-ack::'+key,key,payload,RELEASE,'INTERNAL')
    msg=i._queue(c,env,key,'PH_DELIVERY_STATE',key)
    now=i.utcnow()
    c.execute('''INSERT OR IGNORE INTO ph_bridge_delivery_events_v6611d(event_key,release_id,release_version,package_checksum_sha256,delivery_state,question_count,outbox_message_id,created_at)
                 VALUES(?,?,?,?,?,?,?,?)''',(key,release_id,release_version,payload['package_checksum_sha256'],state,count,msg,now))
    return msg


def queue_reported_question_incident(c, question, feedback_code, category, severity, description, context):
    """Queue one PII-free incident only for an exact Power House learner projection."""
    if not question: return ''
    keys=set(question.keys()) if hasattr(question,'keys') else set(question)
    def val(k): return question[k] if k in keys else None
    if str(val('ph_projection_owner') or '')!='POWER_HOUSE': return ''
    required=('ph_question_id','ph_question_version_id','ph_question_checksum_sha256','ph_release_id','ph_release_version','ph_release_checksum_sha256')
    if any(not str(val(k) or '').strip() for k in required): return ''
    code=str(feedback_code or '').strip()
    if not code: return ''
    existing=c.execute('SELECT outbox_message_id FROM ph_bridge_incident_events_v6611d WHERE feedback_code=?',(code,)).fetchone()
    if existing: return str(existing['outbox_message_id'] or '')
    ctx=dict(context or {})
    payload={
      'incident_id':'SMINC::'+_sha_text(code+'|'+str(val('ph_question_version_id')))[:32],
      'scoremax_feedback_code':code,
      'category':str(category or 'Other')[:120],
      'severity':str(severity or 'MEDIUM').upper()[:20],
      'description':str(description or '')[:4000],
      'source':str(ctx.get('source') or '')[:80],
      'page_path':str(ctx.get('page') or '')[:500],
      'question':{
        'question_id':str(val('ph_question_id')),
        'question_version_id':str(val('ph_question_version_id')),
        'question_checksum_sha256':str(val('ph_question_checksum_sha256')).lower(),
        'release_id':str(val('ph_release_id')),
        'release_version':str(val('ph_release_version')),
        'release_checksum_sha256':str(val('ph_release_checksum_sha256')).lower(),
        'market_id':str(val('ph_market_id') or ''),
        'programme_id':str(val('ph_programme_id') or ''),
        'subject_id':str(val('ph_subject_id') or ''),
        'chapter_id':str(val('ph_chapter_id') or ''),
        'rendered_question_sha256':_sha_text(str(val('question') or '')),
      },
      'reporter_identity_included':False,
      'student_pii_included':False,
      'release_authority_conferred':False,
    }
    i=_INTEGRATION
    idem='content-incident::'+code+'::'+str(val('ph_question_version_id'))
    env=i._envelope(INCIDENT,'POWER_HOUSE',idem,code,payload,RELEASE,'INTERNAL')
    msg=i._queue(c,env,code,'PILOT_FEEDBACK',code)
    c.execute('''INSERT INTO ph_bridge_incident_events_v6611d(feedback_code,question_db_id,ph_question_id,ph_question_version_id,ph_question_checksum_sha256,ph_release_id,ph_release_version,outbox_message_id,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?)''',(code,int(val('id')),str(val('ph_question_id')),str(val('ph_question_version_id')),str(val('ph_question_checksum_sha256')).lower(),str(val('ph_release_id')),str(val('ph_release_version')),msg,i.utcnow()))
    return msg


def _withdraw_one(c, item):
    qid=str(item.get('question_public_id') or '').strip()
    if not qid:
        return {'item_public_id':str(item.get('item_public_id') or ''),'question_public_id':'','state':'NOT_PRESENT','historical_attempts_preserved':True}
    rows=c.execute("SELECT id,active,status FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND ph_question_id=? ORDER BY id",(qid,)).fetchall()
    active=[r for r in rows if int(r['active'] or 0)==1]
    if not rows: state='NOT_PRESENT'
    elif not active: state='ALREADY_WITHDRAWN'
    else:
        ids=[int(r['id']) for r in active]
        marks=','.join('?' for _ in ids)
        c.execute(f"UPDATE questions SET active=0,status='Withdrawn' WHERE id IN ({marks})",ids)
        state='WITHDRAWN'
    return {
      'item_public_id':str(item.get('item_public_id') or ''),
      'question_public_id':qid,
      'state':state,
      'historical_attempts_preserved':True,
    }


def admit_withdrawal_envelope(c, envelope, content_sha_header=''):
    """Execute future-delivery stops only; historical attempts are never mutated."""
    i=_INTEGRATION
    errors=i._strict_envelope_errors(envelope,WITHDRAWAL,'POWER_HOUSE','SCOREMAX')
    if content_sha_header and content_sha_header!=str(envelope.get('payload_checksum_sha256') or ''):
        errors.append({'code':'HEADER_CHECKSUM','path':'X-Content-SHA256','message':'Header checksum mismatch','retryable':False})
    if errors:
        i._begin_immediate(c); rec=i._receipt(c,envelope,'REJECTED',errors); c.commit(); return rec,422
    p=envelope.get('payload') or {}; export_id=str(p.get('export_public_id') or ''); pop=str(p.get('population_sha256') or '').lower(); items=list(p.get('items') or [])
    i._begin_immediate(c)
    existing=c.execute('SELECT * FROM ph_bridge_withdrawal_receipts_v6611d WHERE export_public_id=?',(export_id,)).fetchone()
    if existing:
        rec=i._receipt(c,envelope,'DUPLICATE'); c.commit(); return rec,200
    results=[_withdraw_one(c,item) for item in items]
    ack_payload={
      'export_public_id':export_id,
      'population_sha256':pop,
      'items':results,
      'scoremax_release':RELEASE,
      'release_authority_conferred':False,
    }
    idem='withdrawal-ack::'+export_id+'::'+pop
    env=i._envelope(WITHDRAWAL_ACK,'POWER_HOUSE',idem,export_id,ack_payload,RELEASE,'INTERNAL')
    ack_msg=i._queue(c,env,export_id,'PH_WITHDRAWAL_EXPORT',export_id)
    receipt_sha=_sha_text(i.canonical_json({'export_public_id':export_id,'population_sha256':pop,'items':results}))
    c.execute('''INSERT INTO ph_bridge_withdrawal_receipts_v6611d(export_public_id,population_sha256,inbound_message_id,item_count,ack_message_id,receipt_sha256,created_at)
                 VALUES(?,?,?,?,?,?,?)''',(export_id,pop,str(envelope.get('message_id') or ''),len(items),ack_msg,receipt_sha,i.utcnow()))
    rec=i._receipt(c,envelope,'ACCEPTED'); c.commit(); return rec,202


def install(integration):
    global _INSTALLED,_INTEGRATION
    if _INSTALLED: return
    _INTEGRATION=integration
    _ORIGINALS['dispatch_target']=integration._dispatch_target
    _ORIGINALS['admit_content_envelope']=integration.admit_content_envelope
    _ORIGINALS['activate_release']=integration._activate_release

    def dispatch_target(contract):
        if contract in {DELIVERY_ACK,INCIDENT,WITHDRAWAL_ACK}:
            base=integration.os.environ.get('SCOREMAX_POWER_HOUSE_BASE_URL','').rstrip('/')
            paths={
              DELIVERY_ACK:'/api/integration/v1/scoremax/content-delivery-acks',
              INCIDENT:'/api/integration/v1/scoremax/content-incidents',
              WITHDRAWAL_ACK:'/api/integration/v1/scoremax/question-withdrawal-acks',
            }
            path=paths[contract]
            return (base+path if base else ''),path,'SCOREMAX_TO_POWER_HOUSE'
        return _ORIGINALS['dispatch_target'](contract)

    def admit_content(c,envelope,content_sha_header=''):
        rec,status=_ORIGINALS['admit_content_envelope'](c,envelope,content_sha_header)
        if str(rec.get('status') or '') in {'ACCEPTED','DUPLICATE'}:
            p=envelope.get('payload') if isinstance(envelope.get('payload'),dict) else {}
            if str(p.get('release_operation') or 'PUBLISH_SNAPSHOT').upper()=='PUBLISH_SNAPSHOT':
                rel=p.get('release') or {}; rid=str(rel.get('release_id') or ''); ver=str(rel.get('release_version') or '')
                if rid and ver:
                    init_schema(c); _queue_delivery_state(c,rid,ver,'IMPORTED_STAGED'); c.commit()
        return rec,status

    def activate_release(c,release_id,release_version):
        count=_ORIGINALS['activate_release'](c,release_id,release_version)
        row=c.execute('SELECT local_status FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(release_id,release_version)).fetchone()
        if row and str(row['local_status'] or '')=='ACTIVE':
            init_schema(c); _queue_delivery_state(c,release_id,release_version,'ACTIVATED_LEARNER_LIVE')
        return count

    integration._dispatch_target=dispatch_target
    integration.admit_content_envelope=admit_content
    integration._activate_release=activate_release
    _INSTALLED=True
