"""ScoreMax V6.3 application wiring checks."""
import os, tempfile, importlib, json, threading, queue
from pathlib import Path

root=Path(tempfile.mkdtemp(prefix='scoremax_v63_app_'))
os.environ['SCOREMAX_DB']=str(root/'scoremax.db')
os.environ['SCOREMAX_SECRET']='v6.3-app-test-secret'
os.environ['SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD']='InternalTest-Only-2026!'
os.environ['SCOREMAX_UNIVERSAL_MASTERY']='1'
os.environ['SCOREMAX_ENV']='local'
os.environ['SCOREMAX_INTERNAL_FULL_ACCESS']='1'
os.environ['SCOREMAX_ENFORCE_PAYWALL']='0'

from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import universal_mastery_engine as um
app.init()
checks=[]
def ok(name,cond):
    if not cond: raise AssertionError(name)
    checks.append(name); print('PASS:',name)

c=app.db()
ok('universal schema initializes inside ScoreMax init', c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='universal_claim_families'").fetchone() is not None)
ok('V6.3 env flag enables universal mastery pilot', um.feature_enabled(c,'universal_mastery_runtime'))
st=um.runtime_status(c)
ok('runtime status reports V6.3.0 / architecture 0.8', st['scoremax_version']=='6.3.0' and st['architecture_version']=='0.8')
ok('reviewer workspace is not a universal forward dependency', st['reviewer_workspace_forward_dependency'] is False)
health=app.healthz()[0]
ok('compatibility health keeps parent marker and exposes current V6.3 descendant marker', health['version']=='6.2.8.1' and health['release_version']=='6.3.1')

# Prove the current assessment tables can shadow-feed mapped questions without inventing mappings.
student=c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,session_version) VALUES('STU-999999','student','Synthetic','synthetic@example.invalid','synthetic-user','x','active',0)").lastrowid
qrow=c.execute("SELECT * FROM questions ORDER BY id LIMIT 1").fetchone()
f='APP-F'; n='APP-N'; s='APP-S'
um.upsert_claim_family(c,{'claim_family_id':f,'subject':qrow['subject'],'chapter':qrow['chapter'],'title':'App integration family','closure_policy':{'min_distinct_routes':1,'min_qualifying_weight':1,'require_unseen_transfer':False,'verification_days':90,'reopen_wrong_threshold':2},'status':'CANDIDATE'})
um.upsert_knowledge_node(c,{'knowledge_node_id':n,'claim_family_id':f,'subject':qrow['subject'],'chapter':qrow['chapter'],'claim':'App integration node','status':'CANDIDATE'})
um.upsert_reasoning_seed(c,{'reasoning_seed_id':s,'subject':qrow['subject'],'chapter':qrow['chapter'],'title':'App integration seed','decisive_operation':'synthetic app integration','status':'CANDIDATE'})
um.upsert_question_architecture(c,{'architecture_question_id':'APP-Q','question_db_id':qrow['id'],'external_question_id':qrow['question_id'],'purpose':'SUBJECT_MASTERY','architecture_layer':'L2_UNDERSTAND','independent_mastery_weight':1,'dependency_type':'INDEPENDENT','transfer_level':'UNSEEN_TRANSFER','delivery_context':'BLOCKED','status':'CANDIDATE','node_mappings':[{'knowledge_node_id':n,'mapping_role':'PRIMARY','evidence_weight':1}],'family_mappings':[{'claim_family_id':f,'mapping_role':'PRIMARY','evidence_weight':1}],'seed_mappings':[{'reasoning_seed_id':s,'mapping_role':'PRIMARY','evidence_weight':1}]})
aid=c.execute("INSERT INTO attempts(student_id,scope,programme,subject,chapters,level,score,correct_count,total_count,assessment_kind) VALUES(?,?,?,?,?,?,?,?,?,?)",(student,'practice',qrow['programme'],qrow['subject'],qrow['chapter'],qrow['level'],100,1,1,'standard')).lastrowid
c.execute("INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,marks_awarded,question_version,confidence,response_time_seconds) VALUES(?,?,?,?,?,?,?,?)",(aid,qrow['id'],qrow['answer'],1,1,1,'',15))
cap=um.capture_scoremax_attempt(c,attempt_id=aid,assessment_session_id=None,student_id=student,meta={'programme':qrow['programme'],'subject':qrow['subject'],'assessment_kind':'standard'})
ok('mapped legacy attempt shadow-feeds universal evidence', cap['enabled'] and cap['captured']==1 and cap['skipped_unmapped']==0)
ok('shadow-fed learner receives separate universal family state', c.execute("SELECT 1 FROM universal_learner_family_state WHERE learner_key=? AND claim_family_id=?",(f'USER:{student}',f)).fetchone() is not None)
ok('assessment completion is queued to Growth Engine outbox', c.execute("SELECT 1 FROM universal_growth_event_outbox WHERE event_type='ASSESSMENT_COMPLETED' AND user_key=?",(f'USER:{student}',)).fetchone() is not None)

