from __future__ import annotations
import app as sm

def cols(c,t): return {r['name'] for r in c.execute(f'PRAGMA table_info({t})').fetchall()}
def add(c,role,name,sid):
    v={'system_user_id':sid,'role':role,'full_name':name,'email':name.lower().replace(' ','-')+'@scoremax.test','username':name.lower().replace(' ','-'),'account_status':'active','login_provider':'password','session_version':0,'academic_level':'FSc Part 1','subjects':'Biology,Chemistry,Physics'}
    cc=cols(c,'users'); p={k:x for k,x in v.items() if k in cc}; c.execute(f"INSERT INTO users({','.join(p)}) VALUES({','.join('?' for _ in p)})",tuple(p.values())); return c.execute('SELECT * FROM users WHERE username=?',(v['username'],)).fetchone()
def client(row):
    x=sm.app.test_client()
    with x.session_transaction() as s: s.update(user_id=row['id'],role=row['role'],full_name=row['full_name'],session_version=int(row['session_version'] or 0))
    x.get('/dashboard')
    with x.session_transaction() as s: token=s.get('_csrf_token')
    return x,token
sm.init(); c=sm.db(); teacher=add(c,'teacher','Mutation Teacher','MUT-TCH'); student=add(c,'student','Mutation Student Core','MUT-STC'); admin=add(c,'admin','Mutation Admin Core','MUT-ADC'); c.commit(); c.close()
t,tok=client(teacher); r=t.post('/teacher/create',data={'_csrf_token':tok,'name':'Mutation Biology','level':'FSc Part 1','subject':'Biology'},follow_redirects=False)
c=sm.db(); room=c.execute("SELECT * FROM classrooms WHERE teacher_id=? AND name='Mutation Biology'",(teacher['id'],)).fetchone(); c.close(); assert r.status_code==302 and room
s,tok=client(student); r=s.post('/student/join',data={'_csrf_token':tok,'join_code':room['join_code'],'roll_no':'M-01'},follow_redirects=False)
c=sm.db(); member=c.execute('SELECT * FROM classroom_students WHERE classroom_id=? AND student_id=?',(room['id'],student['id'])).fetchone(); c.close(); assert r.status_code==302 and member
s,tok=client(student); c=sm.db(); before=c.execute('SELECT COUNT(*) n FROM attempts WHERE student_id=?',(student['id'],)).fetchone()['n']; c.close(); r=s.post('/student/demo-progress',data={'_csrf_token':tok},follow_redirects=False); c=sm.db(); after=c.execute('SELECT COUNT(*) n FROM attempts WHERE student_id=?',(student['id'],)).fetchone()['n']; c.close(); assert r.status_code==302 and before==after
a,tok=client(admin); r=a.get('/admin/reviewer-workspace',follow_redirects=False); assert r.status_code==302 and '/admin/integration-health' in (r.headers.get('Location') or '')
for path in ('/test/setup','/student/subjects','/student/weak-areas','/student/mastery','/exam-centre'):
    rr=s.get(path,follow_redirects=False); assert rr.status_code<500,(path,rr.status_code)
c=sm.db(); assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; assert not c.execute('PRAGMA foreign_key_check').fetchall(); assert c.execute('SELECT COUNT(*) n FROM questions').fetchone()['n']==0; c.close()
print('PREIMPORT_MUTATION_CORE_PASS')
