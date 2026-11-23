"""Additive UK11 explanation overlay for an isolated, disposable ScoreMax runtime.

Does not perform production deployment, provider setup, new DB schema or writes.
Fail closed on any unknown native template/startup structure.
"""
from __future__ import annotations
import ast
import shutil
from pathlib import Path

SOURCES=('ai_explanation_candidate.py','uk11_result_explanation.py')
TEMPLATE='uk11_explain_mistake.html'
START_ANCHOR='application=scoremax.app\napp=application'
RESULT_ANCHOR='<a class="question-report-link"'
QUERY_ANCHOR="details=c.execute('''SELECT aa.*,q.question,q.answer,q.explanation,q.level,q.subtopic,q.family_id,q.variant,"
RESULT_MARKER='<!-- UK11 APPROVED EXPLANATION: candidate, default off -->'
RESULT_BLOCK='''<!-- UK11 APPROVED EXPLANATION: candidate, default off -->
{% if uk11_explanation_available() and not d.is_correct and d.selected_answer and (d.explanation or d.capsule_id) and d.ph_question_id and d.ph_market_id == 'UK' and d.ph_is_auto_markable == 1 and d.marks_awarded is not none and d.marking_status|default('') not in ['AUTO_UNSCORED', 'UNSCORED', 'PENDING'] %}
<a class="btn alt" href="{{ url_for('uk11_explain_mistake',attempt_id=a.id,question_id=d.question_db_id) }}">Explain my mistake</a>
{% endif %}
'''
START_CODE='''# UK11 read-only explanation: feature OFF by default; native owned-material check retained.
from uk11_result_explanation import install as install_uk11_explanation
install_uk11_explanation(scoremax)
'''


def apply(root, source=None):
    root=Path(root)
    source=Path(source or Path(__file__).parent)
    if not (root/'.uk11_disposable_qualification_runtime').is_file():
        raise RuntimeError('DISPOSABLE_RUNTIME_REQUIRED')
    for p in SOURCES+(TEMPLATE,):
        if not (source/p).is_file():
            raise RuntimeError('UK_EXPLANATION_SOURCE_MISSING')
    wsgi=root/'scoremax_production.py'
    result=root/'templates/result.html'
    app_source=root/'app.py'
    if not wsgi.is_file() or not result.is_file() or not app_source.is_file():
        raise RuntimeError('NATIVE_RUNTIME_MISSING')
    wsgi_text=wsgi.read_text(encoding='utf-8')
    result_text=result.read_text(encoding='utf-8')
    app_text=app_source.read_text(encoding='utf-8')
    if 'install_uk11_explanation' in wsgi_text or RESULT_MARKER in result_text or 'SELECT aa.*,q.ph_market_id,q.ph_is_auto_markable,q.question' in app_text:
        raise RuntimeError('UK_EXPLANATION_ALREADY_PRESENT')
    if wsgi_text.count(START_ANCHOR)!=1 or result_text.count(RESULT_ANCHOR)!=1 or app_text.count(QUERY_ANCHOR)!=1:
        raise RuntimeError('NATIVE_ANCHOR_MISMATCH')
    if any((root/f).exists() for f in SOURCES) or (root/'templates'/TEMPLATE).exists():
        raise RuntimeError('UK_EXPLANATION_TARGET_CONFLICT')
    # The native paid-AI installation is the authority for owned_material, even
    # when the paid provider feature is switched off. Reject mismatched startup.
    if 'install_written_ai(scoremax)' not in wsgi_text:
        raise RuntimeError('NATIVE_WRITTEN_OWNERSHIP_HOOK_MISSING')
    next_w=wsgi_text.replace(START_ANCHOR,START_CODE+START_ANCHOR,1)
    next_r=result_text.replace(RESULT_ANCHOR,RESULT_BLOCK+RESULT_ANCHOR,1)
    next_app=app_text.replace(QUERY_ANCHOR,QUERY_ANCHOR.replace('SELECT aa.*,q.question','SELECT aa.*,q.ph_market_id,q.ph_is_auto_markable,q.question'),1)
    ast.parse(next_w)
    ast.parse(next_app)
    from jinja2 import Environment
    Environment().parse(next_r)
    Environment().parse((source/TEMPLATE).read_text(encoding='utf-8'))
    for f in SOURCES:
        compile((source/f).read_text(encoding='utf-8'),f,'exec')
    # No changes until preflight succeeds; roll back all files on an I/O error.
    wsgi_before=wsgi.read_bytes()
    result_before=result.read_bytes()
    app_before=app_source.read_bytes()
    added=[root/f for f in SOURCES]+[root/'templates'/TEMPLATE]
    try:
        for f in SOURCES:
            shutil.copyfile(source/f,root/f)
        shutil.copyfile(source/TEMPLATE,root/'templates'/TEMPLATE)
        wsgi.write_text(next_w,encoding='utf-8',newline='\n')
        result.write_text(next_r,encoding='utf-8',newline='\n')
        app_source.write_text(next_app,encoding='utf-8',newline='\n')
    except BaseException:
        wsgi.write_bytes(wsgi_before)
        result.write_bytes(result_before)
        app_source.write_bytes(app_before)
        for path in added:
            if path.exists():path.unlink()
        raise
    return {'candidate_only':True,'new_database_tables':0,'provider_calls':0,
            'official_score_or_mastery_changes':False,'default_enabled':False,
            'files':[str(p) for p in (wsgi,app_source,result,root/'templates'/TEMPLATE)]+[str(root/f) for f in SOURCES]}
