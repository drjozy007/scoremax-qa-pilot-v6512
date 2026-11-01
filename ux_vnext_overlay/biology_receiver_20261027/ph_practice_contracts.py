"""Source-bound practice wire contracts shared by PH publication and ScoreMax.

Pure compilation/validation. No academic decisions, database, network or activation.
"""
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import re

CLOZE_VERSION = 'PH-CLOZE-GAPS-1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def number(value):
    if isinstance(value, bool):
        raise ValueError('SOURCE_MARKS_INVALID')
    try:
        value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError('SOURCE_MARKS_INVALID') from exc
    if not value.is_finite() or value <= 0:
        raise ValueError('SOURCE_MARKS_INVALID')
    return value


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def _assignments(text, separator):
    if not isinstance(text, str) or not text.strip():
        raise ValueError('CLOZE_GAP_KEYS_REQUIRED')
    result = {}
    for part in re.split(separator, text):
        match = re.fullmatch(r'\s*(G[1-9][0-9]*)\s*=\s*(.+?)\s*', part)
        if not match or match[1] in result:
            raise ValueError('CLOZE_GAP_KEYS_INVALID')
        result[match[1]] = match[2]
    return result


def compile_cloze(source, stem, workbook_sha):
    """Consume explicit immutable source fields; never split a combined learner answer."""
    if source.get('Learner_Question') != stem:
        raise ValueError('CLOZE_SOURCE_STEM_MISMATCH')
    count = number(source.get('Gap_Count'))
    if count != int(count) or not 1 <= count <= 50:
        raise ValueError('CLOZE_GAP_COUNT_INVALID')
    count = int(count)
    ids = [x.strip() for x in str(source.get('Gap_IDs') or '').split('|')]
    labels = ['G'+str(i+1) for i in range(count)]
    if len(ids) != count or any(not x for x in ids) or len(set(ids)) != count:
        raise ValueError('CLOZE_SOURCE_GAP_IDS_INVALID')
    keys = _assignments(source.get('Canonical_Answers'), r'\s*\|\s*(?=G[1-9][0-9]*\s*=)')
    alternatives = _assignments(source.get('Acceptable_Alternatives'), r'\s*;\s*(?=G[1-9][0-9]*\s*=)')
    if set(keys) != set(labels) or set(alternatives) != set(labels):
        raise ValueError('CLOZE_SOURCE_GAP_KEY_CARDINALITY')
    if source.get('Answer_Set_Closure_Status') != 'FINITE_CLOSED' or source.get('Auto_Marking_Eligibility') != 'YES_DETERMINISTIC':
        raise ValueError('CLOZE_FINITE_MARKING_AUTHORITY_REQUIRED')
    rules = str(source.get('Answer_Normalization_Rules') or '')
    units = re.split(r'\s*;\s*(?=G[1-9][0-9]*:)', rules)
    policy = 'TRIM_OUTER_WHITESPACE; FULL_RESPONSE_EXACT_AFTER_CASE_NORMALIZATION; EXPLICIT_ALTERNATIVES_ONLY; NO_FUZZY_MATCH'
    if units != [label+':'+policy for label in labels]:
        raise ValueError('CLOZE_NORMALIZATION_POLICY_UNSUPPORTED')
    maximum = number(source.get('Total_Practice_Score'))
    if not _sha(workbook_sha) or not source.get('Source_Locator'):
        raise ValueError('CLOZE_SOURCE_AUTHORITY_REQUIRED')
    gaps = []
    for label, gap_id in zip(labels, ids):
        alt = [] if alternatives[label] == 'NONE' else [x.strip() for x in alternatives[label].split('|')]
        if any(not x or x == 'NONE' for x in alt):
            raise ValueError('CLOZE_ALTERNATIVES_INVALID')
        gaps.append({'id': gap_id, 'label': label, 'canonical_answer': keys[label],
                     'accepted_answers': list(dict.fromkeys([keys[label]]+alt))})
    body = {'version': CLOZE_VERSION, 'source_row_sha256': digest(source),
            'source_workbook_sha256': workbook_sha, 'source_locator': source['Source_Locator'],
            'stem_sha256': digest(stem), 'gap_count': count, 'gaps': gaps,
            'maximum_marks': float(maximum), 'scoring_policy': 'ALL_GAPS_EXACT',
            'case_sensitive': False, 'trim_spaces': True}
    body['contract_sha256'] = digest(body)
    validate_cloze(body, stem, float(maximum))
    return body


