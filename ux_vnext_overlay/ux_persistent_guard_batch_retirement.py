from __future__ import annotations
from pathlib import Path


def apply_persistent_guard_batch_retirement(root: Path) -> None:
    """Extend the existing post-release guard for governed batch retirement only.

    Manual Admin Reject/Retire remains unchanged and still requires per-question
    question_review_events. A batch retirement is accepted only when the exact
    sealed retirement record matches the imported batch identity and population.
    """
    guard=Path('scripts')/'scoremax_persistent_storage_guard.py'
    if not guard.is_file():
        raise SystemExit('SCOREMAX_BATCH_RETIREMENT_GUARD_SOURCE_MISSING')
    text=guard.read_text(encoding='utf-8')
    marker='SCOREMAX-PERSISTENT-GUARD-V4-BATCH-RETIREMENT-V1'
    if marker in text:
        return
    anchor="""            post_release_inactive=0
            for q in qrows:
"""
    replacement="""            post_release_inactive=0
            # SCOREMAX-PERSISTENT-GUARD-V4-BATCH-RETIREMENT-V1
            batch_retirement=None
            if _table(c,'bio13_failed_pilot_retirement_v1'):
                batch_retirement=c.execute(
                    \"SELECT * FROM bio13_failed_pilot_retirement_v1 WHERE batch_id=? ORDER BY id DESC LIMIT 1\",
                    (bid,),
                ).fetchone()
            batch_retirement_valid=bool(
                batch_retirement
                and str(batch_retirement['batch_code'] or '')==code
                and str(batch_retirement['prompt_pack_id'] or '')==str(b['source_prompt_pack_id'] or '')
                and str(batch_retirement['prompt_pack_version'] or '').lower()==str(b['source_prompt_pack_version'] or '').lower()
                and str(batch_retirement['transport_sha256'] or '').lower()==str(b['payload_checksum'] or '').lower()
                and int(batch_retirement['question_count'] or 0)==row_count
                and int(batch_retirement['active_after'])==0
                and int(batch_retirement['historical_attempts_preserved'] or 0)==1
                and str(batch_retirement['policy'] or '')=='SCOREMAX-BIO13-FAILED-PILOT-RETIREMENT-V1'
            )
            if batch_retirement and not batch_retirement_valid:
                print('SCOREMAX_BATCH_RETIREMENT_EVIDENCE_MISMATCH '+json.dumps({
                    'batch_id':bid,
                    'batch_code_equal':str(batch_retirement['batch_code'] or '')==code,
                    'prompt_pack_id_equal':str(batch_retirement['prompt_pack_id'] or '')==str(b['source_prompt_pack_id'] or ''),
                    'prompt_pack_version_equal':str(batch_retirement['prompt_pack_version'] or '').lower()==str(b['source_prompt_pack_version'] or '').lower(),
                    'transport_sha_equal':str(batch_retirement['transport_sha256'] or '').lower()==str(b['payload_checksum'] or '').lower(),
                    'question_count_equal':int(batch_retirement['question_count'] or 0)==row_count,
                    'active_after_zero':int(batch_retirement['active_after'])==0,
                    'history_preserved':int(batch_retirement['historical_attempts_preserved'] or 0)==1,
                    'policy_equal':str(batch_retirement['policy'] or '')=='SCOREMAX-BIO13-FAILED-PILOT-RETIREMENT-V1',
                },sort_keys=True,separators=(',',':')),flush=True)
            elif not batch_retirement:
                print('SCOREMAX_BATCH_RETIREMENT_EVIDENCE_MISSING batch_id='+str(bid),flush=True)
            for q in qrows:
"""
    if "int(batch_retirement['active_after'] or -1)==0" in replacement:
        raise SystemExit('SCOREMAX_BATCH_RETIREMENT_ZERO_REGRESSION')
    if anchor not in text:
        raise SystemExit('SCOREMAX_BATCH_RETIREMENT_GUARD_ANCHOR_MISSING')
    text=text.replace(anchor,replacement,1)

    # Exact sealed batch-retirement evidence must be evaluated before the generic
    # per-question Admin Reject/Retire audit rule. Otherwise a governed batch
    # retirement can be rejected by a rule that only applies to manual actions.
    anchor2="""                if status in {'Rejected','Retired'} and review_status==status and environment=='PRODUCTION':
                    if not _table(c,'question_review_events'):
                        fail(f'emergency_postrelease_audit_table_missing batch={code}')
"""
    replacement2="""                if batch_retirement_valid and environment=='PRODUCTION':
                    # Exact governed batch retirement is authoritative for this
                    # historical pilot population. Manual Admin Reject/Retire rules
                    # remain unchanged for every other question.
                    if status=='Withdrawn' and review_status=='Approved':
                        post_release_inactive+=1
                        continue
                    if status=='Retired' and review_status=='Retired' and int(q['scoremax_ready'] or 0)==0:
                        post_release_inactive+=1
                        continue
                if status in {'Rejected','Retired'} and review_status==status and environment=='PRODUCTION':
                    if not _table(c,'question_review_events'):
                        fail(f'emergency_postrelease_audit_table_missing batch={code}')
"""
    if anchor2 not in text:
        raise SystemExit('SCOREMAX_BATCH_RETIREMENT_GUARD_PRECEDENCE_ANCHOR_MISSING')
    text=text.replace(anchor2,replacement2,1)
    if text.find('if batch_retirement_valid and environment==\'PRODUCTION\':') > text.find("if status in {'Rejected','Retired'} and review_status==status and environment=='PRODUCTION':"):
        raise SystemExit('SCOREMAX_BATCH_RETIREMENT_PRECEDENCE_REGRESSION')
    compile(text,str(guard),'exec')
    guard.write_text(text,encoding='utf-8')
    print(
        'SCOREMAX_PERSISTENT_GUARD_BATCH_RETIREMENT_PASS '
        'exact_batch_evidence=true manual_question_events_unchanged=true '
        'batch_retirement_precedes_manual_audit=true legacy_withdrawn_compatibility=true '
        'canonical_retired_state=true zero_value_safe=true diagnostic_on_mismatch=true '
        'historical_attempts_preserved=true release_authority=false',
        flush=True,
    )
