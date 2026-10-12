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


def _validate_verdict(verdict, candidate, answer):
    if not isinstance(verdict, dict) or verdict.get('version') != VERSION or verdict.get('candidate_sha256') != candidate['candidate_sha256']:
        raise ValueError('VERDICT_CONTRACT_MISMATCH')
    if verdict.get('uncertain') is not False or verdict.get('contradiction') is not False:
        raise ValueError('UNCERTAIN_OR_CONTRADICTORY')
    provided = verdict.get('points')
    if not isinstance(provided, list) or len(provided) != len(candidate['points']):
        raise ValueError('VERDICT_POINT_COUNT')
    vector = []; evidence = []
    for source, decision in zip(candidate['points'], provided):
        if not isinstance(decision, dict) or decision.get('id') != source['id']:
            raise ValueError('VERDICT_POINT_ID')
        awarded = decision.get('marks_awarded')
        if isinstance(awarded, bool):
            raise ValueError('VERDICT_BOOLEAN_MARKS')
        try:
            value = Decimal(str(awarded)); maximum = Decimal(source['marks']); unit = Decimal(source['unit'])
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError('VERDICT_INVALID_MARKS')
        if not value.is_finite() or value < 0 or value > maximum or value / unit != int(value / unit):
            raise ValueError('VERDICT_ALLOCATION_CONFLICT')
        quote = decision.get('learner_quote')
        if not isinstance(quote, str) or (value > 0 and (not quote.strip() or quote not in answer)):
            raise ValueError('VERDICT_UNGROUNDED_EVIDENCE')
        if len(quote) > 500:
            raise ValueError('VERDICT_EVIDENCE_LIMIT')
        vector.append(value); evidence.append({'id':source['id'], 'marks_awarded':str(value),
                                                'learner_quote':quote})
    return vector, evidence


def assess_candidate(candidate, answer, judges):
    """Two independent judges must agree; any failure abstains without evidence."""
    base = {'markable':False, 'marks_awarded':None, 'maximum_marks':float(candidate['maximum_marks']),
            'is_correct':False, 'confidence':0.0, 'evidence_eligible':False,
            'status':'SEMANTIC_MARK_UNRESOLVED', 'marker_version':VERSION, 'feedback':[]}
    if not isinstance(answer, str) or not answer.strip() or len(answer) > 10000:
        return base
    if not isinstance(judges, (tuple, list)) or len(judges) != 2 or judges[0] is judges[1]:
        return base
    try:
        results = [_validate_verdict(judge(candidate, answer), candidate, answer) for judge in judges]
        if results[0][0] != results[1][0]:
            return base
        earned = sum(results[0][0], Decimal(0)); maximum = Decimal(candidate['maximum_marks'])
        return {**base, 'markable':True, 'marks_awarded':float(earned),
                'is_correct':earned == maximum, 'confidence':None,
                'evidence_eligible':True, 'status':'MARK_CONFIRMED',
                'candidate_sha256':candidate['candidate_sha256'],
                'response_sha256':hashlib.sha256(answer.encode()).hexdigest(),
                'point_evidence':results[0][1]}
    except Exception:  # Backend failure, timeout or malformed judgement cannot award marks.
        return base



def local_judges(candidate):
    """Local scorer must be qualified before it can supply independent checks."""
    return None
