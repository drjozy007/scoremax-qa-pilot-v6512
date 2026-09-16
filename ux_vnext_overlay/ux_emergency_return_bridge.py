from __future__ import annotations
from pathlib import Path

MARKER='SM-PH-EMERGENCY-RETURN-BRIDGE-20260916-1'


def _replace_once(path: Path, old: str, new: str) -> None:
    text=path.read_text(encoding='utf-8')
    n=text.count(old)
    if n!=1:
        raise SystemExit(f'EMERGENCY_RETURN_PATCH_ANCHOR_MISMATCH path={path} count={n}')
    path.write_text(text.replace(old,new,1),encoding='utf-8')


def apply_emergency_return_bridge(root: Path) -> None:
    bridge=root/'scoremax_ph_bridge_v6611d.py'
    app=root/'app.py'
    reviewer=root/'ux_content_reviewer.py'

    old="""def queue_reported_question_incident(c, question, feedback_code, category, severity, description, context):
    \"\"\"Queue one privacy-minimised incident only for an exact Power House learner projection.\"\"\"
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
      'description':_redact_free_text(description),
      'source':str(ctx.get('source') or '')[:80],
      'page_path':_safe_page_path(ctx.get('page')),
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
"""
    new="""def _emergency_direct_identity(c, question):
    keys=set(question.keys()) if hasattr(question,'keys') else set(question)
    def val(k): return question[k] if k in keys else None
    qdb=int(val('id') or 0)
    if not qdb: return None
    row=c.execute('''SELECT r.*,b.batch_code,b.source_system,b.source_prompt_pack_id,b.source_prompt_pack_version,b.payload_checksum,
                            b.intake_mode,b.status batch_status,b.release_status,b.released_count,b.row_count,b.valid_count,b.error_count,b.warning_count
                     FROM content_import_batch_rows r JOIN content_import_batches b ON b.id=r.batch_id
                     WHERE r.question_db_id=?''',(qdb,)).fetchall()
    if len(row)!=1: return None
    r=row[0]
    if str(r['intake_mode'] or '').upper()!='EMERGENCY_DIRECT' or str(r['source_system'] or '').upper()!='POWER_HOUSE_GOVERNED': return None
    if str(r['batch_status'] or '').upper()!='IMPORTED' or str(r['release_status'] or '').upper()!='RELEASED_ELIGIBLE': return None
    if int(r['valid_count'] or 0)!=int(r['row_count'] or 0) or int(r['error_count'] or 0) or int(r['warning_count'] or 0): return None
    if str(r['import_status'] or '').upper()!='IMPORTED': return None
    try: source=json.loads(r['row_json'] or '{}')
    except Exception: return None
    source_qid=str(source.get('Question ID') or '').strip()
    ph_public=str(source.get('Power House Public ID') or '').strip()
    ph_source_row=str(source.get('Power House Source Row') or '').strip()
    if not source_qid or source_qid!=str(val('question_id') or '').strip() or not ph_public or not ph_source_row: return None
    ledger=str(r['source_prompt_pack_version'] or '').strip().lower(); transport=str(r['payload_checksum'] or '').strip().lower()
    if len(ledger)!=64 or len(transport)!=64: return None
    return {
      'identity_mode':'EMERGENCY_DIRECT_GOVERNED',
      'source_question_id':source_qid,
      'power_house_public_id':ph_public,
      'power_house_source_row':ph_source_row,
      'batch_code':str(r['batch_code'] or ''),
      'transport_sha256':transport,
      'selection_ledger_sha256':ledger,
      'source_prompt_pack_id':str(r['source_prompt_pack_id'] or ''),
      'rendered_question_sha256':_sha_text(str(val('question') or '')),
    }


def queue_reported_question_incident(c, question, feedback_code, category, severity, description, context):
    \"\"\"Queue one privacy-minimised incident for exact native PH lineage or governed Emergency Direct provenance.\"\"\"
    if not question: return ''
    keys=set(question.keys()) if hasattr(question,'keys') else set(question)
    def val(k): return question[k] if k in keys else None
    code=str(feedback_code or '').strip()
    if not code: return ''
    existing=c.execute('SELECT outbox_message_id FROM ph_bridge_incident_events_v6611d WHERE feedback_code=?',(code,)).fetchone()
    if existing: return str(existing['outbox_message_id'] or '')
    native=(str(val('ph_projection_owner') or '')=='POWER_HOUSE' and all(str(val(k) or '').strip() for k in ('ph_question_id','ph_question_version_id','ph_question_checksum_sha256','ph_release_id','ph_release_version','ph_release_checksum_sha256')))
    emergency=None if native else _emergency_direct_identity(c,question)
    if not native and not emergency: return ''
    ctx=dict(context or {})
    if native:
        q_payload={
          'identity_mode':'NATIVE_POWER_HOUSE_RELEASE',
          'question_id':str(val('ph_question_id')),'question_version_id':str(val('ph_question_version_id')),
          'question_checksum_sha256':str(val('ph_question_checksum_sha256')).lower(),'release_id':str(val('ph_release_id')),
          'release_version':str(val('ph_release_version')),'release_checksum_sha256':str(val('ph_release_checksum_sha256')).lower(),
          'market_id':str(val('ph_market_id') or ''),'programme_id':str(val('ph_programme_id') or ''),
          'subject_id':str(val('ph_subject_id') or ''),'chapter_id':str(val('ph_chapter_id') or ''),
          'rendered_question_sha256':_sha_text(str(val('question') or '')),
        }
        identity_key=str(val('ph_question_version_id'))
        ph_id=str(val('ph_question_id')); ph_ver=str(val('ph_question_version_id')); ph_sha=str(val('ph_question_checksum_sha256')).lower(); rel_id=str(val('ph_release_id')); rel_ver=str(val('ph_release_version'))
    else:
        q_payload=dict(emergency)
        identity_key=emergency['power_house_public_id']+'|'+emergency['source_question_id']+'|'+emergency['power_house_source_row']
        ph_id=emergency['power_house_public_id']; ph_ver=''; ph_sha=''; rel_id=''; rel_ver=''
    payload={
      'incident_id':'SMINC::'+_sha_text(code+'|'+identity_key)[:32],
      'scoremax_feedback_code':code,'category':str(category or 'Other')[:120],
      'severity':str(severity or 'MEDIUM').upper()[:20],'description':_redact_free_text(description),
      'source':str(ctx.get('source') or '')[:80],'page_path':_safe_page_path(ctx.get('page')),
      'question':q_payload,'reporter_identity_included':False,'student_pii_included':False,'release_authority_conferred':False,
    }
    i=_INTEGRATION
    idem='content-incident::'+code+'::'+_sha_text(identity_key)[:20]
    env=i._envelope(INCIDENT,'POWER_HOUSE',idem,code,payload,RELEASE,'INTERNAL')
    msg=i._queue(c,env,code,'PILOT_FEEDBACK',code)
    c.execute('''INSERT INTO ph_bridge_incident_events_v6611d(feedback_code,question_db_id,ph_question_id,ph_question_version_id,ph_question_checksum_sha256,ph_release_id,ph_release_version,outbox_message_id,created_at)
                 VALUES(?,?,?,?,?,?,?,?,?)''',(code,int(val('id')),ph_id,ph_ver,ph_sha,rel_id,rel_ver,msg,i.utcnow()))
    return msg
"""
    _replace_once(bridge,old,new)

    old_review="""    c.execute('UPDATE questions SET review_status=?,status=?,active=?,reviewer=?,reviewed_at=? WHERE id=?',(status_map[action],status_map[action],active,reviewer,reviewed_at,qid))
    c.execute('INSERT INTO question_review_events(question_id,action,reviewer_id,reason_code,note) VALUES(?,?,?,?,?)',(qid,status_map[action],session.get('user_id'),reason,note))
    family=c.execute('SELECT review_status,active FROM question_families WHERE family_key=?',(row['family_key'] or '',)).fetchone()
    family_live=bool(family and family['review_status']=='Approved' and int(family['active'] or 0)==1)
    c.commit(); c.close()
"""
    new_review="""    c.execute('UPDATE questions SET review_status=?,status=?,active=?,reviewer=?,reviewed_at=? WHERE id=?',(status_map[action],status_map[action],active,reviewer,reviewed_at,qid))
    review_event=c.execute('INSERT INTO question_review_events(question_id,action,reviewer_id,reason_code,note) VALUES(?,?,?,?,?)',(qid,status_map[action],session.get('user_id'),reason,note))
    incident_message=''
    if action=='reject':
        incident_code=f'SMAR-{int(review_event.lastrowid)}'
        incident_context={'source':'SCOREMAX_ADMIN_REVIEW','reason_code':reason,'question_db_id':qid,'question_id':row['question_id'],'subject':row['subject'],'chapter':row['chapter'],'requested_action':'POWER_HOUSE_EXCEPTION','withdrawal_authority':'POWER_HOUSE','page':f'/admin/questions/{qid}'}
        incident_message=ph_bridge_v6611d.queue_reported_question_incident(c,row,incident_code,reason or 'ADMIN_REJECT','HIGH',(note or reason or 'ScoreMax admin rejected learner-facing question.'),incident_context)
        if not incident_message:
            c.rollback(); c.close(); flash('Reject blocked because the governed Power House return identity could not be established. Nothing was changed.','error'); return redirect(url_for('admin_question_detail',qid=qid))
    family=c.execute('SELECT review_status,active FROM question_families WHERE family_key=?',(row['family_key'] or '',)).fetchone()
    family_live=bool(family and family['review_status']=='Approved' and int(family['active'] or 0)==1)
    c.commit()
    if incident_message:
        integration_v1.dispatch_due(c,limit=20,timeout=8)
    c.close()
"""
    _replace_once(app,old_review,new_review)

    old_gate="""            if not _has_exact_ph_lineage(q):
                flash('This question does not have complete Power House lineage, so no flag was created.','error')
                return redirect(url_for('ux_content_review_question',question_id=question_id,view='reviewer'))
            label,severity=FLAG_REASONS[reason]
"""
    new_gate="""            label,severity=FLAG_REASONS[reason]
"""
    _replace_once(reviewer,old_gate,new_gate)
    reviewer_text=reviewer.read_text(encoding='utf-8').replace("flash('Power House incident handoff could not be queued. Nothing was changed.','error')","flash('Power House incident handoff could not establish governed return identity. Nothing was changed.','error')")
    reviewer.write_text(reviewer_text,encoding='utf-8')

    for path in (bridge,app,reviewer):
        text=path.read_text(encoding='utf-8')
        if path==bridge and 'EMERGENCY_DIRECT_GOVERNED' not in text: raise SystemExit('EMERGENCY_RETURN_BRIDGE_MARKER_MISSING')
    print(f'{MARKER} PASS admin_reject=true reviewer_flag=true native_lineage_preserved=true emergency_direct_governed=true',flush=True)
