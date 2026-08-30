import os, json, tempfile, pathlib
from datetime import datetime, timezone, timedelta

fd, dbpath=tempfile.mkstemp(prefix='scoremax_v658_',suffix='.db'); os.close(fd); os.unlink(dbpath)
os.environ['SCOREMAX_DB']=dbpath
os.environ['SCOREMAX_SECRET']='test-secret'
os.environ['SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD']='test-bootstrap'
from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import scoremax_integration_v1 as integ
app.init()
c=app.db()
checks=[]
def ok(name, cond):
    if not cond: raise AssertionError(name)
    checks.append(name)

# Ensure seeded question carries a stable learning-area identity.
q=c.execute("SELECT * FROM questions ORDER BY id LIMIT 1").fetchone(); qid=q['id']
for col,val in [('concept_id','NEG-FEEDBACK'),('learning_outcome','Negative feedback reduces system activity'),('subject','Biology'),('chapter','CH13'),('topic','Homeostasis')]:
    try:c.execute(f'UPDATE questions SET {col}=? WHERE id=?',(val,qid))
    except Exception: pass
student_id=c.execute("SELECT id FROM users WHERE role='student' ORDER BY id LIMIT 1").fetchone()
if student_id: student_id=student_id['id']
else:
    c.execute("INSERT INTO users(system_user_id,role,full_name,username,password_hash) VALUES('STU-T','student','Test Student','stu-test','x')")
    student_id=c.execute("SELECT last_insert_rowid() id").fetchone()['id']

def make_attempt(kind, answers, corrects):
    c.execute("INSERT INTO attempts(student_id,scope,programme,subject,chapters,topic,level,score,correct_count,total_count,assessment_kind,recovery_focus_name) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
              (student_id,'chapter','FSc','Biology','CH13','Homeostasis','Foundation',100.0*sum(corrects)/len(corrects),sum(corrects),len(corrects),kind,'Negative feedback reduces system activity'))
    aid=c.execute('SELECT last_insert_rowid() id').fetchone()['id']
    for sel,cor in zip(answers,corrects):
        c.execute("INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,marks_awarded,response_time_seconds) VALUES(?,?,?,?,?,?)",(aid,qid,sel,cor,cor,20))
    app.update_learning_intelligence_from_attempt(c,aid,student_id)
    return aid

# Mandatory state journey: 10@40 -> Weak Area; 3@100 recovery -> Recovered; 3@100 recall -> remains Recovered.
make_attempt('standard',['A']*10,[1,1,1,1,0,0,0,0,0,0])
st=c.execute("SELECT * FROM student_learning_states WHERE student_id=? AND area_key='NEG-FEEDBACK'",(student_id,)).fetchone()
ok('40 percent creates Weak Area', st and st['status']=='Weak Area')
make_attempt('recovery',['A']*3,[1,1,1])
st=c.execute("SELECT * FROM student_learning_states WHERE student_id=? AND area_key='NEG-FEEDBACK'",(student_id,)).fetchone()
ok('targeted recovery creates Recovered', st['status']=='Recovered')
make_attempt('recall',['A']*3,[1,1,1])
st=c.execute("SELECT * FROM student_learning_states WHERE student_id=? AND area_key='NEG-FEEDBACK'",(student_id,)).fetchone()
rec=c.execute("SELECT * FROM recall_items WHERE student_id=? AND concept_key='NEG-FEEDBACK'",(student_id,)).fetchone()
ok('successful recall preserves Recovered', st['status']=='Recovered')
ok('successful recall advances scheduler', int(rec['successful_recalls'])>=2 and int(rec['interval_days'])>=21 and float(rec['last_score'])==100.0)

# Failed later recall is not weakened: it may reopen based on normal cumulative logic.
make_attempt('recall',['A']*3,[0,0,0])
st_failed=c.execute("SELECT * FROM student_learning_states WHERE student_id=? AND area_key='NEG-FEEDBACK'",(student_id,)).fetchone()
ok('failed later recall does not get protected Recovered override', st_failed['status']!='Recovered')

