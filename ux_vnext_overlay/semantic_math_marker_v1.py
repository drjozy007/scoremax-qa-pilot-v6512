"""Candidate semantic Mathematics scorer for the existing constructed marker.

The receiver owns qualification. A source rubric alone never enables this mode.
The frozen source supplies the allocation and descriptions; the evaluator only
decides whether a learner's response demonstrates each supplied criterion.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

VERSION = 'SM-MATH-SEMANTIC-1'
REGISTRY = Path(__file__).with_name('semantic_math_qualification_v1.json')
_SHA = re.compile(r'[0-9a-f]{64}\Z')


def implementation_sha256():
    """Bind receiver qualification to the exact local marking implementation."""
    import sympy
    digest = hashlib.sha256()
    digest.update(('sympy='+sympy.__version__+'\0').encode())
    for name in ('local_math_equivalence_v1.py', 'semantic_math_marker_v1.py'):
        data = Path(__file__).with_name(name).read_bytes()
        digest.update(name.encode('utf-8') + b'\0' + str(len(data)).encode() + b'\0' + data)
    return digest.hexdigest()


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _number(value):
    if isinstance(value, bool):
        raise ValueError('BOOLEAN_MARKS')
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0 or number > 1000:
        raise ValueError('INVALID_MARKS')
    return number


def prepare_candidate(rubric, maximum, stem, model_answer):
    """Validate source allocation without asserting semantic scoring quality."""
    if not isinstance(rubric, dict) or rubric.get('version') != 'PH-SAQ-SCORING-CONTRACT-1':
        return None
    if rubric.get('auto_marking_eligibility') != 'RUBRIC_SEMANTICALLY_SCORABLE' or rubric.get('scoring_type') != 'SEMANTIC_MARK_POINT':
        return None
    source_hash = rubric.get('source_marking_evidence_sha256')
    supplied_hash = rubric.get('contract_sha256')
    if not all(isinstance(x, str) and _SHA.fullmatch(x) for x in (source_hash, supplied_hash)):
        return None
    unsigned = dict(rubric); unsigned.pop('contract_sha256', None)
    if _hash(unsigned) != supplied_hash:
        return None
    try:
        guidance=rubric.get('source_marking_guidance')
        context=[]
        if guidance is not None:
            if not isinstance(guidance,dict):return None
            evidence=dict(guidance);evidence_hash=evidence.pop('evidence_sha256',None)
            if evidence_hash!=source_hash or _hash(evidence)!=source_hash:return None
            if evidence.get('version')!='PH-SOURCE-MARKING-GUIDANCE-1':return None
            context=evidence.get('literal_sources',[])
            if not isinstance(context,list) or len(context)>100:return None
            for item in context:
                if not isinstance(item,dict) or not isinstance(item.get('field'),str):return None
                if not isinstance(item.get('value'),(str,int,float)):return None
                if isinstance(item['value'],str) and len(item['value'])>30000:return None
        total = _number(maximum)
        if total != _number(rubric['maximum_marks']):
            return None
        points = rubric['required_mark_points']
        if not isinstance(points, list) or not points or len(points) > 30:
            return None
        out = []; seen = set(); allocated = Decimal(0)
        for point in points:
            if not isinstance(point, dict):
                return None
            pid = point.get('id'); description = point.get('description')
            if not isinstance(pid, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', pid) or pid in seen:
                return None
            if not isinstance(description, str) or not description.strip() or len(description) > 5000:
                return None
            marks = _number(point.get('marks')); allocated += marks; seen.add(pid)
            # Only source-allocated repeated groups can receive increments.
            unit = point.get('source_per_item_marks')
            if unit is not None:
                unit = _number(unit)
                if marks / unit != int(marks / unit):
                    return None
            out.append({'id':pid, 'description':description, 'marks':str(marks),
                        'unit':str(unit or marks)})
        if allocated != total:
            return None
        if guidance is not None:
            reference_points=guidance.get('required_mark_points')
            if not isinstance(reference_points,list) or len(reference_points)!=len(out) or _number(guidance.get('maximum_marks'))!=total:
                return None
            for point,reference in zip(out,reference_points):
                if not isinstance(reference,dict) or point['id']!=reference.get('id') or point['description']!=str(reference.get('description','')).strip() or Decimal(point['marks'])!=_number(reference.get('marks')):
                    return None
        if not isinstance(stem, str) or not stem.strip() or len(stem) > 10000:
            return None
        if not isinstance(model_answer, str) or not model_answer.strip() or len(model_answer) > 10000:
            return None
        body = {'version':VERSION, 'source_contract_sha256':supplied_hash,
                'source_marking_evidence_sha256':source_hash, 'maximum_marks':str(total),
                'question':stem, 'model_answer':model_answer, 'points':out,
                'source_context':context}
        body['candidate_sha256'] = _hash(body)
        return body
    except (KeyError, TypeError, ValueError, InvalidOperation, OverflowError):
        return None


def qualified(candidate, registry_path=REGISTRY):
    """Only a receiver-owned exact question/model/rubric pin can enable marking."""
    try:
        if not valid_candidate_pin(candidate):
            return False
        document = json.loads(Path(registry_path).read_text(encoding='utf-8'))
        if document.get('version') != 'SM-MATH-QUALIFICATION-1':
            return False
        entry = document['entries'].get(candidate['candidate_sha256'])
        return (isinstance(entry, dict) and entry.get('status') == 'QUALIFIED' and
                entry.get('source_contract_sha256') == candidate['source_contract_sha256'] and
                entry.get('source_marking_evidence_sha256') == candidate['source_marking_evidence_sha256'] and
                entry.get('evaluator_sha256') == implementation_sha256() and
                isinstance(entry.get('qualification_evidence_sha256'), str) and
                bool(_SHA.fullmatch(entry['qualification_evidence_sha256'])))
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ImportError):
        return False


def valid_candidate_pin(candidate):
    try:
        if not isinstance(candidate, dict) or candidate.get('version') != VERSION:
            return False
        unsigned = dict(candidate); supplied = unsigned.pop('candidate_sha256', None)
        return isinstance(supplied, str) and bool(_SHA.fullmatch(supplied)) and _hash(unsigned) == supplied
    except (TypeError, ValueError, OverflowError):
        return False


def _segments(text):
    """Preserve decimal points and commas within tuples/function arguments."""
    parts=[]; start=0; depth=0
    for i,ch in enumerate(text):
        if ch in '([': depth+=1
        elif ch in ')]': depth-=1
        if depth < 0 or depth > 20:
            raise ValueError('RESPONSE_PARENTHESES')
        if depth == 0 and ch in ',;\n':
            if text[start:i].strip(): parts.append(text[start:i].strip())
            start=i+1
    if depth:
        raise ValueError('RESPONSE_PARENTHESES')
    if text[start:].strip(): parts.append(text[start:].strip())
    return parts


def _eq_parts(text):
    parts=[s.strip() for s in text.split('=')]
    if len(parts)!=2 or not all(parts):
        return None
    return parts


def _point_atom(text):
    """Compile explicit source mathematics, without inferring method awards."""
    from local_math_equivalence_v1 import parse_expression, parsed_expression
    text=text.strip().rstrip('.')
    eq=_eq_parts(text)
    if eq:
        left,right=eq
        lp=parsed_expression(left); rp=parse_expression(right)
        # Equations containing a displayed calculation retain that calculation.
        named=bool(re.fullmatch(r'(?:[a-zA-Z][a-zA-Z0-9_]*|(?:Re|Im|bar|conj|abs)\([a-zA-Z][a-zA-Z0-9_]*\)|\|[a-zA-Z][a-zA-Z0-9_]*\||[a-z](?:[₁₂₃])?\u0304)',left))
        return {'kind':'equation','left':left,'right':right,
                'display_required':not named and not bool(lp.value.free_symbols)}
    val=parse_expression(text)
    if val.free_symbols:
        if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',text):
            raise ValueError('BARE_TARGET_IS_NOT_ANSWER_EVIDENCE')
        # A bare polynomial may be an explicit final factorization criterion,
        # but it must retain the displayed form, not just the same value.
        return {'kind':'form','expected':text}
    return {'kind':'value','expected':text}


def _compile_point(description, candidate):
    from local_math_equivalence_v1 import parse_expression, equivalent, distributed_terms, _normalise
    text=description.strip().rstrip('.')
    displayed_use=text.startswith(('using ','use '))
    if re.fullmatch(r'(?:reducing|reduce) (?:(?:the )?(?:powers|exponents|exponent)|\d+)(?: modulo [34])?',text):
        question=re.sub(r'([⁰¹²³⁴⁵⁶⁷⁸⁹]+)',lambda m:'^'+m[1].translate(str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹','0123456789')),candidate['question'])
        powers=list(dict.fromkeys(re.findall(r'(omega|ω|i)\s*\^\s*(\d+)',question)))
        if not powers:return None
        return {'kind':'all','children':[{'kind':'reduction','base':base,'exponent':int(power),'modulus':4 if base=='i' else 3} for base,power in powers]}
    if text in {'expansion','correct expansion','correct expansion using i²=−1',
                'distributing the scalar and subtraction'}:
        for step,support in _source_calculations(candidate):
            if (equivalent(step['right'],candidate['model_answer'].strip().rstrip('.')) is True and
                len(distributed_terms(step['left']))>=3):
                return {'kind':'expansion','source':step['left'],'source_support':support}
        question=candidate['question']
        match=re.fullmatch(r'Simplify\s+(.+?)(?:\s+into (?:the form a\+ib|rectangular form)|\s+in (?:the form a\+ib|rectangular form))?\.',question)
        if not match:return None
        expression=match[1]
        if equivalent(expression,candidate['model_answer'].strip().rstrip('.')) is not True:
            return None
        return {'kind':'expansion','source':expression}
    if text in {'conjugate rationalization','rationalization','conjugate division','conjugate multiplication'}:
        for step,support in _source_calculations(candidate):
            if '/' in step['left'] and '*' in _normalise(step['left']):
                if equivalent(step['right'],candidate['model_answer'].strip().rstrip('.')) is True:
                    return {'kind':'form','expected':step['left'],'source_support':support}
        return None
    if text in {'the simplified result','the final result','the result','the final answer','the final value','the final form'}:
        model=candidate['model_answer'].strip().rstrip('.')
        if not parse_expression(model).free_symbols:
            return {'kind':'value','expected':model}
        return None
    # These wrappers describe evidence already printed in the source rubric.
    text=re.sub(r'^(?:for |the value |the final value |the product |the sum |the real component |the imaginary component |obtaining |obtain |using |use |identify |identifying |find one root |one root |root |including |calculating )','',text)
    text=text.replace(' with the real part unchanged','')
    parts=re.split(r'\s+and\s+',text)
    if len(parts)>1:
        children=[_compile_point(x,candidate) for x in parts]
        return {'kind':'all','children':children} if all(children) else None
    for role,pattern in [('real',r'(?:the )?real part (.+)'),
                         ('imaginary_term',r'(?:the )?imaginary term (.+)'),
                         ('imaginary',r'(?:the )?imaginary part (.+)')]:
        match=re.fullmatch(pattern,text)
        if match:
            atom=_point_atom(match[1])
            if atom['kind']!='value':return None
            return {'kind':'component','component':role,'expected':match[1]}
    # Only explicit atomic evidence is compiled here. Descriptors such as
    # "expansion", "each side" and "conclusion" need a verified method rule.
    try:
        atom=_point_atom(text)
        if displayed_use and atom['kind']=='value':
            atom['kind']='form'
        return atom
    except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
        return None


def _source_calculations(candidate):
    """Read verified arithmetic steps from the preserved source explanation.

    Prefix removal applies to trusted reference text only. Learner answers keep
    whole-span parsing, so ignored prose can never hide a contradiction.
    """
    from local_math_equivalence_v1 import equivalent
    steps=[]
    for item in candidate.get('source_context',[]):
        if re.sub(r'[^a-z]','',item['field'].lower())!='explanation' or not isinstance(item['value'],str):
            continue
        for sentence in re.split(r'(?<=[.!])\s+|;|\n',item['value']):
            if ':' in sentence:sentence=sentence.split(':',1)[1].strip()
            for clause in re.split(r',?\s+(?:so|thus|giving)\s+',sentence):
                clause=re.sub(r'^(?:Expand|Expansion gives|First|Then|Hence|Thus|So|Rewrite as)\s*:?\s*','',clause)
                try:
                    atoms=_learner_atoms(clause)
                except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
                    continue
                for atom in atoms:
                    if atom['kind']=='equation' and equivalent(atom['left'],atom['right']) is True:
                        quote=atom['left']
                        start=item['value'].find(quote)
                        if start>=0:
                            steps.append((atom,{'field':item['field'],'origin':item.get('origin'),
                                                'start':start,'end':start+len(quote),'quote':quote}))
    return steps


def local_predicates(candidate):
    from local_math_equivalence_v1 import equivalent, parse_expression
    if not valid_candidate_pin(candidate):
        return None
    out=[]
    for point in candidate['points']:
        try:
            evidence=_compile_point(point['description'],candidate)
        except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
            return None
        if evidence is None:
            return None
        out.append({**point,'evidence':evidence})
    if len(out)==1:
        ev=out[0]['evidence']
        if (ev['kind']=='equation' and ev['display_required'] and
            re.match(r'^(?:Evaluate|Calculate|Simplify)\b',candidate['question']) and
            not re.search(r'\b(?:show|method|using|by)\b',candidate['question'],re.I) and
            equivalent(ev['left'],ev['right']) is True and
            equivalent(ev['right'],candidate['model_answer'].strip().rstrip('.')) is True):
            out[0]['evidence']={'kind':'any','children':[ev,{'kind':'value','expected':ev['right']}]}
    # Preserve distinct method and outcome marks when explicit source forms
    # reduce to the same number (e.g. sqrt(625), followed by 25).
    for point in out:
        ev=point['evidence']
        if ev['kind']=='value':
            if equivalent(ev['expected'],candidate['model_answer'].strip().rstrip('.')) is True:
                ev['final_result']=True
            if (re.search(r'rectangular|form a\+ib',candidate['question']) and
                equivalent(ev['expected'],candidate['model_answer'].strip().rstrip('.')) is True):
                ev['required_form']='rectangular'
            for other in out:
                oe=other['evidence']
                if other is not point and oe['kind']=='value' and ev['expected']!=oe['expected'] and equivalent(ev['expected'],oe['expected']) is True:
                    if re.search(r'sqrt|√|\*\*|\^|[²³]|\(',ev['expected']):
                        ev['kind']='form'
                        ev.pop('final_result',None)
    # Explicit real/imaginary components in a rectangular answer can be
    # interpreted together, with each original component mark kept separate.
    if len(out)==2 and all(p['evidence']['kind']=='value' for p in out):
        try:
            model=parse_expression(candidate['model_answer'].strip().rstrip('.'))
            import sympy as sp
            if not model.free_symbols and model.is_real is False:
                real=sp.re(model);imag=sp.I*sp.im(model)
                a,b=out[0]['evidence'],out[1]['evidence']
                if equivalent(a['expected'],str(real)) is True and equivalent(b['expected'],str(imag)) is True:
                    a.update(kind='component',component='real')
                    b.update(kind='component',component='imaginary_term')
        except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
            pass
    return out


def _learner_atoms(answer):
    from local_math_equivalence_v1 import parse_expression
    atoms=[]
    for segment in _segments(answer):
        segment=segment.strip().rstrip('.')
        segment=re.sub(r'^(?:Let|let|Therefore|therefore|Hence|hence|Thus|thus|Then|then)\s+','',segment)
        for text in re.split(r'\s+and\s+',segment):
            text=text.strip()
            # Names for real/imaginary parts are unambiguous aliases, not
            # keyword evidence: the complete remaining value must parse.
            text=re.sub(r'^real part\s*(?:is|=|:)\s*','Re(z)=',text,flags=re.I)
            text=re.sub(r'^imaginary part\s*(?:is|=|:)\s*','Im(z)=',text,flags=re.I)
            chain=[s.strip() for s in text.split('=')]
            if len(chain)>8 or any(not s for s in chain):
                raise ValueError('EQUATION_CHAIN_LIMIT')
            for expr in chain:
                parse_expression(expr)
            if len(chain)==1:
                atoms.append({'kind':'value','text':text,'value':chain[0]})
            else:
                for left,right in zip(chain,chain[1:]):
                    atoms.append({'kind':'equation','text':text,'left':left,'right':right})
    if not atoms or len(atoms)>60:
        raise ValueError('RESPONSE_LIMIT')
    return atoms


def _match_evidence(predicate,atoms):
    from local_math_equivalence_v1 import equivalent,parse_expression,same_displayed_form
    import sympy as sp
    kind=predicate['kind']
    if kind in {'all','any'}:
        children=[_match_evidence(p,atoms) for p in predicate['children']]
        satisfied=all(p[0] for p in children) if kind=='all' else any(p[0] for p in children)
        return satisfied,set().union(*(p[1] for p in children)),set().union(*(p[2] for p in children))
    matched=set(); understood=set(); observed=[]
    for idx,atom in enumerate(atoms):
        if kind=='reduction':
            if atom['kind']!='equation':continue
            from local_math_equivalence_v1 import same_displayed_form
            n=predicate['exponent'];m=predicate['modulus'];b=predicate['base'];r=n%m
            pairs=[(f'{b}^{n}',f'{b}^{r}'),(f'{n}%{m}',str(r)),(str(n),f'{m}*{n//m}+{r}')]
            if any(same_displayed_form(left,atom['left']) is True and same_displayed_form(right,atom['right']) is True for left,right in pairs):
                matched.add(idx);understood.add(idx)
            continue
        if kind=='expansion':
            from local_math_equivalence_v1 import demonstrates_expansion
            if atom['kind']=='equation':
                if equivalent(atom['left'],atom['right']) is not True:
                    continue
                forms=[atom['left'],atom['right']]
            else:
                forms=[atom['value']]
            if any(demonstrates_expansion(predicate['source'],x) is True for x in forms):
                matched.add(idx);understood.add(idx)
            continue
        if kind=='equation' and atom['kind']=='equation':
            left_match=(same_displayed_form(predicate['left'],atom['left'])
                        if predicate['display_required'] else equivalent(predicate['left'],atom['left']))
            if left_match is not True:
                continue
            value=parse_expression(atom['right'])
            if predicate['left'].startswith(('Re(', 'Im(')) and value.is_real is not True:
                raise ValueError('REAL_COMPONENT_REQUIRED')
            observed.append(atom['right'])
            result=equivalent(predicate['right'],atom['right'])
            if result is None:
                raise ValueError('VALUE_UNDECIDABLE')
            understood.add(idx)
            if result:matched.add(idx)
        elif kind in {'value','form','component'} and (atom['kind']=='value' or (predicate.get('final_result') and idx==len(atoms)-1 and atom['kind']=='equation' and equivalent(atom['left'],atom['right']) is True)):
            if predicate.get('final_result') and idx!=len(atoms)-1:
                continue
            displayed=atom['value'] if atom['kind']=='value' else atom['right']
            value=parse_expression(displayed)
            if kind=='component':
                if value.free_symbols:
                    continue
                if predicate['component']=='real':
                    component=sp.re(value)
                elif predicate['component']=='imaginary':
                    expected=parse_expression(predicate['expected'])
                    component=sp.im(value) if expected.is_real else sp.I*sp.im(value)
                else:
                    component=sp.I*sp.im(value)
                result=equivalent(predicate['expected'],str(component))
            elif kind=='form':
                result=same_displayed_form(predicate['expected'],displayed)
            else:
                result=equivalent(predicate['expected'],displayed)
                if result and predicate.get('required_form')=='rectangular':
                    from local_math_equivalence_v1 import rectangular_form
                    result=rectangular_form(displayed) is True
                if result and predicate.get('final_result') and parse_expression(predicate['expected']).is_real is True and not re.search(r'\bi\b|ω|omega',predicate['expected']):
                    # An unevaluated complex power is working, not a real result.
                    if re.search(r'\bi\b|ω|omega',displayed):result=False
            if result is None:
                raise ValueError('VALUE_UNDECIDABLE')
            if kind=='form' or (kind=='value' and not predicate.get('final_result')):
                if result:
                    observed.append(displayed);understood.add(idx)
            else:
                observed.append(displayed);understood.add(idx)
            if result:matched.add(idx)
    # Whole-span conflict handling, as in ScoreMax's existing evidence engine.
    # A correct value cannot be selected from a list of incompatible answers.
    if len(observed)>1 and any(equivalent(observed[0],other) is not True for other in observed[1:]):
        raise ValueError('CONFLICTING_VALUES')
    return bool(matched),matched,understood


def assess_local(candidate,answer):
    """Evaluate source-weighted local evidence; unknown material stays unscored."""
    from local_math_equivalence_v1 import equivalent
    base={'markable':False,'marks_awarded':None,'maximum_marks':float(candidate.get('maximum_marks',0)),
          'is_correct':False,'confidence':0.0,'evidence_eligible':False,
          'status':'LOCAL_MATH_UNRESOLVED','marker_version':VERSION,'feedback':[]}
    predicates=local_predicates(candidate)
    if not predicates or not isinstance(answer,str) or not answer.strip() or len(answer)>10000:
        return base
    try:
        atoms=_learner_atoms(answer)
        evidence=[];total=Decimal(0);known=set()
        for point in predicates:
            satisfied,matched,understood=_match_evidence(point['evidence'],atoms)
            known.update(understood)
            awarded=Decimal(point['marks']) if satisfied else Decimal(0)
            total+=awarded
            evidence.append({'id':point['id'],'marks_awarded':str(awarded),
                             'learner_quotes':list(dict.fromkeys(atoms[i]['text'] for i in sorted(matched)))})
        # Additional displayed identities are safe only when proved locally.
        # Unrecognised statements can conceal contradictions and cause abstention.
        for idx,atom in enumerate(atoms):
            if idx not in known and atom['kind']=='equation' and equivalent(atom['left'],atom['right']) is True:
                known.add(idx)
        if known!=set(range(len(atoms))):
            return base
        maximum=Decimal(candidate['maximum_marks'])
        return {**base,'markable':True,'marks_awarded':float(total),
                'is_correct':total==maximum,'confidence':None,'evidence_eligible':True,
                'status':'MARK_CONFIRMED','candidate_sha256':candidate['candidate_sha256'],
                'response_sha256':hashlib.sha256(answer.encode()).hexdigest(),
                'point_evidence':evidence}
    except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError,ZeroDivisionError):
        return base



