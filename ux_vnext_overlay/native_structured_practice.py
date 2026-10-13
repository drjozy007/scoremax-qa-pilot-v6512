"""Bounded response operations used by the existing native SAQ marker.

This is a source compiler and evidence observer, not a grading entry point.
It never supplies academic synonyms, scores, mastery evidence or network calls.
Unrecognised source grammar and unrecognised learner claims fail closed.
"""
import copy
import json
import re

VERSION = 'PH-NATIVE-OPERATIONS-3-PRACTICE'
RESPONSE_VERSION = 'PH-STRUCTURED-PRACTICE-1'
AUTHORITY = {
    'policy': 'CHEMISTRY-STRUCTURED-PRACTICE-OWNER-20261012',
    'purpose': 'STRUCTURED_PRACTICE',
    'original_exam_equivalent': False,
    'exam_readiness_evidence': False,
    'learner_activation_authorised': False,
    'ai_marking': False,
    'ai_fallback': False,
}

# Grammatical inflections only. These are not scientific equivalence rules.
VERBS = {'is':'be', 'are':'be', 'has':'have', 'have':'have',
         'increases':'increase', 'increase':'increase',
         'decreases':'decrease', 'decrease':'decrease',
         'raises':'raise', 'raise':'raise', 'lowers':'lower', 'lower':'lower',
         'contains':'contain', 'contain':'contain', 'occupies':'occupy', 'occupy':'occupy',
         'takes':'take', 'take':'take', 'requires':'require', 'require':'require',
         'means':'mean', 'mean':'mean', 'depends on':'depend on',
         'results from':'result from', 'results in':'result in',
         'causes':'cause', 'cause':'cause', 'resists':'resist', 'resist':'resist',
         'becomes':'become', 'become':'become', 'remains':'remain', 'remain':'remain'}
VERBS.update({'represents':'represent','represent':'represent','uses':'use','use':'use',
              'forms':'form','form':'form','produces':'produce','produce':'produce'})
PREDICATES = set(VERBS.values())


def text(value):
    if not isinstance(value, str) or not value.strip() or len(value)>1000:
        raise ValueError('BOUNDED_TEXT_REQUIRED')
    return ' '.join(value.strip().rstrip('.').split())


def entity(value):
    value=text(value)
    # Sentence-initial case is not a chemical-identity transformation.
    for article in ('A ', 'An ', 'The '):
        if value.startswith(article):value=article.lower()+value[len(article):]
    for article in ('a ', 'an ', 'the '):
        if value.startswith(article):value=value[len(article):]
    return value


def affine_quantity(source):
    """An explicit source-authored conversion policy, not a unit-conversion table."""
    from native_scoring_operations_v1 import _fraction
    policy=source.get('Numerical_Tolerance_Rule','')
    m=re.fullmatch(r'Accept ([0-9.]+) K using \+([0-9.]+); ([0-9.]+) K also acceptable if \+([0-9.]+) is explicitly used\.',policy)
    inputs=re.findall(r'(-?\d+(?:\.\d+)?) degrees C',source.get('Learner_Question',''))
    if not m or len(inputs)!=1 or source.get('Mark_Point_Count')!=1:return None
    if source.get('Significant_Figures_Rule')!='Whole-kelvin answer sufficient.':return None
    standard,offset,alternative,alt_offset=m.groups();original=inputs[0]
    if _fraction(original)+_fraction(offset)!=_fraction(standard):return None
    if _fraction(original)+_fraction(alt_offset)!=_fraction(alternative):return None
    return [{'point_id':'p1','kind':'SOURCE_AFFINE_QUANTITY',
             'canonical':source['Canonical_Accepted_Evidence'],'input':original,
             'standard':standard,'offset':offset,'alternative':alternative,'alternate_offset':alt_offset,'unit':'K',
             'named_unit':'kelvin' if 'kelvin' in source['Learner_Question'].lower() else None}]


def affine_working(expression,original,offset):
    """Execute learner-generated addition without eval or a model call."""
    import ast
    from native_scoring_operations_v1 import _fraction
    if not isinstance(expression,str) or len(expression)>100:return False
    try:
        tree=ast.parse(expression,mode='eval').body
        def literal(n):
            if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
                return (-1 if isinstance(n.op,ast.USub) else 1)*literal(n.operand)
            if isinstance(n,ast.Constant) and type(n.value) in (int,float):return _fraction(n.value)
            raise ValueError('LITERAL_REQUIRED')
        if not isinstance(tree,ast.BinOp) or not isinstance(tree.op,ast.Add):return False
        return sorted((literal(tree.left),literal(tree.right)))==sorted((_fraction(original),_fraction(offset)))
    except (ValueError,SyntaxError,OverflowError,RecursionError):return False


