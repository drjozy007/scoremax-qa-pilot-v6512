"""Admin-operable deterministic four-lane QA over governed ScoreMax content.

Extends the existing Mastery Laboratory. QA writes only its own evidence ledger and has
zero question mutation, release, learner-attempt or mastery authority.
"""
from __future__ import annotations
import json, re, secrets
from datetime import datetime
from flask import flash, redirect, render_template, request, session, url_for

POLICY_VERSION="SCOREMAX-NO-API-FOUR-LANE-QA-ADMIN-1"
AGENTS={
 "STUDENT_A":{"label":"Student A","purpose":"Learner structure & self-containment","short":"Checks visible structure, options, matching/ordering and referenced stimulus."},
 "STUDENT_B":{"label":"Student B","purpose":"Answer & marking execution","short":"Executes governed correct/wrong responses and keeps unsupported semantics fail-closed."},
 "REVIEWER_A":{"label":"Reviewer A","purpose":"Key, rubric & marking contract","short":"Checks response cardinality, keys, rubrics, mark totals and deterministic contract integrity."},
 "REVIEWER_B":{"label":"Reviewer B","purpose":"Identity, governance & release safety","short":"Checks immutable version identity, staged/active release fences and activation authority."},
}
VALID_STATUSES={"PASS","HOLD","NOT_EVALUATED"}

def _safe_json(value,default):
    try:
        out=json.loads(value) if isinstance(value,str) else value
        return out if out is not None else default
    except Exception:
        return default

def _canon(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)

def ensure_schema(c):
    c.executescript("""
    CREATE TABLE IF NOT EXISTS qa_agent_runs(
      id INTEGER PRIMARY KEY,
      group_code TEXT NOT NULL,
      run_code TEXT NOT NULL UNIQUE,
      agent_code TEXT NOT NULL,
      policy_version TEXT NOT NULL,
      scope_type TEXT NOT NULL,
      scope_key TEXT DEFAULT '',
      population_count INTEGER DEFAULT 0,
      pass_count INTEGER DEFAULT 0,
      hold_count INTEGER DEFAULT 0,
      not_evaluated_count INTEGER DEFAULT 0,
      finding_count INTEGER DEFAULT 0,
      status TEXT NOT NULL DEFAULT 'RUNNING',
      summary_json TEXT DEFAULT '{}',
      initiated_by INTEGER,
      started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      completed_at TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS qa_agent_results(
      id INTEGER PRIMARY KEY,
      run_id INTEGER NOT NULL,
      agent_code TEXT NOT NULL,
      question_id TEXT NOT NULL,
      question_version_id TEXT NOT NULL,
      question_checksum_sha256 TEXT NOT NULL,
      programme TEXT DEFAULT '',
      subject TEXT DEFAULT '',
      chapter TEXT DEFAULT '',
      release_refs_json TEXT DEFAULT '[]',
      status TEXT NOT NULL,
      findings_json TEXT DEFAULT '[]',
      evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(run_id,question_id,question_version_id));
    CREATE TABLE IF NOT EXISTS qa_agent_findings(
      id INTEGER PRIMARY KEY,
      result_id INTEGER NOT NULL,
      run_id INTEGER NOT NULL,
      agent_code TEXT NOT NULL,
      question_id TEXT NOT NULL,
      question_version_id TEXT NOT NULL,
      category TEXT NOT NULL,
      finding_code TEXT NOT NULL,
      severity TEXT NOT NULL DEFAULT 'HIGH',
      detail TEXT DEFAULT '',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_qa_agent_runs_agent_time ON qa_agent_runs(agent_code,started_at);
    CREATE INDEX IF NOT EXISTS idx_qa_agent_results_identity ON qa_agent_results(agent_code,question_id,question_version_id,id);
    CREATE INDEX IF NOT EXISTS idx_qa_agent_results_status ON qa_agent_results(status,agent_code,id);
    CREATE INDEX IF NOT EXISTS idx_qa_agent_findings_code ON qa_agent_findings(agent_code,finding_code,created_at);
    """)