# Unmapped questions are skipped, not assigned fabricated nodes/seeds.
q2=c.execute("SELECT * FROM questions WHERE id<>? ORDER BY id LIMIT 1",(qrow['id'],)).fetchone()
aid2=c.execute("INSERT INTO attempts(student_id,scope,programme,subject,chapters,level,score,correct_count,total_count,assessment_kind) VALUES(?,?,?,?,?,?,?,?,?,?)",(student,'practice',q2['programme'],q2['subject'],q2['chapter'],q2['level'],0,0,1,'standard')).lastrowid
c.execute("INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,marks_awarded,question_version,confidence,response_time_seconds) VALUES(?,?,?,?,?,?,?,?)",(aid2,q2['id'],'',0,0,1,'',10))
cap2=um.capture_scoremax_attempt(c,attempt_id=aid2,assessment_session_id=None,student_id=student,meta={'programme':q2['programme'],'subject':q2['subject'],'assessment_kind':'standard'})
ok('unmapped existing questions are skipped instead of fabricating academic mappings', cap2['captured']==0 and cap2['skipped_unmapped']==1)

# Internal-live functional testing opens the full learner journey only under the explicit flag.
access=app.get_access_profile(c,student)
ok('internal-live full-access flag opens the complete learner journey', access['plan_code']=='full_access' and access['mastery_ceiling']=='Elite' and access['source']=='internal_live_full_access')

# Claude P4-01 regression: one assessment session may produce only one scored attempt.
q_submit=c.execute("SELECT * FROM questions WHERE id=?",(qrow['id'],)).fetchone()
session_id=app.create_assessment_session(c,student,'practice',None,[q_submit['id']],{'scope':'practice','programme':q_submit['programme'],'subject':q_submit['subject'],'chapters':q_submit['chapter'],'level':q_submit['level'],'assessment_kind':'standard'})
c.execute("UPDATE assessment_sessions SET saved_answers=? WHERE id=?",(json.dumps({str(q_submit['id']):q_submit['answer']}),session_id)); c.commit()
app.session.clear(); app.session.update(user_id=student,role='student',full_name='Synthetic',session_version=0)
r1=app.submit_assessment_v4(session_id)
r2=app.submit_assessment_v4(session_id)
r3=app.submit_assessment_v4(session_id)
rows=c.execute("SELECT id,assessment_session_id FROM attempts WHERE student_id=? AND assessment_session_id=? ORDER BY id",(student,session_id)).fetchall()
srow=c.execute("SELECT status,submitted_attempt_id FROM assessment_sessions WHERE id=?",(session_id,)).fetchone()
ok('repeat submit replays the existing result instead of creating duplicate attempts', len(rows)==1 and r1==r2==r3=='/result')
ok('submitted session pins the one immutable attempt id', srow['status']=='submitted' and int(srow['submitted_attempt_id'])==int(rows[0]['id']))
idx=c.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_attempts_unique_assessment_session'").fetchone()
ok('database-level unique assessment-session attempt index is present', idx is not None)

# 8-way submit race through the real route function (framework stubs only replace HTTP rendering).
race_session=app.create_assessment_session(c,student,'practice',None,[q_submit['id']],{'scope':'practice','programme':q_submit['programme'],'subject':q_submit['subject'],'chapters':q_submit['chapter'],'level':q_submit['level'],'assessment_kind':'standard'})
c.execute("UPDATE assessment_sessions SET saved_answers=? WHERE id=?",(json.dumps({str(q_submit['id']):q_submit['answer']}),race_session)); c.commit(); c.close()
race_out=queue.Queue()
def race_submit(i):
    try:
        race_out.put((i,app.submit_assessment_v4(race_session)))
    except Exception as exc:
        race_out.put((i,'ERR:'+repr(exc)))
threads=[threading.Thread(target=race_submit,args=(i,)) for i in range(8)]
[t.start() for t in threads]
[t.join() for t in threads]
race_results=[race_out.get() for _ in threads]
c=app.db()
race_attempts=c.execute("SELECT id FROM attempts WHERE student_id=? AND assessment_session_id=?",(student,race_session)).fetchall()
race_row=c.execute("SELECT status,submitted_attempt_id FROM assessment_sessions WHERE id=?",(race_session,)).fetchone()
ok('8-way concurrent submit race creates exactly one attempt', len(race_attempts)==1 and race_row['status']=='submitted')
ok('all concurrent submit callers resolve without an exception', all(result=='/result' for _,result in race_results))

# Admin-only internal status function resolves with the inherited framework stubs.
admin=c.execute("SELECT * FROM users WHERE role='admin' ORDER BY id LIMIT 1").fetchone(); c.commit(); c.close()
app.session.clear(); app.session.update(user_id=admin['id'],role='admin',full_name=admin['full_name'],session_version=int(admin['session_version'] or 0))
resp=app.universal_mastery_status()
ok('admin universal-mastery status endpoint function responds', resp['scoremax_version']=='6.3.0')

print(f'\nV6.3.0 APPLICATION WIRING CHECKS PASSED: {len(checks)}')
print('Temporary database:',root/'scoremax.db')
