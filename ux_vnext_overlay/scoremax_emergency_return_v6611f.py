from __future__ import annotations

import hashlib
import json
from pathlib import Path

CONTRACT='SM_PH_CONTENT_INCIDENT_V1'
IDENTITY_MODE='GOVERNED_EMERGENCY_DIRECT'
PRODUCER_VERSION='6.6.11F'
MARKER='SM-GOVERNED-EMERGENCY-RETURN-V6611F-1'


def _norm(value) -> str:
    return ' '.join(str(value or '').strip().split())


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _safe_json(value, default):
    try: return json.loads(value or '')
    except Exception: return default


def _is_hex64(value) -> bool:
    v=str(value or '').strip().lower()
    return len(v)==64 and all(ch in '0123456789abcdef' for ch in v)


def governed_emergency_provenance(c, q) -> dict | None:
    """Return exact governed Emergency Direct provenance or None for non-emergency rows.

    Raises on an apparent governed-emergency row whose immutable evidence is incomplete
    or inconsistent.  That makes a rejection fail closed instead of becoming an
    untracked local academic decision.
    """
    bid=int(q['source_import_batch_id'] or 0) if 'source_import_batch_id' in q.keys() else 0
    if bid<=0:
        return None
    b=c.execute('SELECT * FROM content_import_batches WHERE id=?',(bid,)).fetchone()
    if not b:
        raise RuntimeError('SM_EMERGENCY_RETURN_BATCH_MISSING')
    mode=str(b['intake_mode'] or '').upper()
    source=str(b['source_system'] or '').upper()
    if mode!='EMERGENCY_DIRECT' or source!='POWER_HOUSE_GOVERNED':
        return None
    code=str(b['batch_code'] or '').strip()
    if str(b['status'] or '').upper()!='IMPORTED': raise RuntimeError('SM_EMERGENCY_RETURN_BATCH_NOT_IMPORTED')
    if str(b['release_status'] or '').upper()!='RELEASED_ELIGIBLE': raise RuntimeError('SM_EMERGENCY_RETURN_BATCH_NOT_RELEASED')
    if int(b['error_count'] or 0)!=0 or int(b['warning_count'] or 0)!=0: raise RuntimeError('SM_EMERGENCY_RETURN_VALIDATION_NOT_CLEAN')
    if int(b['released_count'] or 0)<1: raise RuntimeError('SM_EMERGENCY_RETURN_RELEASE_COUNT_INVALID')
    prompt_id=str(b['source_prompt_pack_id'] or '').strip()
    prompt_version=str(b['source_prompt_pack_version'] or '').strip().lower()
    payload_sha=str(b['payload_checksum'] or '').strip().lower()
    if not prompt_id or not _is_hex64(prompt_version) or not _is_hex64(payload_sha):
        raise RuntimeError('SM_EMERGENCY_RETURN_BATCH_IDENTITY_INCOMPLETE')
    source_path=Path(str(b['source_file_path'] or '')).resolve()
    if not source_path.is_file(): raise RuntimeError('SM_EMERGENCY_RETURN_SOURCE_FILE_MISSING')
    if hashlib.sha256(source_path.read_bytes()).hexdigest()!=payload_sha:
        raise RuntimeError('SM_EMERGENCY_RETURN_SOURCE_CHECKSUM_MISMATCH')
    qid=int(q['id'])
    external=str(q['question_id'] or '').strip()
    if not external: raise RuntimeError('SM_EMERGENCY_RETURN_EXTERNAL_ID_MISSING')
    rows=c.execute('SELECT * FROM content_import_batch_rows WHERE batch_id=? AND question_db_id=?',(bid,qid)).fetchall()
    if len(rows)!=1: raise RuntimeError(f'SM_EMERGENCY_RETURN_ROW_BINDING_COUNT={len(rows)}')
    r=rows[0]
    if str(r['import_status'] or '').upper()!='IMPORTED' or str(r['question_id'] or '')!=external:
        raise RuntimeError('SM_EMERGENCY_RETURN_ROW_BINDING_MISMATCH')
    if _safe_json(r['errors_json'],['invalid'])!=[] or _safe_json(r['warnings_json'],['invalid'])!=[]:
        raise RuntimeError('SM_EMERGENCY_RETURN_ROW_VALIDATION_NOT_CLEAN')
    return {
      'identity_mode':IDENTITY_MODE,
      'source_question_id':external,
      'question_id':external,
      'scoremax_question_db_id':qid,
      'scoremax_import_batch_id':bid,
      'scoremax_batch_code':code,
      'source_system':'POWER_HOUSE_GOVERNED',
      'intake_mode':'EMERGENCY_DIRECT',
      'source_prompt_pack_id':prompt_id,
      'source_prompt_pack_version':prompt_version,
      'payload_checksum_sha256':payload_sha,
    }


def queue_admin_rejection(c, q, *, reason: str, note: str, reviewer_id=None) -> str | None:
    provenance=governed_emergency_provenance(c,q)
    if provenance is None:
        return None
    reason_n=_norm(reason)
    note_n=_norm(note)[:3000]
    version=int(q['question_version'] or 1) if 'question_version' in q.keys() else 1
    external=provenance['source_question_id']
    stable_material='|'.join([external,str(version),reason_n.casefold(),note_n.casefold()])
    stable=_sha_text(stable_material)
    feedback_code='ADMREJ-'+stable[:16].upper()
    incident_id='SM-ADM-REJECT-'+stable[:24].upper()
    description=(reason_n + ('. '+note_n if note_n else '')).strip()
    payload={
      'incident_id':incident_id,
      'scoremax_feedback_code':feedback_code,
      'category':reason_n or 'Admin rejection',
      'severity':'HIGH' if reason_n in {'Incorrect answer/key','Factual/scientific issue','Incorrect LO/mapping','Outside syllabus'} else 'MEDIUM',
      'description':description,
      'page_path':f"/admin/questions/{int(q['id'])}",
      'requested_action':'POWER_HOUSE_EXCEPTION',
      'withdrawal_authority':'POWER_HOUSE',
      'scoremax_academic_authority':False,
      'local_action':'REJECTED_INACTIVE_OPERATIONAL_HOLD',
      'reporter_identity_included':False,
      'student_pii_included':False,
      'release_authority_conferred':False,
      'question':provenance,
    }
    import scoremax_integration_v1 as integration
    idem=f'governed-emergency-admin-reject:{stable}'
    business={'incident_id':incident_id,'source_question_id':external,'identity_mode':IDENTITY_MODE}
    envelope=integration._envelope(
        CONTRACT,'POWER_HOUSE',idem,business,payload,
        producer_version=PRODUCER_VERSION,data_classification='INTERNAL',
    )
    return integration._queue(c,envelope,idem,'QUESTION_ADMIN_REJECTION',str(int(q['id'])))


def dispatch_return_lane(c, *, limit: int = 20, timeout: int = 8):
    import scoremax_integration_v1 as integration
    return integration.dispatch_due(c,limit=limit,timeout=timeout)
