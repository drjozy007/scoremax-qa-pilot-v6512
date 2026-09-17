from __future__ import annotations
from pathlib import Path

MARKER='SCOREMAX_BIO13_FAILED_PILOT_RETIREMENT_V1'
AUTHORITATIVE_TRANSPORT_SHA='ba8e863c4793f694e5227e5b5525147df5e132ecdce0e5ccf5057ae552178fe5'

RUNTIME = r"""from __future__ import annotations
import json,os

PROMPT_PACK_ID='BIO13_SCOREMAX_PILOT100_DIRECT_INTAKE_SAFE_v1_1'
PROMPT_PACK_VERSION='e1ddb25d2213058de86394fa00b119c29b18ac6eb98c285599ee8ca6b1651883'
TRANSPORT_SHA='ba8e863c4793f694e5227e5b5525147df5e132ecdce0e5ccf5057ae552178fe5'
POLICY='SCOREMAX-BIO13-FAILED-PILOT-RETIREMENT-V1'


def _armed():
    return str(os.environ.get('SCOREMAX_RETIRE_FAILED_BIO13_PILOT','OFF')).strip().upper()=='ARMED'


def run(scoremax):
    if not _armed():
        print('SCOREMAX_BIO13_FAILED_PILOT_RETIREMENT disabled=true',flush=True); return
    c=scoremax.db()
    try:
        c.execute('''CREATE TABLE IF NOT EXISTS bio13_failed_pilot_retirement_v1(
          id INTEGER PRIMARY KEY,
          batch_id INTEGER NOT NULL UNIQUE,
          batch_code TEXT NOT NULL,
          prompt_pack_id TEXT NOT NULL,
          prompt_pack_version TEXT NOT NULL,
          transport_sha256 TEXT NOT NULL,
          question_count INTEGER NOT NULL,
          active_before INTEGER NOT NULL,
          inactive_before INTEGER NOT NULL,
          active_after INTEGER NOT NULL,
          historical_attempts_preserved INTEGER NOT NULL DEFAULT 1,
          policy TEXT NOT NULL,
          reason TEXT NOT NULL,
          created_at TEXT NOT NULL
        )''')
        batches=c.execute('''SELECT id,batch_code,row_count,valid_count,error_count,warning_count
          FROM content_import_batches
          WHERE source_prompt_pack_id=? AND source_prompt_pack_version=? AND payload_checksum=?
          ORDER BY id''',(PROMPT_PACK_ID,PROMPT_PACK_VERSION,TRANSPORT_SHA)).fetchall()
        if len(batches)!=1: raise RuntimeError(f'BIO13_RETIRE_BATCH_COUNT:{len(batches)}')
        b=batches[0]; bid=int(b['id'])
        if int(b['row_count'] or 0)!=100 or int(b['valid_count'] or 0)!=100 or int(b['error_count'] or 0)!=0:
            raise RuntimeError('BIO13_RETIRE_BATCH_NOT_EXACT_CLEAN_100')
        rows=c.execute('''SELECT q.id,q.question_id,q.active,q.status,r.row_json
          FROM content_import_batch_rows r JOIN questions q ON q.id=r.question_db_id
          WHERE r.batch_id=? AND r.import_status='IMPORTED' ORDER BY q.id''',(bid,)).fetchall()
        if len(rows)!=100 or len({int(r['id']) for r in rows})!=100:
            raise RuntimeError(f'BIO13_RETIRE_IMPORTED_POPULATION:{len(rows)}')
        for r in rows:
            try: src=json.loads(str(r['row_json'] or '{}'))
            except Exception as exc: raise RuntimeError('BIO13_RETIRE_MALFORMED_IMMUTABLE_ROW') from exc
            if str(src.get('Question ID') or '').strip()!=str(r['question_id'] or '').strip():
                raise RuntimeError('BIO13_RETIRE_SOURCE_QID_MISMATCH')
            if not str(src.get('Power House Public ID') or '').strip() or not str(src.get('Power House Source Row') or '').strip():
                raise RuntimeError('BIO13_RETIRE_IDENTITY_TRIPLET_INCOMPLETE')
        done=c.execute('SELECT * FROM bio13_failed_pilot_retirement_v1 WHERE batch_id=?',(bid,)).fetchone()
        active=sum(1 for r in rows if int(r['active'] or 0)==1); inactive=100-active
        if done:
            if active!=0: raise RuntimeError(f'BIO13_RETIRE_IDEMPOTENCY_ACTIVE:{active}')
            print('SCOREMAX_BIO13_FAILED_PILOT_RETIREMENT PASS idempotent=true questions=100 active=0 historical_attempts_preserved=true',flush=True); return
        if active!=98 or inactive!=2:
            raise RuntimeError(f'BIO13_RETIRE_PRESTATE_MISMATCH:active={active}:inactive={inactive}')
        ids=[int(r['id']) for r in rows if int(r['active'] or 0)==1]
        c.execute('BEGIN IMMEDIATE') if not getattr(c,'in_transaction',False) else None
        marks=','.join('?' for _ in ids)
        c.execute(f"UPDATE questions SET active=0,status='Withdrawn' WHERE id IN ({marks})",ids)
        remaining=int(c.execute('''SELECT COUNT(*) FROM content_import_batch_rows r JOIN questions q ON q.id=r.question_db_id
          WHERE r.batch_id=? AND r.import_status='IMPORTED' AND q.active=1''',(bid,)).fetchone()[0])
        if remaining!=0: raise RuntimeError(f'BIO13_RETIRE_ACTIVE_REMAINS:{remaining}')
        qc=str(c.execute('PRAGMA quick_check').fetchone()[0]); fk=c.execute('PRAGMA foreign_key_check').fetchall()
        if qc!='ok' or fk: raise RuntimeError(f'BIO13_RETIRE_DB_HEALTH:qc={qc}:fk={len(fk)}')
        c.execute('''INSERT INTO bio13_failed_pilot_retirement_v1(
          batch_id,batch_code,prompt_pack_id,prompt_pack_version,transport_sha256,question_count,
          active_before,inactive_before,active_after,historical_attempts_preserved,policy,reason,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))''',
          (bid,str(b['batch_code'] or ''),PROMPT_PACK_ID,PROMPT_PACK_VERSION,TRANSPORT_SHA,100,98,2,0,1,POLICY,
           'Historical Emergency Direct pilot failed governed population authority; retire learner delivery without rewriting historical attempts or source evidence.'))
        c.commit()
        print('SCOREMAX_BIO13_FAILED_PILOT_RETIREMENT PASS questions=100 withdrawn_now=98 already_inactive=2 active_after=0 historical_attempts_preserved=true db_integrity=ok db_fk=0 release_authority=false',flush=True)
    except Exception:
        c.rollback(); raise
    finally:
        c.close()
"""


