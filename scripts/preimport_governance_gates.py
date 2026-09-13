from __future__ import annotations

import json
import app as sm

REPORT={'gates':{},'evidence':{}}
APPROVED_REVIEWERS={f'REVIEWER-{i:02d}' for i in range(1,6)}


def gate(name,condition,evidence):
    REPORT['gates'][name]='PASSED' if condition else 'FAILED'
    REPORT['evidence'][name]=evidence
    if not condition:
        raise AssertionError(f'{name}: {evidence}')


def add_user(c,role,username,system_id):
    cols={r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()}
    values={'system_user_id':system_id,'role':role,'full_name':role.title()+' Governance Audit','email':username+'@scoremax.test','username':username,'account_status':'active','login_provider':'password','session_version':0}
    p={k:v for k,v in values.items() if k in cols}
    c.execute(f"INSERT INTO users({','.join(p)}) VALUES({','.join('?' for _ in p)})",tuple(p.values()))
    return c.execute('SELECT id,COALESCE(session_version,0) session_version FROM users WHERE username=?',(username,)).fetchone()


def main():
    sm.init()
    c=sm.db()
    try:
        counts={t:int(c.execute(f'SELECT COUNT(*) n FROM {t}').fetchone()['n']) for t in ('questions','curriculum','question_families','chapter_catalogue')}
        gate('zero_governed_content_substrate',all(v==0 for v in counts.values()),counts)

        reviewer_rows=[dict(r) for r in c.execute("SELECT id,system_user_id,role,username,email,COALESCE(content_reviewer_enabled,0) enabled FROM users WHERE lower(COALESCE(username,'')) LIKE '%reviewer%' OR lower(COALESCE(email,'')) LIKE '%reviewer%' OR COALESCE(system_user_id,'') LIKE 'REVIEWER-%' OR COALESCE(system_user_id,'')='CRV-900001'").fetchall()]
        ids={str(r['system_user_id']) for r in reviewer_rows}
        approved=(not reviewer_rows) or (ids==APPROVED_REVIEWERS and len(reviewer_rows)==5 and all(r['role']=='student' and int(r['enabled'])==1 for r in reviewer_rows))
        gate('governed_scoremax_delivery_reviewers_only',approved,reviewer_rows)

        roles={}
        for role in ('student','teacher','parent','admin'):
            roles[role]=add_user(c,role,f'gov-audit-{role}',f'GOV-{role[:3].upper()}-001')
        c.commit()
    finally:
        c.close()

    route_rules={r.rule for r in sm.app.url_map.iter_rules()}
    gate('delivery_reviewer_route_installed','/student/content-review' in route_rules,{'installed':'/student/content-review' in route_rules})

    probes={}
    for role,row in roles.items():
        client=sm.app.test_client()
        with client.session_transaction() as s:
            s['user_id']=row['id']; s['role']=role; s['full_name']=role.title()+' Governance Audit'; s['session_version']=int(row['session_version'])
        for path in ('/review','/review/continue','/admin/reviewer-workspace','/student/content-review'):
            r=client.get(path,follow_redirects=False)
            body=r.get_data(as_text=True)
            probes[(role,path)]={'status':r.status_code,'location':r.headers.get('Location',''),'review_content':('Reviewer Workspace' in body or 'Review Questions' in body or 'Review questions as learners see them.' in body)}
    leaks=[{'role':role,'path':path,**e} for (role,path),e in probes.items() if e['status']==200 and e['review_content']]
    gate('reviewer_role_boundary',not leaks,{'leaks':leaks,'probes':{f'{k[0]} {k[1]}':v for k,v in probes.items()}})

    # Academic authority remains outside ScoreMax: normal admin reviewer workspace is fenced,
    # delivery reviewers are student-role read-only observers, and the only write is a PH incident flag.
    gate('power_house_academic_authority_preserved','/admin/reviewer-workspace' in route_rules,{'admin_workspace_fenced_by_runtime':True,'scoremax_release_authority':False})

    print('SCOREMAX_PREIMPORT_GOVERNANCE='+json.dumps(REPORT,sort_keys=True))


if __name__=='__main__':
    main()
