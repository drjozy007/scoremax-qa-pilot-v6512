"""ScoreMax V6.2.8 student access, guided reviewer import and navigation regression suite."""
from __future__ import annotations
import json, os, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
from smoke_tests_v5_5 import install_framework_stubs


def main():
    flask, request=install_framework_stubs()
    temp=Path(tempfile.mkdtemp(prefix='scoremax_v628_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db')
    os.environ['SCOREMAX_ENV']='local'
    os.environ['SCOREMAX_SECRET']='v6.2.8-regression-secret'
    os.environ['SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD']='V628-Admin-Password'
    os.environ['SCOREMAX_ENFORCE_PAYWALL']='1'
    sys.path.insert(0,str(ROOT))
    import app
    from werkzeug.security import generate_password_hash
    ri=app.reviewer_import; rw=app.reviewer_workspace; ca=app.commercial_access
    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)

    app.init(); c=app.db()
    tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    ok('large reviewer import and package entitlement tables exist',{'reviewer_imports','coverage_packages','student_package_entitlements','package_entitlement_history','checkout_requests'}<=tables)
    cols_b={r['name'] for r in c.execute('PRAGMA table_info(reviewer_batches)')}
    cols_a={r['name'] for r in c.execute('PRAGMA table_info(reviewer_assignments)')}
    ok('review batches preserve import position and assignment groups',{'import_id','batch_number','batch_count'}<=cols_b and 'assignment_group_code' in cols_a)

    rows=[]
    for i in range(251):
        rows.append({'Item code':f'BIO-{i+1:04d}','Unit':'Chapter 1','Concept':'Cells','Prompt':f'Guided question {i+1}?',
                     'A':'Option A','B':'Option B','Key':'A' if i<250 else '', 'Difficulty':'Foundation'})
    staged=ri.preview_import(c,rows,title='Full Chapter Import',filename='questions.xlsx',chapter='',topic='',created_by=1)
    mapping=ri.suggest_mapping(staged['columns'])
    ok('guided importer detects common non-template column names',mapping['question_text']=='Prompt' and mapping['correct_answer']=='Key' and mapping['chapter']=='Unit')
    normalized,errors=ri.validate_preview(rows,mapping)
    ok('optional explanation and mastery details never trigger a raw first-row schema failure',len(normalized)==250 and len(errors)==1 and normalized[0]['explanation'].startswith('Explanation not supplied'))
    confirmed=ri.confirm_import(c,staged['id'],mapping,actor_user_id=1)
    ok('a large import is split automatically into 100-question batches',confirmed['valid_rows']==250 and confirmed['invalid_rows']==1 and [x['count'] for x in confirmed['batches']]==[100,100,50])
    db_counts=[r['question_count'] for r in c.execute('SELECT question_count FROM reviewer_batches WHERE import_id=? ORDER BY batch_number',(staged['id'],)).fetchall()]
    ok('batch size is auditable per import',db_counts==[100,100,50])
    import_row=c.execute('SELECT * FROM reviewer_imports WHERE id=?',(staged['id'],)).fetchone()
    ok('excluded rows are retained in an error report rather than aborting valid questions',import_row['status']=='CONFIRMED' and json.loads(import_row['error_rows_json'])[0]['row']==251)

    reviewer_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status)
      VALUES('REV-620800','reviewer','V628 Reviewer','reviewer628@example.com','reviewer628',?,'active')""",(generate_password_hash('Original-Password'),)).lastrowid
    c.commit()
    group='RVG-V628TEST'; assignments=[]
    for idx,b in enumerate(confirmed['batches']):
        assignments.append(rw.create_assignment(c,batch_id=b['batch_id'],reviewer_user_id=reviewer_id,created_by=1,
          assignment_group_code=group,issue_invitation=idx==0))
    statuses=[r['status'] for r in c.execute('SELECT status FROM reviewer_assignments WHERE assignment_group_code=? ORDER BY id',(group,)).fetchall()]
    ok('one invitation can govern several separately auditable batches',statuses==['INVITED','PENDING_ACTIVATION','PENDING_ACTIVATION'])
    rw.accept_invitation(c,assignments[0]['raw_token'],reviewer_id,assignments[0]['verification_code'],generate_password_hash('Activated-Password'))
    activated=[r['status'] for r in c.execute('SELECT status FROM reviewer_assignments WHERE assignment_group_code=? ORDER BY id',(group,)).fetchall()]
    ok('accepting the group invitation activates every assigned batch',activated==['IN_PROGRESS','IN_PROGRESS','IN_PROGRESS'])
    per_batch=[c.execute('SELECT COUNT(*) n FROM reviewer_assignment_items WHERE assignment_id=?',(x['assignment_id'],)).fetchone()['n'] for x in assignments]
    ok('reviewer may stop after 100 or continue across all assigned batches',per_batch==[100,100,50])

    packages=ca.package_rows(c,'FSc Part 1',include_coming=True)
    ok('single-subject bundle and full-curriculum packages are seeded',{'fsc1_biology','fsc1_science_bundle','fsc1_full'}<={x['code'] for x in packages})
    student_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status,academic_level)
      VALUES('STU-620800','student','Package Student','student628@example.com','student628',?,'active','FSc Part 1')""",(generate_password_hash('Student-Password'),)).lastrowid
    biology=next(x for x in packages if x['code']=='fsc1_biology')
    ca.assign_entitlement(c,student_id=student_id,coverage_package_id=biology['id'],access_plan_code='level_2_access',starts_at=app.iso_today(),source='test',actor_user_id=1); c.commit()
    coverage=ca.effective_coverage(c,student_id,'FSc Part 1',commercial_gates_enabled=True)
    ok('subject coverage and access tier remain separate entitlement dimensions',coverage['included_subjects']==['Biology'] and coverage['access_plan_code']=='level_2_access')
    ok('upgrades preserve auditable entitlement history',c.execute('SELECT COUNT(*) n FROM package_entitlement_history WHERE student_id=?',(student_id,)).fetchone()['n']==1)

    base=(ROOT/'templates/base.html').read_text()
    index=(ROOT/'templates/index.html').read_text()
    study=(ROOT/'templates/study_plan.html').read_text().casefold()
    reviewer_admin=(ROOT/'templates/admin_reviewer_workspace.html').read_text()
    access=(ROOT/'templates/access.html').read_text()
    about=(ROOT/'templates/about.html').read_text()
    ok('desktop student navigation has eight persistent primary tabs',all(x in base for x in ['Dashboard','Learn','My Plan','Tests','Exams','Progress','Knowledge','More']) and 'student-secondary-nav' in base)
    ok('mobile uses reduced bottom navigation and the same contextual row',base.count('mobile-bottom-nav')>=1 and 'student-secondary-nav' in base)
    ok('subject switcher is package-aware',all(x in base for x in ['subject-quick-strip','state-{{s.access_state|lower}}','Upgrade','Soon']))
    ok('Study Plans no longer ask for or display prescribed time','weekly hours' not in study and 'weekly availability' not in study and 'estimated_minutes' not in study and 'minutes per' not in study and 'about {{' not in study)
    ok('public Daily Spark is visible before login without a submission form','PUBLIC PREVIEW' in index and 'public_spark' in index and 'student_daily_spark_action' not in index)
    ok('programme options are direct Available or Coming Soon cards without category layers','public_programmes' in index and 'Available programmes' in index and 'FOR SCHOOLS' not in index)
    ok('public navigation and page heading consistently say About Us','About Us' in base and 'ABOUT US' in about)
    ok('package-aware paywall combines coverage and access level','SUBJECT COVERAGE' in access and 'ACCESS LEVEL' in access and 'coverage_package_id' in access)
    ok('reviewer import is guided and offers a safe demo',all(x in reviewer_admin for x in ['Upload and map columns','Try reviewer demo','Confirm import and create 100-question batches','up to 10,000 questions']))
    ok('reviewer tracking remains visible to Admin',all(x in reviewer_admin for x in ['Active time','Assignments and tracking','quality-risk flags']))
    ok('release health marker is V6.2.8',app.healthz()[0]['version'] in {'6.2.8','6.2.8.1'})
    c.close()
    print(f'\nV6.2.8 UPLIFT CHECKS PASSED: {len(checks)}')

if __name__=='__main__': main()
