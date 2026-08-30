from __future__ import annotations
import os,tempfile,time
from pathlib import Path
from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
root=Path(__file__).resolve().parent
tmp=Path(tempfile.mkdtemp(prefix='scoremax_v659_qasandbox_'))
os.environ['SCOREMAX_DB']=str(tmp/'scoremax.db')
os.environ['SCOREMAX_SECRET']='qa-scale-secret'
os.environ['SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD']='qa-scale-bootstrap'
import app
app.init(); c=app.db(); lab=app.mastery_lab
corpus=[]
for i in range(1500):
    corpus.append({'question_id':f'QA1500-{i+1:04d}','family_type':'standard_mcq','relation_type':'independent_seed',
      'seed_key':f'QA1500-SEED-{i+1:04d}','programme':'FSc Part 1','subject':'Biology','chapter':'QA Qualification Only',
      'topic':f'Topic {i%25+1}','learning_outcome_ids':[f'LO-{i%30+1}'],'concept_ids':[f'CONCEPT-{i%80+1}'],
      'mastery_level':['Foundation','Exam Ready','Advanced','Distinction'][i%4],
      'mastery_ceiling':['Foundation','Exam Ready','Advanced','Distinction'][i%4],
      'cognitive_demand':['Recall','Understanding','Application','Integrated analysis'][i%4],
      'question':f'QA sandbox qualification candidate {i+1}',
      'options':[{'id':'A','text':'Correct'},{'id':'B','text':'Incorrect'}],
      'marking_config':{'marks':1,'correct_option_ids':['A']},
      'source_lineage':{'source':'QA qualification fixture','opaque_source_id':f'SRC::{i+1:04d}'}})
t=time.perf_counter(); r=lab.import_candidate_batch(c,corpus,filename='qa_1500.json',file_type='json',imported_by=1,source_reference='QA_SANDBOX_ONLY scale qualification'); elapsed=time.perf_counter()-t
if not r['ok'] or r['imported_count']!=1500: raise AssertionError(r)
bid=r['batch_id']
count=c.execute('SELECT COUNT(*) n FROM mastery_lab_questions WHERE batch_id=?',(bid,)).fetchone()['n']
flags=[dict(x) for x in c.execute('SELECT DISTINCT content_environment,student_release_status,bank_approval_status,mastery_validity FROM mastery_lab_questions WHERE batch_id=?',(bid,)).fetchall()]
expected={'content_environment':'QA_SANDBOX_ONLY','student_release_status':'NOT_STUDENT_RELEASED','bank_approval_status':'NOT_BANK_APPROVED','mastery_validity':'NOT_VALID_FOR_REAL_MASTERY'}
live=c.execute("SELECT COUNT(*) n FROM questions q JOIN mastery_lab_questions mlq ON q.question_id=mlq.external_question_id WHERE mlq.batch_id=?",(bid,)).fetchone()['n']
attempts=c.execute('SELECT COUNT(*) n FROM attempts').fetchone()['n']
evidence=c.execute('SELECT COUNT(*) n FROM mastery_lab_evidence').fetchone()['n']
if count!=1500 or flags!=[expected] or live!=0 or attempts!=0 or evidence!=0: raise AssertionError({'count':count,'flags':flags,'live':live,'attempts':attempts,'evidence':evidence})
# Exact replay is rejected idempotently rather than duplicated.
replay=False
try: lab.import_candidate_batch(c,corpus,filename='qa_1500_replay.json',file_type='json',imported_by=1,source_reference='QA_SANDBOX_ONLY scale qualification')
except ValueError as exc: replay='already imported' in str(exc)
if not replay: raise AssertionError('exact QA replay did not collapse')
if c.execute('SELECT COUNT(*) n FROM mastery_lab_questions WHERE batch_id=?',(bid,)).fetchone()['n']!=1500: raise AssertionError('replay changed row count')
integ=c.execute('PRAGMA integrity_check').fetchone()[0]; fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
if integ!='ok' or fk!=0: raise AssertionError((integ,fk))
print(f'PASS: QA_SANDBOX_ONLY 1500 imported={count} elapsed={elapsed:.3f}s live_questions={live} attempts={attempts} mastery_evidence={evidence}')
print('PASS: QA 1500 exact replay/idempotency preserved one batch without duplicate candidate rows')
print('PASS: QA 1500 isolation flags exact; product activation/learner delivery/real mastery are not available from sandbox storage')
print('PASS: SQLite integrity ok; foreign_key_violations=0')
c.close()
