"""Attach source-bound practice contracts through the existing PH publisher.

Native QA/readiness, source authority, release profiles, snapshots, versioning,
signing and outboxes remain authoritative. This module writes no database rows.
"""
from copy import deepcopy
import json
import re

from ph_practice_contracts import compile_cloze, source_saq_rubric
from guided_self_assessment import bind, MODE


def bind_practice_material(material, row, context, source, workbook_sha):
    content = material['content']
    family = str(content.get('question_family_type') or '').strip().upper()
    if (family == 'CLOZE_CONSTRUCTED_RESPONSE' or (context.get('display') or {}).get('practice_mode') == MODE):
        if not isinstance(workbook_sha, str) or not re.fullmatch('[0-9a-f]{64}', workbook_sha):
            raise ValueError('PRACTICE_SOURCE_WORKBOOK_AUTHORITY_REQUIRED')
    if family == 'CLOZE_CONSTRUCTED_RESPONSE':
        contract = compile_cloze(source, content.get('stem'), workbook_sha)
        marking = dict(content['marking'])
        rubric = deepcopy(marking.get('rubric') or {})
        if not isinstance(rubric, dict):
            raise ValueError('CLOZE_EXISTING_RUBRIC_INVALID')
        rubric['cloze_gap_contract'] = contract
        key = (contract['gaps'][0]['canonical_answer'] if contract['gap_count'] == 1 else
               json.dumps({g['id']: g['canonical_answer'] for g in contract['gaps']}, sort_keys=True))
        marking.update(key_type='TEXT', key=key, accepted_answers=contract['gaps'][0]['accepted_answers']
                       if contract['gap_count'] == 1 else [key], marks=contract['maximum_marks'],
                       negative_marks=0, rubric=rubric)
        content['marking'] = marking
        return material
    display = context.get('display') or {}
    if display.get('practice_mode') != MODE:
        return material
    if family not in {'SHORT_RESPONSE','SHORT_CONSTRUCTED_RESPONSE','CONSTRUCTED_RESPONSE',
                      'EXTENDED_RESPONSE','SAQ','SHORT_ANSWER','LONG_ANSWER'}:
        raise ValueError('GUIDED_WRITTEN_FAMILY_REQUIRED')
    reference = display.get('practice_approval_reference')
    if not isinstance(reference, str) or not reference.strip():
        raise ValueError('GOVERNED_DELIVERY_APPROVAL_REQUIRED')
    if source.get('Learner_Question') != content.get('stem'):
        raise ValueError('GUIDED_SOURCE_STEM_MISMATCH')
    if not isinstance(source.get('Model_Answer'), str) or not source['Model_Answer'].strip():
        raise ValueError('GUIDED_SOURCE_MODEL_ANSWER_REQUIRED')
    rubric = source_saq_rubric(source)
    approved = {'mode': MODE, 'reference': reference,
                'release_profile_public_id': context.get('release_profile_public_id') or context.get('release_profile_id')}
    bound = bind(rubric, source, approved, source_workbook_sha256=workbook_sha)
    marking = dict(content['marking'])
    marking.pop('scoring_contract', None)
    marking.update(key_type='TEXT', key=source['Model_Answer'], accepted_answers=[],
                   marks=rubric['maximum_marks'], negative_marks=0, rubric=bound)
    content['marking'] = marking
    content['options'] = []
    return material


def build_practice_material(material, row, context):
    family = str(material['content'].get('question_family_type') or '').strip().upper()
    guided = (context.get('display') or {}).get('practice_mode') == MODE
    if family != 'CLOZE_CONSTRUCTED_RESPONSE' and not guided:
        return material
    import db
    fidelity = db.query_one('SELECT source_row_json,source_workbook_sha256 FROM question_source_fidelity_v015l1 WHERE question_id=?',
                            (int(row['id']),))
    if not fidelity:
        raise ValueError('PRACTICE_IMMUTABLE_SOURCE_REQUIRED')
    source = json.loads(fidelity['source_row_json'])
    return bind_practice_material(material, row, context, source, str(fidelity['source_workbook_sha256']))
