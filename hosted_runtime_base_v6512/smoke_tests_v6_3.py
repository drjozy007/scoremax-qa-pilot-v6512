"""ScoreMax V6.3.0 Universal Mastery Foundation acceptance checks.

These tests exercise the v0.8 / governance v1.2 software contract without
using QA events as real learner evidence. Synthetic fixtures are explicitly QA-only.
"""
from __future__ import annotations
import json, sqlite3
from datetime import date, timedelta
import universal_mastery_engine as um

checks=[]
def ok(name, cond):
    if not cond:
        raise AssertionError(name)
    checks.append(name); print('PASS:', name)

def conn():
    c=sqlite3.connect(':memory:'); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); um.init_schema(c); return c

def base(c, prefix='T', env=um.ENV_LIVE, family_policy=None, family_weight=1.0, node_role='DIRECT', seed_weight=1.0):
    f=f'{prefix}-F'; n=f'{prefix}-N'; s=f'{prefix}-S'
    um.upsert_claim_family(c, {'claim_family_id':f,'subject':'Physics','chapter':'Pilot','title':f,'independent_weight':family_weight,
                               'closure_policy':family_policy or {'min_distinct_routes':2,'min_qualifying_weight':1,'require_unseen_transfer':True,'verification_days':90,'reopen_wrong_threshold':2},
                               'environment':env,'status':'ACTIVE'})
    um.upsert_knowledge_node(c, {'knowledge_node_id':n,'claim_family_id':f,'subject':'Physics','chapter':'Pilot','claim':n,'source_role':node_role,'environment':env,'status':'ACTIVE'})
    um.upsert_reasoning_seed(c, {'reasoning_seed_id':s,'subject':'Physics','chapter':'Pilot','title':s,'decisive_operation':'test','independent_weight':seed_weight,'environment':env,'status':'ACTIVE'})
    um.map_node_seed(c,n,s,'SUPPORTS','PRIMARY','ACTIVE')
    return f,n,s

def q(c, qid, n, f, s='', env=um.ENV_LIVE, weight=1.0, dep='INDEPENDENT', transfer='UNSEEN_TRANSFER', purpose='SUBJECT_MASTERY', context='BLOCKED', source_role='DIRECT', exam_eligible=True, seed_parent=''):
    payload={'architecture_question_id':qid,'purpose':purpose,'architecture_layer':'L2_UNDERSTAND','independent_mastery_weight':weight,
             'dependency_type':dep,'transfer_level':transfer,'delivery_context':context,'source_role':source_role,
             'exam_mastery_eligible':exam_eligible,'environment':env,'status':'ACTIVE',
             'node_mappings':[{'knowledge_node_id':n,'mapping_role':'PRIMARY','evidence_weight':1}],
             'family_mappings':[{'claim_family_id':f,'mapping_role':'PRIMARY','evidence_weight':1}]}
    if s:
        payload['seed_mappings']=[{'reasoning_seed_id':s,'mapping_role':'PRIMARY','evidence_weight':1}]
    if seed_parent: payload['parent_seed_id']=seed_parent
    um.upsert_question_architecture(c,payload)
    return qid

def event(c, learner, qid, correct=True, env=um.ENV_LIVE, **kw):
    return um.record_response_event(c,learner_key=learner,architecture_question_id=qid,is_correct=correct,environment=env,**kw)

# Contract / shape
c=conn(); st=um.runtime_status(c)
ok('contract range SM-001..SM-069', st['requirements']['range']=='SM-001..SM-069')
ok('contract count is 69', st['requirements']['count']==69)
ok('P0 count is 39', st['requirements']['p0']==39)
ok('legacy mastery remains authoritative in pilot', st['legacy_mastery_authoritative'] is True)
ok('reviewer workspace is not a forward dependency', st['reviewer_workspace_forward_dependency'] is False)
fixture=um.load_synthetic_laws_of_motion_shape_fixture(c)
ok('Laws-of-Motion QA fixture has 195 nodes', fixture['knowledge_nodes']==195)
ok('Laws-of-Motion QA fixture has 52 claim families', fixture['claim_families']==52)
ok('Laws-of-Motion QA fixture has 38 reasoning seeds', fixture['reasoning_seeds']==38)
ok('Laws-of-Motion QA fixture has 29 mandatory gates', fixture['mandatory_gates']==29)
ok('Laws-of-Motion QA fixture has 10 prerequisite controls', fixture['prerequisite_controls']==10)
ok('Laws-of-Motion QA fixture has 76 exam profiles', fixture['exam_seed_profiles']==76)
resolved=c.execute("SELECT COUNT(*) n FROM universal_knowledge_nodes n JOIN universal_claim_families f ON f.claim_family_id=n.claim_family_id WHERE n.environment=?",(um.ENV_QA,)).fetchone()['n']
ok('195/195 QA nodes resolve to a claim family', resolved==195)
try:
    um.load_synthetic_laws_of_motion_shape_fixture(c,environment=um.ENV_LIVE); rejected=False
