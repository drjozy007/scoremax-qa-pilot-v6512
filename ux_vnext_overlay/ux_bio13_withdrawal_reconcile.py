from __future__ import annotations
from pathlib import Path

MARKER='SCOREMAX_BIO13_WITHDRAWAL_RECONCILE_V1'

RUNTIME = r'''from __future__ import annotations
import json,re
from collections import Counter
import scoremax_ph_bridge_v6611d as _bridge

EXPECTED_EXPORT='PH-SMWD15L1-B6705FCBA697B97A8D0BB539'
EXPECTED_POP='0cdea5fb0c8eb960cd2a66bd823ddf26d03f67b281c6077215d45c384b9183c3'
EXPECTED_ITEMS=100
_INSTALLED=False
_ORIGINAL=None


def _ensure(c):
    c.execute('''CREATE TABLE IF NOT EXISTS bio13_withdrawal_reconciliation_v1(
      id INTEGER PRIMARY KEY,
      export_public_id TEXT NOT NULL UNIQUE,
      population_sha256 TEXT NOT NULL,
      original_ack_message_id TEXT NOT NULL,
      original_not_present_count INTEGER NOT NULL,
      corrected_withdrawn_count INTEGER NOT NULL,
      corrected_already_withdrawn_count INTEGER NOT NULL,
      corrected_ack_message_id TEXT NOT NULL,
      historical_attempts_preserved INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL
    )''')


def _ack_envelope(c, ack_message_id):
    found=[]
    tables=[str(r[0]) for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    for table in tables:
        if not re.fullmatch(r'[A-Za-z0-9_]+',table):
            continue
        cols={str(r[1]) for r in c.execute(f'PRAGMA table_info({table})').fetchall()}
        if not {'message_id','envelope_json'} <= cols:
            continue
        rows=c.execute(f'SELECT envelope_json FROM {table} WHERE message_id=?',(ack_message_id,)).fetchall()
        for row in rows:
            try: env=json.loads(str(row[0] or '{}'))
            except Exception as exc: raise RuntimeError('BIO13_RECONCILE_MALFORMED_ACK_ENVELOPE') from exc
            found.append((table,env))
    if len(found)!=1:
        raise RuntimeError(f'BIO13_RECONCILE_ACK_ENVELOPE_COUNT:{len(found)}')
    table,env=found[0]
    if str(env.get('contract_name') or '')!='SM_PH_QUESTION_WITHDRAWAL_ACK_V1':
        raise RuntimeError('BIO13_RECONCILE_ACK_CONTRACT_MISMATCH')
    p=env.get('payload') if isinstance(env.get('payload'),dict) else {}
    if str(p.get('export_public_id') or '')!=EXPECTED_EXPORT or str(p.get('population_sha256') or '').lower()!=EXPECTED_POP:
        raise RuntimeError('BIO13_RECONCILE_ACK_IDENTITY_MISMATCH')
    items=list(p.get('items') or [])
    if len(items)!=EXPECTED_ITEMS:
        raise RuntimeError(f'BIO13_RECONCILE_ACK_ITEM_COUNT:{len(items)}')
    states=Counter(str(x.get('state') or '') for x in items)
    if states!={'NOT_PRESENT':EXPECTED_ITEMS}:
        raise RuntimeError('BIO13_RECONCILE_PRIOR_RESULT_NOT_EXACT_NOT_PRESENT:'+json.dumps(dict(states),sort_keys=True))
    if p.get('historical_attempts_preserved') is not True:
        raise RuntimeError('BIO13_RECONCILE_PRIOR_HISTORY_FLAG_MISSING')
    return env,table


def _exact(envelope):
    p=envelope.get('payload') if isinstance(envelope,dict) and isinstance(envelope.get('payload'),dict) else {}
    return str(p.get('export_public_id') or '')==EXPECTED_EXPORT and str(p.get('population_sha256') or '').lower()==EXPECTED_POP


def install():
    global _INSTALLED,_ORIGINAL
    if _INSTALLED: return
    _ORIGINAL=_bridge.admit_withdrawal_envelope

    def admit(c,envelope,content_sha_header=''):
        if not _exact(envelope):
            return _ORIGINAL(c,envelope,content_sha_header)
        i=_bridge._INTEGRATION
        errors=i._strict_envelope_errors(envelope,_bridge.WITHDRAWAL,'POWER_HOUSE','SCOREMAX')
        if content_sha_header and content_sha_header!=str(envelope.get('payload_checksum_sha256') or ''):
            errors.append({'code':'HEADER_CHECKSUM','path':'X-Content-SHA256','message':'Header checksum mismatch','retryable':False})
        if errors:
            return _ORIGINAL(c,envelope,content_sha_header)
        p=envelope.get('payload') or {}; items=list(p.get('items') or [])
        if len(items)!=EXPECTED_ITEMS:
            raise RuntimeError(f'BIO13_RECONCILE_INCOMING_ITEM_COUNT:{len(items)}')
        _bridge.init_schema(c); _ensure(c)
        prior=c.execute('SELECT * FROM ph_bridge_withdrawal_receipts_v6611d WHERE export_public_id=? AND population_sha256=?',(EXPECTED_EXPORT,EXPECTED_POP)).fetchone()
        if not prior:
            return _ORIGINAL(c,envelope,content_sha_header)
        done=c.execute('SELECT * FROM bio13_withdrawal_reconciliation_v1 WHERE export_public_id=?',(EXPECTED_EXPORT,)).fetchone()
        if done:
            i._begin_immediate(c); rec=i._receipt(c,envelope,'ACCEPTED'); c.commit(); return rec,200
        ack_id=str(prior['ack_message_id'] or '')
        if not ack_id:
            raise RuntimeError('BIO13_RECONCILE_ORIGINAL_ACK_ID_MISSING')
        old_ack,_source_table=_ack_envelope(c,ack_id)

        i._begin_immediate(c)
        try:
            results=[_bridge._withdraw_one(c,item) for item in items]
            states=Counter(str(x.get('state') or '') for x in results)
            expected={'WITHDRAWN':98,'ALREADY_WITHDRAWN':2}
            if states!=expected:
                raise RuntimeError('BIO13_RECONCILE_CORRECTED_STATE_MISMATCH:'+json.dumps(dict(states),sort_keys=True))
            if any(x.get('historical_attempts_preserved') is not True for x in results):
                raise RuntimeError('BIO13_RECONCILE_HISTORY_FLAG_MISSING')
            ack_payload={
              'export_public_id':EXPECTED_EXPORT,'population_sha256':EXPECTED_POP,'items':results,
              'historical_attempts_preserved':True,'scoremax_release':_bridge.RELEASE,'release_authority_conferred':False,
            }
            idem='withdrawal-ack-reconcile::'+EXPECTED_EXPORT+'::'+EXPECTED_POP
            ack_env=i._envelope(_bridge.WITHDRAWAL_ACK,'POWER_HOUSE',idem,EXPECTED_EXPORT,ack_payload,_bridge.RELEASE,'INTERNAL')
            ack_msg=i._queue(c,ack_env,EXPECTED_EXPORT,'PH_WITHDRAWAL_RECONCILIATION',EXPECTED_EXPORT)
            c.execute('''INSERT INTO bio13_withdrawal_reconciliation_v1(
              export_public_id,population_sha256,original_ack_message_id,original_not_present_count,
              corrected_withdrawn_count,corrected_already_withdrawn_count,corrected_ack_message_id,
              historical_attempts_preserved,created_at) VALUES(?,?,?,?,?,?,?,?,?)''',
              (EXPECTED_EXPORT,EXPECTED_POP,ack_id,EXPECTED_ITEMS,98,2,ack_msg,1,i.utcnow()))
            rec=i._receipt(c,envelope,'ACCEPTED')
            c.commit()
        except Exception:
            c.rollback(); raise
        print('SCOREMAX_BIO13_WITHDRAWAL_RECONCILED export='+EXPECTED_EXPORT+' population='+EXPECTED_POP+' prior_not_present=100 withdrawn=98 already_withdrawn=2 historical_attempts_preserved=true release_authority=false',flush=True)
        return rec,202

    _bridge.admit_withdrawal_envelope=admit
    _INSTALLED=True
    print('SCOREMAX_BIO13_WITHDRAWAL_RECONCILE_V1_PASS exact_export_only=true prior_ack_required=true prior_not_present_100_required=true corrected_98_2_required=true transactional=true audit_preserved=true normal_idempotency_unchanged=true',flush=True)
'''


