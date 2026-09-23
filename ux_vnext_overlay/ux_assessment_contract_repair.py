"""Repair the EXISTING native assessment/admission/renderer pipeline at build time.

Checked AST substitutions fail on source drift. No alternate runtime route, academic
content writes, historical score migration or production operation is performed here.
"""
from __future__ import annotations
import ast
from pathlib import Path


def replace_function(text,name,replacement,last=False):
    nodes=[n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name]
    if not nodes or (len(nodes)>1 and not last):raise SystemExit('ASSESSMENT_REPAIR_FUNCTION_AMBIGUOUS:'+name)
    node=nodes[-1] if last else nodes[0]
    lines=text.splitlines()
    return '\n'.join(lines[:node.lineno-1]+[replacement]+lines[node.end_lineno:])+'\n'


def replace_once(text,old,new):
    if text.count(old)!=1:raise SystemExit('ASSESSMENT_REPAIR_ANCHOR_MISMATCH:'+old[:100])
    return text.replace(old,new,1)


def donors(path):
    text=path.read_text();lines=text.splitlines()
    return {n.name:'\n'.join(lines[n.lineno-1:n.end_lineno]) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}


def add_functions(text,functions):
    names={n.name for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    for name,source in functions.items():
        if name in names:text=replace_function(text,name,source,last=True)
        else:text+='\n\n'+source+'\n'
    return text


def apply_written_contract_repair(root):
    root=Path(root);here=Path(__file__).parent
    path=root/'written_response_engine.py';text=path.read_text()
    text=add_functions(text,donors(here/'assessment_written_response_v2.py'))
    # Replace the existing public entrypoint itself; no optional policy dispatch
    # can leave a second route into the unsafe legacy overlap heuristic.
    node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='mark_written_response')
    fn='\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])
    if '_point_evidence' in fn or 'confirmed_confidence' in fn:
        raise SystemExit('WRITTEN_LEGACY_SCORING_BYPASS_SURVIVED')
    compile(text,str(path),'exec');path.write_text(text)


