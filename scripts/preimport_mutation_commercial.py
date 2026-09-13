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
sm.init(); c=sm.db(); admin=add(c,'admin','Mutation Admin','MUT-ADM'); student=add(c,'student','Mutation Student','MUT-STU'); c.commit(); c.close()
a,t=client(admin); r=a.post('/admin/payments',data={'_csrf_token':t,'action':'coverage_package','code':'audit_biology','name':'Audit Biology','programme':'FSc Part 1','coverage_type':'SUBJECTS','subjects':'Biology','price':'1250','currency':'PKR','billing_period':'monthly','package_status':'ACTIVE'},follow_redirects=False)
c=sm.db(); p=c.execute("SELECT * FROM coverage_packages WHERE code='audit_biology'").fetchone(); c.close(); assert r.status_code==302 and p and int(p['price_minor'])==125000
s,t=client(student); r=s.post('/account/access',data={'_csrf_token':t,'coverage_package_id':p['id'],'access_plan_code':'level_1_access'},follow_redirects=False)
c=sm.db(); q=c.execute('SELECT * FROM checkout_requests WHERE student_id=? AND coverage_package_id=?',(student['id'],p['id'])).fetchone(); c.close(); assert r.status_code==302 and q
print('PREIMPORT_MUTATION_COMMERCIAL_PASS')
