from __future__ import annotations
from pathlib import Path

MARKER='SM-PH-EMERGENCY-RETURN-RECOVERY-20260916-1'

def _replace_once(path:Path,old:str,new:str):
    s=path.read_text(encoding='utf-8'); n=s.count(old)
    if n!=1: raise SystemExit(f'EMERGENCY_RECOVERY_PATCH_ANCHOR_MISMATCH path={path} count={n}')
    path.write_text(s.replace(old,new,1),encoding='utf-8')

def apply_emergency_return_recovery(root:Path)->None:
    bridge=root/'scoremax_ph_bridge_v6611d.py'
    prod=root/'scoremax_production.py'
    guard=Path('scripts')/'scoremax_persistent_storage_guard.py'

    s=bridge.read_text(encoding='utf-8')
    if 'def reconcile_governed_emergency_rejections' not in s:
        s += '''\n\ndef reconcile_governed_emergency_rejections(c):\n    \"\"\"Queue one deterministic PH incident for governed Emergency Direct questions already locally Rejected.\"\"\"\n    if not _table_exists(c,'question_review_events'):\n        return 0\n    rows=c.execute(\"\"\"SELECT q.* FROM questions q JOIN content_import_batches b ON b.id=q.source_import_batch_id\n                       WHERE b.intake_mode='EMERGENCY_DIRECT' AND b.source_system='POWER_HOUSE_GOVERNED'\n                         AND q.status='Rejected' AND q.review_status='Rejected' AND COALESCE(q.active,0)=0 ORDER BY q.id\"\"\").fetchall()\n    queued=0\n    for q in rows:\n        ev=c.execute(\"SELECT * FROM question_review_events WHERE question_id=? AND action='Rejected' ORDER BY id DESC LIMIT 1\",(q['id'],)).fetchone()\n        if not ev: continue\n        code=f\"SMAR-RECOVER-{int(q['id'])}-{int(ev['id'])}\"\n        if c.execute('SELECT 1 FROM ph_bridge_incident_events_v6611d WHERE feedback_code=?',(code,)).fetchone(): continue\n        context={'source':'SCOREMAX_ADMIN_REVIEW_RECOVERY','reason_code':str(ev['reason_code'] or ''),'question_db_id':int(q['id']),'question_id':str(q['question_id'] or ''),'subject':str(q['subject'] or ''),'chapter':str(q['chapter'] or ''),'requested_action':'POWER_HOUSE_EXCEPTION','withdrawal_authority':'POWER_HOUSE','page':f\"/admin/questions/{int(q['id'])}\"}\n        msg=queue_reported_question_incident(c,q,code,str(ev['reason_code'] or 'ADMIN_REJECT'),'HIGH',str(ev['note'] or ev['reason_code'] or 'ScoreMax admin rejected learner-facing question.'),context)\n        if not msg: raise RuntimeError(f'EMERGENCY_REJECTION_RECONCILIATION_IDENTITY_FAILED question_db_id={int(q[\"id\"])}')\n        queued+=1\n    if queued: c.commit()\n    return queued\n\n# SM-PH-EMERGENCY-RETURN-RECOVERY-20260916-1\n'''
        bridge.write_text(s,encoding='utf-8')

    old="install_catalogue_browser(scoremax.app)\napplication=scoremax.app"
    new="""install_catalogue_browser(scoremax.app)\nimport scoremax_ph_bridge_v6611d as _emergency_return_bridge\nimport scoremax_integration_v1 as _emergency_return_integration\n_emergency_return_conn=scoremax.db()\ntry:\n    _emergency_return_queued=_emergency_return_bridge.reconcile_governed_emergency_rejections(_emergency_return_conn)\n    if _emergency_return_queued:\n        _emergency_return_integration.dispatch_due(_emergency_return_conn,limit=20,timeout=8)\nfinally:\n    _emergency_return_conn.close()\nprint(f'SCOREMAX_EMERGENCY_RETURN_RECOVERY queued={_emergency_return_queued}',flush=True)\napplication=scoremax.app"""
    _replace_once(prod,old,new)

    old="""    result={'questions':len(non_ph),'batches':0,'released':0,'candidate':0,'batch_codes':[]}\n"""
    new="""    result={'questions':len(non_ph),'batches':0,'released':0,'candidate':0,'pending_exception':0,'batch_codes':[]}\n"""
    _replace_once(guard,old,new)

    old="""        elif release_status=='RELEASED_ELIGIBLE':\n            if not str(b['release_attested_at'] or '').strip() or not b['release_attested_by'] or not str(b['released_at'] or '').strip(): fail(f'emergency_release_attestation_missing batch={code}')\n            if released_count<1 or released_count>row_count or active!=released_count: fail(f'emergency_released_count_mismatch batch={code}')\n            release_backup=c.execute('SELECT * FROM pilot_backups WHERE reason=? ORDER BY id DESC LIMIT 1',(f'Automatic backup before emergency release {code}',)).fetchone()\n            _verify_backup_row(release_backup,'prerelease')\n            for q in qrows:\n                if int(q['active'] or 0)==1:\n                    if str(q['status'] or '')!='Approved' or str(q['review_status'] or '')!='Approved' or str(q['content_environment'] or '')!='PRODUCTION' or int(q['scoremax_ready'] or 0)!=1: fail(f'emergency_released_question_state_invalid batch={code}')\n                elif str(q['content_environment'] or '')!='CANDIDATE': fail(f'emergency_excluded_question_environment_invalid batch={code}')\n            result['released']+=released_count; result['candidate']+=row_count-released_count\n"""
    new="""        elif release_status=='RELEASED_ELIGIBLE':\n            if not str(b['release_attested_at'] or '').strip() or not b['release_attested_by'] or not str(b['released_at'] or '').strip(): fail(f'emergency_release_attestation_missing batch={code}')\n            if released_count<1 or released_count>row_count: fail(f'emergency_released_count_mismatch batch={code}')\n            if not _table(c,'question_review_events'): fail(f'emergency_review_event_table_missing batch={code}')\n            pending_exception=0\n            release_backup=c.execute('SELECT * FROM pilot_backups WHERE reason=? ORDER BY id DESC LIMIT 1',(f'Automatic backup before emergency release {code}',)).fetchone()\n            _verify_backup_row(release_backup,'prerelease')\n            for q in qrows:\n                if int(q['active'] or 0)==1:\n                    if str(q['status'] or '')!='Approved' or str(q['review_status'] or '')!='Approved' or str(q['content_environment'] or '')!='PRODUCTION' or int(q['scoremax_ready'] or 0)!=1: fail(f'emergency_released_question_state_invalid batch={code}')\n                elif str(q['status'] or '')=='Rejected' and str(q['review_status'] or '')=='Rejected' and str(q['content_environment'] or '')=='PRODUCTION':\n                    ev=c.execute(\"SELECT 1 FROM question_review_events WHERE question_id=? AND action='Rejected' ORDER BY id DESC LIMIT 1\",(q['id'],)).fetchone()\n                    if not ev: fail(f'emergency_rejected_question_without_audit_event batch={code} question={q[\"question_id\"]}')\n                    pending_exception+=1\n                elif str(q['content_environment'] or '')!='CANDIDATE': fail(f'emergency_excluded_question_environment_invalid batch={code}')\n            if active+pending_exception!=released_count: fail(f'emergency_released_count_mismatch batch={code} active={active} pending_exception={pending_exception} released={released_count}')\n            result['released']+=active; result['pending_exception']+=pending_exception; result['candidate']+=row_count-released_count\n"""
    _replace_once(guard,old,new)

    for p in (bridge,prod,guard):
        text=p.read_text(encoding='utf-8')
        if p==bridge and MARKER not in text: raise SystemExit('EMERGENCY_RETURN_RECOVERY_MARKER_MISSING')
    print(f'{MARKER} PASS pending_rejection_guard=true startup_reconciliation=true',flush=True)
