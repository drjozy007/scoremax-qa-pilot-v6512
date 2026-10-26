"""Build-time strict-contract additions to the existing written_response_engine."""


def persist_written_marking_result(c, result, *, attempt_id=None, answer_version_id=None,
                                  native_attempt_id=None, native_question_id=None,
                                  processing_job_id=None):
    """One evidence writer for legacy written marks and native provisional feedback.

    The caller owns the transaction. This function never updates assessment scores,
    mastery, recovery tasks or answer versions. Native and written identities cannot
    alias one another; no synthetic written attempt is created for native feedback.
    """
    import json
    native = native_attempt_id is not None
    if native:
        if (attempt_id is not None or answer_version_id is not None
                or not isinstance(native_attempt_id,int) or native_attempt_id<=0
                or not isinstance(native_question_id,int) or native_question_id<=0
                or not isinstance(processing_job_id,int) or processing_job_id<=0
                or result.get('status')!='PROVISIONAL_PRACTICE_FEEDBACK'
                or result.get('evidence_eligible') is not False
                or result.get('official_score_or_mastery_changed') is not False):
            raise ValueError('INVALID_NATIVE_PROVISIONAL_EVIDENCE_IDENTITY')
    elif (attempt_id is None or answer_version_id is None
          or native_question_id is not None or processing_job_id is not None):
        raise ValueError('INVALID_WRITTEN_EVIDENCE_IDENTITY')
    columns = ('attempt_id,answer_version_id,proposed_mark,maximum_mark,percentage,'
               'confidence,result_state,command_verb_met,grader_a_json,grader_b_json,'
               'reconciliation_json,feedback_json,contradictions_json,misconceptions_json,validation_boundary')
    values = [attempt_id,answer_version_id,result['proposed_mark'],result['maximum_mark'],
              result['percentage'],result['confidence'],result['status'],
              1 if result['command_verb_met'] else 0,json.dumps(result['grader_a']),
              json.dumps(result['grader_b']),json.dumps({'policy_version':result['reconciliation_policy_version']}),
              json.dumps(result['feedback']),json.dumps(result.get('contradictions',[])),
              json.dumps(result.get('misconceptions',[])),result['validation_boundary']]
    if native:
        columns += ',source_kind,native_attempt_id,native_question_id,processing_job_id'
        values += ['NATIVE_PROVISIONAL',native_attempt_id,native_question_id,processing_job_id]
    run_id=c.execute('INSERT INTO written_marking_runs ('+columns+') VALUES ('+
                     ','.join('?' for _ in values)+')',values).lastrowid
    for pt in result['mark_points']:
        c.execute("""INSERT INTO written_mark_point_results
          (marking_run_id,point_id,description,available_marks,awarded_marks,status,
           evidence_json,improvement_instruction,grader_a_status,grader_b_status)
          VALUES(?,?,?,?,?,?,?,?,?,?)""",
          (run_id,pt['point_id'],pt['description'],pt['available_marks'],pt['awarded_marks'],
           pt['status'],json.dumps(pt['evidence']),pt['improvement_instruction'],
           pt['grader_a_status'],pt['grader_b_status']))
    return run_id

def _clause_normalise(text, case_sensitive=True):
    # Preserve variable/chemical-symbol case by default. A PH rubric can explicitly
    # permit case-insensitive prose. Question marks are not assertion punctuation.
    value=' '.join(str(text).strip().rstrip('.;').split())
    return value if case_sensitive else value.casefold()