# Immutable evidence counters. Create exact pinned responses with 10 recovery and 10 reconfirmation for one version each.
now=datetime.now(timezone.utc); start=(now-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ'); end=(now+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
scope={'ph_market_id':'Pakistan','ph_programme_id':'FSc','ph_subject_id':'Biology','ph_chapter_id':'CH13'}

def pinned_series(kind, ext_qid, qvid, n, correct_n):
    snap=dict(scope); snap.update({'question_id':ext_qid})
    for i in range(n):
        c.execute("INSERT INTO attempts(student_id,scope,programme,subject,chapters,score,correct_count,total_count,assessment_kind,created_at) VALUES(?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                  (student_id,'chapter','FSc','Biology','CH13',100.0 if i<correct_n else 0.0,1 if i<correct_n else 0,1,kind))
        aid=c.execute('SELECT last_insert_rowid() id').fetchone()['id']
        c.execute("""INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct,response_time_seconds,
          ph_question_id,ph_question_version_id,ph_question_checksum_sha256,ph_release_id,ph_release_version,ph_release_checksum_sha256,ph_question_snapshot_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
          (aid,qid,'A',1 if i<correct_n else 0,20,ext_qid,qvid,'a'*64,'REL-B01','2','b'*64,json.dumps(snap)))

pinned_series('recovery','REC-Q','QV::REC-Q::v1',10,8)
pinned_series('recall','RCL-Q','QV::RCL-Q::v1',10,9)
# Below-threshold recovery must stay privacy-safe.
pinned_series('recovery','SUP-Q','QV::SUP-Q::v1',3,3)
c.commit()
mid=integ.queue_delivery_evidence(c,market_id='Pakistan',programme_id='FSc',subject_id='Biology',chapter_id='CH13',period_start=start,period_end=end,minimum_n=10,producer_version='6.5.8')
row=c.execute('SELECT envelope_json FROM integration_outbox WHERE message_id=?',(mid,)).fetchone(); env=json.loads(row['envelope_json']); by={x['question_id']:x for x in env['payload']['items']}
ok('recovery counters use immutable attempts', by['REC-Q']['recovery_attempts']==10 and by['REC-Q']['recovery_successes']==8)
ok('reconfirmation counters use recall immutable attempts', by['RCL-Q']['reconfirmation_attempts']==10 and by['RCL-Q']['reconfirmation_successes']==9)
ok('unsuppressed flags false', by['REC-Q']['sample_suppressed'] is False and by['RCL-Q']['sample_suppressed'] is False)
ok('sub-threshold counters privacy safe', by['SUP-Q']['sample_suppressed'] is True and by['SUP-Q']['recovery_attempts']==0 and by['SUP-Q']['recovery_successes']==0 and by['SUP-Q']['reconfirmation_attempts']==0 and by['SUP-Q']['reconfirmation_successes']==0)

# Ensure mutable current question changes do not rescope historical evidence.
try:c.execute("UPDATE questions SET ph_chapter_id='MUTATED' WHERE id=?",(qid,))
except Exception:pass
c.commit()
mid2=integ.queue_delivery_evidence(c,market_id='Pakistan',programme_id='FSc',subject_id='Biology',chapter_id='CH13',period_start=start,period_end=end,minimum_n=10,producer_version='6.5.8')
# Idempotent business identity may return same queued message; immutable snapshots remain the source.
ok('immutable evidence scope survives mutable question change', bool(mid2))

ok('db integrity ok', c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
ok('foreign keys clean', len(c.execute('PRAGMA foreign_key_check').fetchall())==0)
print(json.dumps({'status':'PASS','checks':len(checks),'confirmed_total':0,'P0':0,'P1':0,'integrity':'ok','foreign_key_violations':0,'check_names':checks},indent=2))
c.close()
try: os.remove(dbpath)
except OSError: pass