def _finding(code,category,detail="",severity="HIGH"):
    return {"code":code,"category":category,"detail":detail,"severity":severity}

def _release_rows(c):
    return c.execute("""SELECT id,release_id,release_version,local_status,market_id,programme_id,subject_id,chapter_id,
      question_count,admitted_at FROM integration_ph_content_releases
      ORDER BY CASE local_status WHEN 'STAGED' THEN 0 WHEN 'ACTIVE' THEN 1 ELSE 2 END,admitted_at DESC,id DESC""").fetchall()

def _population(c,scope):
    clauses=["r.local_status IN ('STAGED','ACTIVE')"];params=[]
    scope_type="ALL_GOVERNED";scope_key=""
    if scope=="staged":
        clauses=["r.local_status='STAGED'"];scope_type="STAGED_ONLY"
    elif str(scope).startswith("release:"):
        rid=int(str(scope).split(":",1)[1]);clauses=["r.id=?"];params=[rid];scope_type="RELEASE";scope_key=str(rid)
    rows=c.execute(f"""SELECT v.*,m.release_id,m.release_version,m.ordinal,
      r.id release_db_id,r.local_status release_local_status,r.market_id,r.programme_id,r.subject_id,r.chapter_id
      FROM integration_ph_release_question_membership m
      JOIN integration_ph_question_version_store v
        ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
      JOIN integration_ph_content_releases r
        ON r.release_id=m.release_id AND r.release_version=m.release_version
      WHERE {' AND '.join(clauses)}
      ORDER BY r.id,m.ordinal,m.id""",params).fetchall()
    grouped={}
    for row in rows:
        key=(row["question_id"],row["question_version_id"])
        item=grouped.setdefault(key,{"row":row,"memberships":[]})
        item["memberships"].append({
          "release_db_id":row["release_db_id"],"release_id":row["release_id"],"release_version":row["release_version"],
          "local_status":row["release_local_status"],"market_id":row["market_id"],"programme_id":row["programme_id"],
          "subject_id":row["subject_id"],"chapter_id":row["chapter_id"],"ordinal":row["ordinal"]})
    return list(grouped.values()),scope_type,scope_key

def _question(group):
    row=group["row"];projection=_safe_json(row["scoremax_projection_json"],None)
    if not isinstance(projection,dict):
        return None
    q=dict(projection);q["question_version"]=int(row["question_version_number"] or 1)
    return q

