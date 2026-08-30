"""ScoreMax V6.2.7 reviewer baseline regression suite, compatible with V6.2.7.1 and V6.2.7.2."""
from __future__ import annotations
import json, os, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
from smoke_tests_v5_5 import install_framework_stubs


def main():
    flask,request=install_framework_stubs()
    temp=Path(tempfile.mkdtemp(prefix='scoremax_v627_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db')
    os.environ['SCOREMAX_ENV']='local'
    import app
    from werkzeug.security import generate_password_hash
    rw=app.reviewer_workspace
    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)

    app.init(); app.init(); c=app.db(); c.commit()
    def age_timer(item_id, seconds):
        c.execute("UPDATE reviewer_assignment_items SET last_opened_at=datetime('now',?) WHERE id=?",(f'-{int(seconds)} seconds',item_id))
        c.commit()

    tables={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected={'reviewer_feature_controls','reviewer_batches','reviewer_questions','reviewer_assignments','reviewer_assignment_items',
              'reviewer_time_events','reviewer_question_outcomes','reviewer_audit_events'}
    ok('confidential reviewer schema is idempotent and complete',expected<=tables)
    control=c.execute("SELECT * FROM reviewer_feature_controls WHERE feature_code='academic_reviewer_workspace'").fetchone()
    ok('reviewer workspace launches QA-only with a 100-item ceiling',control and control['state']=='QA_ONLY' and json.loads(control['configuration_json'])['max_assignment_items']==100)
    ok('decision set remains deliberately minimal',rw.DECISIONS=={'ACCEPT_UNCHANGED','CORRECTION_REQUIRED','MASTERY_LEVEL_UNSUITABLE','REJECT','UNSURE'})

    reviewers=[]
    for i in (1,2,3):
        cur=c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status) VALUES(?,?,?,?,?,?,'active')",
          (f'REV-{i:06d}','reviewer',f'Reviewer {i}',f'reviewer{i}@example.com',f'reviewer{i}',generate_password_hash('reviewpass123')))
        reviewers.append(cur.lastrowid)
    c.commit()

    rows=[]
    for i in range(100):
        rows.append({'question_id':f'CH1-R-{i+1:03d}','chapter':'Chapter 1','topic':f'Topic {i%5+1}',
          'question':f'Governed review question {i+1}?','option_a':'Correct','option_b':'Incorrect','answer':'A',
          'explanation':f'Explanation {i+1}.','mastery_level':['Foundation','Exam Ready','Advanced','Distinction'][i%4],
          'calibration_expected_decision':'CORRECTION_REQUIRED' if i in {7,63} else ''})
    imported=rw.import_batch(c,rows,title='Chapter 1 Review',filename='chapter1.xlsx',created_by=1,chapter='Chapter 1')
    ok('a full 100-question review batch imports atomically',imported['count']==100 and c.execute('SELECT COUNT(*) n FROM reviewer_questions WHERE batch_id=?',(imported['batch_id'],)).fetchone()['n']==100)
    cols={r['name'] for r in c.execute('PRAGMA table_info(reviewer_questions)')}
    ok('review snapshots contain only minimal academic review fields',{'id','batch_id','external_question_id','display_order','chapter','topic','question_text','options_json','correct_answer','explanation','mastery_level','calibration_expected_decision','snapshot_checksum','created_at'}<=cols and cols<={'id','batch_id','external_question_id','display_order','chapter','topic','question_text','stimulus_context','review_content','options_json','correct_answer','explanation','mastery_level','question_type','review_priority','review_requirement','reviewer2_required','source_sheet','source_row','calibration_expected_decision','snapshot_checksum','created_at'})
    too_many=False
    try: rw.import_batch(c,rows+[dict(rows[0],question_id='CH1-R-101')],title='Too many',filename='too.json',created_by=1)
    except ValueError as exc: too_many='at most 100' in str(exc)
    ok('review batches above 100 are blocked',too_many)
    before=c.execute('SELECT COUNT(*) n FROM reviewer_batches').fetchone()['n']
    duplicate=False
    try: rw.import_batch(c,[rows[0],rows[0]],title='Duplicate',filename='dup.json',created_by=1)
    except ValueError as exc: duplicate='Duplicate question IDs' in str(exc)
    ok('duplicate question IDs reject the whole batch',duplicate and c.execute('SELECT COUNT(*) n FROM reviewer_batches').fetchone()['n']==before)
    retry=False
    try: rw.import_batch(c,rows,title='Chapter 1 Review',filename='retry.xlsx',created_by=1,chapter='Chapter 1')
    except ValueError as exc: retry='already been imported' in str(exc)
    ok('exact batch retry is idempotently rejected',retry)

    assignment=rw.create_assignment(c,batch_id=imported['batch_id'],reviewer_user_id=reviewers[0],created_by=1)
    ok('named reviewer assignment contains exactly 100 items',c.execute('SELECT COUNT(*) n FROM reviewer_assignment_items WHERE assignment_id=?',(assignment['assignment_id'],)).fetchone()['n']==100)
    stored=c.execute('SELECT invitation_token_hash FROM reviewer_assignments WHERE id=?',(assignment['assignment_id'],)).fetchone()['invitation_token_hash']
    ok('only a one-way invitation hash is stored',stored==rw.token_hash(assignment['raw_token']) and assignment['raw_token'] not in stored)
    rw.accept_invitation(c,assignment['raw_token'],reviewers[0],assignment['verification_code'],generate_password_hash('activated-reviewer-1'))
    active=c.execute('SELECT * FROM reviewer_assignments WHERE id=?',(assignment['assignment_id'],)).fetchone()
    ok('one-time invitation acceptance activates the assignment and records confidentiality',active['status']=='IN_PROGRESS' and active['confidentiality_accepted_at'] and not active['invitation_token_hash'])
    reused=False
    try: rw.accept_invitation(c,assignment['raw_token'],reviewers[0],assignment['verification_code'],generate_password_hash('activated-reviewer-1'))
    except ValueError: reused=True
    ok('accepted invitations cannot be reused',reused)

    first=rw.next_unfinished_item(c,assignment['assignment_id'])
    opened=rw.open_item(c,assignment['assignment_id'],first['id'],reviewers[0]); age_timer(first['id'],30)
    ok('reviewer opens only an assigned minimal snapshot',opened['question_text']==rows[0]['question'] and opened['batch_title']=='Chapter 1 Review')
    ok('timer caps each client tick to prevent time inflation',rw.record_active_time(c,first['id'],reviewers[0],999)==30)
    no_comment=False
    try: rw.submit_decision(c,item_id=first['id'],reviewer_user_id=reviewers[0],decision='CORRECTION_REQUIRED',mastery_suitability='SUITABLE',comments='')
    except ValueError as exc: no_comment='meaningful comment' in str(exc)
    ok('non-acceptance decisions require meaningful comments',no_comment)
    result=rw.submit_decision(c,item_id=first['id'],reviewer_user_id=reviewers[0],decision='CORRECTION_REQUIRED',mastery_suitability='SUITABLE',comments='Correct answer requires amendment.',independent_answer='B')
    ok('first review deviation automatically requires independent second review',result['outcome_status']=='SECOND_REVIEW_REQUIRED')
    second=rw.next_unfinished_item(c,assignment['assignment_id']); rw.open_item(c,assignment['assignment_id'],second['id'],reviewers[0]); age_timer(second['id'],5)
    rw.record_active_time(c,second['id'],reviewers[0],5)
    result2=rw.submit_decision(c,item_id=second['id'],reviewer_user_id=reviewers[0],decision='ACCEPT_UNCHANGED',mastery_suitability='SUITABLE')
    ok('very fast reviews are flagged rather than blocked',result2['outcome_status']=='FIRST_REVIEW_ACCEPTED' and 'VERY_FAST_REVIEW' in result2['risk_flags'] and 'ANSWER_NOT_REVEALED' in result2['risk_flags'])
    third=rw.next_unfinished_item(c,assignment['assignment_id']); rw.open_item(c,assignment['assignment_id'],third['id'],reviewers[0]); rw.reveal_answer(c,third['id'],reviewers[0]); age_timer(third['id'],25); rw.record_active_time(c,third['id'],reviewers[0],25)
    rw.submit_decision(c,item_id=third['id'],reviewer_user_id=reviewers[0],decision='ACCEPT_UNCHANGED',mastery_suitability='SUITABLE')
    progress=rw.assignment_progress(c,assignment['assignment_id'])
    ok('progress saves after each question and resume points to the next unfinished item',progress['completed']==3 and rw.next_unfinished_item(c,assignment['assignment_id'])['display_order']==4)
    ok('active review time excludes unreported wall-clock idle time',progress['active_seconds']==60)

    required=[r['question_id'] for r in c.execute("SELECT * FROM reviewer_question_outcomes WHERE status='SECOND_REVIEW_REQUIRED'").fetchall()]
    independent=False
    try: rw.create_assignment(c,batch_id=imported['batch_id'],reviewer_user_id=reviewers[0],created_by=1,round_no=2,parent_assignment_id=assignment['assignment_id'],question_ids=required)
    except ValueError as exc: independent='independent' in str(exc)
    ok('the same person cannot perform the independent second review',independent)
    second_assignment=rw.create_assignment(c,batch_id=imported['batch_id'],reviewer_user_id=reviewers[1],created_by=1,round_no=2,parent_assignment_id=assignment['assignment_id'],question_ids=required)
    rw.accept_invitation(c,second_assignment['raw_token'],reviewers[1],second_assignment['verification_code'],generate_password_hash('activated-reviewer-2')); second_item=rw.next_unfinished_item(c,second_assignment['assignment_id']); rw.open_item(c,second_assignment['assignment_id'],second_item['id'],reviewers[1]); rw.reveal_answer(c,second_item['id'],reviewers[1]); age_timer(second_item['id'],30); rw.record_active_time(c,second_item['id'],reviewers[1],30)
    agreed=rw.submit_decision(c,item_id=second_item['id'],reviewer_user_id=reviewers[1],decision='CORRECTION_REQUIRED',mastery_suitability='SUITABLE',comments='I independently confirm the correction is required.')
    ok('matching second-review decisions are recorded as agreed',agreed['outcome_status']=='SECOND_REVIEW_AGREED')

    # Create another non-acceptance and prove disagreement routes to adjudication.
    fourth=rw.next_unfinished_item(c,assignment['assignment_id']); rw.open_item(c,assignment['assignment_id'],fourth['id'],reviewers[0]); rw.reveal_answer(c,fourth['id'],reviewers[0]); age_timer(fourth['id'],25); rw.record_active_time(c,fourth['id'],reviewers[0],25)
    rw.submit_decision(c,item_id=fourth['id'],reviewer_user_id=reviewers[0],decision='MASTERY_LEVEL_UNSUITABLE',mastery_suitability='UNSUITABLE',comments='The cognitive demand is below the proposed level.')
    disagree_q=[c.execute('SELECT question_id FROM reviewer_assignment_items WHERE id=?',(fourth['id'],)).fetchone()['question_id']]
    disagree_assignment=rw.create_assignment(c,batch_id=imported['batch_id'],reviewer_user_id=reviewers[2],created_by=1,round_no=2,parent_assignment_id=assignment['assignment_id'],question_ids=disagree_q)
    rw.accept_invitation(c,disagree_assignment['raw_token'],reviewers[2],disagree_assignment['verification_code'],generate_password_hash('activated-reviewer-3')); di=rw.next_unfinished_item(c,disagree_assignment['assignment_id']); rw.open_item(c,disagree_assignment['assignment_id'],di['id'],reviewers[2]); rw.reveal_answer(c,di['id'],reviewers[2]); age_timer(di['id'],25); rw.record_active_time(c,di['id'],reviewers[2],25)
    disagreement=rw.submit_decision(c,item_id=di['id'],reviewer_user_id=reviewers[2],decision='ACCEPT_UNCHANGED',mastery_suitability='SUITABLE')
    ok('reviewer disagreement automatically opens adjudication',disagreement['outcome_status']=='ADJUDICATION_REQUIRED')

    quality=rw.assignment_quality(c,assignment['assignment_id'])
    ok('admin quality evidence includes fast items answer-reveal gaps and decision runs',quality['fast_items']>=1 and quality['answer_not_revealed']>=1 and 'ANSWER_REVEAL_GAPS' in quality['flags'])
    source=(ROOT/'reviewer_workspace_engine.py').read_text(); item_template=(ROOT/'templates/reviewer_item.html').read_text(); base=(ROOT/'templates/base.html').read_text(); index=(ROOT/'templates/index.html').read_text()
    ok('reviewer engine has no live question attempt mastery or Study Plan writes',all(term not in source for term in ['INSERT INTO questions','INSERT INTO attempts','INSERT INTO mastery_records','INSERT INTO study_plans']))
    ok('reviewer portal does not extend the normal ScoreMax shell',"extends 'base.html'" not in item_template and 'desktop-nav' not in item_template and 'student_dashboard' not in item_template)
    ok('reviewer screen exposes only agreed review information',all(x in item_template for x in ['item.question_text','item.correct_answer','item.explanation','item.mastery_level','mastery_suitability','decision','comments']))
    ok('active timer pauses for hidden or inactive tabs in the client',"document.visibilityState==='visible'" in item_template and '120000' in item_template)
    ok('reviewer-specific watermark is visible in the confidential portal','review-watermark' in item_template and 'session.get' in item_template)
    ok('normal ScoreMax routes are fenced away from reviewer sessions',"session.get('role')=='reviewer'" in (ROOT/'app.py').read_text() and 'reviewer_endpoints' in (ROOT/'app.py').read_text())
    ok('Teacher of the Year is on the public landing page and not student primary navigation','Teacher of the Year' in index and 'teacher_of_year_page' not in base[base.index("session.get('role')=='student'"):base.index("session.get('role')=='teacher'")])
    ok('student navigation remains accessible after the simplified two-row uplift','student-account-menu' in base and 'subject-quick-strip' in base and 'mobile-bottom-nav' in base)
    ok('admin navigation includes the Reviewer Workspace','Reviewer Workspace' in base and 'admin_reviewer_workspace' in base)
    ok('release health marker is compatible with 6.2.7.1+',app.healthz()[0]['version'] in {'6.2.7.1','6.2.7.2','6.2.8','6.2.8.1'})
    print(f'\nV6.2.7 REVIEWER ASSURANCE / NAVIGATION CHECKS PASSED: {len(checks)}')

if __name__=='__main__': main()
