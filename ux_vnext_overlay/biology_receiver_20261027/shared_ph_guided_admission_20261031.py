"""Bounded ScoreMax PH release-admission compatibility for existing guided SAQs.

Reuses the governed, source-bound guided_self_assessment.from_question.
Never approves an unbound rubric, enables AI, or confers scoring/activation.
"""
from __future__ import annotations
import ast
from pathlib import Path

MARKER = 'SM-PH-SOURCE-BOUND-GUIDED-RELEASE-20261031-1'
ANCHOR = 'question_contracts.validate_assessment_contract(projection)'

def apply(root: Path) -> None:
    target = Path(root) / 'scoremax_integration_v1.py'
    if not target.is_file():
        raise RuntimeError('ACCEPTED_SCOREMAX_RECEIVER_MISSING')
    source = target.read_text(encoding='utf-8')
    if MARKER in source:
        return
    tree = ast.parse(source)
    funcs = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    admission = next((n for n in funcs if n.name == 'admit_content_envelope'), None)
    if not admission:
        raise RuntimeError('ACCEPTED_SCOREMAX_ADMISSION_FUNCTION_MISSING')
    lines = source.splitlines(keepends=True)
    body = ''.join(lines[admission.lineno-1:admission.end_lineno])
    if body.count(ANCHOR) != 1:
        raise RuntimeError('SCOREMAX_NATIVE_ADMISSION_ANCHOR_DRIFT')
    new_body = body.replace(ANCHOR, '_ph_validate_scored_or_guided_assessment(projection)', 1)
    helper = '''
# SM-PH-SOURCE-BOUND-GUIDED-RELEASE-20261031-1
def _ph_validate_scored_or_guided_assessment(projection):
    # Only a fully source-bound, independently validated GUIDED contract may
    # use unscored practice. This is NOT self-marking or learner activation.
    from guided_self_assessment import from_question as verified_guided
    try:
        result = verified_guided(projection)
    except (ValueError, TypeError, KeyError) as exc:
        raise question_contracts.QuestionContractError(
            "SOURCE_BOUND_GUIDED_CONTRACT_INVALID") from exc
    if result is not None:
        if projection.get('ph_is_auto_markable') not in (0, False):
            raise question_contracts.QuestionContractError(
                "GUIDED_AUTO_MARKING_AUTHORITY_CONFLICT")
        if result.get('mode') != 'GUIDED_SELF_ASSESSMENT':
            raise question_contracts.QuestionContractError(
                "GUIDED_MODE_NOT_AUTHORISED")
        authority = result.get('authority') or {}
        if any(authority.get(name) is not False for name in (
                'automatic_marking', 'human_marking', 'exam_readiness_evidence',
                'formal_assessment', 'ai_marking', 'ai_fallback',
                'learner_activation_authorised')):
            raise question_contracts.QuestionContractError(
                "GUIDED_AUTHORITY_NOT_UNSCORED")
        return {'delivery_mode':'GUIDED_UNSCORED', 'scoring_authorised':False}
    return question_contracts.validate_assessment_contract(projection)

'''
    updated = ''.join(lines[:admission.lineno-1]) + helper + new_body + ''.join(lines[admission.end_lineno:])
    compile(updated, str(target), 'exec')
    target.write_text(updated, encoding='utf-8')
    print('SM_GUIDED_RELEASE_BOUNDARY_INSTALLED source_bound_only=true scored_path_unchanged=true release=false', flush=True)
