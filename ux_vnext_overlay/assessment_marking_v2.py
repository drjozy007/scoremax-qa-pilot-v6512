"""Build-time structured-result adapters for the existing app assessment route."""

def mark_question_result(q,selected,blueprint_marking_rules=None):
    import math
    q=dict(q)
    validated=question_contracts.validate_assessment_contract(q)
    qt=validated['qtype'];maximum=validated['maximum_marks']
    ac,mc,_=question_contracts.assessment_configs(q)
    rules=blueprint_marking_rules if isinstance(blueprint_marking_rules,dict) else {}
    def number(value,label,positive=False):
        try:
            if isinstance(value,bool) or not math.isfinite(float(value)) or (positive and float(value)<=0):raise ValueError()
            return float(value)
        except (TypeError,ValueError,OverflowError):
            raise question_contracts.QuestionContractError('INVALID_MARKING_RULE_'+label)
    correct_max=number(rules.get('correct_marks',maximum),'CORRECT',True)
    incorrect=number(rules.get('incorrect_marks',mc.get('negative_marks',0)),'INCORRECT')
    unanswered=number(rules.get('unanswered_marks',0),'UNANSWERED')
    if incorrect>correct_max or unanswered>correct_max:
        raise question_contracts.QuestionContractError('MARKING_RULE_OUT_OF_BOUNDS')
    if 'partial_credit_allowed' in rules and not isinstance(rules['partial_credit_allowed'],bool):
        raise question_contracts.QuestionContractError('PARTIAL_CREDIT_RULE_INVALID')
    text=str(selected or '').strip()
    if len(text)>10000:raise question_contracts.QuestionContractError('RESPONSE_LIMIT_EXCEEDED')
    if qt=='constructed_response':
        from ux_constructed_auto_marker import mark
        result=mark(validated['constructed_contract'],text)
        final=result.get('status')=='MARK_CONFIRMED' and result.get('evidence_eligible') is True
        earned=None
        if final:
            fraction=float(result['marks_awarded'])/maximum
            partial=rules.get('partial_credit_allowed',True)
            if not isinstance(partial,bool):raise question_contracts.QuestionContractError('PARTIAL_CREDIT_RULE_INVALID')
            if not text:earned=unanswered
            elif fraction>=1:earned=correct_max
            elif fraction<=0:earned=incorrect
            else:earned=correct_max*fraction if partial else incorrect
        return {**result,'marks_awarded':earned,'maximum_marks':correct_max,'source_maximum_marks':maximum,'confirmed':final,
                'evidence_eligible':final,'response_type':qt,'result_contract_version':'SM-MARK-RESULT-2','misconception':''}
    # Existing objective marker remains authoritative; do not duplicate its scoring logic.
    q['answer_config']=json.dumps(ac);q['marking_config']=json.dumps(mc)
    ok,earned,misconception=_mark_objective_response(q,text,rules)
    if misconception=='__PENDING_REVIEW__':
        raise question_contracts.QuestionContractError('HUMAN_MARKING_NOT_AVAILABLE')
    earned=number(earned,'AWARDED')
    if earned>correct_max:raise question_contracts.QuestionContractError('AWARD_EXCEEDS_MAXIMUM')
    return {'is_correct':bool(ok),'marks_awarded':earned,'maximum_marks':correct_max,'confirmed':True,
            'evidence_eligible':True,'confidence':1.0,'status':'MARK_CONFIRMED','feedback':[],
            'response_type':qt,'result_contract_version':'SM-MARK-RESULT-2','marker_version':'objective-v1',
            'misconception':misconception}


def mark_question_response(q,selected,blueprint_marking_rules=None):
    result=mark_question_result(q,selected,blueprint_marking_rules)
    if not result['confirmed']:
        raise question_contracts.QuestionContractError('AUTOMATIC_MARK_UNRESOLVED')
    return result['is_correct'],result['marks_awarded'],result['misconception']
