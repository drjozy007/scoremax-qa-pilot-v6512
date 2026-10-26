"""Attach paid practice feedback to the native result and WSGI target."""
from pathlib import Path
import shutil
def apply(root):
    root=Path(root);source=Path(__file__).parent/'paid_ai_marking_20261026'
    for name in ['paid_ai_marking.py']:
        text=(source/name).read_text(encoding='utf8');compile(text,str(source/name),'exec')
        shutil.copyfile(source/name,root/name)
    shutil.copyfile(source/'paid_ai_feedback.html',root/'templates/paid_ai_feedback.html')
    p=root/'scoremax_production.py';text=p.read_text(encoding='utf8')
    anchor='application=scoremax.app\napp=application'
    replacement='from paid_ai_marking import install as install_paid_ai_marking\ninstall_paid_ai_marking(scoremax)\n'+anchor
    if text.count(anchor)!=1:raise RuntimeError('PAID_AI_NATIVE_WSGI_ANCHOR_MISMATCH')
    text=text.replace(anchor,replacement,1);compile(text,str(p),'exec')
    p.write_text(text,encoding='utf8',newline='\n')
    p=root/'templates/result.html';text=p.read_text(encoding='utf8')
    anchor='<a class="question-report-link"'
    replacement=('{% if paid_ai_feedback_enabled() and d.marking_status==\'AUTO_UNSCORED\' %}'
        '<p><a href="{{url_for(\'paid_ai_feedback\',attempt_id=a.id,question_id=d.question_db_id)}}">Paid AI practice feedback</a></p>'
        '{% endif %}\n'+anchor)
    if text.count(anchor)!=1:raise RuntimeError('PAID_AI_NATIVE_RESULT_ANCHOR_MISMATCH')
    p.write_text(text.replace(anchor,replacement,1),encoding='utf8',newline='\n')
    return {'official_score_or_mastery_changes':False,'default_budget_micro_usd':0,'new_provider_calls':0}