def apply_assessment_contract_repair(root):
    root=Path(root);here=Path(__file__).parent
    cp=root/'question_contract_engine.py';c=cp.read_text()
    c=add_functions(c,donors(here/'assessment_question_contracts_v2.py'))
    compile(c,str(cp),'exec');cp.write_text(c)

    ip=root/'scoremax_integration_v1.py';i=ip.read_text()
    i=replace_once(i,"'programme':str(disp.get('programme') or curr.get('programme_id') or '')",
                     "'programme':question_contracts.programme_from_curriculum(curr)")
    i=replace_once(i,"    errors=[]; path=f'payload.questions[{index}]'\n",
        "    errors=[]; path=f'payload.questions[{index}]'\n"
        "    try:\n"
        "        question_contracts.programme_from_curriculum(q.get('curriculum') or {})\n"
        "    except question_contracts.QuestionContractError as exc:\n"
        "        errors.append({'code':str(exc),'path':path+'.curriculum','message':'Existing programme/year fields conflict or do not identify the FSc year.','retryable':False})\n")
    integration_donors=donors(here/'assessment_integration_v2.py')
    projection_source=integration_donors.pop('_projection')
    i+='\n_projection_base=_projection\n'
    i=add_functions(i,integration_donors)
    i+='\n'+projection_source+'\n'
    # Materialise the same effective projection used for staging, marking and NEW pins.
    # Version store content/projection bytes and old attempt snapshots remain untouched.
    i=replace_once(i,"proj=json.loads(rv['scoremax_projection_json']); proj['ph_release_id']=release_id;", "proj=effective_projection(strict_json_loads(rv['scoremax_projection_json']),strict_json_loads(rv['content_json'])); proj['ph_release_id']=release_id;")
    start=i.index("    qvs=c.execute(",i.index('def _activate_release(c,release_id,release_version):'))
    end=i.index("    new_external_ids=",start)
    i=i[:start]+"    qvs=_eligible_release_question_versions(c,release_id,release_version)\n"+i[end:]
    compile(i,str(ip),'exec');ip.write_text(i)

    rp=root/'ux_content_reviewer.py';r=rp.read_text()
    r=add_functions(r,donors(here/'assessment_review_v2.py'))
    start=r.index('    try:\n',r.index('def _staged_question_dict('))
    end=r.index('    q.update({',start)
    r=r[:start]+'''    import scoremax_integration_v1 as integration
    try:
        content=integration.strict_json_loads(row['content_json'])
        q=integration.effective_projection(integration.strict_json_loads(row['scoremax_projection_json']),content)
        q['_source_content']=content
    except (ValueError,TypeError,KeyError) as exc:
        q={'qtype':'unsupported','ph_response_contract':'unsupported','answer_config':'{}','marking_config':'{}','_contract_error':str(exc),'question':'This question is blocked because its response contract could not be verified.'}
'''+r[end:]
    compile(r,str(rp),'exec');rp.write_text(r)

    ap=root/'app.py';a=ap.read_text()
    # Remove the later ad hoc constructed wrapper; preserve the existing objective scorer.
    old='def mark_question_response(q, selected, blueprint_marking_rules=None):'
    if a.count(old)!=2:raise SystemExit('ASSESSMENT_MARKER_SOURCE_COUNT')
    a=a.replace(old,'def _mark_objective_response(q, selected, blueprint_marking_rules=None):',1)
    a=replace_once(a,'_original_mark_question_response_constructed = mark_question_response','')
    a=add_functions(a,donors(here/'assessment_marking_v2.py'))
    a=replace_once(a,"value=float(response); target=float(marking_cfg.get('correct_value')); tolerance=float(marking_cfg.get('tolerance',0)); ok=abs(value-target)<=tolerance","from ux_constructed_auto_marker import _decimal\n            value=_decimal(response); target=_decimal(marking_cfg.get('correct_value')); tolerance=_decimal(marking_cfg.get('tolerance',0)); ok=all(x is not None for x in (value,target,tolerance)) and abs(value-target)<=tolerance")
    a=replace_once(a,"except (TypeError,ValueError): ok=False","except (TypeError,ValueError,ArithmeticError): ok=False")
    a=replace_once(a,"ok=response.upper() in {str(x).strip().upper() for x in correct_ids}","ok=response in {str(x).strip() for x in correct_ids}")
    a=replace_once(a,"        qid=ids[idx]\n        post_q=","        qid=ids[idx]\n        if 'response_question_id' in request.form and request.form.get('response_question_id')!=str(qid):\n            raise question_contracts.QuestionContractError('STALE_QUESTION_FORM')\n        post_q=")
    schema="""    for table,name,definition in (
        ('attempts','maximum_marks','REAL'),('attempts','total_marks_awarded','REAL'),
        ('attempts','question_accuracy_pct','REAL'),('attempts','marking_result_version',"TEXT DEFAULT ''"),
        ('attempt_answers','maximum_marks','REAL'),('attempt_answers','marker_confidence','REAL'),
        ('attempt_answers','marking_result_json',"TEXT DEFAULT '{}'"),
        ('attempt_answers','mastery_evidence_eligible','INTEGER DEFAULT 0')):
        ensure_column(c,table,name,definition)
"""
    a=replace_once(a,'def migrate_v6_6_7a_family_absorption(c):\n', 'def migrate_v6_6_7a_family_absorption(c):\n'+schema)
    a=replace_once(a,"        if answer!='':\n            answers[str(qid)]=answer\n        elif post_qtype in {'matching','ordering','constructed_response'}:\n            answers.pop(str(qid),None)","        if question_contracts.response_was_present(post_qtype,request.form):\n            if answer!='': answers[str(qid)]=answer\n            else: answers.pop(str(qid),None)")
    a=replace_once(a,"    question_ids=list(dict.fromkeys(filter_live_question_ids(c,question_ids)))",'''    requested=list(question_ids)
    try:
        if any(isinstance(x,bool) for x in requested): raise ValueError()
        requested=[int(x) for x in requested]
    except (TypeError,ValueError):
        raise question_contracts.QuestionContractError('INVALID_ASSESSMENT_QUESTION_ID')
    question_ids=list(dict.fromkeys(filter_live_question_ids(c,requested)))
    if question_ids!=requested:
        raise question_contracts.QuestionContractError('ASSESSMENT_POPULATION_CHANGED')''')
    a=replace_once(a,"        action=request.form.get('action','next')","        action=request.form.get('action','next')\n        if remain==0 and a['mode'] in ('exam','mock'): action='review'\n        if action=='clear': answer=''")
    a=replace_once(a,"            else: answers.pop(str(qid),None)\n        if conf: confidence[str(qid)]=conf", "            else:\n                answers.pop(str(qid),None); confidence.pop(str(qid),None)\n        if conf and answer: confidence[str(qid)]=conf")
    a=replace_once(a,"    expires_at=None\n    governed_snapshot=", "    meta=dict(meta or {})\n    # Pin a bounded transport-only grace, not extra question-navigation time.\n    meta['_response_save_grace_seconds']=5\n    expires_at=None\n    governed_snapshot=")
    a=replace_once(a,"    if remain==0 and a['mode'] in ('exam','mock'):\n        c.close()\n        return redirect(url_for('assessment_review_v4',assessment_id=assessment_id))",'''    if remain==0 and a['mode'] in ('exam','mock'):
        grace=safe_json(a['meta_json'],{}).get('_response_save_grace_seconds',0)
        try:
            late=(datetime.now()-datetime.fromisoformat(a['expires_at'])).total_seconds()
            final_save=request.method=='POST' and isinstance(grace,int) and 0<grace<=5 and 0<=late<=grace
        except (TypeError,ValueError): final_save=False
        if not final_save:
            c.close()
            return redirect(url_for('assessment_review_v4',assessment_id=assessment_id))''')
    # Schema failures and corrupt pins must close/rollback their connection, not crash
    # into a fallback projection or leave an assessment in 'submitting'.
    for name in ('take_test_v4','submit_assessment_v4'):
        tree=ast.parse(a);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        lines=a.splitlines();fn='\n'.join(lines[node.lineno-1:node.end_lineno])
        idx=fn.index('\n    c=db()')+len('\n    c=db()')
        body=fn[idx:]
        fn=fn[:idx]+'\n    try:'+''.join('\n    '+line if line else '\n' for line in body.splitlines()[1:])+'''
    except (question_contracts.QuestionContractError, KeyError, ValueError, TypeError) as exc:
        try: c.rollback()
        except Exception: pass
        c.close()
        abort(409,description='Assessment contract could not be verified. Your previous saved work has not been changed.')
'''
        a=replace_function(a,name,fn)

    # Replace the old tuple/manual-review accounting block inside the native route.
    node=next(n for n in ast.parse(a).body if isinstance(n,ast.FunctionDef) and n.name=='submit_assessment_v4')
    lines=a.splitlines();fn='\n'.join(lines[node.lineno-1:node.end_lineno])
    fn=replace_once(fn,'        total_awarded_marks=0.0','        total_awarded_marks=0.0\n        total_possible_marks=0.0\n        marking_results={}\n        auto_unscored=[]')
    start=fn.index('            ok,marks_awarded,misconception=mark_question_response')
    end=fn.index('            answer_rows.append(',start)
    fn=fn[:start]+'''            marking_result=mark_question_result(q,selected,blueprint_marking_rules)
            marking_results[qid]=marking_result
            total_possible_marks+=marking_result['maximum_marks']
            ok=marking_result['is_correct'];marks_awarded=marking_result['marks_awarded']
            misconception=marking_result.get('misconception') or ''
            if marking_result['confirmed']:
                correct+=int(ok);total_awarded_marks+=float(marks_awarded)
            else:
                auto_unscored.append(qid)
'''+fn[end:]
    start=fn.index("        if blueprint_marking_rules and blueprint_marking_rules.get('correct_marks')")
    end=fn.index('        cur=c.execute(',start)
    fn=fn[:start]+'''        if not ids or total_possible_marks<=0:
            raise question_contracts.QuestionContractError('EMPTY_OR_INVALID_ASSESSMENT')
        score=round(max(0.0,100.0*total_awarded_marks/total_possible_marks),1)
        if auto_unscored: score=None
        if is_science_genius and auto_unscored:
            raise question_contracts.QuestionContractError('UNSCORABLE_COMPETITION_RESPONSE')

'''+fn[end:]
    start=fn.index('        if pending_reviews:\n')
    end=fn.index('        # Commit the one-and-only',start)
    fn=fn[:start]+'''        all_confirmed=not auto_unscored
        c.execute("UPDATE attempts SET maximum_marks=?,total_marks_awarded=?,question_accuracy_pct=?,marking_result_version='SM-MARK-RESULT-2',marking_status=?,pending_review_count=0,mastery_evidence_eligible=? WHERE id=?",
          (total_possible_marks,total_awarded_marks if all_confirmed else None,round(100.0*correct/len(ids),1) if all_confirmed else None,
           'FINAL' if all_confirmed else 'AUTO_UNSCORED',1 if all_confirmed and not is_science_genius else 0,attempt_id))
        for qid,result in marking_results.items():
            c.execute("UPDATE attempt_answers SET maximum_marks=?,marker_confidence=?,marking_result_json=?,marking_status=?,mastery_evidence_eligible=? WHERE attempt_id=? AND question_db_id=?",
              (result['maximum_marks'],result['confidence'],integration_v1.canonical_json(result),
               'FINAL' if result['confirmed'] else 'AUTO_UNSCORED',1 if all_confirmed and result['evidence_eligible'] and not is_science_genius else 0,attempt_id,qid))
'''+fn[end:]
    fn=replace_once(fn,'        if not pending_reviews:\n','        if not auto_unscored:\n')
    a=replace_function(a,'submit_assessment_v4',fn)
    diagnostic="""    if 'marking_status' in attempt.keys() and attempt['marking_status']=='AUTO_UNSCORED':
        return dict(attempt=attempt,rows=rows,by_topic=[],by_lo=[],by_difficulty=[],by_skill=[],by_command=[],
          confidence={'confident_correct':0,'confident_wrong':0,'unsure_wrong':0,'guess_correct':0,'recorded':0},
          misconceptions=[],weak=None,strong=None,mastery='Unscored',mastery_state='Unscored',
          next_action={'title':'This answer could not be marked reliably','reason':'Your response is saved, but this attempt has not changed your mastery. There is no later human marking.','kind':'unscored'},
          recovery_comparison=None)
"""
    a=replace_once(a,"    if 'marking_status' in attempt.keys() and attempt['marking_status']=='PENDING_REVIEW':",diagnostic+"    if 'marking_status' in attempt.keys() and attempt['marking_status']=='PENDING_REVIEW':")
    # Existing incident route consumes exact attempt/session snapshot, never today's row.
    a=replace_once(a,"    question=None; attempt=None; written=None\n","    question=None; attempt=None; written=None\n    assessment_session_id=as_int(values.get('assessment_session_id'))\n")
    marker="    if written_attempt_id:\n        written=c.execute("
    incident="""    if assessment_session_id:
        assessment=get_assessment_session(c,assessment_session_id,session['user_id'])
        if not assessment or not question_id or question_id not in parse_ids(assessment['question_ids']):
            c.close();abort(404)
        try: question=integration_v1.pinned_question(assessment,question_id,question)
        except (ValueError,TypeError,KeyError): c.close();abort(409)
        context['assessment_session_id']=assessment_session_id
    if values.get('attempt_id') and not attempt:
        c.close();abort(404)
    if attempt and question_id:
        pinrow=c.execute('SELECT ph_question_pins_json FROM attempts WHERE id=?',(attempt_id,)).fetchone()
        try: question=integration_v1.pinned_question(pinrow,question_id,question)
        except (ValueError,TypeError,KeyError): c.close();abort(409)
"""
    a=replace_once(a,marker,incident+marker)
    a=replace_once(a,"      question_id=question_id,attempt_id=attempt_id,written_attempt_id=written_attempt_id,source=context['source'],page_path=context['page'])", "      question_id=question_id,attempt_id=attempt_id,written_attempt_id=written_attempt_id,assessment_session_id=assessment_session_id,source=context['source'],page_path=context['page'])")
    a=replace_once(a,"c.commit(); c.close(); flash('Improved version marked. Your original evidence remains unchanged.','success')",
        "c.commit(); c.close(); flash('Revised answer saved. Your original evidence remains unchanged.','success')")
    compile(a,str(ap),'exec');ap.write_text(a)

    surface=root/'templates/_learner_question_surface.html';s=surface.read_text()
    line=next(x for x in s.splitlines() if 'pilot_report_issue' in x)
    s=replace_once(s,line,'''{% if qa_sandbox|default(false) and q.membership_id %}
<a class="question-report-link" href="{{url_for('ux_content_review_staged_question',membership_id=q.membership_id,view='reviewer',batch=batch|default(''))}}#staged-report">⚑ Report this question</a>
{% else %}
<a class="question-report-link" href="{{url_for('pilot_report_issue',question_id=q.id,assessment_session_id=assessment_id|default(''),source='assessment_question',page=request.path)}}">⚑ Report this question</a>
{% endif %}
<input type="hidden" name="response_present" value="1"><input type="hidden" name="response_question_id" value="{{q.id}}">''')
    s=s.replace('data-left-item-id="{{ item.id }}" required','data-left-item-id="{{ item.id }}"')
    s=s.replace('data-order-item-id="{{ item.id }}" required','data-order-item-id="{{ item.id }}"')
    s+='\n{% if qtype != "unsupported" and not qa_sandbox|default(false) %}<button type="submit" class="btn alt" name="action" value="clear">Clear answer</button>{% endif %}\n'
    surface.write_text(s)
    p=root/'templates/ux_staged_content_review_question.html';s=p.read_text();s=s.replace('<form class="ux-flag-form"','<form id="staged-report" class="ux-flag-form"');p.write_text(s)
    p=root/'templates/report_issue.html';s=p.read_text();anchor='<input type="hidden" name="question_id"'
    # Template uses single quotes in the current sealed base; insert at first form instead.
    formend=s.index('>',s.index('<form'))+1
    s=s[:formend]+'''<input type="hidden" name="assessment_session_id" value="{{assessment_session_id or ''}}">'''+s[formend:];p.write_text(s)
    p=root/'templates/result.html';s=p.read_text()
    s=replace_once(s,"{% if a.marking_status=='PENDING_REVIEW' %}","{% if a.marking_status=='AUTO_UNSCORED' %}<div class=\"score\">Unscored</div><h2>Your answer is saved</h2><p>This response could not be marked reliably. This attempt has not changed your mastery.</p>{% elif a.marking_status=='PENDING_REVIEW' %}")
    s=replace_once(s,'<h2>{{a.correct_count}} / {{a.total_count}} correct</h2>', '<h2>{{a.correct_count}} / {{a.total_count}} correct</h2>{% if a.maximum_marks is not none %}<p>{{a.total_marks_awarded}} / {{a.maximum_marks}} marks</p>{% endif %}')
    s=replace_once(s,"{% if d.marking_status=='PENDING_REVIEW' %}","{% if d.marking_status=='AUTO_UNSCORED' %}<p>Not automatically scored • Your answer: {{d.selected_answer or 'No answer'}}</p>{% elif d.marking_status=='PENDING_REVIEW' %}")
    # No incorrect-answer remediation recommendations for an unscored attempt.
    s=s.replace('{% if weak_capsules %}',"{% if weak_capsules and a.marking_status=='FINAL' %}")
    p.write_text(s)
    p=root/'templates/written_result.html';s=p.read_text()
    notice="{% if a.result_state=='AUTO_UNSCORED' %}<section class=\"card\"><h2>Your answer is saved, but not scored</h2><p>This answer could not be marked reliably. It has not changed your mastery, and is not waiting for human marking.</p></section>{% endif %}"
    s=replace_once(s,'{% if data.pages %}',notice+'{% if data.pages %}')
    p.write_text(s)
    print('SCOREMAX_ASSESSMENT_CONTRACT_REPAIR_BUILD installed=true single_adapter=true pin_integrity=true marking_result_v2=true historical_scores_unchanged=true',flush=True)
