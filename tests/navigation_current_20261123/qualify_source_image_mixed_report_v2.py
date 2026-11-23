"""Validate native image mixed actions without conflating POSTs and image GETs."""
import json,re,sys
from pathlib import Path

def require(value,reason):
 if not value:raise ValueError(reason)
def qualify(report,mixed):
 require(mixed.get('version')=='SM-MIXED-NATIVE-SOURCE-IMAGE-HTTP-20261123-1','EXACT_IMAGE_WORKLOAD_REQUIRED');require(not mixed['writer_errors'],'NATIVE_WRITER_FAILURE')
 for c in report['conditions']:
  s=c['successful_nav_latency'];require(c['level']==50 and c['errors']==0 and not c['timeout_censoring'] and s['count']>=400,'COMPLETE_UNCENSORED_400_SUCCESSFUL_GETS_REQUIRED');require(s['p95_ms']<1500,'MIXED_NAVIGATION_P95_1500MS_FAILED')
 require(bool(report['conditions']),'MEASUREMENT_CONDITIONS_REQUIRED')
 events=[a for a in mixed['actions'] if 'path' in a];images=[a for a in events if a.get('exact_oversized_source_image_present') is True];posts=[a for a in events if 'exact_oversized_source_image_present' not in a]
 require(len(events)==9 and len(posts)==6 and len(images)==3,'SIX_NATIVE_POSTS_AND_THREE_IMAGE_GETS_REQUIRED')
 releases=[a for a in posts if a['path']=='/api/integration/v1/power-house/content-releases'];stops=[a for a in posts if a['path']=='/api/integration/v1/power-house/question-withdrawals'];submits=[a for a in posts if re.fullmatch(r'/test/session/[1-9][0-9]*/submit',a['path'])]
 require(len(releases)==len(stops)==len(submits)==2,'EXACT_SIGNED_RELEASE_SUBMIT_STOP_AND_REPEATS_REQUIRED');require(all(a['status'] in (200,202) for a in releases+stops) and all(a['status']==302 for a in submits),'NATIVE_POST_SUCCESS_REQUIRED');require(len({a['path'] for a in submits})==1,'EXACT_REPEAT_SUBMISSION_IDENTITY_REQUIRED')
 question_path=submits[0]['path'].removesuffix('/submit');questions=[a for a in images if a['path']==question_path];results=[a for a in images if re.fullmatch(r'/result/[1-9][0-9]*',a['path'])]
 require(len(questions)==1 and len(results)==2 and len({a['path'] for a in results})==1,'EXACT_QUESTION_RESULT_AND_HISTORICAL_RESULT_IMAGE_GETS_REQUIRED');require(all(a['status']==200 and a['response_bytes']>497968 for a in images),'EXACT_ORIGINAL_OVERSIZED_IMAGE_RESPONSE_REQUIRED')
 proofs=[a for a in mixed['actions'] if 'native_writer_result' in a];require(len(proofs)==1 and len(mixed['actions'])==10,'ONE_NATIVE_WRITER_PROOF_REQUIRED');proof=proofs[0];require(proof['preexisting_protected_tables_preserved']==16,'PROTECTED_NATIVE_TABLES_CHANGED');p=proof['native_writer_result']
 for key in ('actual_signed_ingress_and_duplicate','native_activation_authorization','actual_saved_answer_submit_and_duplicate','signed_exact_withdrawal_and_duplicate','historical_attempt_preserved','historical_image_after_withdrawal'):require(p.get(key) is True,'NATIVE_RESULT_REQUIRED:'+key)
 require(p['native_attempts']==p['native_answers']==1 and p['formal_mastery_rows_created']==0,'DUPLICATE_OR_FORMAL_CREDIT_CREATED');require(p['pending_marks_awarded'] is None and p['pending_image_native_marks']==2,'PENDING_NULL_SCORE_AND_SOURCE_MARKS_REQUIRED');require(497968<p['software_image_bytes']<=2000000 and p['maximum_real_source_image_bytes']==497968,'MEASURED_IMAGE_SIZE_REQUIRED');require(p['sqlite_consistent_backup_bytes']>0,'CONSISTENT_NATIVE_BACKUP_REQUIRED');require(p['native_outbox_contract_counts']['SM_PH_CONTENT_DELIVERY_ACK_V1']==2 and p['native_outbox_contract_counts']['SM_PH_QUESTION_WITHDRAWAL_ACK_V1']==1,'NATIVE_ACK_OUTBOX_IDENTITY_REQUIRED')
 return {'status':'PASSED','signed_POSTs':6,'authenticated_original_image_GETs':3,'source_image_question_result_historical_verified':True,'native_submit_release_stop_and_backup':True,'native_peer_ACK_under_load':'PRIOR_UNCHANGED_CONTRACT_EVIDENCE_REUSED_SEPARATELY','real_bank_render_mobile':'PENDING','runtime_modified':False,'production_actions':False}
if __name__=='__main__':
 p=Path(sys.argv[1]);r=json.loads(p.read_text());m=json.loads(p.with_name(p.stem+'_mixed_actions.json').read_text());print(json.dumps(qualify(r,m)))
