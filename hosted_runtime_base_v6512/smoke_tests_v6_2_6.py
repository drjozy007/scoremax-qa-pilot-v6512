"""ScoreMax V6.2.6 Pre-Pilot Assurance & Mastery Laboratory regression suite."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs


def main():
    flask,request=install_framework_stubs()
    temp=Path(tempfile.mkdtemp(prefix='scoremax_v626_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db')
    os.environ['SCOREMAX_ENV']='local'
    import app
    lab=app.mastery_lab
    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)

    app.init(); app.init(); c=app.db(); c.commit()
    expected_tables={
      'mastery_lab_feature_controls','mastery_lab_batches','mastery_lab_questions','mastery_lab_question_relations',
      'mastery_lab_policies','mastery_lab_synthetic_profiles','mastery_lab_runs','mastery_lab_responses',
      'mastery_lab_evidence','mastery_lab_state_history','mastery_lab_recovery_needs','mastery_lab_gate_results',
      'mastery_lab_blockers','mastery_lab_audit_events'}
    tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    ok('Mastery Laboratory schema is idempotent and complete',expected_tables<=tables)
    control=c.execute("SELECT * FROM mastery_lab_feature_controls WHERE feature_code='mastery_laboratory'").fetchone()
    ok('Mastery Laboratory launches in QA_ONLY state',control and control['state']=='QA_ONLY')
    ok('all thirteen explicit mastery states are preserved',lab.MASTERY_STATES==[
      'UNASSESSED','PROVISIONAL_FOUNDATION','VERIFIED_FOUNDATION','PROVISIONAL_EXAM_READY','VERIFIED_EXAM_READY',
      'PROVISIONAL_ADVANCED','VERIFIED_ADVANCED','PROVISIONAL_DISTINCTION','VERIFIED_DISTINCTION','VERIFICATION_DUE',
      'RECOVERY_REQUIRED','RECOVERY_IN_PROGRESS','RECONFIRMED'])
    ok('all required question families have distinct canonical identities',{
      'standard_mcq','four_statement_selection','true_false','cloze','diagram_data_stimulus','matching','ordering',
      'multiple_response','numerical_interpretation','constructed_response','misconception_probe','adaptive_recovery'}<=lab.SUPPORTED_FAMILIES)
    ok('all evidence identity relationships are explicit',lab.RELATION_TYPES=={
      'independent_seed','true_variant','scaffold','shared_stimulus_pair','integrated_question','recovery_item','reconfirmation_item'})

    sample=lab.sample_candidate_corpus()
    result=lab.import_candidate_batch(c,sample['questions'],filename='technical_sample.json',file_type='json',imported_by=1)
    ok('technical corpus imports atomically into QA sandbox',result['ok'] and result['imported_count']>=15)
    batch_id=result['batch_id']
    flags=c.execute("SELECT DISTINCT content_environment,student_release_status,bank_approval_status,mastery_validity FROM mastery_lab_questions WHERE batch_id=?",(batch_id,)).fetchall()
    ok('every candidate receives all four non-release flags',len(flags)==1 and dict(flags[0])=={
      'content_environment':'QA_SANDBOX_ONLY','student_release_status':'NOT_STUDENT_RELEASED',
      'bank_approval_status':'NOT_BANK_APPROVED','mastery_validity':'NOT_VALID_FOR_REAL_MASTERY'})
    ok('candidate import never writes to live questions',c.execute("SELECT COUNT(*) n FROM questions q JOIN mastery_lab_questions mlq ON q.question_id=mlq.external_question_id WHERE mlq.batch_id=?",(batch_id,)).fetchone()['n']==0)
    relation_types={r['relation_type'] for r in c.execute("SELECT * FROM mastery_lab_questions WHERE batch_id=?",(batch_id,))}
    ok('seed variant scaffold stimulus integrated recovery and reconfirmation identities survive import',lab.RELATION_TYPES<=relation_types)
    unresolved=c.execute("SELECT COUNT(*) n FROM mastery_lab_question_relations WHERE batch_id=? AND related_external_question_id<>'' AND related_question_id IS NULL",(batch_id,)).fetchone()['n']
    ok('in-batch parent relationships resolve without false unresolved warnings',unresolved==0)

    duplicate_blocked=False
    try: lab.import_candidate_batch(c,sample['questions'],filename='duplicate.json',file_type='json',imported_by=1)
    except ValueError as exc: duplicate_blocked='already imported' in str(exc)
    ok('exact retry is idempotently rejected rather than duplicated',duplicate_blocked)

    before_batches=c.execute('SELECT COUNT(*) n FROM mastery_lab_batches').fetchone()['n']
    invalid=[{'question_id':'BAD-1','family_type':'standard_mcq','programme':'','subject':'Biology','chapter':'Chapter 1','question':'Bad row'}]
    invalid_result=lab.import_candidate_batch(c,invalid,filename='invalid.json',file_type='json',imported_by=1)
    ok('structural errors reject the whole batch before database insertion',not invalid_result['ok'] and c.execute('SELECT COUNT(*) n FROM mastery_lab_batches').fetchone()['n']==before_batches)

    # Forced mid-import failure proves transaction rollback, followed by a clean retry.
    c.execute("""CREATE TRIGGER mastery_lab_forced_failure BEFORE INSERT ON mastery_lab_questions
      WHEN NEW.external_question_id='FAIL-ROW' BEGIN SELECT RAISE(ABORT,'forced laboratory failure'); END"""); c.commit()
    failure_rows=[]
    for qid in ('SAFE-ROW','FAIL-ROW'):
        failure_rows.append({'question_id':qid,'family_type':'standard_mcq','relation_type':'independent_seed','seed_key':qid,
          'programme':'FSc Part 1','subject':'Biology','chapter':'Failure QA','learning_outcome_ids':['LO-F'],
          'concept_ids':['C-F'],'mastery_level':'Foundation','question':'Atomic import test',
          'options':[{'id':'A','text':'Correct'},{'id':'B','text':'Wrong'}],
          'marking_config':{'marks':1,'correct_option_ids':['A']},'source_lineage':{'source':'test'}})
    before_questions=c.execute('SELECT COUNT(*) n FROM mastery_lab_questions').fetchone()['n']; before_batches=c.execute('SELECT COUNT(*) n FROM mastery_lab_batches').fetchone()['n']
    failed=False
    try: lab.import_candidate_batch(c,failure_rows,filename='forced_failure.json',file_type='json',imported_by=1)
    except Exception as exc: failed='forced laboratory failure' in str(exc)
    ok('forced mid-import failure raises and rolls back',failed and c.execute('SELECT COUNT(*) n FROM mastery_lab_questions').fetchone()['n']==before_questions and c.execute('SELECT COUNT(*) n FROM mastery_lab_batches').fetchone()['n']==before_batches)
    c.execute('DROP TRIGGER mastery_lab_forced_failure'); c.commit()
    retry=lab.import_candidate_batch(c,failure_rows,filename='forced_failure_retry.json',file_type='json',imported_by=1)
    ok('clean retry after rollback imports exactly once',retry['ok'] and retry['imported_count']==2)

    # The real Chapter 1 scale target is exercised with 322 valid candidate rows.
    corpus322=[]
    for i in range(322):
        corpus322.append({'question_id':f'CH1-CAND-{i+1:03d}','family_type':'standard_mcq','relation_type':'independent_seed',
          'seed_key':f'CH1-SEED-{i+1:03d}','programme':'FSc Part 1','subject':'Biology','chapter':'Chapter 1',
          'topic':f'Topic {i%8+1}','learning_outcome_ids':[f'LO-{i%12+1}'],'concept_ids':[f'CONCEPT-{i%20+1}'],
          'mastery_level':['Foundation','Exam Ready','Advanced','Distinction'][i%4],
          'mastery_ceiling':['Foundation','Exam Ready','Advanced','Distinction'][i%4],
          'cognitive_demand':['Recall','Understanding','Application','Integrated analysis'][i%4],
          'question':f'Governed Chapter 1 candidate {i+1}',
          'options':[{'id':'A','text':'Correct'},{'id':'B','text':'Incorrect'}],
          'marking_config':{'marks':1,'correct_option_ids':['A']},
          'source_lineage':{'source':'Power House','candidate_no':i+1}})
    scaled=lab.import_candidate_batch(c,corpus322,filename='chapter1_322.json',file_type='json',imported_by=1,source_reference='Chapter 1 candidate corpus')
    ok('Mastery Laboratory accepts the 322-candidate Chapter 1 scale milestone',scaled['ok'] and scaled['imported_count']==322 and c.execute('SELECT COUNT(*) n FROM mastery_lab_questions WHERE batch_id=?',(scaled['batch_id'],)).fetchone()['n']==322)

    # Family-specific deterministic scoring.
    family_rows={r['family_type']:r for r in c.execute('SELECT * FROM mastery_lab_questions WHERE batch_id=?',(batch_id,)).fetchall()}
    for family,row in family_rows.items():
        manual=float(lab.safe_json(row['marking_config_json'],{}).get('marks') or 1) if family=='constructed_response' else None
        correct=lab.score_lab_response(row,lab._correct_response_for(row),manual_score=manual)
        incorrect=lab.score_lab_response(row,lab._incorrect_response_for(row),manual_score=0 if family=='constructed_response' else None)
        ok(f'{family} recognises governed correct and incorrect responses',correct['is_correct'] and not incorrect['is_correct'])
    mr=family_rows['multiple_response']; partial=lab.score_lab_response(mr,['A'])
    ok('multiple response supports bounded partial credit',0<partial['awarded_marks']<partial['max_marks'] and not partial['is_correct'])
    cloze=family_rows['cloze']; partial_cloze=lab.score_lab_response(cloze,['alpha','wrong'])
    ok('cloze scores individual blanks without collapsing to MCQ',0<partial_cloze['awarded_marks']<partial_cloze['max_marks'])
    matching=family_rows['matching']; partial_match=lab.score_lab_response(matching,{'1':'A','2':'wrong'})
    ok('matching scores governed pairs independently',0<partial_match['awarded_marks']<partial_match['max_marks'])
    ordering=family_rows['ordering']; partial_order=lab.score_lab_response(ordering,['A','C','B'])
    ok('ordering preserves sequence-specific scoring',0<partial_order['awarded_marks']<partial_order['max_marks'])
    numerical=family_rows['numerical_interpretation']; within=lab.score_lab_response(numerical,10.05); outside=lab.score_lab_response(numerical,10.5)
    ok('numerical interpretation applies governed tolerance',within['is_correct'] and not outside['is_correct'])
    misconception=family_rows['misconception_probe']; mis=lab.score_lab_response(misconception,'B')
    ok('misconception probe preserves diagnostic identity',not mis['is_correct'] and 'MIS-QA-1' in mis['diagnostic_tags'])
    constructed=family_rows['constructed_response']; auto=lab.score_lab_response(constructed,'alpha beta gamma')
    ok('constructed response uses its rubric rather than MCQ scoring',auto['is_correct'] and auto['awarded_marks']==auto['max_marks'])

    # Related evidence is capped by seed/stimulus identity.
    seed_a=c.execute("SELECT * FROM mastery_lab_questions WHERE batch_id=? AND seed_key='SEED-A' ORDER BY id",(batch_id,)).fetchall()
    mock=[]
    for q in seed_a:
        mock.append({'question_id':q['id'],'score_fraction':1,'identity_weight':lab.identity_weight(q),'identity_cluster_key':lab.identity_cluster(q),
          'manual_review_required':0,'response_time_seconds':20,'confidence':'high'})
    capped=lab._effective_clustered_rows(seed_a,mock)
    ok('seed variant and scaffold evidence is capped to one effective unit per cluster',round(sum(x['effective_weight'] for x in capped),6)<=1.0)
    stim=c.execute("SELECT * FROM mastery_lab_questions WHERE batch_id=? AND stimulus_group_key='STIM-1' ORDER BY id",(batch_id,)).fetchall()
    stim_mock=[{'question_id':q['id'],'score_fraction':1,'identity_weight':lab.identity_weight(q),'identity_cluster_key':lab.identity_cluster(q),'manual_review_required':0,'response_time_seconds':20,'confidence':'high'} for q in stim]
    ok('shared-stimulus pairs cannot manufacture independent breadth',round(sum(x['effective_weight'] for x in lab._effective_clustered_rows(stim,stim_mock)),6)<=1.0)

    # State-machine unit challenges.
    good={'effective_weight':8,'weighted_accuracy':.9,'independent_units':6,'concept_coverage':1,'lo_coverage':1,'independence_ratio':.9,'application_ratio':.6,'integrated_units':2}
    bad={'effective_weight':6,'weighted_accuracy':.3,'independent_units':3,'concept_coverage':.3,'lo_coverage':.3,'independence_ratio':.5,'application_ratio':.1,'integrated_units':0}
    ok('state machine creates provisional mastery before independent confirmation',lab.transition_mastery_state('UNASSESSED','Foundation',good,event_type='INITIAL')[0]=='PROVISIONAL_FOUNDATION')
    ok('state machine verifies only after independent confirmation',lab.transition_mastery_state('PROVISIONAL_FOUNDATION','Foundation',good,event_type='INDEPENDENT_CONFIRMATION',independent_confirmation=True)[0]=='VERIFIED_FOUNDATION')
    ok('state machine separates Verification Due from downgrade',lab.transition_mastery_state('VERIFIED_FOUNDATION','Foundation',good,event_type='TIME_ELAPSED',verification_due=True)[0]=='VERIFICATION_DUE')
    ok('recovery/scaffold evidence remains Recovery In Progress',lab.transition_mastery_state('RECOVERY_REQUIRED','Foundation',good,event_type='RECOVERY',recovery_item_only=True)[0]=='RECOVERY_IN_PROGRESS')
    ok('successful delayed evidence produces Reconfirmed',lab.transition_mastery_state('VERIFICATION_DUE','Foundation',good,event_type='RECONFIRMATION')[0]=='RECONFIRMED')
    ok('failed delayed evidence produces Recovery Required',lab.transition_mastery_state('VERIFICATION_DUE','Foundation',bad,event_type='RECONFIRMATION')[0]=='RECOVERY_REQUIRED')

    before_attempts=c.execute('SELECT COUNT(*) n FROM attempts').fetchone()['n']; before_mastery=c.execute('SELECT COUNT(*) n FROM mastery_records').fetchone()['n']
    runs={}
    for profile in lab.SYNTHETIC_PROFILES:
        runs[profile]=lab.simulate_profile(c,batch_id,profile,created_by=1)
    ok('all seven synthetic student histories replay successfully',len(runs)==7 and all(x['run_id'] for x in runs.values()))
    ok('repeated variants do not inflate mastery',not runs['REPEATED_VARIANTS_ONLY']['final_state'].startswith('VERIFIED_') and runs['REPEATED_VARIANTS_ONLY']['provisional_level']=='')
    ok('scaffold success followed by independent failure requires recovery',runs['SCAFFOLD_SUCCESS_FAILED_INDEPENDENT']['final_state']=='RECOVERY_REQUIRED')
    ok('delayed forgetting removes apparent mastery and requires recovery',runs['DELAYED_FORGETTING']['final_state']=='RECOVERY_REQUIRED')
    ok('genuine broad Distinction evidence is independently confirmed and reconfirmed',runs['GENUINE_DISTINCTION']['final_state']=='RECONFIRMED' and runs['GENUINE_DISTINCTION']['provisional_level']=='Distinction')
    ok('broad performance with one missing concept produces an explicit next action',runs['BROAD_ONE_MISSING_CONCEPT']['next_action'] and c.execute('SELECT COUNT(*) n FROM mastery_lab_recovery_needs WHERE run_id=?',(runs['BROAD_ONE_MISSING_CONCEPT']['run_id'],)).fetchone()['n']>0)
    ok('every synthetic decision has a human-readable rationale and next action',all(x['decision_summary'] and x['next_action'] and x['rationale']['phases'] for x in runs.values()))
    ok('concept and LO evidence is written to an isolated ledger',c.execute("SELECT COUNT(*) n FROM mastery_lab_evidence WHERE run_id=? AND evidence_type='CONCEPT'",(runs['GENUINE_DISTINCTION']['run_id'],)).fetchone()['n']>0 and c.execute("SELECT COUNT(*) n FROM mastery_lab_evidence WHERE run_id=? AND evidence_type='LEARNING_OUTCOME'",(runs['GENUINE_DISTINCTION']['run_id'],)).fetchone()['n']>0)
    ok('identity-capped evidence is explicitly documented',all(lab.safe_json(r['metadata_json'],{}).get('identity_cap_applied') for r in c.execute('SELECT * FROM mastery_lab_evidence WHERE run_id=?',(runs['GENUINE_DISTINCTION']['run_id'],)).fetchall()))
    ok('synthetic runs never create live attempts or mastery records',c.execute('SELECT COUNT(*) n FROM attempts').fetchone()['n']==before_attempts and c.execute('SELECT COUNT(*) n FROM mastery_records').fetchone()['n']==before_mastery)

    gates=lab.evaluate_all_gates(c,batch_id,runs['GENUINE_DISTINCTION']['run_id'])
    ok('Content Admission gate passes the clean technical corpus',gates['GATE_1']['status']=='PASS')
    ok('Assessment Execution gate covers every imported family',gates['GATE_2']['status']=='PASS' and set(gates['GATE_2']['families_tested'])==set(family_rows))
    ok('Mastery and Study Plan gate confirms no live-evidence leakage',gates['GATE_3']['status']=='PASS')
    ok('Security Privacy and Isolation gate confirms separate QA tables',gates['GATE_4']['status']=='PASS')
    ok('Release Acceptance gate passes only after prior gate evidence',gates['GATE_5']['status']=='PASS')

    # A live-ID collision is blocked rather than silently admitted.
    collision=[{'question_id':'BIO001','family_type':'standard_mcq','relation_type':'independent_seed','seed_key':'COLLIDE',
      'programme':'FSc Part 1','subject':'Biology','chapter':'Collision QA','learning_outcome_ids':['LO-X'],'concept_ids':['C-X'],
      'mastery_level':'Foundation','question':'Collision test','options':[{'id':'A','text':'Correct'},{'id':'B','text':'Wrong'}],
      'marking_config':{'marks':1,'correct_option_ids':['A']},'source_lineage':{'source':'test'}}]
    collision_batch=lab.import_candidate_batch(c,collision,filename='collision.json',file_type='json',imported_by=1)['batch_id']
    isolation=lab.evaluate_security_isolation_gate(c,collision_batch)
    ok('live question-ID collision becomes a Gate 4 blocker',isolation['status']=='BLOCKED' and c.execute("SELECT COUNT(*) n FROM mastery_lab_blockers WHERE batch_id=? AND gate_code='GATE_4' AND status='OPEN'",(collision_batch,)).fetchone()['n']==1)

    # Warnings remain visible rather than being discarded.
    warning_row=[{'question_id':'WARN-1','family_type':'standard_mcq','relation_type':'true_variant','seed_key':'OUTSIDE-SEED',
      'parent_question_id':'OUTSIDE-Q','programme':'FSc Part 1','subject':'Biology','chapter':'Warnings QA',
      'mastery_level':'Foundation','question':'Warning preservation test','options':[{'id':'A','text':'Correct'},{'id':'B','text':'Wrong'}],
      'marking_config':{'marks':1,'correct_option_ids':['A']},'source_lineage':{'source':'test'}}]
    warning_import=lab.import_candidate_batch(c,warning_row,filename='warnings.json',file_type='json',imported_by=1)
    warning_gate=lab.evaluate_content_admission_gate(c,warning_import['batch_id'])
    ok('missing concept LO and outside-parent warnings remain unresolved and visible',warning_import['warning_count']>=2 and warning_gate['status']=='PASS_WITH_WARNINGS' and len(warning_gate['warnings'])>=3)

    # Admin-only route and package/UI contracts.
    c.close(); flask.session.clear(); flask.session.update(user_id=999,role='student',session_version=0,_csrf_token='s')
    request.method='GET'; request.endpoint='admin_mastery_lab'; request.path='/admin/mastery-lab'; request.form={}; request.args={}; request.files={}; request.referrer=''
    denied=app.admin_mastery_lab()
    ok('students cannot open the admin Mastery Laboratory',denied=='/login')
    c=app.db(); admin=c.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']; c.close()
    flask.session.clear(); flask.session.update(user_id=admin,role='admin',session_version=0,_csrf_token='a')
    admin_page=app.admin_mastery_lab()
    ok('admins receive the Mastery Laboratory control centre',admin_page[1][0]=='admin_mastery_lab.html')
    source=(ROOT/'mastery_lab_engine.py').read_text(); base=(ROOT/'templates/base.html').read_text(); lab_page=(ROOT/'templates/admin_mastery_lab.html').read_text(); batch_page=(ROOT/'templates/admin_mastery_lab_batch.html').read_text()
    ok('Mastery Laboratory is not exposed in student More or mobile navigation',base.count('Mastery Laboratory')==1 and base.index('Mastery Laboratory')>base.index("session.get('role')=='admin'"))
    ok('QA sandbox engine contains no write to live questions attempts or mastery records','INSERT INTO questions' not in source and 'INSERT INTO attempts' not in source and 'INSERT INTO mastery_records' not in source)
    ok('admin UI displays all four non-release boundaries',all(x in lab_page for x in ['release_flags.content_environment','release_flags.student_release_status','release_flags.bank_approval_status','release_flags.mastery_validity']))
    ok('batch UI exposes five assurance gates and blocker register','Five assurance gates' in batch_page and 'Blocker register' in batch_page)
    ok('release health marker is 6.2.6',app.healthz()[0]['version'] in {'6.2.6','6.2.7','6.2.7.1','6.2.7.2','6.2.8','6.2.8.1'})
    print(f'\nV6.2.6 PRE-PILOT ASSURANCE / MASTERY LAB CHECKS PASSED: {len(checks)}')

if __name__=='__main__': main()