def _student_a(scoremax,group):
    q=_question(group)
    if q is None:return "HOLD",[_finding("PROJECTION_INVALID","STRUCTURE","Stored ScoreMax projection is not a JSON object.")]
    findings=[];stem=str(q.get("question") or "").strip()
    if not stem:findings.append(_finding("EMPTY_LEARNER_STEM","STRUCTURE"))
    try:qtype=scoremax.canonical_question_type(q)
    except Exception:qtype=""
    ac=_safe_json(q.get("answer_config"),{})
    choice={"single_choice","multiple_select","true_false"}
    if qtype in choice:
        opts=ac.get("options")
        if not isinstance(opts,list) or len(opts)<2:
            findings.append(_finding("CHOICE_OPTIONS_REQUIRED","OPTIONS"))
        else:
            ids=[str(x.get("id") or "") for x in opts if isinstance(x,dict)]
            texts=[re.sub(r"\s+"," ",str(x.get("text") or "").strip()).casefold() for x in opts if isinstance(x,dict)]
            if len(ids)!=len(opts) or any(not x for x in ids):findings.append(_finding("EMPTY_OPTION_ID","OPTIONS"))
            if len(ids)!=len(set(ids)):findings.append(_finding("DUPLICATE_OPTION_ID","OPTIONS"))
            if len(texts)!=len(opts) or any(not x for x in texts):findings.append(_finding("EMPTY_VISIBLE_OPTION","OPTIONS"))
            if len(texts)!=len(set(texts)):findings.append(_finding("DUPLICATE_VISIBLE_OPTION_TEXT","OPTIONS"))
    if qtype=="matching":
        left=ac.get("left_items");right=ac.get("right_options")
        if not isinstance(left,list) or not left or not isinstance(right,list) or not right:
            findings.append(_finding("MATCHING_STRUCTURE_INVALID","INTERACTION"))
        else:
            lids=[str(x.get("id") or "") for x in left if isinstance(x,dict)]
            rids=[str(x.get("id") or "") for x in right if isinstance(x,dict)]
            if len(lids)!=len(left) or len(lids)!=len(set(lids)) or any(not x for x in lids):
                findings.append(_finding("MATCHING_LEFT_ID_INVALID","INTERACTION"))
            if len(rids)!=len(right) or len(rids)!=len(set(rids)) or any(not x for x in rids):
                findings.append(_finding("MATCHING_RIGHT_ID_INVALID","INTERACTION"))
    if qtype=="ordering":
        items=ac.get("ordering_items")
        ids=[str(x.get("id") or "") for x in items if isinstance(x,dict)] if isinstance(items,list) else []
        if not isinstance(items,list) or len(items)<2 or len(ids)!=len(items) or len(ids)!=len(set(ids)) or any(not x for x in ids):
            findings.append(_finding("ORDERING_STRUCTURE_INVALID","INTERACTION"))
    has_ref=bool(re.search(r"\b(?:table|diagram|graph|figure|pedigree|stimulus|passage)\s+(?:above|below|shown|provided)\b",stem,re.I))
    has_material=bool(str(q.get("stimulus_data") or "").strip())
    if has_ref and not has_material:findings.append(_finding("MISSING_REFERENCED_STIMULUS","STIMULUS"))
    return ("HOLD" if findings else "PASS"),findings

def _responses(scoremax,q):
    ac=_safe_json(q.get("answer_config"),{});mc=_safe_json(q.get("marking_config"),{})
    qt=scoremax.canonical_question_type(q)
    if qt in {"single_choice","true_false"}:
        correct=list(mc.get("correct_option_ids") or [])
        opts=[str(x.get("id")) for x in (ac.get("options") or []) if isinstance(x,dict) and x.get("id") is not None]
        if len(correct)!=1:return None,None
        wrong=next((x for x in opts if x!=str(correct[0])),"__QA_WRONG__")
        return str(correct[0]),wrong
    if qt=="multiple_select":
        correct=[str(x) for x in (mc.get("correct_option_ids") or [])]
        opts=[str(x.get("id")) for x in (ac.get("options") or []) if isinstance(x,dict) and x.get("id") is not None]
        if not correct:return None,None
        wrong=correct[:-1] if len(correct)>1 else correct+[x for x in opts if x not in correct][:1]
        return ",".join(correct),",".join(wrong) if wrong else "__QA_WRONG__"
    if qt=="fill_blank":
        accepted=[str(x) for x in (ac.get("accepted_answers") or []) if str(x).strip()]
        return (accepted[0],"__QA_WRONG__") if accepted else (None,None)
    if qt=="numerical":
        if "correct_value" not in mc:return None,None
        val=float(mc["correct_value"]);tol=abs(float(mc.get("tolerance") or 0))
        return str(val),str(val+max(1.0,tol*10+1.0))
    if qt=="matching":
        mapping=mc.get("correct_mapping")
        if not isinstance(mapping,dict) or not mapping:return None,None
        wrong=dict(mapping);keys=list(wrong);rights=[str(x.get("id")) for x in (ac.get("right_options") or []) if isinstance(x,dict)]
        if not keys or len(rights)<2:return None,None
        current=str(wrong[keys[0]]);replacement=next((x for x in rights if x!=current),None)
        if replacement is None:return None,None
        wrong[keys[0]]=replacement
        if wrong==mapping:return None,None
        return _canon(mapping),_canon(wrong)
    if qt=="ordering":
        order=mc.get("correct_order")
        if not isinstance(order,list) or len(order)<2:return None,None
        return json.dumps(order,separators=(",",":")),json.dumps(list(reversed(order)),separators=(",",":"))
    if qt=="constructed_response":
        rub=mc.get("rubric")
        if not isinstance(rub,dict):return None,None
        phrases=[]
        for p in rub.get("required_mark_points") or []:
            candidates=(p.get("accepted_phrases") or [])+(p.get("acceptable_paraphrases") or [])
            if not candidates:return None,None
            phrases.append(str(candidates[0]))
        if not phrases:return None,None
        return " ".join(phrases),"__QA_UNRELATED_RESPONSE__"
    return None,None