def apply_bio13_failed_pilot_retirement(root: Path) -> None:
    audit_builder=(Path(__file__).resolve().parent/'ux_bio13_identity_crosswalk_audit.py').read_text(encoding='utf-8')
    expected=f'EXPECTED_CSV_SHA256="{AUTHORITATIVE_TRANSPORT_SHA}"'
    if expected not in audit_builder:
        raise SystemExit('SCOREMAX_BIO13_RETIREMENT_TRANSPORT_AUTHORITY_DRIFT')
    if f"TRANSPORT_SHA='{AUTHORITATIVE_TRANSPORT_SHA}'" not in RUNTIME:
        raise SystemExit('SCOREMAX_BIO13_RETIREMENT_RUNTIME_SHA_DRIFT')
    module=root/'ux_bio13_failed_pilot_retirement_runtime.py'
    compile(RUNTIME,str(module),'exec')
    module.write_text(RUNTIME,encoding='utf-8')
    production=root/'scoremax_production.py'
    text=production.read_text(encoding='utf-8')
    old='_run_bio13_identity_crosswalk_audit(scoremax)\napplication=scoremax.app'
    new=(
      '_run_bio13_identity_crosswalk_audit(scoremax)\n'
      'from ux_bio13_failed_pilot_retirement_runtime import run as _run_bio13_failed_pilot_retirement\n'
      '_run_bio13_failed_pilot_retirement(scoremax)\n'
      'application=scoremax.app'
    )
    if '_run_bio13_failed_pilot_retirement(scoremax)' not in text:
        if text.count(old)!=1: raise SystemExit('SCOREMAX_BIO13_FAILED_PILOT_RETIREMENT_ANCHOR_MISMATCH')
        text=text.replace(old,new,1); production.write_text(text,encoding='utf-8')
    rendered=production.read_text(encoding='utf-8')
    if '_run_bio13_failed_pilot_retirement(scoremax)' not in rendered:
        raise SystemExit('SCOREMAX_BIO13_FAILED_PILOT_RETIREMENT_INSTALL_MISSING')
    print(MARKER+' BUILD_PASS exact_batch_fingerprint=true authoritative_transport_sha=true authority_drift_gate=true armed_only=true history_preserved=true runtime_compile=true release_authority=false',flush=True)