except ValueError: rejected=True
ok('synthetic architecture fixture is rejected in LIVE', rejected)

# Source-only leakage and variant inflation
c=conn(); f,n,s=base(c,'SO',node_role='SOURCE_ONLY'); q(c,'SO-Q',n,f,s,source_role='SOURCE_ONLY',exam_eligible=False)
r=event(c,'USER:1','SO-Q',True,transfer_level='UNSEEN_TRANSFER')
ns=c.execute("SELECT * FROM universal_learner_node_state WHERE learner_key='USER:1' AND knowledge_node_id=?",(n,)).fetchone()
fs=c.execute("SELECT * FROM universal_learner_family_state WHERE learner_key='USER:1' AND claim_family_id=?",(f,)).fetchone()
ok('SOURCE_ONLY node has zero closure weight', ns['state']=='LEARNING')
ok('SOURCE_ONLY evidence cannot leak into family mastery', fs['state']=='LEARNING')

c=conn(); f,n,s=base(c,'VI',family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2})
q(c,'VI-Q1',n,f,s,weight=1,dep='INDEPENDENT',transfer='UNSEEN_TRANSFER'); q(c,'VI-Q2',n,f,s,weight=1,dep='TRUE_VARIANT',transfer='UNSEEN_TRANSFER')
event(c,'USER:2','VI-Q1',True); event(c,'USER:2','VI-Q2',True)
seed_ev=c.execute("SELECT SUM(qualifying_weight) w,COUNT(DISTINCT independence_key) routes FROM universal_seed_evidence WHERE learner_key='USER:2' AND reasoning_seed_id=?",(s,)).fetchone()
ok('dependent variant carries zero independent seed weight', round(seed_ev['w'],4)==1.0)
ok('same seed remains one independent route despite variants', seed_ev['routes']==1)

# Assistance / transfer / gates
c=conn(); f,n,s=base(c,'AS',family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2}); q(c,'AS-Q',n,f,s,transfer='UNSEEN_TRANSFER')
event(c,'USER:3','AS-Q',True,assistance_state='HINT')
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:3' AND claim_family_id=?",(f,)).fetchone()['state']
ok('assisted correctness does not close mastery', state=='LEARNING')
event(c,'USER:3','AS-Q',True,assistance_state='UNASSISTED')
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:3' AND claim_family_id=?",(f,)).fetchone()['state']
ok('later unassisted evidence can close mastery', state=='VERIFIED_MASTERED')

c=conn(); f,n,s=base(c,'TR'); q(c,'TR-Q1',n,f,'',transfer='NEAR_COPY'); q(c,'TR-Q2',n,f,'',transfer='NEAR_COPY')
event(c,'USER:4','TR-Q1',True); event(c,'USER:4','TR-Q2',True)
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:4' AND claim_family_id=?",(f,)).fetchone()['state']
ok('near-copy-only evidence remains provisional', state=='PROVISIONALLY_MASTERED')
q(c,'TR-Q3',n,f,'',transfer='UNSEEN_TRANSFER'); event(c,'USER:4','TR-Q3',True)
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:4' AND claim_family_id=?",(f,)).fetchone()['state']
ok('unseen transfer permits verified family mastery', state=='VERIFIED_MASTERED')

