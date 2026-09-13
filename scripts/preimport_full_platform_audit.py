from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import urlsplit

import app as sm

REPORT={"gates":{},"findings":[],"metrics":{},"inventory":{}}


def finding(severity,code,message,evidence=None):
    REPORT["findings"].append({"severity":severity,"code":code,"message":message,"evidence":evidence})


def gate(name,ok,detail=None):
    REPORT["gates"][name]={"status":"PASSED" if ok else "FAILED","detail":detail}
    if not ok:
        finding("P0" if name in {"database_integrity","role_isolation","credential_log_hygiene","zero_question_bank","template_endpoint_integrity"} else "P1",name.upper(),f"Gate failed: {name}",detail)


def table_exists(c,name):
    return bool(c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone())


def columns(c,table):
    if not table_exists(c,table): return set()
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}


def count(c,table):
    return c.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"] if table_exists(c,table) else None


def add_user(c,role,username,system_id):
    cols=columns(c,"users")
    values={"system_user_id":system_id,"role":role,"full_name":role.title()+" Platform Audit","email":username+"@scoremax.test","username":username,"account_status":"active","login_provider":"password","session_version":0,"academic_level":"FSc Part 1","subjects":"Biology,Chemistry,Physics"}
    payload={k:v for k,v in values.items() if k in cols}
    names=','.join(payload); marks=','.join('?' for _ in payload)
    c.execute(f"INSERT INTO users({names}) VALUES({marks})",tuple(payload.values()))
    return c.execute("SELECT * FROM users WHERE username=?",(username,)).fetchone()


def setup_fixtures():
    sm.init()
    c=sm.db()
    try:
        roles={}
        for role in ("student","teacher","parent","admin"):
            roles[role]=add_user(c,role,f"platform-audit-{role}",f"AUD-{role[:3].upper()}-001")
        if table_exists(c,"institutions"):
            ic=columns(c,"institutions")
            vals={"institution_code":"AUD-INS-001","name":"Platform Audit College","province":"Punjab","division":"Lahore","district":"Lahore","board":"Punjab Board","institution_type":"College","active":1}
            p={k:v for k,v in vals.items() if k in ic}
            c.execute(f"INSERT INTO institutions({','.join(p)}) VALUES({','.join('?' for _ in p)})",tuple(p.values()))
            inst=c.execute("SELECT id FROM institutions WHERE institution_code='AUD-INS-001'").fetchone()
            if inst and "primary_institution_id" in columns(c,"users"):
                c.execute("UPDATE users SET primary_institution_id=? WHERE id IN (?,?)",(inst["id"],roles["teacher"]["id"],roles["student"]["id"]))
        if table_exists(c,"classrooms"):
            cc=columns(c,"classrooms")
            vals={"teacher_id":roles["teacher"]["id"],"institution_id":None,"name":"Audit Biology","level":"FSc Part 1","subject":"Biology","join_code":"AUDITBIO"}
            p={k:v for k,v in vals.items() if k in cc}
            c.execute(f"INSERT INTO classrooms({','.join(p)}) VALUES({','.join('?' for _ in p)})",tuple(p.values()))
            cl=c.execute("SELECT id FROM classrooms WHERE join_code='AUDITBIO'").fetchone()
            if cl and table_exists(c,"classroom_students"):
                cs=columns(c,"classroom_students")
                if {"classroom_id","student_id"}.issubset(cs):
                    vals={"classroom_id":cl["id"],"student_id":roles["student"]["id"],"roll_no":"AUD-01"}
                    p={k:v for k,v in vals.items() if k in cs}
                    c.execute(f"INSERT OR IGNORE INTO classroom_students({','.join(p)}) VALUES({','.join('?' for _ in p)})",tuple(p.values()))
        c.commit()
        return {k:dict(v) for k,v in roles.items()}
    finally:
        c.close()


