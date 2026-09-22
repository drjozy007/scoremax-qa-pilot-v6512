"""Build-time strict-contract additions to the existing written_response_engine."""

def _clause_normalise(text, case_sensitive=True):
    # Preserve variable/chemical-symbol case by default. A PH rubric can explicitly
    # permit case-insensitive prose. Question marks are not assertion punctuation.
    value=' '.join(str(text).strip().rstrip('.;').split())
    return value if case_sensitive else value.casefold()


def validate_automatic_rubric(rubric, maximum):
    """Bounded grammar, not a general semantic grader or word-overlap score."""
    import math
    errors=[]
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


def _mark_governed_clauses(question, answer):
    maximum=float(question.get('maximum_marks') or 0)
    check=validate_automatic_rubric(question,maximum)
    if not check['valid']:
        return {'status':'NO_MARKING_CONTRACT','proposed_mark':None,'maximum_mark':maximum,
                'percentage':None,'confidence':0.0,'mark_points':[],'feedback':[], 'errors':check['errors']}
    points=question['required_mark_points']; text=str(answer or '').strip()
    positive={}; negative={}
    sensitive=question.get('case_sensitive',True)
    for pt in points:
        for phrase in pt.get('accepted_phrases',[])+pt.get('acceptable_paraphrases',[]):
            positive.setdefault(_clause_normalise(phrase,sensitive),set()).add(pt['id'])
    for item in question.get('contradictions',[]) or []:
        negative.setdefault(_clause_normalise(item['phrase'],sensitive),set()).update(item['point_ids'])
    # First try the whole approved clause (including any internal punctuation).
    whole=_clause_normalise(text,sensitive)
    chunks=[whole] if whole in positive or whole in negative else [_clause_normalise(x,sensitive) for x in re.split(r'[.;\n]+',text) if x.strip()]
    awarded=set(); denied=set(); unknown=[]
    for chunk in chunks:
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
            'marker_version':'governed-clause-1', 'validation_boundary':'Governed complete-clause matching only; unknown paraphrases are not graded.'}