def relation(value):
    value=text(value).lower()
    neg=False
    if value.startswith('does not '):value=value[9:];neg=True
    elif value.startswith('do not '):value=value[7:];neg=True
    elif value.endswith(' not'):value=value[:-4];neg=True
    value=VERBS.get(value,value)
    if value not in PREDICATES:raise ValueError('UNSUPPORTED_RELATION')
    return value,neg


def atom(subject, predicate, object_):
    predicate,neg=relation(predicate)
    subject=entity(subject);object_=entity(object_)
    # Explicit negation can occur in the complement as well as the predicate.
    if object_.startswith('no '):
        if neg:raise ValueError('DOUBLE_NEGATION')
        neg=True;object_=object_[3:]
    return {'subject':subject,'relation':predicate,'object':object_,'negative':neg}


def parse_proposition(clause):
    """Lossless bounded sentence grammar. Never infer missing subjects/causes.

    Only a single unambiguous subject-predicate boundary is executable. Nested
    clauses, coordination and anaphora need an authored structured projection.
    Keeping an entire explanation in an opaque 'object' is prohibited.
    """
    clause=text(clause)
    if re.search(r'[,;:|=∝]|\b(and|or|because|therefore|whereas|although|unless|which|that|when|if|so|as|before|after|while)\b',clause,re.I):
        return None
    if re.match(r'(?i)(it|its|their|this|these|they|there|such|each|both|consequently|at|for|with|without|during)\b',clause):return None
    terms=sorted(VERBS,key=len,reverse=True)
    pattern=r'\b(?:(?:does|do) not )?('+'|'.join(re.escape(v) for v in terms)+r')(?: not)?\b'
    matches=list(re.finditer(pattern,clause))
    if len(matches)!=1:return None
    m=matches[0];subject=clause[:m.start()].strip();obj=clause[m.end():].strip()
    if not subject or not obj or re.search(r'\b(not|no|does|do)\b',subject):return None
    try:return atom(subject,m.group(),obj)
    except ValueError:return None


def parse_bundle(clause):
    direct=parse_proposition(clause)
    if direct:return [direct]
    # Source-explicit conjunctions remain one marking point. Only grammatical
    # shared-subject ellipsis is expanded; anaphora and causal inference are not.
    chunks=re.split(r'\s+and\s+|(?<!\d)\.\s+',text(clause))
    if len(chunks)<2 or len(chunks)>6:return None
    result=[];subject=None
    for chunk in chunks:
        parsed=parse_proposition(chunk)
        starts_verb=any(chunk.startswith(v+' ') for v in VERBS) or chunk.startswith(('does not ','do not '))
        if parsed is None and subject and starts_verb:
            parsed=parse_proposition(subject+' '+chunk)
        if parsed is None:return None
        subject=parsed['subject'];result.append(parsed)
    if len({json.dumps(x,sort_keys=True) for x in result})!=len(result):return None
    return result


def equation_operation(clause,source):
    from native_scoring_operations_v1 import _polynomial_equation
    if source.get('Equation_Equivalence_Rule')!='Algebraically equivalent rearrangements are accepted when they preserve the same relationship.':return None
    s=text(clause)
    prefixes=('The correct ideal-gas equation is ','The ideal-gas equation is ',
              'The ideal gas equation is ','Use ','Rearranging gives ','Rearrangement gives ')
    isolate=s.startswith(('Rearranging gives ','Rearrangement gives '))
    for prefix in prefixes:
        if s.startswith(prefix):s=s[len(prefix):];break
    if not re.fullmatch(r'[A-Za-z0-9 ()*/+=.\-]+',s) or s.count('=')!=1:return None
    symbols=sorted(set(re.findall('[A-Za-z]',s)))
    if not symbols:return None
    try:
        # Only the explicit source expression establishes denominator domains.
        signature,denoms=_polynomial_equation(s,symbols,symbols)
    except (ValueError,SyntaxError,OverflowError):return None
    target=s.split('=')[0].strip() if isolate else None
    if target and target not in symbols:return None
    return {'kind':'SOURCE_EQUATION','equation':s,'symbols':symbols,
            'allowed_denominators':sorted(denoms),'isolated_target':target}


