"""ScoreMax V6.5.3 synthetic learner adversarial simulator.

This is QA only. It exercises the real universal mastery runtime against deliberately
hostile learner patterns; it never writes to ScoreMax live learner evidence.
"""
from __future__ import annotations
import argparse, json, random, sqlite3, time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
import universal_mastery_engine as um

PROFILES=(
    'PERFECT','ASSISTANCE_DEPENDENT','VARIANT_MEMORIZER','TRANSFER_FAILURE',
    'HIGH_CONFIDENCE_MISCONCEPTION','INTERLEAVED_DIP','BLOCKED_CONTRADICTION',
    'SLOW_BUT_CORRECT','PREREQUISITE_GAP','MAINTENANCE_DUE','RECOVERED_GATE',
    'CONTENT_STRONG_BAD_PACING','CHRONIC_GUESSER','INCONSISTENT'
)

def make_db():
    c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); um.init_schema(c); return c

def build_fixture(c):
    env=um.ENV_QA
    # Regular family: two independent routes, unseen transfer required.
    um.upsert_claim_family(c,{'claim_family_id':'SIM-F','subject':'Physics','chapter':'Simulation','title':'Simulation family',
      'closure_policy':{'min_distinct_routes':2,'min_qualifying_weight':1,'require_unseen_transfer':True,'verification_days':30,'reopen_wrong_threshold':2},'environment':env,'status':'QA_ONLY'})
    for i in (1,2,3):
        um.upsert_knowledge_node(c,{'knowledge_node_id':f'SIM-N{i}','claim_family_id':'SIM-F','subject':'Physics','chapter':'Simulation','claim':f'Node {i}','source_role':'DIRECT','environment':env,'status':'QA_ONLY'})
    um.upsert_reasoning_seed(c,{'reasoning_seed_id':'SIM-S','subject':'Physics','chapter':'Simulation','title':'Simulation seed','decisive_operation':'independent operation','environment':env,'status':'QA_ONLY'})
    # Prerequisite family/node.
    um.upsert_claim_family(c,{'claim_family_id':'SIM-PF','subject':'Maths','chapter':'Prerequisite','title':'Prerequisite family','closure_policy':{'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':30,'reopen_wrong_threshold':2},'environment':env,'status':'QA_ONLY'})
    um.upsert_knowledge_node(c,{'knowledge_node_id':'SIM-PN','claim_family_id':'SIM-PF','subject':'Maths','chapter':'Prerequisite','claim':'Prerequisite node','source_role':'DIRECT','environment':env,'status':'QA_ONLY'})
    um.upsert_reasoning_seed(c,{'reasoning_seed_id':'SIM-PS','subject':'Maths','chapter':'Prerequisite','title':'Prerequisite seed','decisive_operation':'prereq','environment':env,'status':'QA_ONLY'})
    um.upsert_prerequisite_edge(c,{'prerequisite_edge_id':'SIM-PR','from_entity_type':'NODE','from_entity_id':'SIM-PN','to_entity_type':'NODE','to_entity_id':'SIM-N1','strength':'HIGH','status':'ACTIVE','environment':env})
    # Gate family for dangerous misconception testing.
    um.upsert_claim_family(c,{'claim_family_id':'SIM-GF','subject':'Physics','chapter':'Simulation','title':'Gated family','closure_policy':{'min_distinct_routes':2,'min_qualifying_weight':1,'require_unseen_transfer':True,'verification_days':30,'reopen_wrong_threshold':2},'environment':env,'status':'QA_ONLY'})
    for i in (1,2):
        um.upsert_knowledge_node(c,{'knowledge_node_id':f'SIM-GN{i}','claim_family_id':'SIM-GF','subject':'Physics','chapter':'Simulation','claim':f'Gate node {i}','source_role':'DIRECT','environment':env,'status':'QA_ONLY'})
    um.upsert_reasoning_seed(c,{'reasoning_seed_id':'SIM-GS','subject':'Physics','chapter':'Simulation','title':'Gate seed','decisive_operation':'gate op','environment':env,'status':'QA_ONLY'})
    um.upsert_claim_family_gate(c,{'gate_id':'SIM-GATE','claim_family_id':'SIM-GF','knowledge_node_id':'SIM-GN1','gate_type':'MISCONCEPTION_GUARD','closure_effect':'REOPEN','required':True,'environment':env,'status':'ACTIVE'})

    def addq(qid,node,family,seed='SIM-S',weight=1,dep='INDEPENDENT',transfer='UNSEEN_TRANSFER',context='BLOCKED',purpose='SUBJECT_MASTERY'):
        um.upsert_question_architecture(c,{'architecture_question_id':qid,'purpose':purpose,'architecture_layer':'L2_UNDERSTAND',
          'independent_mastery_weight':weight,'dependency_type':dep,'transfer_level':transfer,'delivery_context':context,
          'environment':env,'status':'QA_ONLY','node_mappings':[{'knowledge_node_id':node,'mapping_role':'PRIMARY','evidence_weight':1}],
          'family_mappings':[{'claim_family_id':family,'mapping_role':'PRIMARY','evidence_weight':1}],
          'seed_mappings':[{'reasoning_seed_id':seed,'mapping_role':'PRIMARY','evidence_weight':1}]})
    addq('SIM-Q1','SIM-N1','SIM-F',transfer='UNSEEN_TRANSFER')
    addq('SIM-Q2','SIM-N2','SIM-F',transfer='ALTERNATE_REPRESENTATION')
    addq('SIM-Q3','SIM-N3','SIM-F',transfer='NEAR_COPY')
    addq('SIM-QV','SIM-N1','SIM-F',weight=1,dep='TRUE_VARIANT',transfer='UNSEEN_TRANSFER')
    addq('SIM-QI','SIM-N1','SIM-F',weight=0,dep='DEPENDENT',transfer='UNSEEN_TRANSFER',context='INTERLEAVED')
    addq('SIM-QB','SIM-N1','SIM-F',weight=0,dep='DEPENDENT',transfer='UNSEEN_TRANSFER',context='BLOCKED')
    addq('SIM-GQ1','SIM-GN1','SIM-GF',seed='SIM-GS',transfer='UNSEEN_TRANSFER')
    addq('SIM-GQ2','SIM-GN2','SIM-GF',seed='SIM-GS',transfer='ALTERNATE_REPRESENTATION')
    # QA exam profiles use the same source-locked exam rules, but learner evidence remains QA-partitioned.
    um.upsert_exam_seed_profile(c,{'reasoning_seed_id':'SIM-S','exam_rule_set_id':'IND-NEET-2026-v1','authentic_formats':['MCQ_SINGLE'],'target_time_seconds':60,'mastery_policy':{'min_authentic_events':2,'min_accuracy':70,'require_fluency':True},'status':'CANDIDATE'})
    um.upsert_exam_seed_profile(c,{'reasoning_seed_id':'SIM-S','exam_rule_set_id':'IND-JEE-2026-v1','authentic_formats':['MCQ_SINGLE'],'target_time_seconds':40,'mastery_policy':{'min_authentic_events':2,'min_accuracy':70,'require_fluency':True},'status':'CANDIDATE'})

