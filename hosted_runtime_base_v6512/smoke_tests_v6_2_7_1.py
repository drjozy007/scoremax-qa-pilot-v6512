"""ScoreMax V6.2.7.1 Reviewer Assurance Hardening regression suite."""
from __future__ import annotations
import os, tempfile, threading
from pathlib import Path

ROOT=Path(__file__).resolve().parent
from smoke_tests_v5_5 import install_framework_stubs


def main():
    install_framework_stubs()
    temp=Path(tempfile.mkdtemp(prefix='scoremax_v6271_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db'); os.environ['SCOREMAX_ENV']='local'
    import app
    from werkzeug.security import generate_password_hash
    rw=app.reviewer_workspace
    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)
    def rows(prefix,count=3):
        return [{'question_id':f'{prefix}-{i+1}','chapter':'Chapter 1','topic':'Topic 1','question':f'Question {prefix} {i+1}?',
          'option_a':'A','option_b':'B','answer':'A','explanation':f'Explanation for {prefix} {i+1}.','mastery_level':'Foundation'} for i in range(count)]
    def reviewer(c,n):
        cur=c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,account_status) VALUES(?,?,?,?,?,?,'active')",
          (f'REV-H-{n}', 'reviewer',f'Hardening Reviewer {n}',f'hardening{n}@example.com',f'hardening{n}',generate_password_hash('original-password')))
        c.commit(); return cur.lastrowid
    def age_item(c,item_id,seconds):
        c.execute("UPDATE reviewer_assignment_items SET last_opened_at=datetime('now',?),last_ping_at=NULL WHERE id=?",(f'-{seconds} seconds',item_id)); c.commit()

    app.init(); c=app.db()
    cols_a={r['name'] for r in c.execute('PRAGMA table_info(reviewer_assignments)')}; cols_i={r['name'] for r in c.execute('PRAGMA table_info(reviewer_assignment_items)')}
    indexes={r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    ok('hardening schema adds verification and round metadata',{'invitation_verification_hash','invitation_verification_attempts','invitation_locked_at'}<=cols_a and 'round_no' in cols_i)
    ok('database uniqueness backstops are installed',{'uq_reviewer_batch_checksum','uq_reviewer_first_assignment','uq_reviewer_second_question'}<=indexes)

    reviewers=[reviewer(c,i) for i in range(1,7)]
    batch=rw.import_batch(c,rows('MAIN',4),title='Hardening Main',filename='main.json',created_by=1)
    assignment=rw.create_assignment(c,batch_id=batch['batch_id'],reviewer_user_id=reviewers[0],created_by=1)
    stored=c.execute('SELECT invitation_token_hash,invitation_verification_hash FROM reviewer_assignments WHERE id=?',(assignment['assignment_id'],)).fetchone()
    ok('invitation link and separate verification code are stored only as hashes',stored['invitation_token_hash']==rw.token_hash(assignment['raw_token']) and stored['invitation_verification_hash']==rw.token_hash(assignment['verification_code'].replace('-','').upper()) and assignment['verification_code'] not in tuple(stored))
    before_password=c.execute('SELECT password_hash FROM users WHERE id=?',(reviewers[0],)).fetchone()['password_hash']
    wrong=False
    try: rw.accept_invitation(c,assignment['raw_token'],reviewers[0],'WRONG-CODE',generate_password_hash('changed-password'))
    except ValueError as exc: wrong='incorrect' in str(exc)
    after_wrong=c.execute('SELECT ra.status,ra.invitation_verification_attempts,u.password_hash FROM reviewer_assignments ra JOIN users u ON u.id=ra.reviewer_user_id WHERE ra.id=?',(assignment['assignment_id'],)).fetchone()
    ok('link possession alone cannot activate or reset the reviewer account',wrong and after_wrong['status']=='INVITED' and after_wrong['invitation_verification_attempts']==1 and after_wrong['password_hash']==before_password)
    rw.accept_invitation(c,assignment['raw_token'],reviewers[0],assignment['verification_code'],generate_password_hash('verified-password'))
    activated=c.execute('SELECT * FROM reviewer_assignments WHERE id=?',(assignment['assignment_id'],)).fetchone()
    ok('correct two-part invitation activates once and clears both credentials',activated['status']=='IN_PROGRESS' and not activated['invitation_token_hash'] and not activated['invitation_verification_hash'])

    first=rw.next_unfinished_item(c,assignment['assignment_id']); rw.open_item(c,assignment['assignment_id'],first['id'],reviewers[0]); age_item(c,first['id'],30)
    accepted=rw.record_active_time(c,first['id'],reviewers[0],30)
    replayed=sum(rw.record_active_time(c,first['id'],reviewers[0],30) for _ in range(20))
    total=c.execute('SELECT active_seconds FROM reviewer_assignment_items WHERE id=?',(first['id'],)).fetchone()['active_seconds']
    ok('server elapsed time prevents rapid timer inflation',accepted==30 and replayed==0 and total==30)
    second=c.execute('SELECT id FROM reviewer_assignment_items WHERE assignment_id=? AND display_order=2',(assignment['assignment_id'],)).fetchone(); rw.open_item(c,assignment['assignment_id'],second['id'],reviewers[0]); age_item(c,first['id'],30)
    blocked_current=False
    try: rw.record_active_time(c,first['id'],reviewers[0],30)
    except PermissionError: blocked_current=True
    ok('only the currently open item can receive active-time credit',blocked_current)
    punctuation=False
    try: rw.submit_decision(c,item_id=second['id'],reviewer_user_id=reviewers[0],decision='CORRECTION_REQUIRED',mastery_suitability='SUITABLE',comments='............')
    except ValueError: punctuation=True
    ok('punctuation padding cannot satisfy meaningful-comment validation',punctuation)
    rw.submit_decision(c,item_id=first['id'],reviewer_user_id=reviewers[0],decision='CORRECTION_REQUIRED',mastery_suitability='SUITABLE',comments='The configured answer requires correction.')
    blocked_completed=False
    try: rw.record_active_time(c,first['id'],reviewers[0],30)
    except PermissionError: blocked_completed=True
    ok('completed items cannot receive further active-time credit',blocked_completed)
    qid=c.execute('SELECT question_id FROM reviewer_assignment_items WHERE id=?',(first['id'],)).fetchone()['question_id']
    missing_parent=False
    try: rw.create_assignment(c,batch_id=batch['batch_id'],reviewer_user_id=reviewers[1],created_by=1,round_no=2,question_ids=[qid])
    except ValueError as exc: missing_parent='requires the original' in str(exc)
    same_reviewer=False
    try: rw.create_assignment(c,batch_id=batch['batch_id'],reviewer_user_id=reviewers[0],created_by=1,round_no=2,parent_assignment_id=assignment['assignment_id'],question_ids=[qid])
    except ValueError as exc: same_reviewer='independent' in str(exc)
    ok('shared assignment engine unconditionally enforces second-review parent and independence',missing_parent and same_reviewer)

    # Legacy unused invitations are invalidated and can be safely reissued.
    legacy_batch=rw.import_batch(c,rows('LEGACY',1),title='Legacy Invite',filename='legacy.json',created_by=1)
    legacy=rw.create_assignment(c,batch_id=legacy_batch['batch_id'],reviewer_user_id=reviewers[1],created_by=1)
    c.execute("UPDATE reviewer_assignments SET invitation_verification_hash=NULL WHERE id=?",(legacy['assignment_id'],)); c.commit(); rw.init_reviewer_schema(c); c.commit()
    state=c.execute('SELECT status,invitation_token_hash FROM reviewer_assignments WHERE id=?',(legacy['assignment_id'],)).fetchone()
    reissued=rw.reissue_invitation(c,legacy['assignment_id'],1)
    ok('legacy one-part invitations are invalidated and reissued as two-part invitations',state['status']=='INVITATION_REISSUE_REQUIRED' and not state['invitation_token_hash'] and reissued['verification_code'])
    for _ in range(rw.INVITATION_CODE_ATTEMPT_LIMIT):
        try: rw.accept_invitation(c,reissued['raw_token'],reviewers[1],'WRONG-CODE',generate_password_hash('never-applied'))
        except ValueError: pass
    locked=c.execute('SELECT invitation_locked_at FROM reviewer_assignments WHERE id=?',(legacy['assignment_id'],)).fetchone()['invitation_locked_at']
    ok('eight failed verification attempts lock the invitation',bool(locked))
    replacement_invite=rw.reissue_invitation(c,legacy['assignment_id'],1)
    old_rejected=False
    try: rw.accept_invitation(c,reissued['raw_token'],reviewers[1],reissued['verification_code'],generate_password_hash('old-code-password'))
    except ValueError: old_rejected=True
    ok('reissuing invalidates the previous link and verification code',old_rejected and replacement_invite['raw_token']!=reissued['raw_token'])

    # Genuine concurrency: duplicate checksum.
    race_rows=rows('RACE-BATCH',2); barrier=threading.Barrier(2); results=[]
    def import_worker():
        conn=app.db(); barrier.wait()
        try: results.append(('ok',rw.import_batch(conn,race_rows,title='Race Batch',filename='race.json',created_by=1)['batch_id']))
        except Exception as exc: results.append(('error',str(exc)))
        finally: conn.close()
    threads=[threading.Thread(target=import_worker) for _ in range(2)]
    [t.start() for t in threads]; [t.join() for t in threads]
    race_digest=rw.checksum({'title':'Race Batch','chapter':'','topic':'','questions':[rw.normalize_question(r,i+1) for i,r in enumerate(race_rows)]})
    count=c.execute('SELECT COUNT(*) n FROM reviewer_batches WHERE source_checksum=?',(race_digest,)).fetchone()['n']
    ok('concurrent duplicate batch imports commit exactly one row',count==1 and sum(x[0]=='ok' for x in results)==1)

    # Genuine concurrency: one first review per batch.
    first_race_batch=rw.import_batch(c,rows('RACE-FIRST',2),title='First Assignment Race',filename='first-race.json',created_by=1)
    barrier=threading.Barrier(2); results=[]
    def first_worker(uid):
        conn=app.db(); barrier.wait()
        try: results.append(('ok',rw.create_assignment(conn,batch_id=first_race_batch['batch_id'],reviewer_user_id=uid,created_by=1)['assignment_id']))
        except Exception as exc: results.append(('error',str(exc)))
        finally: conn.close()
    threads=[threading.Thread(target=first_worker,args=(reviewers[i],)) for i in (2,3)]
    [t.start() for t in threads]; [t.join() for t in threads]
    count=c.execute('SELECT COUNT(*) n FROM reviewer_assignments WHERE batch_id=? AND round_no=1',(first_race_batch['batch_id'],)).fetchone()['n']
    ok('concurrent first-review assignments commit exactly one row',count==1 and sum(x[0]=='ok' for x in results)==1)

    # Genuine concurrency: one second-review claim per question.
    second_race_batch=rw.import_batch(c,rows('RACE-SECOND',1),title='Second Assignment Race',filename='second-race.json',created_by=1)
    parent=rw.create_assignment(c,batch_id=second_race_batch['batch_id'],reviewer_user_id=reviewers[4],created_by=1)
    rw.accept_invitation(c,parent['raw_token'],reviewers[4],parent['verification_code'],generate_password_hash('race-parent-password'))
    pi=rw.next_unfinished_item(c,parent['assignment_id']); rw.open_item(c,parent['assignment_id'],pi['id'],reviewers[4])
    rw.submit_decision(c,item_id=pi['id'],reviewer_user_id=reviewers[4],decision='REJECT',mastery_suitability='UNSUITABLE',comments='The question is academically invalid and must be replaced.')
    sqid=c.execute('SELECT question_id FROM reviewer_assignment_items WHERE id=?',(pi['id'],)).fetchone()['question_id']
    barrier=threading.Barrier(2); results=[]
    def second_worker(uid):
        conn=app.db(); barrier.wait()
        try: results.append(('ok',rw.create_assignment(conn,batch_id=second_race_batch['batch_id'],reviewer_user_id=uid,created_by=1,round_no=2,parent_assignment_id=parent['assignment_id'],question_ids=[sqid])['assignment_id']))
        except Exception as exc: results.append(('error',str(exc)))
        finally: conn.close()
    threads=[threading.Thread(target=second_worker,args=(reviewers[i],)) for i in (0,5)]
    [t.start() for t in threads]; [t.join() for t in threads]
    count=c.execute('SELECT COUNT(*) n FROM reviewer_assignment_items WHERE question_id=? AND round_no=2',(sqid,)).fetchone()['n']
    ok('concurrent second-review claims commit exactly one item',count==1 and sum(x[0]=='ok' for x in results)==1)

    invite_template=(ROOT/'templates/reviewer_invite.html').read_text(); admin_template=(ROOT/'templates/admin_reviewer_workspace.html').read_text()
    ok('invitation UI requires a separate code and suppresses token referrers','verification_code' in invite_template and 'no-referrer' in invite_template and 'separate channels' in admin_template)
    ok('release health marker remains compatible with V6.2.7.1+',app.healthz()[0]['version'] in {'6.2.7.1','6.2.7.2','6.2.8','6.2.8.1'})
    c.close(); print(f'\nV6.2.7.1 REVIEWER HARDENING CHECKS PASSED: {len(checks)}')

if __name__=='__main__': main()