def audit_database(roles):
    c=sm.db()
    try:
        integrity=c.execute("PRAGMA integrity_check").fetchone()[0]
        fk=c.execute("PRAGMA foreign_key_check").fetchall()
        gate("database_integrity",integrity=="ok" and len(fk)==0,{"integrity_check":integrity,"foreign_key_violations":len(fk)})
        tables=[r["name"] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]
        REPORT["inventory"]["tables"]={t:count(c,t) for t in tables}
        REPORT["metrics"]["table_count"]=len(tables)

        # A governed bank must be genuinely empty immediately before content import.
        qn=count(c,"questions") or 0
        gate("zero_question_bank",qn==0,{"question_count":qn})
        cn=count(c,"curriculum") or 0
        if cn and qn==0:
            finding("P1","ORPHAN_CURRICULUM_PREIMPORT","Curriculum rows exist while the governed question bank is empty.",{"curriculum_rows":cn})

        # No default commercial catalogue or hidden prices.
        packages=[]
        if table_exists(c,"coverage_packages"):
            packages=[dict(r) for r in c.execute("SELECT code,name,programme,price_minor,status FROM coverage_packages ORDER BY id").fetchall()]
        gate("commercial_catalogue_empty",len(packages)==0,{"coverage_packages":packages})
        if table_exists(c,"plans"):
            priced=[dict(r) for r in c.execute("SELECT code,name,audience,price_minor,active FROM plans WHERE COALESCE(price_minor,0)>0 ORDER BY code").fetchall()]
            gate("no_seeded_plan_prices",len(priced)==0,{"priced_plans":priced})

        # Identity uniqueness and required opaque IDs.
        dup=[]
        for col in ("email","username","system_user_id"):
            if col in columns(c,"users"):
                rows=c.execute(f"SELECT lower({col}) value,COUNT(*) n FROM users WHERE COALESCE({col},'')<>'' GROUP BY lower({col}) HAVING COUNT(*)>1").fetchall()
                dup.extend({"field":col,"value":r["value"],"count":r["n"]} for r in rows)
        gate("identity_uniqueness",not dup,{"duplicates":dup})

        # Manual orphan checks for tables whose historical schemas do not always declare FK constraints.
        relationships=[
            ("classrooms","teacher_id","users","id"),("classroom_students","classroom_id","classrooms","id"),("classroom_students","student_id","users","id"),
            ("attempts","student_id","users","id"),("attempt_answers","attempt_id","attempts","id"),("attempt_answers","question_db_id","questions","id"),
            ("assessment_sessions","student_id","users","id"),("subscriptions","user_id","users","id"),("subscriptions","plan_id","plans","id"),
            ("payment_transactions","user_id","users","id"),("student_package_entitlements","student_id","users","id"),("student_package_entitlements","coverage_package_id","coverage_packages","id"),
            ("checkout_requests","student_id","users","id"),("checkout_requests","coverage_package_id","coverage_packages","id"),
            ("challenge_questions","challenge_id","challenges","id"),("challenge_questions","question_id","questions","id"),("challenge_entries","challenge_id","challenges","id"),("challenge_entries","student_id","users","id"),
        ]
        orphans=[]
        for child,child_col,parent,parent_col in relationships:
            if table_exists(c,child) and table_exists(c,parent) and child_col in columns(c,child) and parent_col in columns(c,parent):
                n=c.execute(f"SELECT COUNT(*) n FROM {child} x LEFT JOIN {parent} p ON p.{parent_col}=x.{child_col} WHERE x.{child_col} IS NOT NULL AND p.{parent_col} IS NULL").fetchone()["n"]
                if n: orphans.append({"child":child,"column":child_col,"parent":parent,"count":n})
        gate("relationship_orphans",not orphans,{"orphans":orphans})

        # Hierarchy and catalogue consistency for whatever content physically exists now.
        hierarchy={}
        if table_exists(c,"questions"):
            qc=columns(c,"questions")
            dims=[x for x in ("programme","qualification","subject","chapter","topic","subtopic") if x in qc]
            hierarchy["question_dimensions"]=dims
            if dims and qn:
                blanks={d:c.execute(f"SELECT COUNT(*) n FROM questions WHERE COALESCE(trim({d}),'')='' AND COALESCE(status,'Approved') NOT IN ('Discarded','Rejected')").fetchone()["n"] for d in dims[:5]}
                bad={k:v for k,v in blanks.items() if v}
                if bad: finding("P0","QUESTION_HIERARCHY_BLANKS","Learner question hierarchy contains required blank dimensions.",bad)
                combos=c.execute("SELECT DISTINCT "+','.join(dims)+" FROM questions ORDER BY "+','.join(dims)).fetchall()
                hierarchy["question_combinations"]=[list(r) for r in combos[:5000]]
        if table_exists(c,"curriculum"):
            dims=[x for x in ("programme","subject","chapter","topic","subtopic") if x in columns(c,"curriculum")]
            hierarchy["curriculum_dimensions"]=dims
            if dims:
                hierarchy["curriculum_combinations"]=[list(r) for r in c.execute("SELECT DISTINCT "+','.join(dims)+" FROM curriculum ORDER BY "+','.join(dims)).fetchall()[:5000]]
        REPORT["inventory"]["hierarchy"]=hierarchy

        # Programme constants must not duplicate or contain empty labels/codes.
        choices=getattr(sm,"STUDENT_PROGRAMME_CHOICES",[])
        dup_codes=[x[0] for x in __import__('collections').Counter(str(p.get('code','')).lower() for p in choices).items() if x[1]>1]
        dup_labels=[x[0] for x in __import__('collections').Counter(str(p.get('label','')).lower() for p in choices).items() if x[1]>1]
        malformed=[p for p in choices if not p.get('code') or not p.get('label') or not p.get('value')]
        gate("programme_choice_integrity",not dup_codes and not dup_labels and not malformed,{"choices":choices,"duplicate_codes":dup_codes,"duplicate_labels":dup_labels,"malformed":malformed})
    finally:
        c.close()


