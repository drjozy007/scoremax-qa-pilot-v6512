"""ScoreMax V6.3.1 Student UX V2 deterministic checks.

These checks supersede historical V6.2.x assertions that intentionally pinned the
older eight-tab + contextual-third-row student navigation.
"""
import os, tempfile
from pathlib import Path
from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
ROOT=Path(__file__).resolve().parent
os.environ['SCOREMAX_DB']=str(Path(tempfile.mkdtemp(prefix='scoremax_v631_ux_'))/'scoremax.db')
import app

n=0
def ok(name, condition):
    global n
    if not condition: raise AssertionError(name)
    n+=1; print('PASS:',name)

app.init(); c=app.db()
# Minimal student for chapter mastery snapshot tests.
c.execute("""INSERT INTO users(system_user_id,role,full_name,academic_level,subjects,profile_completed)
  VALUES('STU-UX-1','student','UX Student','FSc Part 1','Biology',1)""")
sid=c.execute("SELECT id FROM users WHERE system_user_id='STU-UX-1'").fetchone()['id']

# Demo-only inventory must never advertise learner-facing potential mastery.
demo=app.chapter_mastery_opportunity(c,sid,'Biology','Demo Chapter 1','FSc Part 1')
ok('demo-only chapter does not inflate potential mastery',demo['potential_level']=='Bank building' and demo['potential_pct']==0)

# Turn the already governed demo fixture into a production fixture for capacity testing only.
c.execute("UPDATE questions SET is_demo=0,calibration_status='PROVISIONAL',subject='Biology' WHERE chapter='Demo Chapter 1'")
c.commit()
cap=app.chapter_mastery_opportunity(c,sid,'Biology','Demo Chapter 1','FSc Part 1')
ok('potential mastery is derived from governed production bank capacity',cap['potential_level']=='Distinction' and cap['potential_pct']==100)
ok('unverified learner starts at zero existing mastery',cap['existing_level']=='Not verified' and cap['existing_pct']==0)

scope=app.mastery_scope_key('chapter','FSc Part 1','Biology','Demo Chapter 1')
c.execute("""INSERT INTO mastery_records(student_id,scope_type,scope_key,programme,subject,chapter,mastery_level,status,
  verified_at,verification_due_at,best_accuracy,forms_passed,questions_total,source)
  VALUES(?, 'chapter', ?, 'FSc Part 1','Biology','Demo Chapter 1','Exam Ready','Verified',
  datetime('now'),date('now','+60 day'),82,2,24,'formal')""",(sid,scope)); c.commit()
opp=app.chapter_mastery_opportunity(c,sid,'Biology','Demo Chapter 1','FSc Part 1')
ok('existing mastery comes from formal mastery records',opp['existing_level']=='Exam Ready' and opp['existing_pct']==50 and opp['has_formal_mastery'])
ok('chapter opportunity shows only the unearned gap',opp['potential_level']=='Distinction' and opp['opportunity_pct']==50)

c.execute("UPDATE mastery_records SET verification_due_at=date('now','-1 day') WHERE student_id=? AND scope_key=?",(sid,scope)); c.commit()
due=app.chapter_mastery_opportunity(c,sid,'Biology','Demo Chapter 1','FSc Part 1')
ok('verification due preserves earned level while exposing freshness state',due['existing_level']=='Exam Ready' and due['existing_status']=='Verification Due')

base=(ROOT/'templates/base.html').read_text()
ok('student primary navigation is reduced to six learning journeys',all(f'>{x}</a>' in base for x in ['Home','Learn','My Plan','Practice','Exams','Progress']))
ok('Knowledge support and account controls move out of primary navigation','student-account-menu' in base and 'Knowledge Hub' in base and 'Settings' in base)
ok('Academic Reviewer Workspace remains disabled from the forward ScoreMax shell',app.app.jinja_env.globals.get('reviewer_workspace_forward_enabled') is False)
ok('student shell renders no contextual third navigation row','student_secondary_nav_global %}<nav' not in base)
ok('mobile Learn opens subjects rather than the test builder',"url_for('subject_browser')" in base and '▦<span>Learn' in base)
ok('mobile Practice remains a direct core action',"url_for('test_setup')" in base and '✎<span>Practice' in base)

subject=(ROOT/'templates/subject_detail.html').read_text(); chapter=(ROOT/'templates/chapter_page.html').read_text()
ok('every subject chapter card exposes Existing Mastery and Potential Mastery','Existing mastery' in subject and 'Potential mastery' in subject and 'mastery-opportunity-track' in subject)
ok('chapter detail repeats the mastery opportunity prominently','Existing mastery' in chapter and 'Potential mastery' in chapter and 'mastery-opportunity-track large' in chapter)
ok('mastery opportunity cards keep practice accuracy separate from formal mastery','practice accuracy' in subject and 'practice accuracy' in chapter)

home=(ROOT/'templates/student.html').read_text()
ok('home is organised around one Today focus','TODAY\'S FOCUS' in home and 'home-priority-grid' in home)
ok('home keeps subjects and coming-up actions visible without workspace tabs','MY SUBJECTS' in home and 'COMING UP' in home and 'workspace-tabs' not in home)
ok('Daily Spark remains a single compact optional module',home.count('class="daily-spark card')==1 and 'Academic' in home and 'Word of the day' in home)
ok('Daily Spark still protects formal mastery','never used as proof of formal mastery' in home)

practice=(ROOT/'templates/test_setup.html').read_text()
ok('practice wording is learner-facing','What do you want to practise?' in practice and 'Quick Practice' in practice and 'Build My Own Test' in practice)
ok('technical governed-bank wording is removed from the main Practice choice','available governed bank' not in practice)
progress=(ROOT/'templates/student_analytics.html').read_text()
ok('progress opens with improvement language rather than evidence-system language','See how you are improving.' in progress and 'Your evidence picture.' not in progress)
result=(ROOT/'templates/result.html').read_text()
ok('result shows learner result before technical exam metadata',result.index('TEST COMPLETE') < result.index('Assessment details'))
ok('blueprint and assembly metadata remain available under details','assessment-technical-details' in result and 'assembly' in result.lower())

css=(ROOT/'static/styles.css').read_text()
ok('mastery graph has distinct potential and existing layers','.potential-fill' in css and '.existing-fill' in css)
ok('only the subject strip remains as the sticky learner second row','.subject-quick-strip{top:64px!important}' in css and '.student-secondary-nav{display:none!important}' in css)
ok('release marker identifies the Student UX V2 descendant',app.healthz()[0]['release_version'] in {'6.3.2','6.4.0'})

c.close()
print(f'\nV6.3.1 STUDENT UX V2 CHECKS PASSED: {n}')