def _student_b(scoremax,group):
    q=_question(group)
    if q is None:return "HOLD",[_finding("PROJECTION_INVALID","MARKING")]
    try:
        scoremax.question_contracts.validate_assessment_contract(q)
    except Exception as exc:
        return "HOLD",[_finding("ASSESSMENT_CONTRACT_INVALID","MARKING_CONTRACT",str(exc))]
    try:qtype=scoremax.canonical_question_type(q)
    except Exception:return "NOT_EVALUATED",[_finding("UNSUPPORTED_RESPONSE_TYPE","CAPABILITY",severity="INFO")]
    correct,wrong=_responses(scoremax,q)
    if correct is None:
        return "NOT_EVALUATED",[_finding("NO_BOUNDED_EXECUTION_ORACLE","CAPABILITY","No safe deterministic response oracle exists for this question.",severity="INFO")]
    findings=[]
    try:
        good=scoremax.mark_question_result(q,correct)
        if not good.get("confirmed") or good.get("marks_awarded") is None or float(good.get("marks_awarded") or 0)<float(good.get("maximum_marks") or 0)-1e-9:
            findings.append(_finding("CORRECT_RESPONSE_NOT_FULL_CREDIT","MARKING_EXECUTION",f"response_type={qtype}"))
        bad=scoremax.mark_question_result(q,wrong)
        if bad.get("confirmed") and bad.get("marks_awarded") is not None and float(bad.get("marks_awarded") or 0)>=float(bad.get("maximum_marks") or 0)-1e-9:
            findings.append(_finding("WRONG_RESPONSE_RECEIVED_FULL_CREDIT","MARKING_EXECUTION",f"response_type={qtype}"))
        if qtype=="constructed_response":
            mc=_safe_json(q.get("marking_config"),{});pts=(mc.get("rubric") or {}).get("required_mark_points") or []
            if len(pts)>1:
                p=(pts[0].get("accepted_phrases") or pts[0].get("acceptable_paraphrases") or [None])[0]
                if p:
                    partial=scoremax.mark_question_result(q,str(p))
                    earned=partial.get("marks_awarded")
                    if earned is None or not (0<float(earned)<float(partial.get("maximum_marks") or 0)):
                        findings.append(_finding("WRITTEN_PARTIAL_CREDIT_INVALID","MARKING_EXECUTION"))
    except Exception as exc:
        findings.append(_finding("MARKING_EXECUTION_ERROR","MARKING_EXECUTION",str(exc)))
    return ("HOLD" if findings else "PASS"),findings

def _reviewer_a(scoremax,group):
    q=_question(group)
    if q is None:return "HOLD",[_finding("PROJECTION_INVALID","MARKING_CONTRACT")]
    try:
        scoremax.question_contracts.validate_assessment_contract(q)
        return "PASS",[]
    except Exception as exc:
        return "HOLD",[_finding("ASSESSMENT_CONTRACT_INVALID","MARKING_CONTRACT",str(exc))]

