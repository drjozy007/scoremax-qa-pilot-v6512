"""Source-bound, unscored delivery contract. This module never judges an answer."""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json

VERSION = 'PH-GUIDED-SELF-ASSESSMENT-1'
MODE = 'GUIDED_SELF_ASSESSMENT'
AUTHORITY = {
    'automatic_marking': False, 'human_marking': False,
    'exam_readiness_evidence': False, 'formal_assessment': False,
    'ai_marking': False, 'ai_fallback': False, 'learner_activation_authorised': False,
}
REVIEWS = ('demonstrated', 'not_demonstrated', 'unsure')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def bind(rubric, source, approval):
    """Called only after a governed PH delivery amendment; never changes the rubric."""
    original = deepcopy(rubric)
    unsigned = dict(original); supplied = unsigned.pop('contract_sha256', None)
    if supplied != digest(unsigned):
        raise ValueError('ORIGINAL_CONTRACT_CHECKSUM_MISMATCH')
    if not isinstance(approval, dict) or approval.get('mode') != MODE or not approval.get('reference'):
        raise ValueError('GOVERNED_DELIVERY_APPROVAL_REQUIRED')
    if source.get('Required_Produced_Representation') != 'NONE' or source.get('Learner_Output_Type') != 'TEXT_SHORT_RESPONSE':
        raise ValueError('WRITTEN_RESPONSE_REQUIRED')
    if source.get('Capability_Status') != 'READY':
        raise ValueError('ACADEMIC_READY_REQUIRED')
    points = original.get('required_mark_points', [])
    evidence = str(source.get('Canonical_Accepted_Evidence') or '').split(' | ')
    weights = str(source.get('Mark_Point_Values') or '').split(';')
    if len(points) != len(evidence) or len(points) != len(weights) or len(points) != source.get('Mark_Point_Count'):
        raise ValueError('SOURCE_POINTS_MISMATCH')
    for pt, text, weight in zip(points, evidence, weights):
        if pt.get('description') != text or Decimal(str(pt.get('marks'))) != Decimal(weight):
            raise ValueError('SOURCE_POINT_FIDELITY_MISMATCH')
    delivery = {
        'version': VERSION, 'mode': MODE, 'authority': deepcopy(AUTHORITY),
        'approval': deepcopy(approval), 'original_contract_sha256': supplied,
        'source_row_sha256': digest(source),
        'source_master_sha256': source.get('_PH_Original_Master_SHA256'),
        'question_sha256': digest(source.get('Learner_Question')),
        'answer_sha256': digest(source.get('Model_Answer')),
        'points_sha256': digest(points), 'maximum_marks': source.get('Marks'),
        'response_type': 'LEARNER_GENERATED_WRITTEN_RESPONSE',
    }
    delivery['contract_sha256'] = digest(delivery)
    result = deepcopy(original)
    result['guided_self_assessment'] = delivery
    result.pop('contract_sha256')
    result['contract_sha256'] = digest(result)
    return result


def contract(marking, stem, answer, maximum):
    """Validate delivery independently of automatic-scoring eligibility."""
    try:
        rubric = marking.get('rubric')
        if not isinstance(rubric, dict) or 'guided_self_assessment' not in rubric:
            return None
        if rubric.get('version') != 'PH-SAQ-SCORING-CONTRACT-1' or 'native_scoring' in rubric:
            raise ValueError('GUIDED_ORIGINAL_RUBRIC_REQUIRED')
        body = deepcopy(rubric); supplied = body.pop('contract_sha256', None)
        if supplied != digest(body): raise ValueError('GUIDED_RUBRIC_CHECKSUM')
        delivery = body.pop('guided_self_assessment')
        if not isinstance(delivery, dict): raise ValueError('GUIDED_CONTRACT_INVALID')
        original_sha = digest(body)
        unsigned = dict(delivery); supplied = unsigned.pop('contract_sha256', None)
        if supplied != digest(unsigned): raise ValueError('GUIDED_CONTRACT_CHECKSUM')
        if delivery.get('version') != VERSION or delivery.get('mode') != MODE or delivery.get('authority') != AUTHORITY:
            raise ValueError('GUIDED_AUTHORITY_INVALID')
        if delivery.get('original_contract_sha256') != original_sha:
            raise ValueError('GUIDED_ORIGINAL_CONTRACT_MISMATCH')
        approval = delivery.get('approval', {})
        if approval.get('mode') != MODE or not approval.get('reference'):
            raise ValueError('GUIDED_APPROVAL_REQUIRED')
        if marking.get('auto_markable') is True or marking.get('scoring_contract'):
            raise ValueError('GUIDED_SCORING_AUTHORITY_CONFLICT')
        if delivery.get('question_sha256') != digest(stem) or delivery.get('answer_sha256') != digest(answer):
            raise ValueError('GUIDED_CONTENT_MISMATCH')
        if not isinstance(stem, str) or not stem.strip() or not isinstance(answer, str) or not answer.strip():
            raise ValueError('GUIDED_CONTENT_REQUIRED')
        points = body.get('required_mark_points')
        if not isinstance(points, list) or not points or len(points) > 50 or delivery.get('points_sha256') != digest(points):
            raise ValueError('GUIDED_POINTS_MISMATCH')
        ids = [p['id'] for p in points]
        if any(not isinstance(p, str) or not p for p in ids) or len(ids) != len(set(ids)):
            raise ValueError('GUIDED_POINT_IDS_INVALID')
        weights = [Decimal(str(p['marks'])) for p in points]
        if any(isinstance(p['marks'], bool) or not isinstance(p['description'], str) or not p['description'].strip() for p in points):
            raise ValueError('GUIDED_POINT_INVALID')
        if any(not w.is_finite() or w <= 0 for w in weights): raise ValueError('GUIDED_WEIGHT_INVALID')
        total = sum(weights, Decimal(0))
        if isinstance(maximum, bool) or total != Decimal(str(maximum)) or total != Decimal(str(delivery['maximum_marks'])) or total != Decimal(str(body['maximum_marks'])):
            raise ValueError('GUIDED_MAXIMUM_MISMATCH')
        return deepcopy(delivery)
    except (TypeError, KeyError, InvalidOperation, OverflowError) as exc:
        raise ValueError('GUIDED_CONTRACT_INVALID') from exc


def from_question(q):
    q = dict(q)
    marking = q.get('marking_config') or {}
    if isinstance(marking, str): marking = json.loads(marking)
    return contract(marking, q.get('question'), q.get('answer'), q.get('marks'))


def guidance(q):
    """Allowlisted learner fields. Call only after the server has frozen a response."""
    q = dict(q)
    if not from_question(q): raise ValueError('GUIDED_CONTRACT_REQUIRED')
    marking = q['marking_config']
    if isinstance(marking, str): marking = json.loads(marking)
    points = marking['rubric']['required_mark_points']
    policies = marking['rubric'].get('source_scoring_policies', {})
    notes = [policies[k] for k in ('Partial_Credit_Rule', 'Contradiction_Rule', 'Unacceptable_Near_Misses')
             if isinstance(policies.get(k), str) and policies[k] not in ('', 'NOT_APPLICABLE')]
    return {'question': q['question'], 'model_answer': q['answer'], 'maximum_marks': q['marks'],
            'points': [{'description': p['description'], 'marks': p['marks']} for p in points],
            'source_guidance': notes}