c=conn(); f,n,s=base(c,'GT',family_policy={'min_distinct_routes':2,'min_qualifying_weight':1,'require_unseen_transfer':True,'verification_days':90,'reopen_wrong_threshold':2})
um.upsert_claim_family_gate(c,{'gate_id':'GT-G','claim_family_id':f,'knowledge_node_id':n,'gate_type':'MISCONCEPTION_GUARD','closure_effect':'REOPEN','required':True,'environment':um.ENV_LIVE,'status':'ACTIVE'})
q(c,'GT-Q1',n,f,'',transfer='UNSEEN_TRANSFER'); q(c,'GT-Q2',n,f,'',transfer='UNSEEN_TRANSFER')
event(c,'USER:5','GT-Q1',True); event(c,'USER:5','GT-Q2',True)
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:5' AND claim_family_id=?",(f,)).fetchone()['state']
ok('family can verify after mandatory misconception gate passes', state=='VERIFIED_MASTERED')
event(c,'USER:5','GT-Q1',False,confidence_band='CERTAIN',primary_error='MISCONCEPTION')
row=c.execute("SELECT state,reopen_reason FROM universal_learner_family_state WHERE learner_key='USER:5' AND claim_family_id=?",(f,)).fetchone()
ok('high-confidence failed hard gate reopens verified family', row['state']=='REOPENED' and row['reopen_reason']=='MANDATORY_GATE_FAILED')
event(c,'USER:5','GT-Q1',True,confidence_band='FAIRLY_SURE',transfer_level='UNSEEN_TRANSFER')
row=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:5' AND claim_family_id=?",(f,)).fetchone()
ok('one fresh correction repairs gate but cannot recycle stale routes to reverify', row['state']=='PROVISIONALLY_MASTERED')
event(c,'USER:5','GT-Q2',True,confidence_band='FAIRLY_SURE',transfer_level='UNSEEN_TRANSFER')
row=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:5' AND claim_family_id=?",(f,)).fetchone()
ok('fresh post-reopen evidence can reverify after closure thresholds are re-earned', row['state']=='VERIFIED_MASTERED')