def validate_automatic_rubric(rubric, maximum):
    """Bounded grammar, not a general semantic grader or word-overlap score."""
    import math
    errors=[]
    try:
        value=float(maximum)
        if isinstance(maximum,bool) or not math.isfinite(value) or value<=0: raise ValueError()
    except (TypeError,ValueError,OverflowError):
        return {'valid':False,'errors':['INVALID_MAXIMUM_MARKS']}
    if isinstance(rubric,dict) and rubric.get('version') == 'SM-RUBRIC-NATIVE-1':
        from native_scoring_operations_v1 import validate_native_rubric
        return validate_native_rubric(rubric,maximum)
    if not isinstance(rubric,dict) or rubric.get('version') != 'SM-RUBRIC-CLAUSES-1':
        return {'valid':False,'errors':['EXPLICIT_RUBRIC_VERSION_REQUIRED']}
    if not isinstance(rubric.get('case_sensitive',True),bool): errors.append('RUBRIC_CASE_POLICY_INVALID')
    sensitive=rubric.get('case_sensitive',True)
    points=rubric.get('required_mark_points')
    if not isinstance(points,list) or not 1 <= len(points) <= 50:
        return {'valid':False,'errors':['GOVERNED_MARK_POINTS_REQUIRED']}
    ids=[]; total=0.0; claims={}
    for pt in points:
        if not isinstance(pt,dict): errors.append('INVALID_MARK_POINT'); continue
        pid=pt.get('id')
        if not isinstance(pid,str) or not pid.strip() or not isinstance(pt.get('description'),str):
            errors.append('MARK_POINT_ID_AND_DESCRIPTION_REQUIRED'); continue
        ids.append(pid)
        try:
            weight=float(pt.get('marks'))
            if isinstance(pt.get('marks'),bool) or not math.isfinite(weight) or weight <= 0: raise ValueError()
            total+=weight
        except (TypeError,ValueError,OverflowError): errors.append('MARK_POINT_WEIGHT_INVALID')
        phrases=pt.get('accepted_phrases',[]); alternatives=pt.get('acceptable_paraphrases',[])
        if not isinstance(phrases,list) or not isinstance(alternatives,list) or not phrases+alternatives:
            errors.append('GOVERNED_COMPLETE_CLAUSES_REQUIRED'); continue
        for phrase in phrases+alternatives:
            if not isinstance(phrase,str) or not phrase.strip() or len(phrase)>2000:
                errors.append('CLAUSE_INVALID'); continue
            normal=_clause_normalise(phrase,sensitive)
            # One clause may legitimately demonstrate several rubric points; each
            # point can earn its governed allocation once, never once per repetition.
            claims.setdefault(normal,set()).add(pid)
    if len(ids)!=len(set(ids)): errors.append('DUPLICATE_MARK_POINT_ID')
    if not math.isfinite(total) or abs(total-float(maximum))>1e-8: errors.append('RUBRIC_MARKS_MISMATCH')
    contradictions=rubric.get('contradictions',[])
    if not isinstance(contradictions,list):
        return {'valid':False,'errors':errors+['CONTRADICTION_LIST_REQUIRED']}
    for item in contradictions:
        if not isinstance(item,dict) or not isinstance(item.get('phrase'),str) or not item['phrase'].strip():
            errors.append('CONTRADICTION_INVALID'); continue
        targets=item.get('point_ids')
        if not isinstance(targets,list) or not targets or any(x not in ids for x in targets):
            errors.append('CONTRADICTION_TARGETS_REQUIRED')
        if _clause_normalise(item['phrase'],sensitive) in claims: errors.append('CONTRADICTORY_RUBRIC')
    return {'valid':not errors,'errors':errors}


def _governed_clause_chunks(text, positive, negative, sensitive):
    """Segment only complete authored clauses; punctuation inside them is literal.

    Consume the entire response. Unknown text and ambiguous point attribution stay
    unscored. A decimal point cannot act as a clause separator.
    """
    whole = _clause_normalise(text, sensitive)
    if whole in positive or whole in negative:
        return [whole]
    if not text.strip():
        return []
    text = text if sensitive else text.casefold()
    patterns = [(phrase, re.compile(re.escape(phrase).replace(r'\ ', r'\s+')))
                for phrase in positive.keys() | negative.keys()]
    separator = re.compile(r'[^\S\n]*(?:(?:[;\n]|(?<!\d)\.|\.(?!\d))[^\S\n]*)+')
    states = {0: (frozenset(), frozenset(), None, None)}
    for start in range(len(text)):
        if start not in states:
            continue
        awarded, denied = states[start][:2]
        for phrase, pattern in patterns:
            match = pattern.match(text, start)
            if match is None:
                continue
            end = match.end()
            if text[end:].strip():
                boundary = separator.match(text, end)
                if boundary is None:
                    continue
                end = boundary.end()
            else:
                end = len(text)
            new_awarded = awarded | frozenset(positive.get(phrase, ()))
            new_denied = denied | frozenset(negative.get(phrase, ()))
            prior = states.get(end)
            if prior is not None and prior[:2] != (new_awarded, new_denied):
                return None
            states[end] = (new_awarded, new_denied, start, phrase)
    if len(text) not in states:
        return None
    chunks = []
    end = len(text)
    while end:
        _, _, start, phrase = states[end]
        chunks.append(phrase)
        end = start
    return list(reversed(chunks))