def make_client(role,roles):
    client=sm.app.test_client()
    if role!="anonymous":
        row=roles[role]
        with client.session_transaction() as s:
            s["user_id"]=row["id"]; s["role"]=role; s["full_name"]=row.get("full_name") or role.title(); s["session_version"]=int(row.get("session_version") or 0)
    return client


def audit_templates():
    root=Path(__file__).resolve().parents[1]/"scoremax_runtime_v669b"
    templates=root/"templates"
    static=root/"static"
    endpoints={r.endpoint for r in sm.app.url_map.iter_rules()}
    broken=[]; missing_static=[]; dead=[]; scanned=0
    for p in templates.rglob("*.html"):
        scanned+=1
        text=p.read_text(encoding="utf-8",errors="replace")
        for ep in sorted(set(re.findall(r"url_for\(['\"]([^'\"]+)",text))):
            if ep not in endpoints:
                broken.append({"template":str(p.relative_to(root)),"endpoint":ep})
        for fn in re.findall(r"url_for\(['\"]static['\"],\s*filename\s*=\s*['\"]([^'\"]+)",text):
            if not (static/fn).is_file(): missing_static.append({"template":str(p.relative_to(root)),"file":fn})
        for token in ("href=\"#\"","href='#'","javascript:void","TODO","FIXME"):
            if token.lower() in text.lower(): dead.append({"template":str(p.relative_to(root)),"token":token})
    REPORT["metrics"]["templates_scanned"]=scanned
    gate("template_endpoint_integrity",not broken,{"broken":broken})
    gate("static_asset_integrity",not missing_static,{"missing":missing_static})
    # '#' can be deliberate anchors; retain as evidence rather than hard failure.
    if dead: finding("P2","STATIC_DEAD_END_MARKERS","Templates contain placeholder/TODO-like markers requiring later UX review.",dead[:100])