def substitution_operation(clause,source):
    """Source-explicit substitution working, with original premises retained."""
    s=text(clause)
    patterns=[r'(?:Substitute|Use) (.+?) (?:into|in) (.+?) to (?:obtain|give) (.+)',
              r'Substituting (.+?) gives (.+)',
              r'Substitute (.+?) to (?:obtain|give) (.+)']
    for pattern in patterns:
        m=re.fullmatch(pattern,s)
        if not m:continue
        forms=[]
        for expression in m.groups():
            operation=equation_operation(expression,source)
            if operation is None:return None
            forms.append(operation)
        # A substitution cannot be inferred from the final formula alone.
        return {'kind':'SOURCE_SUBSTITUTION','required_steps':forms}
    return None


def derive(source):
    """Each operation retains exactly one original point, allocation and evidence."""
    from native_scoring_operations_v1 import _fraction
    if source.get('Required_Produced_Representation')!='NONE':return None
    if source.get('Numerical_Tolerance_Rule')!='NOT_APPLICABLE':return affine_quantity(source)
    if source.get('Significant_Figures_Rule')!='NOT_APPLICABLE':return None
    if source.get('Partial_Credit_Rule')!='Award 1 mark for each independently satisfied mark point.':return None
    if not source.get('Contradiction_Rule','').startswith('A direct contradiction of a credited proposition removes credit for that proposition;'):return None
    evidence=source.get('Canonical_Accepted_Evidence','').split(' | ')
    values=source.get('Mark_Point_Values','').split(';')
    if not len(evidence)==len(values)==source.get('Mark_Point_Count'):return None
    if sum(_fraction(v) for v in values)!=_fraction(source['Marks']):return None
    operations=[]
    for i,clause in enumerate(evidence,1):
        parsed=parse_bundle(clause)
        if parsed:
            operation={'kind':'TYPED_PROPOSITION','assertions':parsed}
        else:
            operation=equation_operation(clause,source) or substitution_operation(clause,source)
            if not operation:return None
        operations.append({'point_id':f'p{i}','canonical':clause,**operation})
    # Identical claims cannot be separate credit opportunities.
    signatures=[json.dumps({k:v for k,v in op.items() if k not in ('point_id','canonical')},sort_keys=True) for op in operations]
    if len(signatures)!=len(set(signatures)):return None
    return operations


def attach(rubric,source):
    from native_scoring_operations_v1 import stable_hash, _original_points_match
    operations=derive(source)
    if not operations or 'native_scoring' in rubric:return None
    if not _original_points_match(rubric,source,operations):return None
    body=copy.deepcopy(rubric);original=body.pop('contract_sha256',None)
    if original!=stable_hash(body):return None
    body['native_scoring']={'version':VERSION,'original_contract_sha256':original,
        'source_row_sha256':stable_hash(source),'source_row':copy.deepcopy(source),
        'operations':operations,'response_contract':RESPONSE_VERSION,
        'practice_authority':copy.deepcopy(AUTHORITY)}
    body['contract_sha256']=stable_hash(body)
    return body