# Claude P2-01 regression: pre-reopen positive on route B must not be recycled.
c=conn(); f,n,s=base(c,'SP',family_policy={'min_distinct_routes':2,'min_qualifying_weight':2,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2})
q(c,'SP-QA',n,f,'',weight=1,dep='INDEPENDENT',transfer='UNSEEN_TRANSFER'); q(c,'SP-QB',n,f,'',weight=1,dep='INDEPENDENT',transfer='UNSEEN_TRANSFER')
event(c,'USER:SP','SP-QA',True); event(c,'USER:SP','SP-QB',True)
ok('stale-positive fixture first verifies on two routes', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:SP' AND claim_family_id=?",(f,)).fetchone()['state']=='VERIFIED_MASTERED')
event(c,'USER:SP','SP-QA',False); event(c,'USER:SP','SP-QA',False)
ok('two later contradictions reopen the family', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:SP' AND claim_family_id=?",(f,)).fetchone()['state']=='REOPENED')
event(c,'USER:SP','SP-QA',True)
ok('one fresh route cannot reverify from stale pre-reopen route B', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:SP' AND claim_family_id=?",(f,)).fetchone()['state']=='PROVISIONALLY_MASTERED')
event(c,'USER:SP','SP-QA',True)
ok('repeat of the same fresh route still cannot recycle stale route B', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:SP' AND claim_family_id=?",(f,)).fetchone()['state']=='PROVISIONALLY_MASTERED')
event(c,'USER:SP','SP-QB',True)
ok('second fresh independent route legitimately reverifies', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:SP' AND claim_family_id=?",(f,)).fetchone()['state']=='VERIFIED_MASTERED')

# AT_RISK also starts a fresh-evidence epoch until re-verification.
c=conn(); f,n,s=base(c,'AR',family_policy={'min_distinct_routes':2,'min_qualifying_weight':2,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2})
q(c,'AR-Q1',n,f,'',weight=1,dep='INDEPENDENT'); q(c,'AR-Q2',n,f,'',weight=1,dep='INDEPENDENT')
event(c,'USER:AR','AR-Q1',True); event(c,'USER:AR','AR-Q2',True); event(c,'USER:AR','AR-Q1',False,confidence_band='CERTAIN')
ok('high-confidence contradiction creates AT_RISK recovery epoch', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:AR' AND claim_family_id=?",(f,)).fetchone()['state']=='AT_RISK')
event(c,'USER:AR','AR-Q1',True)
ok('AT_RISK cannot recycle stale second route after one fresh correct', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:AR' AND claim_family_id=?",(f,)).fetchone()['state']=='PROVISIONALLY_MASTERED')
event(c,'USER:AR','AR-Q2',True)
ok('AT_RISK closes only after fresh closure thresholds are re-earned', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:AR' AND claim_family_id=?",(f,)).fetchone()['state']=='VERIFIED_MASTERED')

# MAINTENANCE_DUE likewise requires prospective reconfirmation rather than one stale-credit refresh.
c=conn(); f,n,s=base(c,'MD',family_policy={'min_distinct_routes':2,'min_qualifying_weight':2,'require_unseen_transfer':False,'verification_days':1,'reopen_wrong_threshold':2})
q(c,'MD-Q1',n,f,'',weight=1,dep='INDEPENDENT'); q(c,'MD-Q2',n,f,'',weight=1,dep='INDEPENDENT')
event(c,'USER:MD','MD-Q1',True); event(c,'USER:MD','MD-Q2',True)
c.execute("UPDATE universal_learner_family_state SET maintenance_due_at=? WHERE learner_key='USER:MD' AND claim_family_id=?",((date.today()-timedelta(days=1)).isoformat(),f)); um.apply_maintenance_due(c,as_of=date.today(),environment=um.ENV_LIVE,learner_key='USER:MD')
event(c,'USER:MD','MD-Q1',True)
ok('maintenance reconfirmation remains due until fresh policy evidence is sufficient', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:MD' AND claim_family_id=?",(f,)).fetchone()['state']=='MAINTENANCE_DUE')
event(c,'USER:MD','MD-Q2',True)
ok('maintenance reconfirmation closes after fresh policy evidence', c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:MD' AND claim_family_id=?",(f,)).fetchone()['state']=='VERIFIED_MASTERED')

# QA/LIVE partition
c=conn(); fL,nL,sL=base(c,'LIV',env=um.ENV_LIVE,family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2}); q(c,'LIV-Q',nL,fL,sL,env=um.ENV_LIVE)
fQ,nQ,sQ=base(c,'QA1',env=um.ENV_QA,family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2}); q(c,'QA1-Q',nQ,fQ,sQ,env=um.ENV_QA)
event(c,'USER:6','QA1-Q',True,env=um.ENV_QA)
live=c.execute("SELECT COUNT(*) n FROM universal_response_events WHERE learner_key='USER:6' AND environment='LIVE'").fetchone()['n']
ok('QA evidence creates zero LIVE response events', live==0)
ok('QA and LIVE evidence stores are partitioned', c.execute("SELECT COUNT(*) n FROM universal_response_events WHERE learner_key='USER:6' AND environment=?",(um.ENV_QA,)).fetchone()['n']==1)

# Retention / interleaving / reopen
c=conn(); f,n,s=base(c,'RT',family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':1,'reopen_wrong_threshold':2}); q(c,'RT-Q',n,f,s)
event(c,'USER:7','RT-Q',True)
c.execute("UPDATE universal_learner_family_state SET maintenance_due_at=? WHERE learner_key='USER:7' AND claim_family_id=?",((date.today()-timedelta(days=1)).isoformat(),f))
changed=um.apply_maintenance_due(c,as_of=date.today(),learner_key='USER:7')
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:7' AND claim_family_id=?",(f,)).fetchone()['state']
ok('retention scheduler moves verified evidence to MAINTENANCE_DUE', changed>=1 and state=='MAINTENANCE_DUE')

c=conn(); f,n,s=base(c,'IL',family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2}); q(c,'IL-Q',n,f,s); event(c,'USER:8','IL-Q',True)
q(c,'IL-Q2',n,f,s,context='INTERLEAVED',weight=0,dep='DEPENDENT'); event(c,'USER:8','IL-Q2',False,delivery_context='INTERLEAVED')
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:8' AND claim_family_id=?",(f,)).fetchone()['state']
ok('isolated interleaved failure does not erase verified knowledge', state=='VERIFIED_MASTERED')
q(c,'IL-Q3',n,f,s,context='BLOCKED',weight=0,dep='DEPENDENT'); event(c,'USER:8','IL-Q3',False); event(c,'USER:8','IL-Q3',False)
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:8' AND claim_family_id=?",(f,)).fetchone()['state']
ok('repeated contradictory blocked evidence can reopen mastery', state=='REOPENED')

# Prerequisite recovery
c=conn(); f1,n1,s1=base(c,'PR1'); f2,n2,s2=base(c,'PR2')
um.upsert_prerequisite_edge(c,{'prerequisite_edge_id':'PR-E','from_entity_type':'NODE','from_entity_id':n1,'to_entity_type':'NODE','to_entity_id':n2,'strength':'HIGH','status':'ACTIVE','environment':um.ENV_LIVE})
cands=um.prerequisite_candidates(c,'NODE',n2)
ok('prerequisite candidates are discoverable', len(cands)==1 and cands[0]['from_entity_id']==n1)
um.diagnose_prerequisite(c,learner_key='USER:9',target_entity_type='NODE',target_entity_id=n2,prerequisite_edge_id='PR-E',result='PREREQUISITE_GAP_CONFIRMED')
rec=c.execute("SELECT * FROM universal_recovery_queue WHERE learner_key='USER:9' AND entity_type='NODE' AND entity_id=? AND status='OPEN'",(n1,)).fetchone()
ok('confirmed prerequisite gap routes recovery to prerequisite entity', rec is not None and rec['cause_code']=='PREREQUISITE_GAP')

# Exam rule separation
c=conn()
ok('MDCAT wrong answer has zero penalty', um.score_exam_response(c,'PAK-MDCAT-2026-v1','MCQ','WRONG')['marks']==0)
ok('NEET wrong answer has -1 penalty', um.score_exam_response(c,'IND-NEET-2026-v1','MCQ_SINGLE','WRONG')['marks']==-1)
ok('JEE numerical correct scores +4', um.score_exam_response(c,'IND-JEE-2026-v1','NUMERICAL_VALUE','CORRECT','B')['marks']==4)
ok('JEE numerical blank scores zero', um.score_exam_response(c,'IND-JEE-2026-v1','NUMERICAL_VALUE','BLANK','B')['marks']==0)
ok('exam rules are source/version specific rather than a shared negative-marking default', um.resolve_exam_rule_set(c,'PAKISTAN','MDCAT',2026)['exam_rule_set_id'] != um.resolve_exam_rule_set(c,'INDIA','NEET',2026)['exam_rule_set_id'])

# Exam-specific readiness and fluency
c=conn(); f,n,s=base(c,'EX',family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2})
q(c,'EX-Q1',n,f,s,context='AUTHENTIC_EXAM',transfer='UNSEEN_TRANSFER'); q(c,'EX-Q2',n,f,s,context='AUTHENTIC_EXAM',transfer='UNSEEN_TRANSFER')
um.upsert_exam_seed_profile(c,{'reasoning_seed_id':s,'exam_rule_set_id':'IND-NEET-2026-v1','authentic_formats':['MCQ_SINGLE'],'target_time_seconds':60,'mastery_policy':{'min_authentic_events':2,'min_accuracy':70,'require_fluency':True},'status':'ACTIVE'})
um.upsert_exam_seed_profile(c,{'reasoning_seed_id':s,'exam_rule_set_id':'IND-JEE-2026-v1','authentic_formats':['MCQ_SINGLE'],'target_time_seconds':40,'mastery_policy':{'min_authentic_events':2,'min_accuracy':70,'require_fluency':True},'status':'ACTIVE'})
for qq in ('EX-Q1','EX-Q2'):
    event(c,'USER:10',qq,True,delivery_context='AUTHENTIC_EXAM',exam_rule_set_id='IND-NEET-2026-v1',exam_format_code='MCQ_SINGLE',active_duration_seconds=50)
neet=um.recalculate_exam_seed_state(c,'USER:10',s,'IND-NEET-2026-v1')
# JEE evidence same correctness but slower than JEE target
for qq in ('EX-Q1','EX-Q2'):
    event(c,'USER:10',qq,True,delivery_context='AUTHENTIC_EXAM',exam_rule_set_id='IND-JEE-2026-v1',exam_format_code='MCQ_SINGLE',active_duration_seconds=50)
jee=um.recalculate_exam_seed_state(c,'USER:10',s,'IND-JEE-2026-v1')
ok('same common seed can be NEET-ready', neet['state']=='VERIFIED_MASTERED')
ok('same common seed can remain JEE-developing due to fluency', jee['state']=='PROVISIONALLY_MASTERED' and jee['fluency_state']=='DEVELOPING')
subject=c.execute("SELECT state FROM universal_learner_seed_state WHERE learner_key='USER:10' AND reasoning_seed_id=?",(s,)).fetchone()['state']
ok('correct-but-slow exam evidence does not erase subject seed mastery', subject=='VERIFIED_MASTERED')

# High-confidence wrong / calibration / EV
c=conn(); f,n,s=base(c,'HC',family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2}); q(c,'HC-Q',n,f,s); event(c,'USER:11','HC-Q',True); event(c,'USER:11','HC-Q',False,confidence_band='CERTAIN',primary_error='MISCONCEPTION')
state=c.execute("SELECT state FROM universal_learner_family_state WHERE learner_key='USER:11' AND claim_family_id=?",(f,)).fetchone()['state']
ok('high-confidence wrong on verified family creates AT_RISK state', state=='AT_RISK')
cal=um.confidence_calibration(c,'USER:11')
ok('confidence analytics stay uncalibrated below sample gate', cal['calibrated'] is False and cal['descriptive_only'] is True)
ev=um.descriptive_attempt_ev(c,'IND-NEET-2026-v1','MCQ_SINGLE',0.25)
ok('attempt EV remains descriptive with no prescriptive threshold', ev['descriptive_only'] is True and ev['prescriptive_threshold'] is None)

# PYQ allocation / novelty / score opportunity
c=conn(); f,n,s1=base(c,'PY'); um.upsert_reasoning_seed(c,{'reasoning_seed_id':'PY-S2','subject':'Physics','chapter':'Pilot','title':'s2','decisive_operation':'x','environment':um.ENV_LIVE,'status':'ACTIVE'}); um.upsert_reasoning_seed(c,{'reasoning_seed_id':'PY-S3','subject':'Physics','chapter':'Pilot','title':'s3','decisive_operation':'y','environment':um.ENV_LIVE,'status':'ACTIVE'})
c.execute("INSERT INTO universal_pyq_papers(pyq_paper_id,exam_rule_set_id,exam_year,source_id,compatibility,evidence_grade,status,created_at) VALUES('P1','IND-NEET-2026-v1',2025,'SRC','CURRENT_COMPATIBLE','OFFICIAL','ACTIVE',?)",(um.utcnow(),))
c.execute("INSERT INTO universal_pyq_questions(pyq_question_id,pyq_paper_id,marks,format_code,source_locator,status,created_at) VALUES('PQ1','P1',4,'MCQ_SINGLE','Q1','ACTIVE',?)",(um.utcnow(),))
c.execute("INSERT INTO universal_pyq_seed_map(pyq_question_id,reasoning_seed_id,mapping_role,allocation_weight,compatibility,confidence) VALUES('PQ1',?,'PRIMARY',0.6,'CURRENT_COMPATIBLE','HIGH')",(s1,))
c.execute("INSERT INTO universal_pyq_seed_map(pyq_question_id,reasoning_seed_id,mapping_role,allocation_weight,compatibility,confidence) VALUES('PQ1','PY-S2','SHARED_PRIMARY',0.4,'CURRENT_COMPATIBLE','HIGH')")
c.execute("INSERT INTO universal_pyq_seed_map(pyq_question_id,reasoning_seed_id,mapping_role,allocation_weight,compatibility,confidence) VALUES('PQ1','PY-S3','SECONDARY',0,'CURRENT_COMPATIBLE','HIGH')")
alloc=um.validate_pyq_allocations(c,'PQ1')
ok('PYQ primary mark allocation sums to one with secondary zero', alloc['valid'] and alloc['primary_allocation']==1.0 and alloc['secondary_allocation']==0.0)
nov=um.compute_score_opportunity(c,learner_key='USER:12',exam_rule_set_id='IND-NEET-2026-v1',reasoning_seed_id=s1,historical_exam_weight=None,current_expected_score=.3,target_expected_score=.8,syllabus_compatibility='SYLLABUS_NOVEL')
ok('SYLLABUS_NOVEL is protected from false zero-history low-yield logic', nov['novelty_protected'] and nov['historical_weight_confidence']=='UNRESOLVED' and nov['priority_score'] is None)
out=um.compute_score_opportunity(c,learner_key='USER:12',exam_rule_set_id='IND-NEET-2026-v1',reasoning_seed_id='PY-S2',historical_exam_weight=5,current_expected_score=.3,target_expected_score=.8,syllabus_compatibility='OUTSIDE_CURRENT_SYLLABUS')
ok('outside-current-syllabus content receives no current score-opportunity priority', out['priority_score'] is None)

# Repair cost / goals / execution separation
c=conn(); cold=um.repair_cost_estimate(c,'USER:13','FAMILY','X','HIGH')
ok('repair-cost cold start uses content complexity only', cold['learner_specific'] is False and cold['source_state']=='CONTENT_COMPLEXITY' and cold['precise_minutes'] is None)
for i in range(5): c.execute("INSERT INTO universal_repair_observations(learner_key,entity_type,entity_id,complexity_band,observation_value,qualifying,observed_at) VALUES('USER:13','FAMILY','X','HIGH',?,1,?)",(1.0+i*.1,um.utcnow()))
blend=um.repair_cost_estimate(c,'USER:13','FAMILY','X','HIGH')
ok('repair cost phases learner history in only after evidence gate', blend['learner_specific'] is True and blend['observation_count']==5)
um.set_learner_goal(c,'USER:13','IND-NEET-2026-v1','AMBITIOUS',650)
goal=c.execute("SELECT * FROM universal_learner_goal_policy WHERE learner_key='USER:13'").fetchone()
ok('learner goal can change target while rank promises remain prohibited', goal['target_score_objective']==650 and goal['rank_promise_prohibited']==1)
rowid=um.record_full_exam_execution_opportunity(c,learner_key='USER:13',exam_rule_set_id='IND-NEET-2026-v1',attempt_id=1,component='PACING',estimated_loss=12,evidence_confidence='HIGH',remediation_code='PACE_PRACTICE')
exe=c.execute("SELECT * FROM universal_full_exam_execution_state WHERE id=?",(rowid,)).fetchone()
ok('full-exam execution loss has zero content-seed attribution', exe['content_seed_attribution']==0.0 and exe['execution_component']=='PACING')

# Feature flags / market source locks / growth outbox
c=conn()
ok('universal mastery is off by default', not um.feature_enabled(c,'universal_mastery_runtime'))
um.set_feature_flag(c,'universal_mastery_runtime',True,mode='PILOT')
ok('universal mastery can be enabled under a controlled pilot flag', um.feature_enabled(c,'universal_mastery_runtime'))
ready=um.market_release_ready(c,'PAKISTAN-FSC-MDCAT-v1')
ok('Pakistan adapter blocks release with missing exact authority inputs', not ready['ready'] and len(ready['missing_roles'])==4)
for role in ['FEDERAL_STANDARD','PROVINCIAL_CURRICULUM','GOVERNING_TEXTBOOK','EXAM_AUTHORITY']:
    um.register_authority_source(c,adapter_id='PAKISTAN-FSC-MDCAT-v1',authority_role=role,authority_name=role,source_id='SRC-'+role,source_version='1')
ok('Pakistan adapter becomes ready only after all required authority roles are source-locked', um.market_release_ready(c,'PAKISTAN-FSC-MDCAT-v1')['ready'])
ge=um.emit_growth_event(c,'ASSESSMENT_COMPLETED','USER:14',{'attempt_id':9})
ok('ScoreMax growth boundary writes an outbox event rather than synchronous control', bool(ge) and c.execute("SELECT status FROM universal_growth_event_outbox WHERE event_id=?",(ge,)).fetchone()['status']=='PENDING')

# Deterministic replay
c=conn(); f,n,s=base(c,'RP',family_policy={'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2}); q(c,'RP-Q',n,f,s); event(c,'USER:15','RP-Q',True)
r1=um.replay_entity_state(c,'USER:15','FAMILY',f); r2=um.replay_entity_state(c,'USER:15','FAMILY',f)
ok('fixed evidence + ruleset replay produces identical mastery state', r1['result']['state']==r2['result']['state'] and r1['result']['qualifying_weight']==r2['result']['qualifying_weight'] and r1['result']['gate']==r2['result']['gate'] and r1['input_checksum']==r2['input_checksum'])

print(f"\nV6.3.0 UNIVERSAL MASTERY FOUNDATION CHECKS PASSED: {len(checks)}")
