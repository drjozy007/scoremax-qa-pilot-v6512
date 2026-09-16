from __future__ import annotations

from pathlib import Path


def apply_persistent_guard_postrelease_state(root: Path) -> None:
    """Teach persistent qualification about governed post-release deactivation.

    ``content_import_batches.released_count`` is immutable historical evidence of the
    release event. A later explicit Admin Reject/Retire must reduce learner-live
    inventory without rewriting that historical release count. The guard therefore
    requires a matching question_review_events audit record for every post-release
    inactive question and reports historical release separately from current live.
    """
    guard=Path('scripts')/'scoremax_persistent_storage_guard.py'
    if not guard.is_file():
        raise SystemExit('SCOREMAX_PERSISTENT_GUARD_SOURCE_MISSING')
    text=guard.read_text(encoding='utf-8')
    marker='SCOREMAX-PERSISTENT-GUARD-V4-POSTRELEASE-STATE-V1'
    if marker in text:
        return

    old_result="result={'questions':len(non_ph),'batches':0,'released':0,'candidate':0,'batch_codes':[]}"
    new_result=("result={'questions':len(non_ph),'batches':0,'released':0,'historical_released':0,"
                "'post_release_inactive':0,'candidate':0,'batch_codes':[]}")
    if old_result not in text:
        raise SystemExit('SCOREMAX_PERSISTENT_GUARD_RESULT_ANCHOR_MISSING')
    text=text.replace(old_result,new_result,1)

    old="""        elif release_status=='RELEASED_ELIGIBLE':
            if not str(b['release_attested_at'] or '').strip() or not b['release_attested_by'] or not str(b['released_at'] or '').strip(): fail(f'emergency_release_attestation_missing batch={code}')
            if released_count<1 or released_count>row_count or active!=released_count: fail(f'emergency_released_count_mismatch batch={code}')
            release_backup=c.execute('SELECT * FROM pilot_backups WHERE reason=? ORDER BY id DESC LIMIT 1',(f'Automatic backup before emergency release {code}',)).fetchone()
            _verify_backup_row(release_backup,'prerelease')
            for q in qrows:
                if int(q['active'] or 0)==1:
                    if str(q['status'] or '')!='Approved' or str(q['review_status'] or '')!='Approved' or str(q['content_environment'] or '')!='PRODUCTION' or int(q['scoremax_ready'] or 0)!=1: fail(f'emergency_released_question_state_invalid batch={code}')
                elif str(q['content_environment'] or '')!='CANDIDATE': fail(f'emergency_excluded_question_environment_invalid batch={code}')
            result['released']+=released_count; result['candidate']+=row_count-released_count
"""
    new="""        elif release_status=='RELEASED_ELIGIBLE':
            # SCOREMAX-PERSISTENT-GUARD-V4-POSTRELEASE-STATE-V1
            if not str(b['release_attested_at'] or '').strip() or not b['release_attested_by'] or not str(b['released_at'] or '').strip(): fail(f'emergency_release_attestation_missing batch={code}')
            if released_count<1 or released_count>row_count or active>released_count: fail(f'emergency_released_count_mismatch batch={code}')
            release_backup=c.execute('SELECT * FROM pilot_backups WHERE reason=? ORDER BY id DESC LIMIT 1',(f'Automatic backup before emergency release {code}',)).fetchone()
            _verify_backup_row(release_backup,'prerelease')
            post_release_inactive=0
            for q in qrows:
                if int(q['active'] or 0)==1:
                    if str(q['status'] or '')!='Approved' or str(q['review_status'] or '')!='Approved' or str(q['content_environment'] or '')!='PRODUCTION' or int(q['scoremax_ready'] or 0)!=1: fail(f'emergency_released_question_state_invalid batch={code}')
                    continue
                status=str(q['status'] or '')
                review_status=str(q['review_status'] or '')
                environment=str(q['content_environment'] or '')
                if status in {'Rejected','Retired'} and review_status==status and environment=='PRODUCTION':
                    if not _table(c,'question_review_events'):
                        fail(f'emergency_postrelease_audit_table_missing batch={code}')
                    event=c.execute(
                        "SELECT 1 FROM question_review_events WHERE question_id=? AND action=? ORDER BY id DESC LIMIT 1",
                        (q['id'],status),
                    ).fetchone()
                    if not event:
                        fail(f'emergency_postrelease_audit_missing batch={code} question={q[\"question_id\"]}')
                    post_release_inactive+=1
                    continue
                if environment=='CANDIDATE':
                    continue
                fail(f'emergency_inactive_question_state_invalid batch={code} question={q[\"question_id\"]} status={status} review={review_status} env={environment}')
            if active+post_release_inactive>released_count:
                fail(f'emergency_postrelease_population_invalid batch={code}')
            result['historical_released']+=released_count
            result['released']+=active
            result['post_release_inactive']+=post_release_inactive
            result['candidate']+=row_count-released_count
"""
    if old not in text:
        raise SystemExit('SCOREMAX_PERSISTENT_GUARD_RELEASE_ANCHOR_MISSING')
    text=text.replace(old,new,1)
    compile(text,str(guard),'exec')
    guard.write_text(text,encoding='utf-8')
    print(
        'SCOREMAX_PERSISTENT_GUARD_POSTRELEASE_STATE_PASS '
        'historical_release_preserved=true current_live_separate=true '
        'rejected_requires_audit_event=true retired_requires_audit_event=true '
        'release_authority_unchanged=true',
        flush=True,
    )