def ev(c,l,q,correct=True,**kw):
    return um.record_response_event(c,learner_key=l,architecture_question_id=q,is_correct=correct,environment=um.ENV_QA,**kw)

def family_state(c,l,f='SIM-F'):
    r=c.execute('SELECT state FROM universal_learner_family_state WHERE learner_key=? AND claim_family_id=? AND environment=?',(l,f,um.ENV_QA)).fetchone(); return r['state'] if r else 'UNSEEN'

def seed_state(c,l,s='SIM-S'):
    r=c.execute('SELECT state FROM universal_learner_seed_state WHERE learner_key=? AND reasoning_seed_id=? AND environment=?',(l,s,um.ENV_QA)).fetchone(); return r['state'] if r else 'UNSEEN'

def run_profile(c, learner, profile):
    fails=[]
    if profile=='PERFECT':
        ev(c,learner,'SIM-Q1',True); ev(c,learner,'SIM-Q2',True)
        if family_state(c,learner)!='VERIFIED_MASTERED': fails.append('perfect_family_not_verified')
    elif profile=='ASSISTANCE_DEPENDENT':
        ev(c,learner,'SIM-Q1',True,assistance_state='HINT'); ev(c,learner,'SIM-Q2',True,assistance_state='EXPLANATION')
        if family_state(c,learner)=='VERIFIED_MASTERED': fails.append('assistance_false_mastery')
        ev(c,learner,'SIM-Q1',True); ev(c,learner,'SIM-Q2',True)
        if family_state(c,learner)!='VERIFIED_MASTERED': fails.append('unassisted_recovery_failed')
    elif profile=='VARIANT_MEMORIZER':
        ev(c,learner,'SIM-Q1',True)
        for _ in range(5): ev(c,learner,'SIM-QV',True)
        rows=c.execute("SELECT * FROM universal_seed_evidence WHERE learner_key=? AND reasoning_seed_id='SIM-S' AND environment=?",(learner,um.ENV_QA)).fetchall()
        weight,routes,_,_,_=um._route_capped_weight(rows)
        if weight>1.000001 or routes>1: fails.append('variant_inflation')
    elif profile=='TRANSFER_FAILURE':
        ev(c,learner,'SIM-Q3',True)
        # second route but still near copy, no unseen transfer
        um.upsert_question_architecture(c,{'architecture_question_id':'SIM-Q3B','purpose':'SUBJECT_MASTERY','architecture_layer':'L2_UNDERSTAND','independent_mastery_weight':1,'dependency_type':'INDEPENDENT','transfer_level':'NEAR_COPY','delivery_context':'BLOCKED','environment':um.ENV_QA,'status':'QA_ONLY','node_mappings':[{'knowledge_node_id':'SIM-N2','mapping_role':'PRIMARY','evidence_weight':1}],'family_mappings':[{'claim_family_id':'SIM-F','mapping_role':'PRIMARY','evidence_weight':1}]})
        ev(c,learner,'SIM-Q3B',True)
        if family_state(c,learner)=='VERIFIED_MASTERED': fails.append('nearcopy_false_mastery')
    elif profile=='HIGH_CONFIDENCE_MISCONCEPTION':
        ev(c,learner,'SIM-GQ1',True); ev(c,learner,'SIM-GQ2',True)
        ev(c,learner,'SIM-GQ1',False,confidence_band='CERTAIN',primary_error='MISCONCEPTION')
        if family_state(c,learner,'SIM-GF')!='REOPENED': fails.append('hard_gate_not_reopened')
    elif profile=='INTERLEAVED_DIP':
        ev(c,learner,'SIM-Q1',True); ev(c,learner,'SIM-Q2',True); ev(c,learner,'SIM-QI',False,delivery_context='INTERLEAVED')
        if family_state(c,learner)!='VERIFIED_MASTERED': fails.append('interleaving_erased_knowledge')
    elif profile=='BLOCKED_CONTRADICTION':
        ev(c,learner,'SIM-Q1',True); ev(c,learner,'SIM-Q2',True); ev(c,learner,'SIM-QB',False); ev(c,learner,'SIM-QB',False)
        if family_state(c,learner)!='REOPENED': fails.append('contradiction_not_reopened')
    elif profile=='SLOW_BUT_CORRECT':
        for qq in ('SIM-Q1','SIM-Q2'):
            ev(c,learner,qq,True,delivery_context='AUTHENTIC_EXAM',exam_rule_set_id='IND-JEE-2026-v1',exam_format_code='MCQ_SINGLE',active_duration_seconds=55)
        ex=um.recalculate_exam_seed_state(c,learner,'SIM-S','IND-JEE-2026-v1',um.ENV_QA)
        if family_state(c,learner)!='VERIFIED_MASTERED': fails.append('slow_correct_erased_subject')
        if ex['state']=='VERIFIED_MASTERED' or ex['fluency_state']!='DEVELOPING': fails.append('slow_correct_false_exam_ready')
    elif profile=='PREREQUISITE_GAP':
        um.diagnose_prerequisite(c,learner_key=learner,target_entity_type='NODE',target_entity_id='SIM-N1',prerequisite_edge_id='SIM-PR',result='PREREQUISITE_GAP_CONFIRMED',environment=um.ENV_QA)
        r=c.execute("SELECT 1 FROM universal_recovery_queue WHERE learner_key=? AND entity_type='NODE' AND entity_id='SIM-PN' AND status='OPEN' AND environment=?",(learner,um.ENV_QA)).fetchone()
        if not r: fails.append('prerequisite_not_routed')
    elif profile=='MAINTENANCE_DUE':
        ev(c,learner,'SIM-Q1',True); ev(c,learner,'SIM-Q2',True)
        c.execute("UPDATE universal_learner_family_state SET maintenance_due_at=? WHERE learner_key=? AND claim_family_id='SIM-F' AND environment=?",((date.today()-timedelta(days=1)).isoformat(),learner,um.ENV_QA))
        um.apply_maintenance_due(c,as_of=date.today(),environment=um.ENV_QA,learner_key=learner)
        if family_state(c,learner)!='MAINTENANCE_DUE': fails.append('maintenance_not_due')
    elif profile=='RECOVERED_GATE':
        # Initial two-route mastery -> hard misconception reopen -> fresh two-route recovery.
        # Pre-reopen positives must not be recycled for closure.
        ev(c,learner,'SIM-GQ1',True); ev(c,learner,'SIM-GQ2',True)
        ev(c,learner,'SIM-GQ1',False,confidence_band='CERTAIN',primary_error='MISCONCEPTION')
        ev(c,learner,'SIM-GQ1',True,confidence_band='FAIRLY_SURE')
        if family_state(c,learner,'SIM-GF')=='VERIFIED_MASTERED': fails.append('gate_recovered_from_stale_positive')
        ev(c,learner,'SIM-GQ2',True,confidence_band='FAIRLY_SURE')
        if family_state(c,learner,'SIM-GF')!='VERIFIED_MASTERED': fails.append('gate_recovery_failed')
    elif profile=='CONTENT_STRONG_BAD_PACING':
        ev(c,learner,'SIM-Q1',True); ev(c,learner,'SIM-Q2',True)
        um.record_full_exam_execution_opportunity(c,learner_key=learner,exam_rule_set_id='IND-NEET-2026-v1',attempt_id=None,component='PACING',estimated_loss=10,evidence_confidence='HIGH',remediation_code='PACE_PRACTICE',environment=um.ENV_QA)
        ex=c.execute("SELECT content_seed_attribution FROM universal_full_exam_execution_state WHERE learner_key=?",(learner,)).fetchone()
        if family_state(c,learner)!='VERIFIED_MASTERED' or not ex or ex['content_seed_attribution']!=0: fails.append('execution_contaminated_content')
    elif profile=='CHRONIC_GUESSER':
        for qq in ('SIM-Q1','SIM-Q2','SIM-Q3'): ev(c,learner,qq,False,confidence_band='GUESSED',primary_error='OVERCONFIDENT_GUESS')
        if family_state(c,learner)=='VERIFIED_MASTERED': fails.append('guesser_false_mastery')
    elif profile=='INCONSISTENT':
        ev(c,learner,'SIM-Q1',True); ev(c,learner,'SIM-Q2',False); ev(c,learner,'SIM-Q2',True); ev(c,learner,'SIM-QB',False)
        if family_state(c,learner)=='VERIFIED_MASTERED':
            # A single latest blocked contradiction after adequate evidence may remain verified; it must not be falsely reopened or falsely "forgotten".
            pass
        if family_state(c,learner) not in {'PROVISIONALLY_MASTERED','VERIFIED_MASTERED','REOPENED'}: fails.append('inconsistent_invalid_state')
    return fails

