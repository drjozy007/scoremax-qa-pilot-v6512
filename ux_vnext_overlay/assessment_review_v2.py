"""Build-time donors for the existing staged reviewer. No separate question adapter."""

def _staged_learner_render_context(q):
    import app as scoremax
    q['id']=int(q.get('membership_id') or q.get('id') or 0)
    try:
        ac,mc,_=scoremax.question_contracts.assessment_configs(q)
    except (ValueError,TypeError,KeyError):
        ac,mc={},{}
        q['qtype']='unsupported';q['ph_response_contract']='unsupported'
    return {'qtype':scoremax.canonical_question_type(q),'options':ac.get('options') or [],
            'answer_cfg':ac,'marking_cfg':mc,'answers':{},'saved_struct':{},'saved_positions':{},
            'confidence':{},'response_times':{},'qa_sandbox':True,'qa_session_id':'STAGED-POWER-HOUSE',
            'qa_render_checksum':str(q.get('ph_question_checksum_sha256') or ''),
            'assessment':{'mode':'review'},'exam_meta':{}}


def _staged_release_markable(ctx,q=None):
    import app as scoremax
    try:
        if (q or {}).get('_contract_error'):
            return False,str(q['_contract_error'])
        scoremax.question_contracts.validate_assessment_contract(q or {})
        return True,''
    except (ValueError,TypeError,KeyError) as exc:
        return False,str(exc)


def _staged_canonical_surface_probe(q):
    import re
    ctx=_staged_learner_render_context(q)
    html=render_template('_learner_question_surface.html',q=q,**ctx)
    controls=re.findall(r'<(?:input|textarea|select)\b[^>]*>',html,flags=re.I)
    interactive=any(re.search(r'name=[\"\'](?:answer|match::[^\"\']+|order::[^\"\']+)[\"\']',tag,re.I) and not re.search(r'type=[\"\']hidden',tag,re.I) for tag in controls)
    return ctx,bool(interactive and ctx['qtype']!='unsupported'),html