def observations(binding,answer):
    """Return evidence only; the existing engine allocates original point marks."""
    awarded=set();denied=set();unknown=[]
    try:
        def unique(pairs):
            result={}
            for k,v in pairs:
                if k in result:raise ValueError('DUPLICATE_JSON_KEY')
                result[k]=v
            return result
        data=json.loads(answer,object_pairs_hook=unique)
        if set(data)!={'version','assertions','equations','values'} or data['version']!=RESPONSE_VERSION:
            raise ValueError('RESPONSE_CONTRACT_INVALID')
        assertions=data['assertions']
        if not isinstance(assertions,list) or len(assertions)>50:raise ValueError('RESPONSE_LIMIT')
        observed=[]
        for claim in assertions:
            if not isinstance(claim,dict) or set(claim)!={'subject','relation','object'}:
                raise ValueError('ASSERTION_FIELDS_INVALID')
            actual=atom(claim['subject'],claim['relation'],claim['object'])
            matched=False
            for op in binding['operations']:
                for expected in op.get('assertions',[]):
                    if all(actual[k]==expected[k] for k in ('subject','relation','object')):
                        if actual['negative']!=expected['negative']:denied.add(op['point_id'])
                        matched=True
            observed.append(actual)
            if not matched:unknown.append('UNSUPPORTED_ASSERTION')
        for op in binding['operations']:
            if op['kind']=='TYPED_PROPOSITION' and all(a in observed for a in op['assertions']):
                awarded.add(op['point_id'])
        equations=data['equations']
        if not isinstance(equations,list) or len(equations)>50:raise ValueError('EQUATION_LIMIT')
        from native_scoring_operations_v1 import _polynomial_equation
        # Duplicate algebraically equivalent evidence cannot earn two steps.
        candidates={};seen=set()
        for value in equations:
            value=text(value);matched=[];recognised=False
            equation_ops=[]
            for parent in binding['operations']:
                if parent['kind']=='SOURCE_EQUATION':equation_ops.append(parent)
                elif parent['kind']=='SOURCE_SUBSTITUTION':equation_ops.extend(parent['required_steps'])
            for op in equation_ops:
                try:
                    sig,_=_polynomial_equation(value,op['symbols'],op['allowed_denominators'])
                    expected,_=_polynomial_equation(op['equation'],op['symbols'],op['allowed_denominators'])
                    isolated=op['isolated_target']
                    if sig==expected and (not isolated or isolated in [side.strip() for side in value.split('=')]):
                        recognised=True
                        if 'point_id' in op:matched.append(op['point_id'])
                except (ValueError,SyntaxError,OverflowError):pass
            if not recognised:unknown.append('UNSUPPORTED_EQUATION')
            normal=''.join(value.split())
            if normal not in seen:
                candidates[normal]=matched;seen.add(normal)
        # Maximum one original point per submitted equation, including when the
        # source has a separate equation and rearrangement point.
        assigned={}
        def allocate(line,visited):
            for pid in candidates[line]:
                if pid in visited:continue
                visited.add(pid)
                if pid not in assigned or allocate(assigned[pid],visited):
                    assigned[pid]=line;return True
            return False
        for line in candidates:allocate(line,set())
        awarded.update(assigned)
        for op in binding['operations']:
            if op['kind']!='SOURCE_SUBSTITUTION':continue
            complete=True
            for step in op['required_steps']:
                found=False
                for line in equations:
                    try:
                        sig,_=_polynomial_equation(line,step['symbols'],step['allowed_denominators'])
                        expected,_=_polynomial_equation(step['equation'],step['symbols'],step['allowed_denominators'])
                        if sig==expected:found=True
                    except (ValueError,SyntaxError,OverflowError):pass
                if not found:complete=False
            if complete:awarded.add(op['point_id'])
        values=data['values']
        if not isinstance(values,list) or len(values)>50:raise ValueError('VALUE_LIMIT')
        from native_scoring_operations_v1 import _fraction
        for value in values:
            if not isinstance(value,dict) or set(value)!={'value','unit','working'}:raise ValueError('VALUE_FIELDS')
            number=_fraction(value['value']);matched=False
            for op in binding['operations']:
                if op['kind']!='SOURCE_AFFINE_QUANTITY':continue
                unit=value['unit']
                if not isinstance(unit,str):raise ValueError('UNIT_TYPE')
                if unit!=op['unit'] and (not op.get('named_unit') or unit.casefold()!=op['named_unit']):continue
                matched=True;pid=op['point_id']
                working=value['working']
                if not isinstance(working,str):raise ValueError('WORKING_TYPE')
                if number==_fraction(op['standard']) and (not working.strip() or affine_working(working,op['input'],op['offset'])):
                    awarded.add(pid)
                elif number==_fraction(op['alternative']) and affine_working(working,op['input'],op['alternate_offset']):
                    awarded.add(pid)
                elif number not in (_fraction(op['standard']),_fraction(op['alternative'])):
                    denied.add(pid)
                else:unknown.append('UNVERIFIED_WORKING')
            if not matched:unknown.append('UNSUPPORTED_VALUE_OR_UNIT')
    except (ValueError,TypeError,KeyError,RecursionError):
        return set(),set(),['MALFORMED_OR_UNSUPPORTED_RESPONSE']
    return awarded,denied,unknown


def practice_contract(runtime_rubric):
    return runtime_rubric.get('native_contract',{}).get('native_scoring',{}).get('version')==VERSION


def response_descriptor(runtime_rubric):
    """Learner-safe descriptor: never contains answer evidence or expected terms."""
    if not practice_contract(runtime_rubric):return None
    return {'version':RESPONSE_VERSION,'purpose':'STRUCTURED_PRACTICE',
            'fields':['subject','relation','object'],'original_exam_equivalent':False,
            'exam_readiness_evidence':False}
