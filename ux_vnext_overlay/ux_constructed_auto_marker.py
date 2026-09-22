"""Compile only explicit, auditable automatic marking contracts.

A model answer is not a rubric. No semantic mark points or synthetic confidence
are inferred from word overlap. The existing written-response engine handles the
bounded governed-clause lane; unsupported language is unscored, never sent to a human.
"""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re

from written_response_engine import mark_written_response, validate_automatic_rubric

MARKER_VERSION = 'SM-CONSTRUCTED-AUTO-2'
_NUMERIC = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,4})?\Z')


def _decimal(value):
    text = str(value).strip()
    if len(text) > 256 or not _NUMERIC.fullmatch(text):
        return None
    try:
        result = Decimal(text)
        return result if result.is_finite() and abs(result.adjusted()) <= 1000 else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def _normalise(value, case_sensitive=True):
    text = ' '.join(str(value).strip().split())
    return text if case_sensitive else text.casefold()


def compile_contract(answer_cfg, fallback_answer='', marks=1.0, stem='', command_word='', marking_cfg=None):
    """Return a versioned contract or None. Input is immutable PH-derived metadata.

    The only implicit legacy compatibility is a one-mark, finite numeric answer.
    Formula/exact-text comparison requires an explicit governed scoring contract.
    Conceptual/multi-point answers require the original structured rubric.
    """
    try:
        ac = dict(answer_cfg or {}); mc = dict(marking_cfg or {})
        maximum = float(marks)
        if isinstance(marks, bool) or not math.isfinite(maximum) or maximum <= 0:
            return None
        accepted = ac.get('accepted_answers') or []
        if not isinstance(accepted, list) or any(not isinstance(x, str) or not x.strip() for x in accepted):
            return None
        accepted = list(dict.fromkeys(accepted))
        if str(fallback_answer or '').strip() and str(fallback_answer) not in accepted:
            accepted.insert(0, str(fallback_answer))
        rubric = mc.get('rubric')
        mode = str(mc.get('scoring_contract') or ac.get('scoring_contract') or '')
        if rubric is not None:
            if not isinstance(rubric, dict) or not validate_automatic_rubric(rubric, maximum)['valid']:
                return None
            mode = 'governed_clause_rubric_v1'
            material = {'rubric':copy.deepcopy(rubric)}
        elif (mode == 'numeric_decimal_v1' or (not mode and maximum == 1.0)) and accepted and all(_decimal(x) is not None for x in accepted):
            mode = 'numeric_decimal_v1'
            material = {'accepted_answers':accepted}
        elif mode in {'normalised_text_exact','case_sensitive_exact'} and mc.get('auto_markable') is True and accepted:
            sensitive = ac.get('case_sensitive', True)
            if not isinstance(sensitive, bool):
                return None
            material = {'accepted_answers':accepted, 'case_sensitive':sensitive if mode != 'case_sensitive_exact' else True}
        else:
            return None
        contract = {'version':MARKER_VERSION, 'mode':mode, 'maximum_marks':maximum,
                    'command_verb':str(command_word or ''), **material}
        raw = json.dumps(contract,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
        contract['contract_sha256'] = hashlib.sha256(raw.encode()).hexdigest()
        return contract
    except (TypeError, ValueError, OverflowError):
        return None


def is_markable(answer_cfg, fallback_answer='', marks=1.0, stem='', command_word='', marking_cfg=None):
    return compile_contract(answer_cfg,fallback_answer,marks,stem,command_word,marking_cfg) is not None


def mark(contract, response):
    if not contract:
        return {'markable':False,'marks_awarded':None,'maximum_marks':0.0,'is_correct':False,
                'confidence':0.0,'status':'NO_MARKING_CONTRACT','evidence_eligible':False,'feedback':[]}
    unsigned = dict(contract); expected_hash = unsigned.pop('contract_sha256', None)
    actual_hash = hashlib.sha256(json.dumps(unsigned,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    if expected_hash != actual_hash or contract.get('version') != MARKER_VERSION:
        return {'markable':False,'marks_awarded':None,'maximum_marks':0.0,'is_correct':False,
                'confidence':0.0,'status':'INVALID_MARKING_CONTRACT','evidence_eligible':False,'feedback':[]}
    maximum = float(contract['maximum_marks']); answer = str(response or '').strip()
    base = {'markable':True, 'maximum_marks':maximum, 'marker_version':MARKER_VERSION,
            'contract_sha256':expected_hash, 'evidence_eligible':True, 'confidence':1.0,
            'status':'MARK_CONFIRMED', 'feedback':[]}
    if not answer:
        return {**base, 'marks_awarded':0.0,'is_correct':False,'response_present':False}
    if len(answer) > 10000:
        return {**base,'marks_awarded':None,'is_correct':False,'status':'RESPONSE_LIMIT_EXCEEDED',
                'confidence':0.0,'evidence_eligible':False,'feedback':['Please use a shorter answer.']}
    if contract['mode'] == 'numeric_decimal_v1':
        candidate = _decimal(answer)
        ok = candidate is not None and any(candidate == _decimal(x) for x in contract['accepted_answers'])
    elif contract['mode'] in {'normalised_text_exact','case_sensitive_exact'}:
        ok = _normalise(answer,contract['case_sensitive']) in {_normalise(x,contract['case_sensitive']) for x in contract['accepted_answers']}
    elif contract['mode'] == 'governed_clause_rubric_v1':
        result = mark_written_response({**contract['rubric'],'maximum_marks':maximum}, answer,
                                       {'scoring_contract':'governed_clause_rubric_v1'})
        final = result.get('status') == 'MARK_CONFIRMED'
        awarded = result['proposed_mark'] if final else None
        return {**base,'marks_awarded':awarded,'is_correct':bool(final and awarded >= maximum),
                'confidence':result['confidence'],'status':result['status'], 'evidence_eligible':final,
                'feedback':result['feedback'],'result':result}
    else:
        return {**base,'markable':False,'marks_awarded':None,'is_correct':False,
                'status':'UNSUPPORTED_MARKER_VERSION','confidence':0.0,'evidence_eligible':False}
    return {**base, 'marks_awarded':maximum if ok else 0.0, 'is_correct':ok, 'response_present':True}


def fixture_qualification():
    exact=compile_contract({'accepted_answers':['-314']},'-314',1)
    assert mark(exact,'-314.0')['is_correct'] and not mark(exact,'314')['is_correct']
    rubric={'version':'SM-RUBRIC-CLAUSES-1','required_mark_points':[{
        'id':'P1','description':'A causal explanation.', 'marks':1,
        'accepted_phrases':['The particle moves irregularly because molecules collide with it.'],
        'acceptable_paraphrases':['Unequal molecular impacts cause irregular motion.']}],
        'contradictions':[{'phrase':'No molecules collide with the particle.', 'point_ids':['P1']}]}
    contract=compile_contract({},'',1,marking_cfg={'rubric':rubric})
    assert mark(contract,'Unequal molecular impacts cause irregular motion.')['is_correct']
    assert mark(contract,'No molecules collide with the particle.')['marks_awarded']==0
    assert not mark(contract,'The particle does not move irregularly because molecules collide with it.')['evidence_eligible']
    assert compile_contract({'accepted_answers':['Molecules cause irregular movement.']},'',1) is None
    return {'exact':True,'semantic':True,'fail_closed':True}