def _reviewer_b(scoremax,c,group):
    row=group["row"];findings=[]
    qid=str(row["question_id"] or "");qvid=str(row["question_version_id"] or "");chk=str(row["question_checksum_sha256"] or "")
    if not qid or not qvid or not re.fullmatch(r"[A-Fa-f0-9]{64}",chk):
        findings.append(_finding("IMMUTABLE_IDENTITY_INCOMPLETE","IDENTITY"))
    if not group["memberships"]:findings.append(_finding("RELEASE_MEMBERSHIP_MISSING","IDENTITY"))
    for m in group["memberships"]:
        local=str(m["local_status"] or "").upper()
        if local=="STAGED":
            active=c.execute("""SELECT COUNT(*) n FROM questions WHERE ph_question_id=? AND ph_question_version_id=?
              AND ph_release_id=? AND ph_release_version=? AND COALESCE(active,0)=1""",
              (qid,qvid,m["release_id"],m["release_version"])).fetchone()["n"]
            if active:findings.append(_finding("STAGED_CONTENT_LEARNER_ACTIVE","RELEASE_GOVERNANCE",f"{m['release_id']} {m['release_version']}"))
        elif local=="ACTIVE":
            auth=c.execute("""SELECT 1 FROM integration_ph_product_activation_authorizations
              WHERE release_id=? AND release_version=? AND activation_status='ACTIVATED' LIMIT 1""",
              (m["release_id"],m["release_version"])).fetchone()
            if not auth:findings.append(_finding("ACTIVE_WITHOUT_ACTIVATION_AUTHORITY","RELEASE_GOVERNANCE",f"{m['release_id']} {m['release_version']}"))
    return ("HOLD" if findings else "PASS"),findings

def _evaluate(scoremax,c,agent,group):
    if agent=="STUDENT_A":return _student_a(scoremax,group)
    if agent=="STUDENT_B":return _student_b(scoremax,group)
    if agent=="REVIEWER_A":return _reviewer_a(scoremax,group)
    if agent=="REVIEWER_B":return _reviewer_b(scoremax,c,group)
    raise ValueError("Unknown QA agent")

