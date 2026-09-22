"""Build-time donors for the EXISTING question_contract_engine; no parallel runtime."""

def assessment_configs(row):
    import math
    q=dict(row)
    configs=[]
    for field in ('answer_config','marking_config'):
        value=q.get(field)
        if isinstance(value,str):
            try:
                value=json.loads(value or '{}',parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
            except (ValueError,TypeError):
                raise QuestionContractError('MALFORMED_'+field.upper())
        if not isinstance(value,dict):
            raise QuestionContractError('MISSING_'+field.upper())
        configs.append(value)
    ac,mc=configs
    maximum=mc.get('marks',q.get('marks'))
    try:
        if isinstance(maximum,bool) or not math.isfinite(float(maximum)) or float(maximum)<=0:
            raise ValueError()
    except (TypeError,ValueError,OverflowError):
        raise QuestionContractError('INVALID_MAXIMUM_MARKS')
    return ac,mc,float(maximum)


def validate_assessment_contract(row):
    import math
    q=dict(row); qt=runtime_type_from_row(q)
    ac,mc,maximum=assessment_configs(q)
    if qt=='constructed_response':
        from ux_constructed_auto_marker import compile_contract
        contract=compile_contract(ac,q.get('answer') or '',maximum,q.get('question') or '',q.get('command_word') or '',mc)
        if contract is None:
            raise QuestionContractError('SELF_MARKING_CONTRACT_REQUIRED')
        return {'qtype':qt,'maximum_marks':maximum,'constructed_contract':contract}
    if mc.get('auto_markable') is not True:
        raise QuestionContractError('SELF_MARKING_CONTRACT_REQUIRED')
    if qt in {'single_choice','true_false','multiple_select'}:
        options=ac.get('options')
        if not isinstance(options,list) or len(options)<2 or any(not isinstance(x,dict) or not isinstance(x.get('id'),str) or not x['id'].strip() or not str(x.get('text') or '').strip() for x in options):
            raise QuestionContractError('CHOICE_OPTIONS_REQUIRED')
        ids=[x['id'] for x in options]
        keys=mc.get('correct_option_ids')
        if len(ids)!=len(set(ids)) or not isinstance(keys,list) or not keys or any(not isinstance(k,str) or k not in ids for k in keys) or len(keys)!=len(set(keys)):
            raise QuestionContractError('CHOICE_KEY_INVALID')
        if qt!='multiple_select' and len(keys)!=1:
            raise QuestionContractError('SINGLE_CHOICE_KEY_INVALID')
    elif qt=='numerical':
        try:
            target=mc['correct_value'];tol=mc.get('tolerance',0)
            if isinstance(target,bool) or isinstance(tol,bool) or not math.isfinite(float(target)) or not math.isfinite(float(tol)) or float(tol)<0:
                raise ValueError()
        except (KeyError,TypeError,ValueError,OverflowError):
            raise QuestionContractError('NUMERICAL_KEY_INVALID')
    elif qt=='fill_blank':
        vals=ac.get('accepted_answers')
        if not isinstance(vals,list) or not vals or any(not isinstance(x,str) or not x.strip() for x in vals):
            raise QuestionContractError('ACCEPTED_ANSWERS_REQUIRED')
    elif qt=='matching':
        parse_matching_contract(statements=ac.get('left_items'),options=ac.get('right_options'),key=mc.get('correct_mapping'),allow_duplicate_targets=bool(mc.get('allow_duplicate_targets')))
    elif qt=='ordering':
        parse_ordering_contract(statements=ac.get('ordering_items'),key=mc.get('correct_order'))
    else:
        raise QuestionContractError('UNSUPPORTED_ASSESSMENT_CONTRACT')
    return {'qtype':qt,'maximum_marks':maximum}


def response_was_present(qtype,form):
    # Unticked checkbox/radio groups have no browser field; the shared surface supplies
    # the sentinel. An omitted response on a non-answer navigation request stays unchanged.
    if form.get('response_present')=='1' or 'answer' in form:
        return True
    prefix={'matching':'match::','ordering':'order::'}.get(qtype)
    return bool(prefix and any(str(k).startswith(prefix) for k in form))


def canonical_submission(qtype,form):
    if qtype not in SUPPORTED_RUNTIME:
        raise QuestionContractError('UNSUPPORTED_SUBMISSION_TYPE')
    if qtype=='matching':
        mapping={str(k)[7:]:str(form.get(k) or '').strip() for k in form if str(k).startswith('match::') and str(form.get(k) or '').strip()}
        return json.dumps(mapping,sort_keys=True,separators=(',',':')) if mapping else ''
    if qtype=='ordering':
        raw=form.get('answer')
        if raw:
            try:
                values=json.loads(raw)
                if not isinstance(values,list) or len(values)!=len(set(values)) or any(not isinstance(x,str) or not x for x in values):raise ValueError()
                return json.dumps(values,separators=(',',':'))
            except (ValueError,TypeError):
                raise QuestionContractError('INVALID_ORDER_SUBMISSION')
        entries=[]
        for k in form:
            if not str(k).startswith('order::'):continue
            value=str(form.get(k) or '').strip()
            if not value:continue
            try: pos=int(value)
            except (ValueError,TypeError): raise QuestionContractError('INVALID_ORDER_POSITION')
            if pos<1:raise QuestionContractError('INVALID_ORDER_POSITION')
            entries.append((pos,str(k)[7:]))
        if not entries:return ''
        if sorted(x[0] for x in entries)!=list(range(1,len(entries)+1)):
            raise QuestionContractError('DUPLICATE_OR_MISSING_ORDER_POSITION')
        return json.dumps([x[1] for x in sorted(entries)],separators=(',',':'))
    values=form.getlist('answer') if hasattr(form,'getlist') else form.get('answer',[])
    if qtype=='multiple_select':
        values=values if isinstance(values,list) else [values]
        return ','.join(sorted(set(str(x).strip() for x in values if str(x).strip())))
    if isinstance(values,list) and len(values)>1:
        raise QuestionContractError('MULTIPLE_VALUES_FOR_SINGLE_RESPONSE')
    return str(form.get('answer') or '').strip()
