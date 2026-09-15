from __future__ import annotations

import base64
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path

PAYLOAD_ENV='SCOREMAX_ONE_TIME_BIO13_GZ_B64'
PAYLOAD_CHUNK_PREFIX='SCOREMAX_ONE_TIME_BIO13_GZ_B64_'
EXPECTED_CSV_SHA256='ba8e863c4793f694e5227e5b5525147df5e132ecdce0e5ccf5057ae552178fe5'
EXPECTED_COUNT=100
PROMPT_PACK_ID='BIO13_SCOREMAX_PILOT100_DIRECT_INTAKE_SAFE_v1_1'
PROMPT_PACK_VERSION='e1ddb25d2213058de86394fa00b119c29b18ac6eb98c285599ee8ca6b1651883'
HELD_IDS={'BIO12-CH13-B02-123','BIO12-CH13-B02-137'}
ATTESTATION='I CONFIRM THIS IS A FROZEN ACADEMICALLY APPROVED RELEASE'
RECEIPT_NAME='BIO13_SCOREMAX_PILOT100_LIVE_INTAKE_RECEIPT.json'


def _fail(msg: str) -> None:
    raise RuntimeError('BIO13_ONE_TIME_INTAKE_FAIL:'+msg)


def _encoded_payload() -> str:
    direct=os.environ.get(PAYLOAD_ENV,'').strip()
    if direct:
        return direct
    chunks=[]
    for i in range(1,9):
        value=os.environ.get(f'{PAYLOAD_CHUNK_PREFIX}{i}','').strip()
        if value:
            chunks.append(value)
    return ''.join(chunks)


def _decode_payload() -> tuple[bytes,list[dict],set[str]]:
    encoded=_encoded_payload()
    if not encoded:
        return b'',[],set()
    try:
        raw=gzip.decompress(base64.b64decode(encoded,validate=True))
    except Exception as exc:
        _fail('payload_decode_error='+type(exc).__name__)
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=EXPECTED_CSV_SHA256:
        _fail('payload_sha256_mismatch')
    try:
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    except Exception as exc:
        _fail('csv_decode_error='+type(exc).__name__)
    ids=[str(r.get('Question ID') or '').strip() for r in rows]
    if len(rows)!=EXPECTED_COUNT or len(set(ids))!=EXPECTED_COUNT or any(not x for x in ids):
        _fail(f'population_identity_invalid rows={len(rows)} unique={len(set(ids))}')
    if HELD_IDS.intersection(ids):
        _fail('held_question_present')
    if any(str(r.get('ScoreMax Ready') or '').strip().casefold() not in {'yes','true','1'} for r in rows):
        _fail('scoremax_ready_not_universal')
    return raw,rows,set(ids)


def _batch(scoremax):
    c=scoremax.db()
    try:
        rows=c.execute(
            """SELECT * FROM content_import_batches
               WHERE source_prompt_pack_id=? AND source_prompt_pack_version=? AND payload_checksum=?
               ORDER BY id""",
            (PROMPT_PACK_ID,PROMPT_PACK_VERSION,EXPECTED_CSV_SHA256),
        ).fetchall()
    finally:
        c.close()
    if len(rows)>1:
        _fail('multiple_matching_batches')
    return rows[0] if rows else None


def _target_questions(scoremax, ids:set[str]):
    c=scoremax.db()
    try:
        marks=','.join('?' for _ in ids)
        return c.execute(f'SELECT * FROM questions WHERE question_id IN ({marks}) ORDER BY question_id',sorted(ids)).fetchall()
    finally:
        c.close()


def _admin(scoremax):
    c=scoremax.db()
    try:
        row=c.execute("SELECT id,full_name,COALESCE(session_version,0) session_version FROM users WHERE role='admin' AND COALESCE(account_status,'active')='active' ORDER BY id LIMIT 1").fetchone()
    finally:
        c.close()
    if not row:
        _fail('active_admin_missing')
    return row


def _client(scoremax, admin, token:str):
    client=scoremax.app.test_client()
    with client.session_transaction() as s:
        s.update(user_id=int(admin['id']),role='admin',full_name=str(admin['full_name']),session_version=int(admin['session_version']),_csrf_token=token)
    return client