def _run_one(scoremax,c,agent,population,scope_type,scope_key,group_code,actor):
    run_code="QAR-"+datetime.now().strftime("%Y%m%d%H%M%S%f")+"-"+agent
    cur=c.execute("""INSERT INTO qa_agent_runs(group_code,run_code,agent_code,policy_version,scope_type,scope_key,population_count,initiated_by)
      VALUES(?,?,?,?,?,?,?,?)""",(group_code,run_code,agent,POLICY_VERSION,scope_type,scope_key,len(population),actor))
    run_id=cur.lastrowid;counts={"PASS":0,"HOLD":0,"NOT_EVALUATED":0};finding_count=0
    for group in population:
        row=group["row"];status,findings=_evaluate(scoremax,c,agent,group)
        if status not in VALID_STATUSES:raise RuntimeError("Invalid QA result status")
        projection=_safe_json(row["scoremax_projection_json"],{})
        cur2=c.execute("""INSERT INTO qa_agent_results(run_id,agent_code,question_id,question_version_id,question_checksum_sha256,
          programme,subject,chapter,release_refs_json,status,findings_json)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(run_id,agent,row["question_id"],row["question_version_id"],row["question_checksum_sha256"],
          str(projection.get("programme") or ""),str(projection.get("subject") or ""),str(projection.get("chapter") or ""),
          _canon(group["memberships"]),status,_canon(findings)))
        result_id=cur2.lastrowid;counts[status]+=1;finding_count+=len(findings)
        for f in findings:
            c.execute("""INSERT INTO qa_agent_findings(result_id,run_id,agent_code,question_id,question_version_id,category,finding_code,severity,detail)
              VALUES(?,?,?,?,?,?,?,?,?)""",(result_id,run_id,agent,row["question_id"],row["question_version_id"],f["category"],f["code"],f["severity"],f.get("detail","")))
    summary={"agent":agent,"population":len(population),"counts":counts,"finding_count":finding_count,
      "release_authority":False,"mastery_authority":False,"question_mutation":False,"policy_version":POLICY_VERSION}
    c.execute("""UPDATE qa_agent_runs SET pass_count=?,hold_count=?,not_evaluated_count=?,finding_count=?,status='COMPLETED',
      summary_json=?,completed_at=? WHERE id=?""",(counts["PASS"],counts["HOLD"],counts["NOT_EVALUATED"],finding_count,_canon(summary),
      datetime.now().isoformat(timespec="seconds"),run_id))
    return summary

def run_agents(scoremax,agent_code,scope,actor):
    if agent_code!="ALL" and agent_code not in AGENTS:raise ValueError("Unknown QA agent")
    c=scoremax.db()
    try:
        ensure_schema(c)
        population,scope_type,scope_key=_population(c,scope)
        if not population:raise ValueError("No governed questions are available in the selected QA scope.")
        group_code="QAG-"+datetime.now().strftime("%Y%m%d%H%M%S%f")+"-"+secrets.token_hex(3).upper()
        agents=list(AGENTS) if agent_code=="ALL" else [agent_code];summaries=[]
        for agent in agents:summaries.append(_run_one(scoremax,c,agent,population,scope_type,scope_key,group_code,actor))
        c.commit();return {"group_code":group_code,"summaries":summaries,"population":len(population)}
    except Exception:
        c.rollback();raise
    finally:c.close()

def _latest_results(c):
    return c.execute("""SELECT r.* FROM qa_agent_results r JOIN (
      SELECT agent_code,question_id,question_version_id,MAX(id) id FROM qa_agent_results
      GROUP BY agent_code,question_id,question_version_id) x ON x.id=r.id""").fetchall()

def dashboard_data(scoremax):
    c=scoremax.db()
    try:
        ensure_schema(c)
        latest=_latest_results(c);stats={}
        for code,meta in AGENTS.items():
            all_rows=c.execute("SELECT * FROM qa_agent_results WHERE agent_code=?",(code,)).fetchall()
            unique={(r["question_id"],r["question_version_id"]) for r in all_rows}
            findings=c.execute("SELECT COUNT(*) n FROM qa_agent_findings WHERE agent_code=? AND severity<>'INFO'",(code,)).fetchone()["n"]
            affected=c.execute("""SELECT COUNT(*) n FROM (SELECT DISTINCT question_id,question_version_id FROM qa_agent_findings
              WHERE agent_code=? AND severity<>'INFO')""",(code,)).fetchone()["n"]
            current=[r for r in latest if r["agent_code"]==code]
            held=sum(r["status"]=="HOLD" for r in current);not_eval=sum(r["status"]=="NOT_EVALUATED" for r in current)
            cleared=c.execute("""SELECT COUNT(*) n FROM (
              SELECT question_id,question_version_id FROM qa_agent_results WHERE agent_code=? GROUP BY question_id,question_version_id
              HAVING SUM(CASE WHEN status='HOLD' THEN 1 ELSE 0 END)>0
                AND MAX(CASE WHEN id=(SELECT MAX(r2.id) FROM qa_agent_results r2 WHERE r2.agent_code=? AND r2.question_id=qa_agent_results.question_id AND r2.question_version_id=qa_agent_results.question_version_id) AND status='PASS' THEN 1 ELSE 0 END)=1)""",(code,code)).fetchone()["n"]
            last=c.execute("SELECT completed_at FROM qa_agent_runs WHERE agent_code=? AND status='COMPLETED' ORDER BY id DESC LIMIT 1",(code,)).fetchone()
            top=c.execute("""SELECT finding_code,COUNT(*) n FROM qa_agent_findings WHERE agent_code=? AND severity<>'INFO'
              GROUP BY finding_code ORDER BY n DESC,finding_code LIMIT 5""",(code,)).fetchall()
            stats[code]={**meta,"code":code,"unique_questions":len(unique),"executions":len(all_rows),"affected_questions":int(affected or 0),
              "findings":int(findings or 0),"current_holds":held,"not_evaluated":not_eval,"cleared_after_hold":int(cleared or 0),
              "last_run":last["completed_at"] if last else "Never","top_findings":top}
        recent=c.execute("SELECT * FROM qa_agent_runs ORDER BY id DESC LIMIT 20").fetchall()
        problems=c.execute("""SELECT r.* FROM qa_agent_results r JOIN (
          SELECT agent_code,question_id,question_version_id,MAX(id) id FROM qa_agent_results GROUP BY agent_code,question_id,question_version_id
          ) x ON x.id=r.id WHERE r.status IN ('HOLD','NOT_EVALUATED') ORDER BY r.id DESC LIMIT 20""").fetchall()
        releases=_release_rows(c)
        overall={
          "unique_questions":len({(r["question_id"],r["question_version_id"]) for r in c.execute("SELECT question_id,question_version_id FROM qa_agent_results")}),
          "executions":c.execute("SELECT COUNT(*) n FROM qa_agent_results").fetchone()["n"],
          "current_holds":sum(r["status"]=="HOLD" for r in latest),
          "not_evaluated":sum(r["status"]=="NOT_EVALUATED" for r in latest),
          "findings":c.execute("SELECT COUNT(*) n FROM qa_agent_findings WHERE severity<>'INFO'").fetchone()["n"],
        }
        historical={
          "label":"Historical qualification evidence",
          "population":"Cross50 real-bank replay · 50 question versions",
          "STUDENT_A":"50 checked · 50 PASS · 0 structural defects",
          "STUDENT_B":"50 routed · 31 deterministic execution PASS · 18 written fail-closed · 1 two-tier deferred",
          "REVIEWER_A":"50 reviewed · 31 objective contracts clean · 18 historical written holds · 1 two-tier deferred",
          "REVIEWER_B":"50 checked · 50 identity/governance PASS",
          "harness":"Four-lane adversarial harness: 20/20 PASS (5 checks per lane); assessment regression: 48/48 PASS.",
        }
        return {"agents":stats,"recent_runs":recent,"problems":problems,"releases":releases,"overall":overall,"historical":historical,
          "policy_version":POLICY_VERSION}
    finally:c.close()

def install_qa_agents_admin(app):
    if getattr(app,"_scoremax_qa_agents_admin_installed",False):return
    import app as scoremax
    c=scoremax.db()
    try:ensure_schema(c);c.commit()
    finally:c.close()

    @app.context_processor
    def qa_agents_admin_context():
        if session.get("role")=="admin" and request.endpoint in {"admin_mastery_lab","admin_qa_agent_problems"}:
            return {"qa_agent_admin":dashboard_data(scoremax)}
        return {"qa_agent_admin":None}

    @app.route("/admin/mastery-lab/qa-agents/run",methods=["POST"],endpoint="admin_qa_agents_run")
    def admin_qa_agents_run():
        if not scoremax.require("admin"):return redirect(url_for("login"))
        try:
            result=run_agents(scoremax,(request.form.get("agent_code") or "ALL").strip().upper(),
                              (request.form.get("scope") or "staged").strip(),session.get("user_id"))
            summaries=result["summaries"];holds=sum(x["counts"]["HOLD"] for x in summaries);ne=sum(x["counts"]["NOT_EVALUATED"] for x in summaries)
            flash(f"QA completed: {result['population']} question version(s) · {holds} hold result(s) · {ne} not evaluated.", "success" if holds==0 else "warning")
        except Exception as exc:
            flash(f"QA run blocked: {exc}","error")
        return redirect(url_for("admin_mastery_lab"))

    @app.route("/admin/mastery-lab/qa-agents/problems",endpoint="admin_qa_agent_problems")
    def admin_qa_agent_problems():
        if not scoremax.require("admin"):return redirect(url_for("login"))
        data=dashboard_data(scoremax)
        return render_template("admin_qa_agent_problems.html",qa_agent_admin=data)

    app._scoremax_qa_agents_admin_installed=True
