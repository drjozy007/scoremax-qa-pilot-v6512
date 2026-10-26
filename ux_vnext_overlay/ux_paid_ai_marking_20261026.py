"""Consolidate semantic interpretation into the accepted written-response pathway."""
import ast,shutil
from pathlib import Path

def function_source(path,name):
    text=Path(path).read_text(encoding='utf8')
    node=next(n for n in ast.parse(text).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    return '\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])+'\n'

def apply(root):
    root=Path(root);overlay=Path(__file__).parent;source=overlay/'paid_ai_marking_20261026'
    for old in (root/'paid_ai_marking.py',root/'templates/paid_ai_feedback.html'):
        if old.exists():raise RuntimeError('START_FROM_ACCEPTED_PUBLIC_RUNTIME_NOT_PARALLEL_AI')
    adapter=(source/'written_ai_adapter.py').read_text(encoding='utf8')
    compile(adapter,'written_ai_adapter.py','exec')
    shutil.copyfile(source/'written_ai_adapter.py',root/'written_ai_adapter.py')
    shutil.copyfile(source/'_written_marking_run.html',root/'templates/_written_marking_run.html')
    p=root/'written_response_engine.py';text=p.read_text(encoding='utf8')
    helper=function_source(overlay/'assessment_written_response_v2.py','persist_written_marking_result')
    if 'def persist_written_marking_result(' in text:raise RuntimeError('WRITTEN_WRITER_ALREADY_INSTALLED')
    p.write_text(text+'\n\n'+helper,encoding='utf8',newline='\n')
    p=root/'app.py';text=p.read_text(encoding='utf8')
    original=function_source(p,'written_evaluate_attempt')
    replacement=function_source(overlay/'assessment_marking_v2.py','written_evaluate_attempt')
    if text.count(original)!=1:raise RuntimeError('EXISTING_WRITTEN_EVALUATOR_ANCHOR_MISMATCH')
    text=text.replace(original,replacement,1)
    anchor="if not job or not str(job['state'] or '').startswith('FAILED'):"
    if text.count(anchor)!=1:raise RuntimeError('EXISTING_ADMIN_RETRY_ANCHOR_MISMATCH')
    text=text.replace(anchor,"if not job or job['job_type']=='SEMANTIC_FEEDBACK' or not str(job['state'] or '').startswith('FAILED'):",1)
    compile(text,str(p),'exec');p.write_text(text,encoding='utf8',newline='\n')
    p=root/'scoremax_production.py';text=p.read_text(encoding='utf8')
    anchor='application=scoremax.app\napp=application'
    replacement='from written_ai_adapter import install as install_written_ai\ninstall_written_ai(scoremax)\n'+anchor
    if text.count(anchor)!=1:raise RuntimeError('NATIVE_WSGI_ANCHOR_MISMATCH')
    p.write_text(text.replace(anchor,replacement,1),encoding='utf8',newline='\n')
    p=root/'templates/written_result.html';text=p.read_text(encoding='utf8')
    begin=text.index('{% for run in data.runs %}')
    end=text.index('\n<section class="grid">',begin)
    text=text[:begin]+"{% for run in data.runs %}{% include '_written_marking_run.html' %}{% endfor %}"+text[end:]
    p.write_text(text,encoding='utf8',newline='\n')
    p=root/'templates/result.html';text=p.read_text(encoding='utf8')
    anchor='<a class="question-report-link"'
    action="""{% if paid_ai_feedback_enabled() and d.marking_status=='AUTO_UNSCORED' %}
{% set run=written_ai_feedback(a.id,d.question_db_id) %}
{% if run %}{% include '_written_marking_run.html' %}{% else %}
<form method="post" action="{{url_for('paid_ai_feedback',attempt_id=a.id,question_id=d.question_db_id)}}">
{% if csrf_token %}<input type="hidden" name="_csrf_token" value="{{csrf_token()}}">{% endif %}
<label><input type="checkbox" name="confirm_ai_processing" value="yes" required> Send this saved answer and approved rubric for provisional AI practice feedback.</label>
<p class="muted">Paid members only · 20 requests per day, 200 per month. This feedback does not change official marks or mastery.</p>
<button class="btn" type="submit">Request practice feedback</button>
</form>{% endif %}{% endif %}
"""
    if text.count(anchor)!=1:raise RuntimeError('NATIVE_RESULT_ANCHOR_MISMATCH')
    p.write_text(text.replace(anchor,action+anchor,1),encoding='utf8',newline='\n')
    return {'additional_tables':0,'shared_written_evidence_writer':True,
            'official_score_or_mastery_changes':False,'default_budget_micro_usd':0,
            'new_provider_calls':0,'independent_semantic_approval':'PENDING'}
