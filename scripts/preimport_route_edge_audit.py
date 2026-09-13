from __future__ import annotations
import json
from collections import defaultdict
import app as sm

R={'get_failures':[],'mutation_failures':[],'counts':defaultdict(int)}

def cols(c,t): return {r['name'] for r in c.execute(f'PRAGMA table_info({t})').fetchall()}
def add(c,role,name,sid):
    v={'system_user_id':sid,'role':role,'full_name':name,'email':name.lower().replace(' ','-')+'@scoremax.test','username':name.lower().replace(' ','-'),'account_status':'active','login_provider':'password','session_version':0,'academic_level':'FSc Part 1','subjects':'Biology,Chemistry,Physics'}
    cc=cols(c,'users'); p={k:x for k,x in v.items() if k in cc}; c.execute(f"INSERT INTO users({','.join(p)}) VALUES({','.join('?' for _ in p)})",tuple(p.values())); return c.execute('SELECT * FROM users WHERE username=?',(v['username'],)).fetchone()
def client(row=None):
    x=sm.app.test_client()
    if row:
        with x.session_transaction() as s: s.update(user_id=row['id'],role=row['role'],full_name=row['full_name'],session_version=int(row['session_version'] or 0))
        x.get('/dashboard',follow_redirects=False)
    with x.session_transaction() as s: token=s.get('_csrf_token')
    return x,token
def vals(rule):
    out={}
    for arg in rule.arguments:
        conv=rule._converters[arg].__class__.__name__.lower()
        if 'int' in conv: out[arg]=999999
        elif 'float' in conv: out[arg]=999999.0
        elif 'uuid' in conv: out[arg]='00000000-0000-0000-0000-000000000000'
        else: out[arg]='audit-missing'
    return out

def intended_role(path):
    if path.startswith('/admin'): return 'admin'
    if path.startswith('/teacher'): return 'teacher'
    if path.startswith('/student') or path.startswith('/test') or path.startswith('/exam-centre') or path.startswith('/written-practice') or path.startswith('/challenges'): return 'student'
    if path.startswith('/parent'): return 'parent'
    return None

sm.init(); c=sm.db(); roles={r:add(c,r,'Edge '+r.title(),'EDGE-'+r[:3].upper()) for r in ('student','teacher','parent','admin')}; c.commit(); c.close()
adapter=sm.app.url_map.bind('localhost')
rules=sorted(sm.app.url_map.iter_rules(),key=lambda r:(r.rule,r.endpoint))
# Every parameterized GET must fail safely (never 5xx) for every ordinary role and anonymous.
for rule in rules:
    if 'GET' not in rule.methods or not rule.arguments or rule.endpoint=='static': continue
    try: path=adapter.build(rule.endpoint,vals(rule),force_external=False)
    except Exception as e:
        R['get_failures'].append({'endpoint':rule.endpoint,'rule':rule.rule,'build_error':repr(e)}); continue
    for role in (None,'student','teacher','parent','admin'):
        x,_=client(roles.get(role) if role else None)
        try:
            resp=x.get(path,follow_redirects=False); R['counts']['parameterized_get_probes']+=1
            if resp.status_code>=500: R['get_failures'].append({'role':role or 'anonymous','path':path,'endpoint':rule.endpoint,'status':resp.status_code})
        except Exception as e: R['get_failures'].append({'role':role or 'anonymous','path':path,'endpoint':rule.endpoint,'exception':repr(e)})
# Every mutation route gets malformed-request probes. Anonymous must never 5xx; inferred owning role must never 5xx with valid CSRF but empty payload.
for rule in rules:
    methods=[m for m in rule.methods if m in {'POST','PUT','PATCH','DELETE'}]
    if not methods: continue
    try: path=adapter.build(rule.endpoint,vals(rule),force_external=False)
    except Exception as e:
        R['mutation_failures'].append({'endpoint':rule.endpoint,'rule':rule.rule,'build_error':repr(e)}); continue
    method=methods[0]
    x,_=client(None)
    try:
        resp=x.open(path,method=method,data={},follow_redirects=False); R['counts']['anonymous_mutation_probes']+=1
        if resp.status_code>=500: R['mutation_failures'].append({'role':'anonymous','method':method,'path':path,'endpoint':rule.endpoint,'status':resp.status_code})
    except Exception as e: R['mutation_failures'].append({'role':'anonymous','method':method,'path':path,'endpoint':rule.endpoint,'exception':repr(e)})
    role=intended_role(path)
    if role:
        x,tok=client(roles[role]); data={'_csrf_token':tok} if tok else {}
        try:
            resp=x.open(path,method=method,data=data,follow_redirects=False); R['counts']['owned_mutation_probes']+=1
            if resp.status_code>=500: R['mutation_failures'].append({'role':role,'method':method,'path':path,'endpoint':rule.endpoint,'status':resp.status_code})
        except Exception as e: R['mutation_failures'].append({'role':role,'method':method,'path':path,'endpoint':rule.endpoint,'exception':repr(e)})
print('SCOREMAX_ROUTE_EDGE_AUDIT='+json.dumps({'counts':dict(R['counts']),'get_failures':R['get_failures'],'mutation_failures':R['mutation_failures']},sort_keys=True))
assert not R['get_failures'],R['get_failures']
assert not R['mutation_failures'],R['mutation_failures']
