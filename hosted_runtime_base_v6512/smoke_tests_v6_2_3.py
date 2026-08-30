"""ScoreMax V6.2.3 Student Command Centre & Adaptive UX regression suite."""
from __future__ import annotations
import os, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs

def main():
    flask,request=install_framework_stubs(); temp=Path(tempfile.mkdtemp(prefix='scoremax_v623_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db'); os.environ['SCOREMAX_ENV']='local'
    import app
    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)
    app.init(); app.init()
    c=app.db(); tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}; user_cols={r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()}
    ok('V6.2.3 schema is idempotent',{'student_pathway_preferences','coach_nudge_events','platform_social_links'}<=tables)
    ok('student coach and pathway columns exist',{'coach_enabled','future_pathway_code'}<=user_cols)
    social=c.execute('SELECT COUNT(*) n FROM platform_social_links').fetchone()['n']; ok('official social registry is seeded but governed',social==6)
    student_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,session_version,academic_level,coach_enabled)
      VALUES('STU-V623','student','Matric UX Student','2010-05-05','ux@test','ux-test','x','active',0,'Matric Class 10',1)""").lastrowid; c.commit()
    subjects=app._subject_map(c,student_id); names={x['subject'] for x in subjects}
    ok('Matric catalogue shows broad current studies before bank availability',{'English','Urdu','Mathematics','Islamiyat','Pakistan Studies','Physics','Chemistry','Biology','Computer Science'}<=names)
    coming=next(x for x in subjects if x['subject']=='Mathematics'); ok('catalogue separates Coming Soon from live inventory',coming['availability']=='COMING_SOON' and coming['available_questions']==0)
    p=app.student_pathway_snapshot(c,student_id); ok('Matric pathway catalogue includes core post-Matric routes',{'PRE_MEDICAL','PRE_ENGINEERING','COMPUTER_SCIENCE','COMMERCE','HUMANITIES','UNDECIDED'}<={x['code'] for x in p['options']})
    coach=app.scoremax_coach(c,student_id); ok('ScoreMax Coach prioritises pathway guidance for a new Matric student',coach and coach['key']=='choose-future-pathway')
    ok('Core workload is expressed as a weekly range',app.workload_range('Core')['label']=='5–8 focused hours/week')
    fit=app.workload_fit(360,app.workload_range('Core')); ok('weekly capacity fit is evaluated separately',fit['status']=='Realistic')
    ok('preparation pathway labels never leak into mastery',app.scoremax_level_from_evidence(75,12)=='Advanced' and app.scoremax_level_from_evidence(96,35,98)=='Elite')
    ok('formal level list excludes Stretch and Peak',all(x not in app.SCOREMAX_LEVELS for x in ('Stretch','Peak')))
    c.close()
    flask.session.clear(); flask.session.update(user_id=student_id,role='student',full_name='Matric UX Student',session_version=0)
    request.method='POST'; request.form={'pathway_code':'PRE_MEDICAL'}
    app.student_pathways(); c=app.db(); saved=c.execute('SELECT pathway_code FROM student_pathway_preferences WHERE student_id=?',(student_id,)).fetchone(); c.close(); ok('student can save a future pathway without changing current study level',saved and saved['pathway_code']=='PRE_MEDICAL')
    request.method='GET'; request.form={}; request.args={}; request.files={}; request.endpoint='student_dashboard'; request.path='/student'; request.referrer=''
    dash=app.student_dashboard(); ok('dashboard route supplies the adaptive pathway and coach context',dash[1][0]=='student.html' and 'pathway_data' in dash[2] and 'scoremax_coach' in dash[2])
    base=(ROOT/'templates/base.html').read_text(); desktop=base.split('<div class="mobile-site-menu"',1)[0]
    ok('primary navigation prioritises six learning journeys before support',all(x in desktop for x in ['>Home</a>','>Learn</a>','>My Plan</a>','>Practice</a>','>Exams</a>','>Progress</a>']) and 'student-account-menu' in desktop)
    ok('teacher discovery and messages remain supporting account-menu links','Find a Teacher' in base and '>Messages</a>' in base and 'student-account-dropdown' in base)
    dashboard=(ROOT/'templates/student.html').read_text(); ok('dashboard is a compact next-action home without workspace tabs',"TODAY'S FOCUS" in dashboard and 'home-priority-grid' in dashboard and 'workspace-tabs' not in dashboard)
    ok('dashboard keeps teacher discovery out of the core daily-action surface','Find a Teacher' not in dashboard and 'Find a Teacher' in base)
    plan=(ROOT/'templates/study_plan.html').read_text(); ok('Study Plan removes prescribed time and uses evidence priorities','weekly_hours' not in plan and 'weekly availability' not in plan.lower() and 'PRIORITY QUEUE' in plan)
    ok('Study Plan uses real tabs rather than a long anchor page','data-tab-button="today"' in plan and 'data-tab-button="settings"' in plan)
    setup=(ROOT/'templates/test_setup.html').read_text(); ok('custom test supports sixty questions','<option value="60">60</option>' in setup)
    ok('custom test supports an explicit sixty-minute session','<option value="60">60 minutes</option>' in setup and 'durationMinutes' in setup)
    ok('practice setup uses learner-facing progressive disclosure tabs',all(x in setup for x in ['Quick Practice','Choose What to Practise','Build My Own Test']))
    issue=(ROOT/'templates/report_issue.html').read_text(); ok('students are never asked for technical database IDs','Question database ID' not in issue and 'Attempt ID' not in issue)
    ok('issue context is captured through hidden fields',all(x in issue for x in ['name="question_id"','name="attempt_id"','CAPTURED CONTEXT']))
    faq=(ROOT/'templates/faq.html').read_text(); ok('FAQs are searchable and cover current architecture','faqSearch' in faq and 'Verification Due' in faq and 'Academic Messages' in faq and 'Pathway Explorer' in faq)
    browser=(ROOT/'templates/subject_browser.html').read_text(); ok('subject browser exposes current studies and future pathways','MY CURRENT STUDIES' in browser and 'WHAT COMES NEXT' in browser)
    detail=(ROOT/'templates/subject_detail.html').read_text(); ok('coming-soon subjects cannot start fake tests',"selected.availability=='LIVE'" in detail and 'Practice will open when approved content is ready' in detail)
    exams=(ROOT/'templates/exam_centre.html').read_text(); progress=(ROOT/'templates/student_analytics.html').read_text()
    ok('Exam Centre is tabbed to avoid repeated long scrolling',all(x in exams for x in ['data-tab-button="mocks"','data-tab-button="past-papers"','data-tab-button="history"']))
    ok('Progress is tabbed by student question',all(x in progress for x in ['Overview','Subjects & areas','Mastery levels','Next actions']))
    result=(ROOT/'templates/result.html').read_text(); take=(ROOT/'templates/take_test_v4.html').read_text(); ok('question and result pages provide contextual issue reporting','Report this question' in take and 'Report a problem with this result' in result)
    ok('Knowledge Hub and official social channels are reachable from the shell','knowledge_home' in base and 'connect_page' in base and 'social_links_global' in base)
    ok('new pathway and official-channel templates exist',all((ROOT/'templates'/x).exists() for x in ['student_pathways.html','connect.html','admin_social_links.html']))
    ok('release health marker is current',app.healthz()[0]['version'] in {'6.2.3','6.2.4','6.2.5','6.2.6','6.2.7','6.2.7.1','6.2.7.2','6.2.8','6.2.8.1'})
    print(f'\nV6.2.3 STUDENT EXPERIENCE CHECKS PASSED: {len(checks)}')
if __name__=='__main__': main()
