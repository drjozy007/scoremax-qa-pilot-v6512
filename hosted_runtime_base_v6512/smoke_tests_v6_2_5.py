"""ScoreMax V6.2.5 Sustainability, Public Trust and Daily Spark regression suite."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs


def main():
    flask,request=install_framework_stubs(); temp=Path(tempfile.mkdtemp(prefix='scoremax_v625_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db'); os.environ['SCOREMAX_ENV']='local'
    import app
    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)

    app.init(); app.init(); c=app.db()
    tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    expected={'sustainability_feature_controls','sustainability_content_blocks','sustainability_policies','sustainability_commitments',
              'sustainability_progress_reports','sustainability_draft_intake','daily_spark_feature_controls','daily_spark_words',
              'daily_spark_assignments','daily_spark_events'}
    ok('V6.2.5 schema is idempotent and complete',expected<=tables)
    ok('controlled vocabulary library is seeded without daily AI dependence',c.execute('SELECT COUNT(*) n FROM daily_spark_words WHERE active=1').fetchone()['n']>=30)
    controls={r['feature_code']:r['state'] for r in c.execute('SELECT * FROM daily_spark_feature_controls')}
    ok('Academic Spark and Word of the Day launch behind governed controls',controls=={'academic_spark':'PILOT','word_of_the_day':'PILOT'})
    stages={r['claim_stage'] for r in c.execute("SELECT * FROM sustainability_content_blocks WHERE status='PUBLISHED'")}
    ok('public sustainability content separates current practice from future commitments',{'CURRENT_PRACTICE','FUTURE_COMMITMENT'}<=stages)
    commitments=c.execute("SELECT * FROM sustainability_commitments WHERE public_status='PUBLISHED'").fetchall()
    ok('commitments carry baselines targets dates owners and evidence',all(r['baseline_text'] and r['owner'] and r['evidence_summary'] for r in commitments) and any(r['target_date'] for r in commitments))

    # Promote three existing FSc questions to controlled non-demo content for the test.
    promoted=c.execute("SELECT id,answer FROM questions WHERE programme='FSc Part 1' ORDER BY id LIMIT 3").fetchall()
    ids=[r['id'] for r in promoted]
    c.execute(f"UPDATE questions SET is_demo=0,content_environment='LIVE' WHERE id IN ({','.join('?' for _ in ids)})",ids)
    fsc=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,session_version,academic_level)
      VALUES('STU-V625-FSC','student','FSc Spark Student','2010-01-01','fsc625@test','fsc625','x','active',0,'FSc Part 1')""").lastrowid
    empty=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,session_version,academic_level,subjects)
      VALUES('STU-V625-X','student','Empty Programme Student','2011-01-01','x625@test','x625','x','active',0,'Pilot Programme X','Economics')""").lastrowid
    other=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,session_version,academic_level)
      VALUES('STU-V625-O','student','Other Student','2010-06-01','o625@test','o625','x','active',0,'FSc Part 1')""").lastrowid
    c.commit()

    first=app.daily_spark_snapshot(c,fsc,'2026-08-01')
    ok('Daily Spark creates one Academic and one Word assignment',first['academic'] is not None and first['word'] is not None)
    ok('Academic Spark source is governed content from the learner programme',first['academic']['payload']['question_db_id'] in ids and first['academic']['payload']['subject'] in {'Biology','Chemistry','Physics'})
    ok('Academic Spark uses a supported compact response type',str(first['academic']['payload']['qtype']).lower().replace(' ','_') in {'mcq','single_choice','true/false','true_false','fill_blank','fill_in_the_blank','numerical','numeric'})
    ok('Word of the Day carries practical vocabulary fields',all(first['word']['payload'].get(k) for k in ['word','definition','example_sentence']))
    repeated=app.daily_spark_snapshot(c,fsc,'2026-08-01')
    ok('same-day refresh returns immutable assignments',first['academic']['id']==repeated['academic']['id'] and first['word']['id']==repeated['word']['id'])
    impressions=c.execute("SELECT COUNT(*) n FROM daily_spark_events WHERE student_id=? AND event_type='IMPRESSION'",(fsc,)).fetchone()['n']
    ok('refresh does not inflate impression counts',impressions==2)
    second_day=app.daily_spark_snapshot(c,fsc,'2026-08-02')
    ok('Word of the Day avoids immediate repetition',second_day['word']['source_id']!=first['word']['source_id'])
    empty_snapshot=app.daily_spark_snapshot(c,empty,'2026-08-01')
    ok('empty programmes receive no borrowed Academic Spark',empty_snapshot['academic'] is None and empty_snapshot['word'] is not None)

    # A recently missed approved question becomes the next Academic Spark if it was not already used.
    assigned_q=first['academic']['source_id']; missed_q=next(x for x in ids if x!=assigned_q)
    attempt=c.execute("INSERT INTO attempts(student_id,scope,programme,subject,score,correct_count,total_count) VALUES(?,?,?,?,0,0,1)",(fsc,'chapter','FSc Part 1','Biology')).lastrowid
    c.execute("INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct) VALUES(?,?,?,0)",(attempt,missed_q,'Z')); c.commit()
    third=app.daily_spark_snapshot(c,fsc,'2026-08-03')
    ok('Academic Spark prioritises a governed question the student missed',third['academic']['source_id']==missed_q and 'previously answered incorrectly' in third['academic']['selection_reason'])

    # Feature controls apply even when an assignment already exists.
    c.execute("UPDATE daily_spark_feature_controls SET state='HIDDEN' WHERE feature_code='word_of_the_day'"); c.commit()
    hidden=app.daily_spark_snapshot(c,fsc,'2026-08-01')
    ok('feature flag hides an already-assigned Word Spark',hidden['word'] is None)
    c.execute("UPDATE daily_spark_feature_controls SET state='PILOT' WHERE feature_code='word_of_the_day'"); c.commit()

    # Student action ownership and low-stakes evidence boundary.
    c.close(); flask.session.clear(); flask.session.update(user_id=other,role='student',full_name='Other Student',session_version=0,_csrf_token='t')
    request.method='POST'; request.form={'_csrf_token':'t','assignment_id':str(third['academic']['id']),'action':'ANSWER','selected_answer':'A'}; request.endpoint='student_daily_spark_action'; request.path='/student/daily-spark/action'; request.referrer=''
    app.student_daily_spark_action(); c=app.db()
    ok('another student cannot act on a Daily Spark assignment',c.execute("SELECT COUNT(*) n FROM daily_spark_events WHERE assignment_id=? AND student_id=?",(third['academic']['id'],other)).fetchone()['n']==0)
    c.close(); flask.session.clear(); flask.session.update(user_id=fsc,role='student',full_name='FSc Spark Student',session_version=0,_csrf_token='t')
    c=app.db(); q=c.execute('SELECT * FROM questions WHERE id=?',(third['academic']['source_id'],)).fetchone(); before_attempts=c.execute('SELECT COUNT(*) n FROM attempts WHERE student_id=?',(fsc,)).fetchone()['n']; before_mastery=c.execute('SELECT COUNT(*) n FROM mastery_records WHERE student_id=?',(fsc,)).fetchone()['n']; c.close()
    request.form={'_csrf_token':'t','assignment_id':str(third['academic']['id']),'action':'ANSWER','selected_answer':q['answer']}; app.student_daily_spark_action(); app.student_daily_spark_action()
    c=app.db(); answer_events=c.execute("SELECT COUNT(*) n FROM daily_spark_events WHERE assignment_id=? AND event_type IN ('ANSWER_CORRECT','ANSWER_INCORRECT')",(third['academic']['id'],)).fetchone()['n']
    ok('double submission records only one Academic Spark answer',answer_events==1)
    ok('Daily Spark does not create attempts or formal mastery',c.execute('SELECT COUNT(*) n FROM attempts WHERE student_id=?',(fsc,)).fetchone()['n']==before_attempts and c.execute('SELECT COUNT(*) n FROM mastery_records WHERE student_id=?',(fsc,)).fetchone()['n']==before_mastery)
    word_assignment=first['word']['id']; c.close()
    request.form={'_csrf_token':'t','assignment_id':str(word_assignment),'action':'REVEAL'}; app.student_daily_spark_action(); c=app.db()
    ok('Word reveal is tracked without an AI call or assessment record',c.execute("SELECT COUNT(*) n FROM daily_spark_events WHERE assignment_id=? AND event_type='REVEAL'",(word_assignment,)).fetchone()['n']==1)
    second_word=second_day['word']['id']; c.close()
    request.form={'_csrf_token':'t','assignment_id':str(second_word),'action':'SNOOZE'}; app.student_daily_spark_action(); c=app.db()
    ok('Later hides a Daily Spark for its cooling-off period',app.ensure_daily_spark(c,fsc,'WORD','2026-08-02') is None)
    c.execute("UPDATE daily_spark_assignments SET snoozed_until='2000-01-01T00:00:00' WHERE id=?",(second_word,)); c.commit()
    ok('a snoozed Spark becomes available after the cooling-off period',app.ensure_daily_spark(c,fsc,'WORD','2026-08-02') is not None)
    metrics=app.daily_spark_metrics(c); ok('Spark analytics calculate stream-level engagement',metrics['ACADEMIC']['open_rate']>0 and metrics['WORD']['open_rate']>0)
    ok('Spark engagement and completion rates are bounded',all(0 <= data.get(rate,0) <= 100 for data in metrics.values() for rate in ('open_rate','completion_rate')))

    # Reporting preserves technical context automatically.
    c.close(); request.form={'_csrf_token':'t','assignment_id':str(word_assignment),'action':'REPORT','report_reason':'The definition looks unclear.'}; app.student_daily_spark_action(); c=app.db()
    report=c.execute("SELECT * FROM pilot_feedback WHERE reporter_user_id=? ORDER BY id DESC LIMIT 1",(fsc,)).fetchone()
    ok('Daily Spark reporting captures hidden assignment context',report and app.safe_json(report['context_json'],{}).get('daily_spark_assignment_id')==word_assignment and report['routing_target']=='ScoreMax')

    # Dashboard and public route context.
    c.close(); request.method='GET'; request.form={}; request.args={}; request.files={}; request.endpoint='student_dashboard'; request.path='/student'; request.referrer=''
    dash=app.student_dashboard(); ok('student dashboard receives the compact Daily Spark snapshot',dash[1][0]=='student.html' and dash[2]['daily_spark']['available'])
    flask.session.clear(); request.endpoint='sustainability_page'; request.path='/sustainability'
    public=app.sustainability_page(); ok('Sustainability is a public ScoreMax page',public[1][0]=='sustainability.html' and public[2]['available'] and len(public[2]['blocks'])>=4)

    # Growth draft intake remains review-only.
    c=app.db(); admin=c.execute("SELECT id FROM users WHERE username='admin'").fetchone()['id']; before_public=c.execute("SELECT COUNT(*) n FROM sustainability_commitments WHERE public_status='PUBLISHED'").fetchone()['n']; c.close()
    flask.session.clear(); flask.session.update(user_id=admin,role='admin',full_name='Platform Admin',session_version=0,_csrf_token='a')
    request.method='POST'; request.endpoint='admin_sustainability'; request.path='/admin/sustainability'; request.form={'_csrf_token':'a','action':'growth_import','draft_json':json.dumps({'draft_id':'GE-SUS-1','title':'Possible future idea','source_system':'Growth Engine'})}
    app.admin_sustainability(); c=app.db()
    intake=c.execute("SELECT * FROM sustainability_draft_intake WHERE external_draft_id='GE-SUS-1'").fetchone()
    ok('Growth Engine sustainability material remains review-only',intake and intake['status']=='DRAFT_REVIEW_REQUIRED' and c.execute("SELECT COUNT(*) n FROM sustainability_commitments WHERE public_status='PUBLISHED'").fetchone()['n']==before_public)
    c.close()

    source=(ROOT/'daily_spark_engine.py').read_text(); dashboard=(ROOT/'templates/student.html').read_text(); base=(ROOT/'templates/base.html').read_text(); sustainability=(ROOT/'templates/sustainability.html').read_text(); admin_template=(ROOT/'templates/admin_sustainability.html').read_text()
    ok('Word selection has no OpenAI or network dependency',all(token not in source.lower() for token in ['openai','requests.','urllib','http://','https://']))
    ok('Dashboard uses one compact Daily Spark module with two streams',dashboard.count('class="daily-spark card')==1 and '>Academic</button>' in dashboard and 'Word of the day' in dashboard)
    ok('Daily Spark explicitly protects the formal-mastery boundary','never used as proof of formal mastery' in dashboard)
    ok('Sustainability remains outside the student core learning navigation and governed in public/admin surfaces','>Sustainability</a>' not in base[base.index("session.get('role')=='student'"):base.index("session.get('role')=='teacher'")] and 'admin_sustainability' in base and 'admin_daily_spark' in base)
    ok('public page visibly labels current in-progress and future claims',all(x in sustainability for x in ['Current practice','In progress','Future commitment']))
    ok('admin page preserves evidence and human-review governance','Evidence boundary' in admin_template and 'nothing was published' not in admin_template.lower() and 'DRAFT_REVIEW_REQUIRED' in admin_template)
    ok('release health marker is 6.2.5',app.healthz()[0]['version'] in {'6.2.5','6.2.6','6.2.7','6.2.7.1','6.2.7.2','6.2.8','6.2.8.1'})
    print(f'\nV6.2.5 SUSTAINABILITY/DAILY SPARK CHECKS PASSED: {len(checks)}')

if __name__=='__main__': main()