def apply_bio13_withdrawal_reconcile(root: Path) -> None:
    module=root/'ux_bio13_withdrawal_reconcile_runtime.py'
    module.write_text(RUNTIME,encoding='utf-8')
    production=root/'scoremax_production.py'
    text=production.read_text(encoding='utf-8')
    old='_run_bio13_identity_crosswalk_audit(scoremax)\napplication=scoremax.app'
    new=(
      '_run_bio13_identity_crosswalk_audit(scoremax)\n'
      'from ux_bio13_withdrawal_reconcile_runtime import install as _install_bio13_withdrawal_reconcile\n'
      '_install_bio13_withdrawal_reconcile()\n'
      'application=scoremax.app'
    )
    if '_install_bio13_withdrawal_reconcile()' not in text:
        if text.count(old)!=1:
            raise SystemExit('SCOREMAX_BIO13_WITHDRAWAL_RECONCILE_ANCHOR_MISMATCH')
        text=text.replace(old,new,1)
        production.write_text(text,encoding='utf-8')
    rendered=production.read_text(encoding='utf-8')
    for token in ('_install_bio13_withdrawal_reconcile()','ux_bio13_withdrawal_reconcile_runtime'):
        if token not in rendered: raise SystemExit('SCOREMAX_BIO13_WITHDRAWAL_RECONCILE_INSTALL_MISSING:'+token)
    print(MARKER+' BUILD_PASS exact_export_only=true audit_preserved=true release_authority=false',flush=True)
