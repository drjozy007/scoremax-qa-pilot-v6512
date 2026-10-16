"""Checked integration into the accepted receiver, sessions and learner surface."""
import ast
from pathlib import Path
import shutil
from ux_vnext_overlay.ux_assessment_contract_repair import replace_once, replace_function, donors, add_functions


def apply(root):
    root = Path(root); here = Path(__file__).parent
    for name in ('guided_self_assessment.py', 'templates/guided_self_review.html'):
        shutil.copy2(here/name, root/name)
    def edit(path, fn):
        p = root/path; s = fn(p.read_text())
        if str(p).endswith('.py'): compile(s, str(p), 'exec')
        p.write_text(s)
    def change(s, name, old, new):
        node = next(n for n in ast.parse(s).body if isinstance(n, ast.FunctionDef) and n.name == name)
        fn = ast.get_source_segment(s, node)
        return replace_function(s, name, replace_once(fn, old, new))

    def contracts(s):
        return change(s, 'validate_assessment_contract', "    if qt=='constructed_response':", '''    from guided_self_assessment import from_question
    try:
        guided = from_question(q)
    except ValueError as exc:
        raise QuestionContractError(str(exc)) from exc
    if guided:
        if qt!='constructed_response': raise QuestionContractError('GUIDED_WRITTEN_RESPONSE_REQUIRED')
        return {'qtype':qt,'maximum_marks':maximum,'guided_contract':guided}
    if qt=='constructed_response':''')
    edit('question_contract_engine.py', contracts)
    def projection(s):
        s = change(s, 'effective_projection', "    out['answer_config']=canonical_json(ac);out['marking_config']=canonical_json(mc)", '''    from guided_self_assessment import contract as guided_contract
    try:
        guided = guided_contract(mc,out.get('question'),out.get('answer'),out.get('marks'))
    except ValueError as exc:
        raise question_contracts.QuestionContractError(str(exc)) from exc
    if guided: mc['auto_markable']=False
    out['answer_config']=canonical_json(ac);out['marking_config']=canonical_json(mc)''')
        return s
    edit('scoremax_integration_v1.py', projection)
    def marker(s):
        return change(s, 'compile_contract', '        rubric = mc.get(\'rubric\')', '''        rubric = mc.get('rubric')
        if isinstance(rubric,dict) and 'guided_self_assessment' in rubric:
            return None  # Unscored delivery never compiles into a marking contract.''')
    edit('ux_constructed_auto_marker.py', marker)
    def app(s):
        s = 'from flask import make_response\n'+s
        live_nodes=[n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='live_question_clause']
        live=ast.get_source_segment(s,live_nodes[-1])
        live=replace_once(live,"'('+base+') AND ('", "'('+base+') AND CASE WHEN json_valid('+alias+\".marking_config) THEN json_type(\"+alias+\".marking_config,'$.rubric.guided_self_assessment') IS NULL ELSE 1 END AND (\"")
        s=replace_function(s,'live_question_clause',live,last=True)
        s = add_functions(s, donors(here/'guided_assessment_routes.py'))
        s += "\napp.add_url_rule('/test/session/<int:assessment_id>/guidance', 'guided_session_review', guided_session_review, methods=['GET','POST'])\n"
        s += "app.add_url_rule('/test/session/<int:assessment_id>/retry', 'guided_retry_session', guided_retry_session, methods=['POST'])\n"
        s = change(s, 'create_assessment_session', '    question_ids=list(dict.fromkeys(filter_live_question_ids(c,requested)))', '''    guided_mode=(meta or {}).get('response_mode')=='GUIDED_SELF_ASSESSMENT'
    if guided_mode:
        if mode!='practice' or duration_minutes or any((meta or {}).get(k) for k in ('blueprint_snapshot','assessment_blueprint_id','assignment_id','challenge_id','science_genius')):
            raise question_contracts.QuestionContractError('GUIDED_PRACTICE_ONLY')
        slots=','.join('?' for _ in requested)
        guided_programme=canonical_programme((meta or {}).get('programme') or student_programme(c,student_id))
        guided_scope,guided_params=_programme_scope_sql(_programme_aliases(guided_programme),'q')
        available={r['id'] for r in c.execute(f'SELECT q.id FROM questions q WHERE q.id IN ({slots}) AND {guided_live_question_clause("q")} AND {guided_scope}',requested+guided_params)} if requested else set()
        question_ids=[i for i in requested if i in available]
    else:
        question_ids=list(dict.fromkeys(filter_live_question_ids(c,requested)))''')
        s = change(s, 'create_assessment_session', "        from native_structured_practice import practice_contract", '''        if bool(checked.get('guided_contract')) != guided_mode:
            raise question_contracts.QuestionContractError('GUIDED_SESSION_MODE_MISMATCH')
        from native_structured_practice import practice_contract''')
        s = change(s, 'mark_question_result', "    qt=validated['qtype'];maximum=validated['maximum_marks']", '''    if validated.get('guided_contract'):
        raise question_contracts.QuestionContractError('GUIDED_PRACTICE_HAS_NO_MARKS')
    qt=validated['qtype'];maximum=validated['maximum_marks']''')
        s = change(s, 'submit_assessment_v4', "        submission_meta=safe_json(a['meta_json'],{})", '''        guided_response=guided_submit_session(c,a)
        if guided_response is not None: return guided_response
        submission_meta=safe_json(a['meta_json'],{})''')
        # A request can read in_progress before another request freezes the
        # response. The write itself must still require that open state.
        s = change(s, 'save_assessment',
            '        c.execute(f"UPDATE assessment_sessions SET {\', \'.join(sets)} WHERE id=?",params)',
            '''        updated=c.execute(f"""UPDATE assessment_sessions SET {', '.join(sets)} WHERE id=?
            AND (COALESCE(json_extract(CASE WHEN json_valid(meta_json) THEN meta_json ELSE '{{}}' END,
                 '$.response_mode'),'')<>'GUIDED_SELF_ASSESSMENT' OR status='in_progress')""",params)
        if updated.rowcount!=1:
            raise question_contracts.QuestionContractError('GUIDED_SESSION_CLOSED')''')
        s = change(s, 'take_test_v4', "        if a['status']!='in_progress':", '''        if a['status']=='guided_submitted':
            c.close(); return redirect(url_for('guided_session_review',assessment_id=assessment_id))
        if a['status']!='in_progress':''')
        s = change(s, 'take_test_v4', "            action=request.form.get('action','next')", '''            if safe_json(a['meta_json'],{}).get('response_mode')=='GUIDED_SELF_ASSESSMENT' and len(answer)>10000:
                raise question_contracts.QuestionContractError('GUIDED_RESPONSE_LIMIT')
            action=request.form.get('action','next')''')
        # Remove answer-bearing objects from the initial Jinja context, not only visible HTML.
        s = change(s, 'take_test_v4', "        saved_current=answers.get(str(ids[idx]),'')", '''        if exam_meta.get('response_mode')=='GUIDED_SELF_ASSESSMENT':
            from guided_self_assessment import from_question
            if not from_question(q): raise question_contracts.QuestionContractError('GUIDED_CONTRACT_REQUIRED')
            q={k:q[k] for k in ('id','question','marks','level','stimulus_data') if k in q.keys()}
            answer_cfg={}; marking_cfg={'guided_self_assessment':True}; options=[]
        saved_current=answers.get(str(ids[idx]),'')''')
        s = change(s, 'test_setup', "    subject_cards=_subject_map(c,session['user_id'])", '''    subject_cards=_subject_map(c,session['user_id'])
    if request.args.get('response_mode')=='GUIDED_SELF_ASSESSMENT':
        guided=guided_setup_context(c,session['user_id'])
        programmes=guided['programmes'];subjects=guided['subjects']
        subject_programmes=guided['subject_programmes'];chapters=guided['chapters']
        topics=guided['topics'];subject_cards=guided['subject_cards']''')
        s = change(s, 'test_setup', "'subtopic','level','scope','mode']", "'subtopic','level','scope','mode','response_mode']")
        s = change(s, 'test_start', "    mode=request.form.get('mode','practice')", '''    mode=request.form.get('mode','practice')
    guided_mode=request.form.get('response_mode')=='GUIDED_SELF_ASSESSMENT'
    if guided_mode and (mode!='practice' or request.form.get('mcq_only') or request.form.get('question_type')=='MCQ'):
        abort(409,description='Guided written practice is separate from scored and MCQ-only tests.')''')
        s = change(s, 'test_start', "    clauses=[live_question_clause('q'),'q.subject=?']", "    clauses=[guided_live_question_clause('q') if guided_mode else live_question_clause('q'),'q.subject=?']")
        s = change(s, 'test_start', "    state=student_subject_state(access_check,session['user_id'],subject,programme)", '''    if guided_mode:
        programme=canonical_programme(programme or student_programme(access_check,session['user_id']))
        guided_scope,guided_params=_programme_scope_sql(_programme_aliases(programme),'q')
        guided_available=bool(access_check.execute(f'SELECT 1 FROM questions q WHERE {guided_live_question_clause("q")} AND {guided_scope} AND lower(q.subject)=lower(?) LIMIT 1',guided_params+[subject]).fetchone())
        state=commercial_access.subject_state(access_check,session['user_id'],programme,subject,available=guided_available,commercial_gates_enabled=COMMERCIAL_GATES_ENABLED)
    else:
        state=student_subject_state(access_check,session['user_id'],subject,programme)''')
        s = change(s, 'test_start', "        clauses+=['q.programme=?']; params+=[programme]", '''        if guided_mode:
            guided_scope,guided_params=_programme_scope_sql(_programme_aliases(programme),'q')
            clauses.append(guided_scope);params+=guided_params
        else:
            clauses+=['q.programme=?']; params+=[programme]''')
        s = change(s, 'test_start', "        clauses+=['q.chapter=?']; params+=[request.form['chapter']]", '''        if guided_mode:
            guided_chapter,guided_params=_programme_chapter_scope_sql(programme,request.form['chapter'],'q')
            clauses.append(guided_chapter);params+=guided_params
        else:
            clauses+=['q.chapter=?']; params+=[request.form['chapter']]''')
        s = change(s, 'test_start', '        if programme:\n            all_chapters=', '''        if guided_mode:
            all_chapters=guided_chapters(ctmp,programme,subject)
        elif programme:
            all_chapters=''')
        s = change(s, 'test_start', '''                clauses+=[f"q.chapter IN ({','.join('?' for _ in chapters)})"]
                params+=chapters''', '''                if guided_mode:
                    parts=[_programme_chapter_scope_sql(programme,ch,'q') for ch in chapters]
                    clauses.append('('+ ' OR '.join('('+sql+')' for sql,values in parts)+')')
                    params += [value for sql,values in parts for value in values]
                else:
                    clauses+=[f"q.chapter IN ({','.join('?' for _ in chapters)})"]
                    params+=chapters''')
        s = change(s, 'test_start', '''        clauses+=[f"q.chapter IN ({','.join('?' for _ in chapters)})"]
        params+=chapters''', '''        if guided_mode:
            parts=[_programme_chapter_scope_sql(programme,ch,'q') for ch in chapters]
            clauses.append('('+ ' OR '.join('('+sql+')' for sql,values in parts)+')')
            params += [value for sql,values in parts for value in values]
        else:
            clauses+=[f"q.chapter IN ({','.join('?' for _ in chapters)})"]
            params+=chapters''')
        s = change(s, 'test_start', '    assessment_id=create_assessment_session(', '''    if guided_mode:
        duration=None
        meta={k:meta[k] for k in ('scope','programme','subject','chapters','topic','subtopic','level')}
        meta.update(response_mode='GUIDED_SELF_ASSESSMENT',assessment_kind='guided_self_assessment')
    assessment_id=create_assessment_session(''')
        return s
    edit('app.py', app)
    edit('ux_content_reviewer.py', lambda s: change(s, '_staged_learner_render_context',
        "    return {'qtype':scoremax.canonical_question_type(q)",
        "    from guided_self_assessment import from_question\n    if from_question(q): mc={'guided_self_assessment':True};ac={}\n    return {'qtype':scoremax.canonical_question_type(q)"))
    edit('templates/_learner_question_surface.html', lambda s: replace_once(s,
        "{{ 'Structured practice' if is_structured_practice else q.level }}",
        "{{ 'Guided practice · no score' if marking_cfg.get('guided_self_assessment') else ('Structured practice' if is_structured_practice else q.level) }}"))
    edit('templates/take_test_v4.html', lambda s: replace_once(replace_once(s,
        "{% if assessment.mode=='practice' %}", "{% if assessment.mode=='practice' and exam_meta.get('response_mode')!='GUIDED_SELF_ASSESSMENT' %}"),
        '<div class="question-card">', '''{% if exam_meta.get('response_mode')=='GUIDED_SELF_ASSESSMENT' %}<p>Write your answer first. After you submit, compare it with the approved answer. This practice has no score.</p>{% if exam_meta.get('guided_parent_session_id') %}<p>This is an improvement attempt after viewing the answer.</p>{% endif %}{% endif %}<div class="question-card">'''))
    old_setup='<div class="form-grid"><label>Exam / programme'
    new_setup="""<div class="form-grid"><label>Practice type<select name="response_mode" aria-label="Practice type"><option value="SCORED">Scored practice</option><option value="GUIDED_SELF_ASSESSMENT" {% if prefill.response_mode=='GUIDED_SELF_ASSESSMENT' %}selected{% endif %}>Guided written practice · no score</option></select></label><label>Exam / programme"""
    # The accepted materializer can retain templates on a repeat build. Only the
    # exact completed insertion is idempotent; every other anchor drift fails.
    edit('templates/test_setup.html', lambda s: s if s.count(new_setup)==1 else replace_once(s,old_setup,new_setup))

    def guided_setup_template(s):
        s=replace_once(s,'<section class="compact-page">', '''<section class="compact-page"><p>{% if prefill.response_mode=='GUIDED_SELF_ASSESSMENT' %}Guided written practice · no score · untimed. <a href="{{url_for('test_setup')}}">Scored practice</a>{% else %}<a href="{{url_for('test_setup',response_mode='GUIDED_SELF_ASSESSMENT',scope='full')}}">Guided written practice · no score</a>{% endif %}</p>''')
        s=replace_once(s,"{% if subjects %}<form method=\"post\" action=\"{{url_for('scoremax_test_me')}}\"", "{% if subjects and prefill.response_mode!='GUIDED_SELF_ASSESSMENT' %}<form method=\"post\" action=\"{{url_for('scoremax_test_me')}}\"")
        s=replace_once(s,'No live question bank is available yet.', "{{ 'Use Build My Own Test below for guided written practice.' if prefill.response_mode=='GUIDED_SELF_ASSESSMENT' else 'No live question bank is available yet.' }}")
        s=s.replace("url_for('test_setup',scope=", "url_for('test_setup',response_mode=prefill.response_mode,scope=")
        s=replace_once(s,'<label>Timing<select id="timingSelect">', '''<label {% if prefill.response_mode=='GUIDED_SELF_ASSESSMENT' %}hidden{% endif %}>Timing<select id="timingSelect">''')
        s+='''\n<script>document.querySelector('select[name="response_mode"]')?.addEventListener('change',e=>{const u=new URL(window.location.href);u.searchParams.set('response_mode',e.target.value);u.searchParams.set('scope','full');u.hash='custom';window.location.href=u.href;});</script>\n'''
        return s
    edit('templates/test_setup.html',guided_setup_template)