def _mark_governed_clauses(question, answer):
    maximum=float(question.get('maximum_marks') or 0)
    check=validate_automatic_rubric(question,maximum)
    if not check['valid']:
        return {'status':'NO_MARKING_CONTRACT','proposed_mark':None,'maximum_mark':maximum,
                'percentage':None,'confidence':0.0,'mark_points':[],'feedback':[], 'errors':check['errors']}
    points=question['required_mark_points']; text=str(answer or '').strip()
    if question.get('version') == 'SM-RUBRIC-NATIVE-1':
        from native_scoring_operations_v1 import native_observations
        awarded,denied,unknown=native_observations(question,text)
    else:
        positive={}; negative={}
        sensitive=question.get('case_sensitive',True)
        for pt in points:
            for phrase in pt.get('accepted_phrases',[])+pt.get('acceptable_paraphrases',[]):
                positive.setdefault(_clause_normalise(phrase,sensitive),set()).add(pt['id'])
        for item in question.get('contradictions',[]) or []:
            negative.setdefault(_clause_normalise(item['phrase'],sensitive),set()).update(item['point_ids'])
        chunks=_governed_clause_chunks(text,positive,negative,sensitive)
        awarded=set(); denied=set(); unknown=[] if chunks is not None else [text]
        for chunk in chunks or []:
            if chunk in negative: denied.update(negative[chunk])
            elif chunk in positive: awarded.update(positive[chunk])
            else: unknown.append(chunk)
    awarded-=denied
    outputs=[{'point_id':pt['id'],'description':pt['description'],'available_marks':float(pt['marks']),
              'awarded_marks':float(pt['marks']) if pt['id'] in awarded else 0.0,
              'status':'awarded' if pt['id'] in awarded else 'contradicted' if pt['id'] in denied else 'absent'} for pt in points]
    final=not unknown
    mark=sum(p['awarded_marks'] for p in outputs) if final else None
    return {'status':'MARK_CONFIRMED' if final else 'MORE_EVIDENCE_REQUIRED',
            'proposed_mark':mark,'maximum_mark':maximum,'percentage':round(mark/maximum*100,4) if final and maximum else None,
            'confidence':1.0 if final else 0.0,'mark_points':outputs,
            'feedback':([] if final else ['This response could not be marked reliably. It has not changed your mastery.']),
            'contradictions':[p for p in outputs if p['status']=='contradicted'],
            'marker_version':'native-operations-1' if question.get('version')=='SM-RUBRIC-NATIVE-1' else 'governed-clause-1',
            'validation_boundary':'Source-bound native operations; unknown responses are unscored.' if question.get('version')=='SM-RUBRIC-NATIVE-1' else 'Governed complete-clause matching only; unknown paraphrases are not graded.'}



def mark_written_response(question, answer, policy=None):
    """The existing public marker has no opt-out into the legacy word-overlap path.

    This is bounded approved-clause marking, NOT general semantic understanding.
    Unsupported answers/contracts produce no score and no invented confidence.
    """
    import math
    maximum=0.0
    try:
        raw=question.get('maximum_marks') if isinstance(question,dict) else None
        if isinstance(raw,bool) or not math.isfinite(float(raw)) or float(raw)<=0: raise ValueError()
        maximum=float(raw)
    except (TypeError,ValueError,OverflowError): pass
    base={'proposed_mark':None,'maximum_mark':maximum,'percentage':None,'confidence':0.0,
          'status':'NO_MARKING_CONTRACT','evidence_eligible':False,'mark_points':[],
          'feedback':['This response could not be marked reliably. It has not changed your mastery.'],
          'contradictions':[],'misconceptions':[],
          'command_verb':question.get('command_verb','') if isinstance(question,dict) else '',
          'command_verb_met':False,'grader_a':{'score':None,'version':'governed-clause-1'},
          'grader_b':{'score':None,'version':'NOT_USED'},
          'reconciliation_policy_version':'single-governed-marker-1',
          'validation_boundary':'Governed complete-clause matching only; not general semantic grading.',
          'confidence_basis':'EXACT_CONTRACT_MATCH_COMPLETENESS_NOT_CALIBRATED_PROBABILITY'}
    if maximum<=0 or not isinstance(question,dict):return {**base,'errors':['INVALID_WRITTEN_QUESTION']}
    if policy is not None and not isinstance(policy,dict):return {**base,'errors':['INVALID_MARKING_POLICY']}
    if (policy or {}).get('scoring_contract') not in (None,'','governed_clause_rubric_v1'):
        return {**base,'errors':['UNSUPPORTED_SCORING_CONTRACT']}
    if not isinstance(answer,str):return {**base,'status':'MORE_EVIDENCE_REQUIRED'}
    if len(answer)>10000:return {**base,'status':'RESPONSE_LIMIT_EXCEEDED'}
    try:
        check=validate_automatic_rubric(question,maximum)
        if not check['valid']:return {**base,'errors':check['errors']}
        result=_mark_governed_clauses(question,answer)
    except (TypeError,ValueError,OverflowError,KeyError):return {**base,'errors':['INVALID_WRITTEN_RUBRIC']}
    if result.get('status')!='MARK_CONFIRMED':return {**base,'status':result.get('status','MORE_EVIDENCE_REQUIRED')}
    awarded=result.get('proposed_mark')
    if isinstance(awarded,bool) or not isinstance(awarded,(int,float)) or not math.isfinite(awarded) or not 0<=awarded<=maximum:
        return {**base,'errors':['INVALID_MARKER_RESULT']}
    points=[{**pt,'evidence':[answer] if pt['status'] in {'awarded','contradicted'} else [],
             'improvement_instruction':'Point demonstrated.' if pt['status']=='awarded' else 'Review this approved mark point.',
             'grader_a_status':pt['status'],'grader_b_status':'NOT_USED'} for pt in result['mark_points']]
    from native_structured_practice import practice_contract
    practice=practice_contract(question)
    return {**base,**result,'mark_points':points,'evidence_eligible':not practice,'practice_score_confirmed':practice,'assessment_purpose':'STRUCTURED_PRACTICE' if practice else 'ORIGINAL','command_verb_met':True,
            'grader_a':{'score':awarded,'version':result.get('marker_version','governed-clause-1')},'grader_b':{'score':None,'version':'NOT_USED'},
            'validation_boundary':result.get('validation_boundary',base['validation_boundary'])}

