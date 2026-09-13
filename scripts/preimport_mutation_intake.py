from __future__ import annotations
import app as sm

def cols(c,t): return {r['name'] for r in c.execute(f'PRAGMA table_info({t})').fetchall()}
def add_admin(c):
    v={'system_user_id':'MUT-ADI','role':'admin','full_name':'Mutation Intake Admin','email':'mutation-intake-admin@scoremax.test','username':'mutation-intake-admin','account_status':'active','login_provider':'password','session_version':0}
    cc=cols(c,'users'); p={k:x for k,x in v.items() if k in cc}; c.execute(f"INSERT INTO users({','.join(p)}) VALUES({','.join('?' for _ in p)})",tuple(p.values())); return c.execute("SELECT * FROM users WHERE username='mutation-intake-admin'").fetchone()
def client(row):
    x=sm.app.test_client()
    with x.session_transaction() as s: s.update(user_id=row['id'],role=row['role'],full_name=row['full_name'],session_version=int(row['session_version'] or 0))
    x.get('/admin')
    with x.session_transaction() as s: token=s.get('_csrf_token')
    return x,token
sm.init(); c=sm.db(); admin=add_admin(c); c.commit(); c.close()
p=sm.app.test_client(); p.get('/register-interest?programme=ECAT')
with p.session_transaction() as s: tok=s.get('_csrf_token')
r=p.post('/register-interest?programme=ECAT',data={'_csrf_token':tok,'programme':'ECAT','full_name':'Mutation Interest','email':'mutation-interest@example.com','mobile':'03001234567','role':'Student','school':'Mutation College','city':'Lahore'},follow_redirects=False)
c=sm.db(); i=c.execute("SELECT * FROM ux_interest_registrations WHERE email='mutation-interest@example.com'").fetchone(); c.close(); assert r.status_code==200 and i and i['programme']=='ECAT'
a,tok=client(admin); c=sm.db(); before=c.execute('SELECT COUNT(*) n FROM questions').fetchone()['n']; c.close(); r=a.post('/admin/import',data={'_csrf_token':tok},follow_redirects=False); c=sm.db(); after=c.execute('SELECT COUNT(*) n FROM questions').fetchone()['n']; c.close(); assert r.status_code<500 and before==after==0
print('PREIMPORT_MUTATION_INTAKE_PASS')