def audit_routes(roles):
    rules=sorted(sm.app.url_map.iter_rules(),key=lambda r:(r.rule,r.endpoint))
    REPORT["metrics"]["route_count"]=len(rules)
    REPORT["inventory"]["routes"]=[{"rule":r.rule,"endpoint":r.endpoint,"methods":sorted(m for m in r.methods if m not in {'HEAD','OPTIONS'}),"arguments":sorted(r.arguments)} for r in rules]
    parameterless=[r for r in rules if "GET" in r.methods and not r.arguments and not r.rule.startswith('/static/')]
    failures=[]; statuses=defaultdict(lambda:defaultdict(int))
    roles_to_probe=("anonymous","student","teacher","parent","admin")
    for role in roles_to_probe:
        client=make_client(role,roles)
        for r in parameterless:
            try:
                resp=client.get(r.rule,follow_redirects=False)
                statuses[role][str(resp.status_code)]+=1
                if resp.status_code>=500:
                    failures.append({"role":role,"rule":r.rule,"endpoint":r.endpoint,"status":resp.status_code})
            except Exception as e:
                failures.append({"role":role,"rule":r.rule,"endpoint":r.endpoint,"exception":repr(e)})
    REPORT["inventory"]["route_statuses"]={k:dict(v) for k,v in statuses.items()}
    gate("parameterless_route_runtime",not failures,{"failures":failures,"probed":len(parameterless)*len(roles_to_probe)})

    # Hard role fences.
    checks=[]
    protected={
        "admin":["/admin","/admin/users","/admin/interests","/admin/payments","/admin/integration-health"],
    }
    for owner,paths in protected.items():
        for role in ("student","teacher","parent"):
            client=make_client(role,roles)
            for path in paths:
                resp=client.get(path,follow_redirects=False)
                leak=resp.status_code==200 and ("SCOREMAX ADMIN" in resp.get_data(as_text=True) or "Interest & Demand" in resp.get_data(as_text=True))
                checks.append({"owner":owner,"role":role,"path":path,"status":resp.status_code,"leak":leak})
    gate("role_isolation",not any(x["leak"] for x in checks),checks)

    # Crawl every internal href rendered from parameterless pages for each role.
    crawl_fail=[]; crawl_metrics={}; ignored_prefixes=("mailto:","tel:","javascript:","#")
    for role in roles_to_probe:
        client=make_client(role,roles)
        seeds={r.rule for r in parameterless}
        queue=deque(sorted(seeds)); seen=set(); checked=0
        while queue and len(seen)<2500:
            path=queue.popleft()
            if path in seen: continue
            seen.add(path)
            try: resp=client.get(path,follow_redirects=False)
            except Exception as e:
                crawl_fail.append({"role":role,"path":path,"exception":repr(e)}); continue
            checked+=1
            if resp.status_code>=500:
                crawl_fail.append({"role":role,"path":path,"status":resp.status_code}); continue
            if resp.status_code!=200 or "text/html" not in (resp.content_type or ""): continue
            html=resp.get_data(as_text=True)
            for href in re.findall(r"href\s*=\s*['\"]([^'\"]+)",html,re.I):
                href=href.strip()
                if not href or href.startswith(ignored_prefixes): continue
                parts=urlsplit(href)
                if parts.scheme or parts.netloc: continue
                target=parts.path or '/'
                if target.startswith('/static/'): continue
                full=target+(("?"+parts.query) if parts.query else "")
                if full not in seen: queue.append(full)
        crawl_metrics[role]={"pages_checked":checked,"unique_paths":len(seen)}
    REPORT["inventory"]["crawl_metrics"]=crawl_metrics
    gate("rendered_internal_link_runtime",not crawl_fail,{"failures":crawl_fail[:200],"total_failures":len(crawl_fail)})


def audit_security_source():
    app_text=Path(__file__).resolve().parents[1].joinpath("scoremax_runtime_v669b","app.py").read_text(encoding="utf-8",errors="replace")
    forbidden=("One-time bootstrap admin created: admin /","New one-time local password: admin /")
    gate("credential_log_hygiene",not any(x in app_text for x in forbidden),{"forbidden_found":[x for x in forbidden if x in app_text]})
    # Academic review must stay outside normal ScoreMax admin navigation.
    base=Path(__file__).resolve().parents[1].joinpath("scoremax_runtime_v669b","templates","base.html").read_text(encoding="utf-8",errors="replace")
    admin_start=base.find("session.get('role')=='admin'")
    admin_end=base.find("{% else %}",admin_start)
    block=base[admin_start:admin_end] if admin_start>=0 and admin_end>admin_start else ''
    forbidden_nav=[x for x in ("Reviewer Workspace","Question Families","Governance Audit","Direct Intake","Power House Bridge") if x in block]
    gate("power_house_boundary",not forbidden_nav,{"forbidden_admin_nav":forbidden_nav})


def main():
    roles=setup_fixtures()
    audit_database(roles)
    audit_templates()
    audit_routes(roles)
    audit_security_source()
    hard=[f for f in REPORT["findings"] if f["severity"] in ("P0","P1")]
    REPORT["summary"]={"p0":sum(f["severity"]=="P0" for f in REPORT["findings"]),"p1":sum(f["severity"]=="P1" for f in REPORT["findings"]),"p2":sum(f["severity"]=="P2" for f in REPORT["findings"]),"hard_fail":bool(hard)}
    print("SCOREMAX_PREIMPORT_AUDIT="+json.dumps(REPORT,sort_keys=True,default=str))
    Path("/tmp/scoremax_preimport_audit.json").write_text(json.dumps(REPORT,indent=2,sort_keys=True,default=str),encoding="utf-8")
    if hard:
        raise SystemExit(2)


if __name__=="__main__":
    main()