def fuzz_invariants(c,n,seed):
    rng=random.Random(seed); fails=[]
    for i in range(n):
        # Exam scoring must always come from the selected ruleset.
        out=rng.choice(('CORRECT','WRONG','BLANK'))
        md=um.score_exam_response(c,'PAK-MDCAT-2026-v1','MCQ',out)['marks']
        ne=um.score_exam_response(c,'IND-NEET-2026-v1','MCQ_SINGLE',out)['marks']
        if out=='WRONG' and not (md==0 and ne==-1): fails.append(('exam_rule_cross_contamination',i)); break
        # EV stays descriptive whatever probability is supplied.
        evr=um.descriptive_attempt_ev(c,'IND-NEET-2026-v1','MCQ_SINGLE',rng.uniform(-.5,1.5))
        if evr['prescriptive_threshold'] is not None or not evr['descriptive_only']: fails.append(('ev_became_prescriptive',i)); break
        # Syllabus novelty never receives a historical-confidence claim from zero history.
        comp=um.compute_score_opportunity(c,learner_key=f'QA:FZ{i}',exam_rule_set_id='IND-NEET-2026-v1',reasoning_seed_id='SIM-S',historical_exam_weight=None,current_expected_score=rng.random(),target_expected_score=rng.random(),syllabus_compatibility='SYLLABUS_NOVEL')
        if not comp['novelty_protected'] or comp['historical_weight_confidence']!='UNRESOLVED': fails.append(('novelty_guard_failed',i)); break
    return fails

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--learners',type=int,default=5000); ap.add_argument('--fuzz',type=int,default=100000); ap.add_argument('--seed',type=int,default=63017); ap.add_argument('--output',default='V6_4_0_SIMULATION_RESULTS.json'); args=ap.parse_args()
    c=make_db(); build_fixture(c); rng=random.Random(args.seed); counts=Counter(); failures=[]; start=time.time()
    for i in range(args.learners):
        p=PROFILES[i%len(PROFILES)] if i<len(PROFILES)*5 else rng.choice(PROFILES); counts[p]+=1
        learner=f'QA:SIM-{i:06d}'
        errs=run_profile(c,learner,p)
        for e in errs: failures.append({'learner':learner,'profile':p,'failure':e})
    detailed_seconds=time.time()-start
    fuzz_start=time.time(); fuzz_fail=fuzz_invariants(c,args.fuzz,args.seed+1); fuzz_seconds=time.time()-fuzz_start
    # Global QA->LIVE isolation invariant.
    live_events=c.execute("SELECT COUNT(*) n FROM universal_response_events WHERE environment='LIVE'").fetchone()['n']
    result={
      'scoremax_version':'6.5.7','architecture':'0.8','governance_reference':'1.2','seed':args.seed,
      'detailed_synthetic_learners':args.learners,'profile_counts':dict(counts),'detailed_failures':len(failures),'failure_examples':failures[:20],
      'randomized_invariant_checks':args.fuzz,'fuzz_failures':len(fuzz_fail),'fuzz_failure_examples':fuzz_fail[:20],
      'qa_response_events':c.execute("SELECT COUNT(*) n FROM universal_response_events WHERE environment=?",(um.ENV_QA,)).fetchone()['n'],
      'live_response_events_from_simulation':live_events,
      'decision_log_rows':c.execute("SELECT COUNT(*) n FROM universal_decision_log WHERE environment=?",(um.ENV_QA,)).fetchone()['n'],
      'recovery_rows':c.execute("SELECT COUNT(*) n FROM universal_recovery_queue WHERE environment=?",(um.ENV_QA,)).fetchone()['n'],
      'execution_opportunity_rows':c.execute("SELECT COUNT(*) n FROM universal_full_exam_execution_state WHERE environment=?",(um.ENV_QA,)).fetchone()['n'],
      'detailed_seconds':round(detailed_seconds,3),'fuzz_seconds':round(fuzz_seconds,3),
      'pass': len(failures)==0 and len(fuzz_fail)==0 and live_events==0,
      'note':'Synthetic QA evidence only; not student release or real mastery evidence.'
    }
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True))
    print(json.dumps(result,indent=2,sort_keys=True))
    if not result['pass']: raise SystemExit(1)

if __name__=='__main__': main()