def validate_cloze(contract, stem, maximum):
    if not isinstance(contract, dict):
        raise ValueError('CLOZE_STRUCTURED_CONTRACT_REQUIRED')
    body = deepcopy(contract)
    checksum = body.pop('contract_sha256', None)
    if checksum != digest(body) or body.get('version') != CLOZE_VERSION:
        raise ValueError('CLOZE_CONTRACT_CHECKSUM')
    if not all(_sha(body.get(k)) for k in ('source_row_sha256', 'source_workbook_sha256')) or not body.get('source_locator'):
        raise ValueError('CLOZE_SOURCE_AUTHORITY_REQUIRED')
    if not isinstance(stem, str) or body.get('stem_sha256') != digest(stem):
        raise ValueError('CLOZE_CONTENT_BINDING')
    gaps = body.get('gaps')
    count = body.get('gap_count')
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 50 or not isinstance(gaps, list) or len(gaps) != count:
        raise ValueError('CLOZE_GAP_CARDINALITY')
    if len(re.findall(r'_{3,}', stem)) != count:
        raise ValueError('CLOZE_RENDERED_GAP_CARDINALITY')
    ids = []
    for i, gap in enumerate(gaps, 1):
        if not isinstance(gap, dict) or gap.get('label') != 'G'+str(i):
            raise ValueError('CLOZE_GAP_ORDER')
        ids.append(gap.get('id'))
        values = gap.get('accepted_answers')
        if not isinstance(values, list) or not values or any(not isinstance(x, str) or not x.strip() for x in values) or gap.get('canonical_answer') not in values:
            raise ValueError('CLOZE_ACCEPTED_ANSWERS_REQUIRED')
    if any(not isinstance(x, str) or not x or len(x) > 200 for x in ids) or len(set(ids)) != count:
        raise ValueError('CLOZE_GAP_IDENTITY')
    if (body.get('scoring_policy') != 'ALL_GAPS_EXACT' or body.get('case_sensitive') is not False
            or body.get('trim_spaces') is not True or number(maximum) != number(body.get('maximum_marks'))):
        raise ValueError('CLOZE_MARKING_POLICY_CONFLICT')
    return deepcopy(contract)


def response_mapping(response, gaps):
    """One independently named answer per source gap, including explicit blanks."""
    try:
        value = json.loads(response) if isinstance(response, str) else response
    except (ValueError, TypeError) as exc:
        raise ValueError('CLOZE_GAP_RESPONSE_OBJECT_REQUIRED') from exc
    if not isinstance(value, dict) or set(value) != {g['id'] for g in gaps}:
        raise ValueError('CLOZE_RESPONSE_GAP_IDENTITY')
    if any(not isinstance(x, str) or len(x) > 1000 for x in value.values()):
        raise ValueError('CLOZE_GAP_RESPONSE_INVALID')
    return value


def score_gaps(contract, response):
    gaps = contract['gaps']
    submitted = response_mapping(response, gaps)
    checks = {g['id']: submitted[g['id']].strip().casefold() in
              {x.strip().casefold() for x in g['accepted_answers']} for g in gaps}
    # Source total is preserved. Partial marks require a separate explicit source allocation.
    # No inferred weights, fuzzy matches, cross-gap permutations or AI fallbacks.
    return all(checks.values()), checks


def source_saq_rubric(source):
    """Compile explicit point weights and literal numbered rubric, without scoring authority."""
    count = number(source.get('Mark_Point_Count'))
    values = re.split(r'\s*[;|]\s*', str(source.get('Mark_Point_Values') or ''))
    evidence = str(source.get('Canonical_Accepted_Evidence') or '')
    clauses = evidence.split(' || ') if ' || ' in evidence else evidence.split(' | ')
    if count != int(count) or not 1 <= count <= 50 or len(values) != int(count) or len(clauses) != int(count):
        raise ValueError('SOURCE_STRUCTURED_MARK_CARDINALITY_CONFLICT')
    weights = [number(v) for v in values]
    maximum = number(source.get('Marks'))
    if sum(weights, Decimal(0)) != maximum or any(not x.strip() for x in clauses):
        raise ValueError('SOURCE_STRUCTURED_MARK_TOTAL_CONFLICT')
    literal = str(source.get('Marking_Rubric') or '')
    points = re.split(r'\s*\|\s*', literal)
    if len(points) != int(count):
        raise ValueError('SOURCE_STRUCTURED_MARK_RUBRIC_CONFLICT')
    for i, (text, clause, weight) in enumerate(zip(points, clauses, weights), 1):
        match = re.fullmatch(r'\s*'+str(i)+r'\.\s*([0-9]+(?:\.[0-9]+)?)\s+marks?\s*[—–:-]\s*(.+?)\s*', text)
        if not match or number(match[1]) != weight or match[2] != clause:
            raise ValueError('SOURCE_STRUCTURED_MARK_RUBRIC_CONFLICT')
    body = {'version': 'PH-SAQ-SCORING-CONTRACT-1', 'maximum_marks': float(maximum),
            'auto_marking_eligibility': 'RUBRIC_SEMANTICALLY_SCORABLE', 'scoring_type': 'SEMANTIC_MARK_POINT',
            'required_mark_points': [{'id': 'p'+str(i), 'description': text, 'marks': float(weight)}
                                     for i, (text, weight) in enumerate(zip(clauses, weights), 1)],
            'source_scoring_policies': {k: v for k, v in source.items() if k.endswith('_Rule') or k in
                                       ('Unacceptable_Near_Misses', 'Marking_Rubric', 'Acceptable_Alternatives')},
            'source_marking_evidence_sha256': digest(source), 'academic_approval_conferred': False}
    body['contract_sha256'] = digest(body)
    return body
