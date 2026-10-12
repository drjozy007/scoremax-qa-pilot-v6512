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
        if not isinstance(stem, str) or not stem.strip() or len(stem) > 10000:
            return None
        if not isinstance(model_answer, str) or not model_answer.strip() or len(model_answer) > 10000:
            return None
        body = {'version':VERSION, 'source_contract_sha256':supplied_hash,
                'source_marking_evidence_sha256':source_hash, 'maximum_marks':str(total),
                'question':stem, 'model_answer':model_answer, 'points':out}
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
                isinstance(entry.get('qualification_evidence_sha256'), str) and
                bool(_SHA.fullmatch(entry['qualification_evidence_sha256'])))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def valid_candidate_pin(candidate):
    try:
        if not isinstance(candidate, dict) or candidate.get('version') != VERSION:
            return False
        unsigned = dict(candidate); supplied = unsigned.pop('candidate_sha256', None)
        return isinstance(supplied, str) and bool(_SHA.fullmatch(supplied)) and _hash(unsigned) == supplied
    except (TypeError, ValueError, OverflowError):
        return False



_POINT_EQ = re.compile(r'(?:for\s+)?(?P<lhs>Re\(z\)|Im\(z\)|[a-zA-Z][a-zA-Z0-9_]{0,4})\s*=\s*(?P<rhs>.+)\Z')


def local_predicates(candidate):
    """Compile only explicit equations in the original weighted criteria."""
    from local_math_equivalence_v1 import parse_expression
    if not valid_candidate_pin(candidate):
        return None
    out=[]
    for point in candidate['points']:
        match=_POINT_EQ.fullmatch(point['description'].strip())
        if not match:
            return None
        try:
            if parse_expression(match['rhs']).free_symbols:
                return None
        except (ValueError,SyntaxError,TypeError,OverflowError,RecursionError):
            return None
        out.append({'id':point['id'],'lhs':match['lhs'],'rhs':match['rhs'],
                    'marks':point['marks']})
    if len({p['lhs'] for p in out})!=len(out):
        return None
    return out


def assess_local(candidate,answer):
    """Score a fully parsed set of source-backed equations or abstain."""
    from local_math_equivalence_v1 import statement_equivalent
    base={'markable':False,'marks_awarded':None,'maximum_marks':float(candidate['maximum_marks']),
          'is_correct':False,'confidence':0.0,'evidence_eligible':False,
          'status':'LOCAL_MATH_UNRESOLVED','marker_version':VERSION,'feedback':[]}
    predicates=local_predicates(candidate)
    if not predicates or not isinstance(answer,str) or not answer.strip() or len(answer)>10000:
        return base
    statements=[s.strip() for s in re.split(r'[,;\n]+',answer) if s.strip()]
    if not statements or len(statements)>30:
        return base
    by_lhs={p['lhs']:[] for p in predicates}
    for statement in statements:
        match=_POINT_EQ.fullmatch(statement)
        if not match or match['lhs'] not in by_lhs:
            return base
        by_lhs[match['lhs']].append(statement)
    if any(len(values)>1 for values in by_lhs.values()):
        return base
    evidence=[];total=Decimal(0)
    for point in predicates:
        matches=by_lhs[point['lhs']]
        result=statement_equivalent(point['lhs']+'='+point['rhs'],matches[0]) if matches else False
        if result is None:
            return base
        awarded=Decimal(point['marks']) if result else Decimal(0)
        total+=awarded
        evidence.append({'id':point['id'],'marks_awarded':str(awarded),
                         'learner_quote':matches[0] if matches else ''})
    maximum=Decimal(candidate['maximum_marks'])
    return {**base,'markable':True,'marks_awarded':float(total),
            'is_correct':total==maximum,'confidence':None,'evidence_eligible':True,
            'status':'MARK_CONFIRMED','candidate_sha256':candidate['candidate_sha256'],
            'response_sha256':hashlib.sha256(answer.encode()).hexdigest(),
            'point_evidence':evidence}
