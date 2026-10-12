"""Install practice controls into existing response surfaces and routes."""
from pathlib import Path
import shutil


def apply(root):
    from ux_vnext_overlay.ux_assessment_contract_repair import replace_once as checked_replace, replace_function
    import ast
    def replace_once(text,old,new):
        # Some accepted overlays restore a previously assembled template. Only
        # an exact already-installed block is idempotent; drift still fails.
        return text if new in text else checked_replace(text,old,new)
    root=Path(root);here=Path(__file__).parent
    for name in ('templates/_structured_practice.html','static/structured_practice.js'):
        (root/name).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(here/name,root/name)
    p=root/'templates/_learner_question_surface.html';s=p.read_text()
    s=replace_once(s,'<span class="pill">{{ q.level }}</span>',
      "{% set is_structured_practice=marking_cfg.get('rubric',{}).get('native_scoring',{}).get('version')=='PH-NATIVE-OPERATIONS-3-PRACTICE' %}<span class=\"pill\">{{ 'Structured practice' if is_structured_practice else q.level }}</span>")
    s=replace_once(s,'<label>Your answer<textarea name="answer" rows="5">{{ saved }}</textarea></label>',
      '''{% if marking_cfg.get('rubric',{}).get('native_scoring',{}).get('version')=='PH-NATIVE-OPERATIONS-3-PRACTICE' %}
      {% set structured_saved=saved %}{% include '_structured_practice.html' %}
      {% else %}<label>Your answer<textarea name="answer" rows="5">{{ saved }}</textarea></label>{% endif %}''')
    p.write_text(s)
    p=root/'templates/written_question.html';s=p.read_text()
    s=replace_once(s,'<label>Mode<select name="attempt_mode">',
        "{% set structured=payload.get('native_contract',{}).get('native_scoring',{}).get('version')=='PH-NATIVE-OPERATIONS-3-PRACTICE' %}{% if structured %}<input type=\"hidden\" name=\"attempt_mode\" value=\"practice\">{% else %}<label>Mode<select name=\"attempt_mode\">")
    s=replace_once(s,'</select></label><label>Your answer<textarea name="answer_text" rows="14" required placeholder="Write your complete answer here..."></textarea></label>',
        '''</select></label>{% endif %}{% if structured %}{% set structured_field='answer_text' %}{% include '_structured_practice.html' %}{% else %}<label>Your answer<textarea name="answer_text" rows="14" required placeholder="Write your complete answer here..."></textarea></label>{% endif %}''')
    p.write_text(s)
    p=root/'app.py';s=p.read_text();tree=ast.parse(s)
    def change_function(name,old,new):
        nonlocal s
        n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
        fn='\n'.join(s.splitlines()[n.lineno-1:n.end_lineno]);fn=replace_once(fn,old,new)
        s=replace_function(s,name,fn)
    change_function('create_assessment_session','    expires_at=None', '''    for structured_qid in question_ids:
        structured_q=c.execute('SELECT * FROM questions WHERE id=?',(structured_qid,)).fetchone()
        checked=question_contracts.validate_assessment_contract(structured_q)
        from native_structured_practice import practice_contract
        if practice_contract(checked.get('constructed_contract',{}).get('rubric',{})):
            if mode!='practice' or (meta or {}).get('blueprint_snapshot') or (meta or {}).get('science_genius'):
                raise question_contracts.QuestionContractError('STRUCTURED_PRACTICE_ONLY')
    expires_at=None''')
    change_function('written_submit_typed','    payload=written_question_payload(q)', '''    payload=written_question_payload(q)
    from native_structured_practice import practice_contract
    if practice_contract(payload) and mode!='practice':
        c.close();abort(409,description='This version is approved for structured practice only.')''')
    # Retrying an old or manually altered session cannot bypass the purpose fence.
    change_function('submit_assessment_v4',"            marking_results[qid]=marking_result", """            if marking_result.get('assessment_purpose')=='STRUCTURED_PRACTICE' and a['mode']!='practice':
                raise question_contracts.QuestionContractError('STRUCTURED_PRACTICE_ONLY')
            marking_results[qid]=marking_result""")
    change_function('attempt_diagnostics',"    if 'marking_status' in attempt.keys() and attempt['marking_status']=='PENDING_REVIEW':", """    if any(safe_json(r['marking_result_json'],{}).get('assessment_purpose')=='STRUCTURED_PRACTICE' for r in rows):
        return dict(attempt=attempt,rows=rows,by_topic=[],by_lo=[],by_difficulty=[],by_skill=[],by_command=[],
          confidence={'confident_correct':0,'confident_wrong':0,'unsure_wrong':0,'guess_correct':0,'recorded':0},
          misconceptions=[],weak=None,strong=None,mastery='Structured practice',mastery_state='Structured practice',
          next_action={'title':'Structured practice result','reason':'These marks do not confer examination-format equivalence or exam-readiness mastery.','kind':'structured_practice'},
          recovery_comparison=None)
    if 'marking_status' in attempt.keys() and attempt['marking_status']=='PENDING_REVIEW':""")
    change_function('written_attempt_view',"    return {'attempt':attempt,'versions':versions,'runs':runs,'recovery':recovery,'pages':pages,'candidate':candidate}", """    from native_structured_practice import practice_contract
    structured=practice_contract(safe_json(attempt['question_json'],{}))
    return {'attempt':attempt,'versions':versions,'runs':runs,'recovery':recovery,'pages':pages,'candidate':candidate,'structured_practice':structured}""")
    compile(s,str(p),'exec');p.write_text(s)
    p=root/'templates/result.html';s=p.read_text()
    s=replace_once(s,'<p class="eyebrow">TEST COMPLETE</p>',"<p class=\"eyebrow\">{{ 'STRUCTURED PRACTICE COMPLETE' if diagnostic.mastery_state=='Structured practice' else 'TEST COMPLETE' }}</p>{% if diagnostic.mastery_state=='Structured practice' %}<p>These marks do not confer examination-format equivalence or exam-readiness mastery.</p>{% endif %}")
    p.write_text(s)
    p=root/'templates/written_result.html';s=p.read_text()
    s=replace_once(s,'{% set a=data.attempt %}',"{% set a=data.attempt %}{% if data.structured_practice %}<p>Structured practice only. These marks do not confer examination-format equivalence or exam-readiness mastery.</p>{% endif %}")
    s=replace_once(s,'<label>Revised answer<textarea name="answer_text" rows="12" required>{{data.versions[-1].confirmed_transcript or data.versions[-1].answer_text}}</textarea></label>',
      "{% if data.structured_practice %}{% set structured_field='answer_text' %}{% set structured_saved=data.versions[-1].confirmed_transcript or data.versions[-1].answer_text %}{% include '_structured_practice.html' %}{% else %}<label>Revised answer<textarea name=\"answer_text\" rows=\"12\" required>{{data.versions[-1].confirmed_transcript or data.versions[-1].answer_text}}</textarea></label>{% endif %}")
    p.write_text(s)