def _verify_batch(scoremax, batch, ids:set[str], *, released:bool) -> tuple[int,int]:
    if not batch:
        _fail('batch_missing')
    if str(batch['intake_mode'] or '').upper()!='EMERGENCY_DIRECT':
        _fail('batch_intake_mode_mismatch')
    if str(batch['source_system'] or '').upper()!='POWER_HOUSE_GOVERNED':
        _fail('batch_source_system_mismatch')
    if int(batch['row_count'] or 0)!=EXPECTED_COUNT or int(batch['valid_count'] or 0)!=EXPECTED_COUNT or int(batch['error_count'] or 0)!=0 or int(batch['warning_count'] or 0)!=0:
        _fail('batch_validation_not_clean')
    qs=_target_questions(scoremax,ids)
    if len(qs)!=EXPECTED_COUNT or {str(q['question_id']) for q in qs}!=ids:
        _fail(f'question_population_mismatch count={len(qs)}')
    if any(int(q['source_import_batch_id'] or 0)!=int(batch['id']) for q in qs):
        _fail('question_batch_binding_mismatch')
    scored=0
    for q in qs:
        if scoremax.canonical_question_type(q)!='single_choice':
            _fail('non_single_choice_question='+str(q['question_id']))
        result=scoremax.mark_question_response(q,q['answer'])
        if not bool(result[0]) or float(result[1])<=0:
            _fail('scoring_failure='+str(q['question_id']))
        scored+=1
    if released:
        if str(batch['release_status'] or '').upper()!='RELEASED_ELIGIBLE' or int(batch['released_count'] or 0)!=EXPECTED_COUNT:
            _fail('release_batch_state_invalid')
        if any(str(q['status'] or '')!='Approved' or str(q['review_status'] or '')!='Approved' or int(q['active'] or 0)!=1 or str(q['content_environment'] or '')!='PRODUCTION' for q in qs):
            _fail('released_question_state_invalid')
    else:
        if str(batch['release_status'] or '').upper()!='NOT_RELEASED':
            _fail('candidate_release_state_invalid')
        if any(str(q['status'] or '')!='Draft' or str(q['review_status'] or '')!='Draft' or int(q['active'] or 0)!=0 or str(q['content_environment'] or '')!='CANDIDATE' for q in qs):
            _fail('candidate_question_state_invalid')
    c=scoremax.db()
    try:
        quick=c.execute('PRAGMA quick_check').fetchone()[0]
        fk=c.execute('PRAGMA foreign_key_check').fetchall()
    finally:
        c.close()
    if quick!='ok' or fk:
        _fail(f'db_integrity_failed quick={quick} fk={len(fk)}')
    return len(qs),scored


def _write_receipt(batch, scored:int) -> None:
    root=Path(os.environ.get('SCOREMAX_CONTENT_INTAKE_DIR','/data/scoremax/intake')).resolve()
    root.mkdir(parents=True,exist_ok=True)
    receipt={
        'status':'PASS',
        'operation':'BIO13_SCOREMAX_PILOT100_ONE_TIME_GOVERNED_EMERGENCY_DIRECT',
        'transport_sha256':EXPECTED_CSV_SHA256,
        'selection_ledger_sha256':PROMPT_PACK_VERSION,
        'question_count':EXPECTED_COUNT,
        'scoring_pass':scored,
        'batch_code':str(batch['batch_code'] or ''),
        'batch_id':int(batch['id']),
        'release_status':str(batch['release_status'] or ''),
        'released_count':int(batch['released_count'] or 0),
        'held_ids_absent':True,
    }
    target=root/RECEIPT_NAME
    tmp=target.with_suffix('.tmp')
    tmp.write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    os.replace(tmp,target)


def run_one_time_bio13_intake(scoremax) -> None:
    raw,rows,ids=_decode_payload()
    if not raw:
        print('BIO13_ONE_TIME_INTAKE_DISABLED payload_present=false',flush=True)
        return
    existing=_target_questions(scoremax,ids)
    batch=_batch(scoremax)
    if existing and len(existing)!=EXPECTED_COUNT:
        _fail(f'partial_target_population count={len(existing)}')
    if existing and not batch:
        _fail('target_questions_exist_without_matching_batch')

    admin=_admin(scoremax)
    token='bio13-one-time-governed-intake'
    client=_client(scoremax,admin,token)

    if not batch:
        resp=client.post(
            '/admin/import?mode=emergency',
            data={
                '_csrf_token':token,
                'intake_mode':'EMERGENCY_DIRECT',
                'source_system':'POWER_HOUSE_GOVERNED',
                'source_prompt_pack_id':PROMPT_PACK_ID,
                'source_prompt_pack_version':PROMPT_PACK_VERSION,
                'file':(io.BytesIO(raw),'BIO13_SCOREMAX_PILOT100_LIVE_BASELINE_TRANSPORT.csv'),
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        if resp.status_code!=200:
            _fail('preview_http_'+str(resp.status_code))
        batch=_batch(scoremax)
        if not batch or str(batch['status'] or '').upper()!='PREVIEWED':
            _fail('preview_batch_not_created')

    if str(batch['status'] or '').upper()=='PREVIEWED':
        resp=client.post('/admin/import/confirm',data={'_csrf_token':token,'batch_id':int(batch['id'])},follow_redirects=False)
        if resp.status_code not in {302,303}:
            _fail('confirm_http_'+str(resp.status_code))
        batch=_batch(scoremax)

    if str(batch['status'] or '').upper()!='IMPORTED':
        _fail('batch_not_imported')

    if str(batch['release_status'] or '').upper()=='NOT_RELEASED':
        _verify_batch(scoremax,batch,ids,released=False)
        resp=client.post(
            f"/admin/import/batch/{int(batch['id'])}/release-eligible",
            data={
                '_csrf_token':token,
                'attestation':ATTESTATION,
                'release_note':'Bio13 exact frozen 100 Power House-qualified pilot; one-time governed live admission.',
            },
            follow_redirects=False,
        )
        if resp.status_code not in {302,303}:
            _fail('release_http_'+str(resp.status_code))
        batch=_batch(scoremax)

    count,scored=_verify_batch(scoremax,batch,ids,released=True)
    _write_receipt(batch,scored)
    print(
        'BIO13_ONE_TIME_INTAKE_PASS '
        f'questions={count} scored={scored} released={int(batch["released_count"] or 0)} '
        f'transport_sha256={EXPECTED_CSV_SHA256} ledger_sha256={PROMPT_PACK_VERSION}',
        flush=True,
    )
