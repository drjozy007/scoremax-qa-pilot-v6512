"""Checked source repairs to existing programme, evidence and mastery paths.

No production content or account changes; generated runtime modules stay authoritative.
"""
from pathlib import Path
import ast
from ux_vnext_overlay.ux_assessment_contract_repair import replace_function,replace_once,donors


def add_functions(text,functions):
    # Parse a large native module once for the donor batch, not once per replacement.
    # Last-definition semantics exactly match the existing checked source installer.
    indexed={n.name:n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    lines=text.splitlines()
    for name in sorted((n for n in functions if n in indexed),key=lambda n:indexed[n].lineno,reverse=True):
        node=indexed[name]
        lines[node.lineno-1:node.end_lineno]=[functions[name]]
    result='\n'.join(lines)+'\n'
    for name,source in functions.items():
        if name not in indexed:result+='\n\n'+source+'\n'
    return result


def fn(text,name):
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
    return '\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])


def apply_programme_mastery_repair(root):
    root=Path(root);here=Path(__file__).parent
    ap=root/'app.py';a=ap.read_text()
    a=add_functions(a,donors(here/'programme_evidence_v3.py'))
    a=add_functions(a,donors(here/'mastery_policy_v3.py'))
    # Schema changes are additive, leave all saved histories and unscoped legacy states intact.
    anchor='def init():\n'
    # Install schema at the end of native init before its final commit, never after routes run.
    init=fn(a,'init')
    idx=init.rfind('    c.commit()')
    if idx<0:raise SystemExit('PROGRAMME_REPAIR_INIT_COMMIT_MISSING')
    init=init[:idx]+'''    ensure_column(c,'attempt_answers','evidence_context_json',"TEXT DEFAULT '{}'")
    for _table in ('student_learning_states','student_misconceptions','recall_items'):
        ensure_column(c,_table,'programme',"TEXT NOT NULL DEFAULT ''")
        ensure_column(c,_table,'source_area_key',"TEXT NOT NULL DEFAULT ''")
    c.execute('CREATE INDEX IF NOT EXISTS idx_attempt_programme_evidence ON attempts(student_id,programme,marking_status,mastery_evidence_eligible)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_answer_attempt_evidence ON attempt_answers(attempt_id,marking_status,mastery_evidence_eligible)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_mastery_record_scope_status ON mastery_records(programme,subject,chapter,status)')
'''+init[idx:]
    a=replace_function(a,'init',init)
    submit=fn(a,'submit_assessment_v4')
    submit=replace_once(submit,'        marking_results={}','        marking_results={}\n        evidence_contexts={}')
    submit=replace_once(submit,"            marking_results[qid]=marking_result","            marking_results[qid]=marking_result\n            evidence_contexts[qid]=evidence_context(q,submission_meta.get('programme',''),qid)")
    pos=submit.index('        # Commit the one-and-only')
    submit=submit[:pos]+'''        for qid,context in evidence_contexts.items():
            c.execute('UPDATE attempt_answers SET evidence_context_json=? WHERE attempt_id=? AND question_db_id=?',
              (integration_v1.canonical_json(context),attempt_id,qid))
'''+submit[pos:]
    a=replace_function(a,'submit_assessment_v4',submit)
    # Persisted per-attempt context, not mutable question metadata, feeds future caches.
    u=fn(a,'update_learning_intelligence_from_attempt')
    start=u.index('    rows=c.execute(');end=u.index('    now=',start)
    u=u[:start]+'''    attempt=c.execute('SELECT * FROM attempts WHERE id=? AND student_id=?',(attempt_id,student_id)).fetchone()
    if not attempt:return
    programme=canonical_programme(attempt['programme'])
    rows=learner_answer_evidence(c,student_id,programme,attempt_id=attempt_id)
    if not rows:return
'''+u[end:]
    u=replace_once(u,'        key=_area_key_from_question(q)','        raw_key=_area_key_from_question(q)\n        key=integration_v1.canonical_json([programme,q[\'subject\'],q[\'chapter\'],raw_key]) if raw_key else \'\'')
    u=replace_once(u,"'topic':q['topic'] or '','area_name':_area_name_from_question(q),'answered':0,'correct':0}","'topic':q['topic'] or '','area_name':_area_name_from_question(q),'raw_key':raw_key,'answered':0,'correct':0}")
    u=replace_once(u,"        if misconception and not q['is_correct']:","        if misconception and not q['is_correct']:\n            raw_misconception=misconception\n            misconception=integration_v1.canonical_json([programme,q['subject'],q['chapter'],misconception])")
    # Exact original cache functions retained, with scoped identity and programme tagging.
    insert="""              (student_id,misconception,q['subject'] or '',_area_name_from_question(q),ev,confident,status,attempt_id,now))"""
    u=replace_once(u,insert,insert+"\n            c.execute('UPDATE student_misconceptions SET programme=?,source_area_key=? WHERE student_id=? AND misconception_key=?',(programme,raw_misconception,student_id,misconception))")
    u=replace_once(u,"        ev=(int(prior['evidence_count'] or 0) if prior else 0)+g['answered']", "        if prior and prior['last_attempt_id']==attempt_id:continue\n        ev=(int(prior['evidence_count'] or 0) if prior else 0)+g['answered']")
    u=replace_once(u,"WHERE student_id=? AND status='Confirmed' AND subject=? AND area_name=?\"\"\",\n              (now,student_id,g['subject'],g['area_name']))", "WHERE student_id=? AND status='Confirmed' AND subject=? AND area_name=? AND programme=?\"\"\",\n              (now,student_id,g['subject'],g['area_name'],programme))")
    anchor="          (student_id,key,g['subject'],g['chapter'],g['topic'],g['area_name'],ev,cor,accuracy,status,attempt_id,now,recovered_at))"
    u=replace_once(u,anchor,anchor+"\n        c.execute('UPDATE student_learning_states SET programme=?,source_area_key=? WHERE student_id=? AND area_key=?',(programme,g['raw_key'],student_id,key))")
    u+="\n        c.execute('UPDATE recall_items SET programme=?,source_area_key=? WHERE student_id=? AND concept_key=?',(programme,g['raw_key'],student_id,key))"
    a=replace_function(a,'update_learning_intelligence_from_attempt',u)
    # Fix older getters to share the same scoped eligible evidence reader.
    s=fn(a,'_subject_map')
    s=replace_once(s,'    data=[]','    evidence=learner_answer_evidence(c,student_id)\n    data=[]')
    start=s.index('        r=c.execute(f"""SELECT COUNT(aa.id)')
    end=s.index('        chapters=[]',start)
    s=s[:start]+'''        stats=evidence_summary([r for r in evidence if r['subject'].casefold()==display.casefold()])
        answered=stats['answered'];accuracy=stats['accuracy']
'''+s[end:]
    start=s.index('            cr=c.execute(');end=s.index('            identity=',start)
    s=s[:start]+'''            stats=evidence_summary([r for r in evidence if r['subject'].casefold()==display.casefold() and r['chapter']==ch['chapter']])
            ca=stats['answered'];cp=stats['accuracy']
'''+s[end:]
    a=replace_function(a,'_subject_map',s)
    w=fn(a,'weekly_progress_summary')
    start=w.index('    attempts=c.execute(');end=w.index('    avg=',start)
    w=w[:start]+"    attempts=[r for r in eligible_attempts(c,student_id) if monday.isoformat()<=str(r['created_at'])[:10]<=sunday.isoformat()]\n"+w[end:]
    a=replace_function(a,'weekly_progress_summary',w)
    estimate=fn(a,'_estimate_starting_coverage')
    estimate=replace_once(estimate,'    tested=_tested_chapters(c,student_id)','    tested=_tested_chapters(c,student_id,target_exam)')
    a=replace_function(a,'_estimate_starting_coverage',estimate)
    # No fallback to an unscoped record when the requested programme has no mastery.
    m=fn(a,'chapter_mastery_opportunity')
    start=m.index('    if not rec:');end=m.index('    existing_level=',start)
    m=m[:start]+m[end:]
    a=replace_function(a,'chapter_mastery_opportunity',m)
    m=fn(a,'current_mastery_records')
    m=replace_once(m,"WHERE student_id=? ORDER BY scope_type,scope_key\",(student_id,)","WHERE student_id=? AND programme=? ORDER BY scope_type,scope_key\",(student_id,student_programme(c,student_id))")
    a=replace_function(a,'current_mastery_records',m)
    # Every current slider calculation shares strict zero-preserving parsing.
    import re
    a=re.sub(r"int\((assembly_policy|policy|prior)\['(rigor_score|mastery_standard_score)'\] or 50\)",r"policy_score(\1['\2'])",a)
    # Plans must explicitly name their target programme before they can contribute to it.
    plan=fn(a,'get_active_study_plan')
    plan=replace_once(plan,"WHERE student_id=? AND status='active'\n      ORDER BY id DESC LIMIT 1\"\"\",(student_id,))", "WHERE student_id=? AND status='active' AND lower(trim(target_exam))=lower(?)\n      ORDER BY id DESC LIMIT 1\"\"\",(student_id,student_programme(c,student_id)))")
    a=replace_function(a,'get_active_study_plan',plan)
    # New mastery forms retain original policy settings, stable coverage source and
    # accurate target share; no inventory-derived coverage fallback.
    m=fn(a,'build_mastery_form')
    start=m.index('    if not programme:');end=m.index('    governing_blueprint=',start)
    m=m[:start]+"    programme=canonical_programme(programme or student_programme(c,student_id))\n    if not programme:raise ValueError('A programme is required for mastery')\n"+m[end:]
    m=replace_once(m,"        clauses.append(\"(lower(COALESCE(q.programme,''))=lower(?) OR lower(COALESCE(q.qualification,''))=lower(?))\")\n        params.extend([programme,programme])", "        scope_sql,scope_args=_programme_scope_sql(_programme_aliases(programme),'q')\n        clauses.append(scope_sql);params.extend(scope_args)")
    m=replace_once(m,"    previous=_mastery_previous_families", "    coverage=mastery_coverage_contract(c,programme,subject,chapter,scope_type) if not demo_only else None\n    previous=_mastery_previous_families")
    m=replace_once(m,"          'mastery_effective_policy':effective_policy,", "          'mastery_effective_policy':effective_policy,'mastery_base_policy':dict(policy),")
    m=m.replace("float(effective_policy.get('target_band_pct') or policy['target_band_pct'] or .25)","float(effective_policy['target_band_pct'])")
    m=m.replace("float(effective_policy.get('unseen_family_pct') or policy['unseen_family_pct'] or .6)","float(effective_policy['unseen_family_pct'])")
    start=m.index('    chosen=[]; used_families=set()')
    end=m.index('    unseen=sum(',start)
    original=m[start:end]
    # Keep demonstration-only software path untouched; production form uses the same
    # fixed academic population as its final breadth gate, not random bank coverage.
    m=m[:start]+"    if not demo_only:\n        chosen=select_mastery_coverage_questions(pool,min_q,target_level,float(effective_policy['target_band_pct']),float(effective_policy['unseen_family_pct']),previous,dict(coverage,min_breadth_pct=effective_policy['min_breadth_pct']),rigor)\n    else:\n"+'\n'.join('    '+line for line in original.splitlines())+'\n'+m[end:]
    m=replace_once(m,'    return chosen,meta','    return attach_mastery_coverage(c,chosen,meta)')
    a=replace_function(a,'build_mastery_form',m)
    # Reuse all existing promotion/reconfirmation rules; add stricter gates and bind
    # accumulated forms to identical effective settings and policy identity.
    m=fn(a,'process_mastery_result')
    old="    passed=bool(policy and score>=float(effective_policy.get('min_accuracy') or policy['min_accuracy'] or 0) and meta.get('mastery_breadth_ok'))"
    new="""    frozen=meta.get('mastery_coverage_snapshot') or {}
    frozen_digest=frozen.get('checksum_sha256')
    expected_digest=hashlib.sha256(integration_v1.canonical_json({k:v for k,v in frozen.items() if k!='checksum_sha256'}).encode()).hexdigest()
    coverage_valid=bool(frozen_digest and frozen_digest==expected_digest)
    passed=bool(policy and score is not None and coverage_valid and meta.get('mastery_mandatory_covered')
      and score>=float(effective_policy.get('min_accuracy',100))
      and len(question_ids)>=int(effective_policy.get('min_questions',0))
      and float(meta.get('mastery_breadth_ratio',0))>=float(effective_policy.get('min_breadth_pct',1))
      and float(meta.get('mastery_target_band_ratio',0))>=float(effective_policy.get('target_band_pct',1))
      and float(meta.get('mastery_unseen_family_ratio',0))>=float(effective_policy.get('unseen_family_pct',1))
      and meta.get('mastery_breadth_ok'))"""
    m=replace_once(m,old,new)
    m=replace_once(m,'json.dumps(dict(policy) if policy else {})',"json.dumps(meta.get('mastery_base_policy') or {})")
    anchor='    if demo_only or not policy: return\n'
    m=replace_once(m,anchor,anchor+"""    # An in-flight older form is still scored under its pinned rules, but cannot
    # reconfirm/promote a record under a different current policy/coverage contract.
    active_bp=active_assessment_blueprint(c,meta.get('programme',''))
    current=active_assembly_policy(c,active_bp['id'] if active_bp else None,
      active_bp['framework_version_id'] if active_bp else None,programme=meta.get('programme',''),
      subject=meta.get('subject',''),chapter=meta.get('chapters',''),assessment_type='mastery')
    current_effective=effective_mastery_requirements(policy,current)
    try:
        current_coverage=mastery_coverage_contract(c,meta.get('programme',''),meta.get('subject',''),meta.get('chapters',''),scope_type)
    except ValueError:return
    current_effective['coverage_contract_checksum']=current_coverage['checksum_sha256']
    if not coverage_valid or current_effective!=effective_policy:return
""")
    # Same human version string on two different scopes must not merge their evidence.
    m=m.replace("AND COALESCE(assembly_policy_version,'1')=?", "AND COALESCE(assembly_policy_version,'1')=? AND COALESCE(assembly_policy_id,-1)=? AND effective_policy_json=?")
    m=m.replace('policy_version,max(10,effective_min_forms+2)', "policy_version,meta.get('assembly_policy_id') if meta.get('assembly_policy_id') is not None else -1,json.dumps(effective_policy),max(10,effective_min_forms+2)")
    a=replace_function(a,'process_mastery_result',m)
    # Chapter page topic inventory and evidence use exact active programme too.
    m=fn(a,'chapter_page')
    m=replace_once(m,'    topics=[]',"    programme=student_programme(c,session['user_id'])\n    scope_sql,scope_args=_programme_scope_sql(_programme_aliases(programme),'q')\n    evidence=learner_answer_evidence(c,session['user_id'],programme,subject,chapter)\n    topics=[]")
    m=replace_once(m,"AND q.subject=? AND q.chapter=? AND COALESCE(q.topic,'')<>'' ORDER BY q.topic\",(subject,chapter)","AND q.subject=? AND q.chapter=? AND {scope_sql} AND COALESCE(q.topic,'')<>'' ORDER BY q.topic\",[subject,chapter]+scope_args")
    start=m.index('        r=c.execute(');end=m.index("        topics.append",start)
    m=m[:start]+"        stats=evidence_summary([r for r in evidence if r['topic']==topic]);answered=stats['answered'];accuracy=stats['accuracy']\n"+m[end:]
    start=m.index('    cr=c.execute(');end=m.index('    weak=',start)
    m=m[:start]+"    stats=evidence_summary(evidence);answered=stats['answered'];accuracy=stats['accuracy']\n"+m[end:]
    m=replace_once(m,"WHERE student_id=? AND subject=? AND chapter=? ORDER BY next_due_date\",(session['user_id'],subject,chapter)","WHERE student_id=? AND subject=? AND chapter=? AND programme=? ORDER BY next_due_date\",(session['user_id'],subject,chapter,programme)")
    m=replace_once(m,"AND spa.status<>'completed'\n      ORDER BY spa.activity_date,spa.priority LIMIT 5\"\"\",(session['user_id'],subject,chapter)","AND spa.status<>'completed' AND sp.target_exam=?\n      ORDER BY spa.activity_date,spa.priority LIMIT 5\"\"\",(session['user_id'],subject,chapter,programme)")
    a=replace_function(a,'chapter_page',m)
    # Scope recovery/weak-area selection too, so correct cards cannot feed a mixed form.
    m=fn(a,'recovery_question_ids')
    m=replace_once(m,"    params=[attempt['subject']]", "    params=[attempt['subject']]\n    scope_sql,scope_params=_programme_scope_sql(_programme_aliases(attempt['programme']),'q')\n    clauses.append(scope_sql);params.extend(scope_params)")
    a=replace_function(a,'recovery_question_ids',m)
    m=fn(a,'weak_areas_start')
    m=replace_once(m,"    weak=student_weak_areas", "    programme=student_programme(c,session['user_id'])\n    scope_sql,scope_params=_programme_scope_sql(_programme_aliases(programme),'q')\n    weak=student_weak_areas")
    m=replace_once(m,"FROM questions q WHERE q.subject=? AND {live_question_clause('q')}","FROM questions q WHERE q.subject=? AND {scope_sql} AND {live_question_clause('q')}")
    m=replace_once(m,"(session['user_id'],w['subject'],w['concept_key'],w['concept_key'],w['area'],w['area'],per_area+2)","[session['user_id'],w['subject']]+scope_params+[w['concept_key'],w['concept_key'],w['area'],w['area'],per_area+2]")
    a=replace_function(a,'weak_areas_start',m)
    # Future local sessions cannot silently assign a differently scoped question to
    # their programme. PH mappings retain their own governed destination authority.
    m=fn(a,'create_assessment_session')
    m=replace_once(m,"    meta=dict(meta or {})", "    meta=dict(meta or {})\n    meta['programme']=canonical_programme(meta.get('programme') or student_programme(c,student_id))\n    for _qid in question_ids:\n        _q=c.execute('SELECT programme,qualification,ph_projection_owner FROM questions WHERE id=?',(_qid,)).fetchone()\n        if str(_q['ph_projection_owner'] or '')!='POWER_HOUSE' and canonical_programme(_q['programme'] or _q['qualification'])!=meta['programme']:\n            raise question_contracts.QuestionContractError('ASSESSMENT_PROGRAMME_MISMATCH')")
    a=replace_function(a,'create_assessment_session',m)
    m=fn(a,'active_assembly_policy')
    m=replace_once(m,'    candidates=[]',"    programme=canonical_programme(programme)\n    subject=str(subject or '').strip();chapter=str(chapter or '').strip()\n    candidates=[]")
    a=replace_function(a,'active_assembly_policy',m)
    m=fn(a,'chapter_mastery_opportunity')
    m=replace_once(m,"    programme=(programme or student_programme(c,student_id) or '').strip()", "    programme=canonical_programme(programme or student_programme(c,student_id))")
    m=replace_once(m,"    potential_level=''", "    try:\n        coverage=mastery_coverage_contract(c,programme,subject,chapter,'chapter')\n    except ValueError:\n        coverage=None\n    potential_level=''")
    m=replace_once(m,'        if not policy: continue','        if not policy or not coverage: continue')
    m=replace_once(m,'        potential_level=level',"        seen=_mastery_previous_families(c,student_id,'chapter',scope_key,level)\n        try:\n            select_mastery_coverage_questions(pool,min_q,level,effective['target_band_pct'],effective['unseen_family_pct'],seen,dict(coverage,min_breadth_pct=effective['min_breadth_pct']),policy_score(assembly_policy['rigor_score']) if assembly_policy else 50)\n        except ValueError:continue\n        potential_level=level")
    a=replace_function(a,'chapter_mastery_opportunity',m)
    # Unseen means unseen across previous levels too; no five-form forgetting window.
    m=fn(a,'_mastery_previous_families')
    m=m.replace(" AND target_level=? ORDER BY id DESC LIMIT 5"," ORDER BY id DESC").replace('(student_id,scope_type,scope_key,target_level)', '(student_id,scope_type,scope_key)')
    m=replace_once(m,'    seen=set()','    seen=seen_question_families(c,student_id)')
    a=replace_function(a,'_mastery_previous_families',m)
    compile(a,str(ap),'exec');ap.write_text(a)

    p=root/'ux_student_batch.py';s=p.read_text()
    s=add_functions(s,donors(here/'programme_student_views_v3.py'))
    # This earlier before_request override was the actual year-reset root cause.
    start=s.index("                if subject.casefold() in {'biology','chemistry','physics'}:")
    end=s.index('                chapters=_chapter_snapshots',start)
    s=s[:start]+"                # Explicit programme selection wins; GET never resets it from academic_level.\n"+s[end:]
    start=s.index('        ans=conn.execute(',s.index('def _chapter_snapshots'));end=s.index('        mastery=',start)
    s=s[:start]+"        stats=runtime.evidence_summary(runtime.learner_answer_evidence(conn,student_id,programme,subject,source_chapter))\n        answered=stats['answered'];acc=round(stats['accuracy'])\n\n"+s[end:]
    # No unscoped catalogue fallback when programme is unknown.
    s=s.replace("programme_clause,programme_params='1=1',[]","programme_clause,programme_params='0=1',[]")
    compile(s,str(p),'exec');p.write_text(s)
    p=root/'ux_catalogue_browser.py';s=p.read_text()
    start=s.index('    def _sync_main_fsc_subject_context()');end=s.index('    @app.before_request',start)
    s=s[:start]+"    def _sync_main_fsc_subject_context():\n        # The selected programme is authoritative; do not restore an older school year.\n        return None\n\n"+s[end:]
    compile(s,str(p),'exec');p.write_text(s)
    p=root/'ux_mastery_rigor_admin.py';s=p.read_text()
    start=s.index('    original_effective=');end=s.index("    @app.route('/admin/mastery-rigor'",start)
    s=s[:start]+"    # Native engine owns the calculations and fixed curriculum coverage contract.\n\n"+s[end:]
    # Adding a new schema column may initialize defaults once; an owner's later zero
    # must not be overwritten every restart.
    s=replace_once(s,"        _ensure_col(conn,'mastery_policies','min_breadth_pct',\"REAL NOT NULL DEFAULT 0\")\n        for level,value in DEFAULT_BREADTH.items():", "        new_column='min_breadth_pct' not in {r[1] for r in conn.execute('PRAGMA table_info(mastery_policies)')}\n        _ensure_col(conn,'mastery_policies','min_breadth_pct',\"REAL NOT NULL DEFAULT 0\")\n        for level,value in (DEFAULT_BREADTH.items() if new_column else []):")
    start=s.index('        try:\n            values={',s.index('def admin_mastery_rigor_level'))
    end=s.index('        c=scoremax.db()',start)
    s=s[:start]+"        try:\n            values=scoremax.validate_mastery_policy_values(request.form)\n        except ValueError as exc:\n            flash(str(exc),'error')\n            return redirect(url_for('admin_mastery_rigor'))\n"+s[end:]
    s=replace_once(s,"            before=dict(row)","            before=dict(row)\n            scoremax.sqlite_mutation.begin_immediate(c)")
    s=replace_once(s,"            c.commit()\n        finally:\n            c.close()\n        flash(f'{level} mastery rule updated.","            scoremax.mark_baseline_changes_for_verification(c,level,before,reason)\n            c.commit()\n        finally:\n            c.close()\n        flash(f'{level} mastery rule updated.")
    compile(s,str(p),'exec');p.write_text(s)
    t=root/'templates/admin_mastery_rigor.html';s=t.read_text()
    s=s.replace('How much of the available knowledge-node / LO coverage is represented.','How much of the frozen, approved curriculum node register is represented. Inventory size cannot change this denominator.')
    s=s.replace('{{x.estimated_proposed_form_pass_rate}}%',"{% if x.estimated_proposed_form_pass_rate is not none %}{{x.estimated_proposed_form_pass_rate}}%{% else %}Unknown — historical evidence incomplete{% endif %}")
    t.write_text(s)
    print('SCOREMAX_PROGRAMME_MASTERY_REPAIR_V3 source_installed=true selected_programme_preserved=true scoped_evidence=true policy_scope=true fixed_curriculum_required=true not_full_mastery_freeze=true',flush=True)
