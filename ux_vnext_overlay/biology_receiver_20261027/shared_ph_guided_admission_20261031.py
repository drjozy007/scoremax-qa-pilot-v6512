"""Use the existing signed PH release admission and source-bound guided SAQ path.

No new endpoint, release mode, database table, academic approval, marking
authority or student activation. Only the precise rubric-only semantic error is
suppressed, and only after validating the full, existing guided contract.
"""
from __future__ import annotations

import ast
from pathlib import Path

MARKER = "SM-PH-SOURCE-BOUND-GUIDED-RELEASE-20261031-2"
SCORED_ANCHOR = "question_contracts.validate_assessment_contract(projection)"
SEMANTIC_ANCHOR = "errors.extend(_semantic_content_errors(questions,stimuli,schema_version))"


def apply(root: Path) -> None:
    path = Path(root) / "scoremax_integration_v1.py"
    if not path.is_file():
        raise RuntimeError("ACCEPTED_SCOREMAX_RECEIVER_MISSING")
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return
    if "SM-PH-SOURCE-BOUND-GUIDED-RELEASE-20261031-1" in source:
        raise RuntimeError("PARTIALLY_INSTALLED_GUIDED_RECEIVER")
    parsed = ast.parse(source)
    matches = [node for node in parsed.body
               if isinstance(node, ast.FunctionDef)
               and node.name == "admit_content_envelope"]
    if len(matches) != 1:
        raise RuntimeError("SCOREMAX_NATIVE_ADMISSION_FUNCTION_DRIFT")
    node = matches[0]
    lines = source.splitlines(keepends=True)
    original = "".join(lines[node.lineno - 1:node.end_lineno])
    if original.count(SCORED_ANCHOR) != 1 or original.count(SEMANTIC_ANCHOR) != 1:
        raise RuntimeError("SCOREMAX_NATIVE_ADMISSION_CONTRACT_DRIFT")
    amended = original.replace(
        SCORED_ANCHOR, "_ph_validate_scored_or_guided_assessment(projection)", 1
    ).replace(
        SEMANTIC_ANCHOR,
        "errors.extend(_ph_semantic_errors_with_governed_guided(questions,stimuli,schema_version))",
        1,
    )
    helper = '''
# SM-PH-SOURCE-BOUND-GUIDED-RELEASE-20261031-2
def _ph_validate_scored_or_guided_assessment(projection):
    """A fully verified guided contract, or the original scored validator."""
    from guided_self_assessment import from_question as verified_guided
    try:
        guided = verified_guided(projection)
    except (ValueError, TypeError, KeyError) as exc:
        raise question_contracts.QuestionContractError(
            "SOURCE_BOUND_GUIDED_CONTRACT_INVALID") from exc
    if guided is None:
        return question_contracts.validate_assessment_contract(projection)
    if projection.get("ph_is_auto_markable") not in (0, False):
        raise question_contracts.QuestionContractError(
            "GUIDED_AUTO_MARKING_AUTHORITY_CONFLICT")
    if guided.get("mode") != "GUIDED_SELF_ASSESSMENT":
        raise question_contracts.QuestionContractError(
            "GUIDED_MODE_NOT_AUTHORISED")
    authority = guided.get("authority") or {}
    if any(authority.get(name) is not False for name in (
            "automatic_marking", "human_marking", "exam_readiness_evidence",
            "formal_assessment", "ai_marking", "ai_fallback",
            "learner_activation_authorised")):
        raise question_contracts.QuestionContractError(
            "GUIDED_AUTHORITY_NOT_UNSCORED")
    import math
    from decimal import Decimal, InvalidOperation
    try:
        config = projection.get("marking_config") or {}
        if isinstance(config, str):
            config = strict_json_loads(config)
        if not isinstance(config, dict):
            raise ValueError("MARKING_CONFIGURATION_MISSING")
        negative = Decimal(str(config.get("negative_marks", 0)))
        marks = Decimal(str(projection.get("marks", config.get("marks"))))
        if (not negative.is_finite() or negative != 0 or
                not marks.is_finite() or marks <= 0):
            raise ValueError("GUIDED_MARKS_INVALID")
        answer = projection.get("answer_config") or {}
        if isinstance(answer, str):
            answer = strict_json_loads(answer)
        if not isinstance(answer, dict) or answer.get("options"):
            raise ValueError("GUIDED_OPTIONS_NOT_ALLOWED")
    except (TypeError, ValueError, InvalidOperation, OverflowError, KeyError) as exc:
        raise question_contracts.QuestionContractError(
            "GUIDED_RESPONSE_STRUCTURE_INVALID") from exc
    return {"delivery_mode": "GUIDED_UNSCORED", "scoring_authorised": False}


def _ph_semantic_errors_with_governed_guided(questions, stimuli, schema_version):
    """Preserve every native semantic error unless its sole rubric-only ban
    is superseded by an actual independently validated guided contract.
    """
    errors = _semantic_content_errors(questions, stimuli, schema_version)
    lookup = {str(s.get("stimulus_id")): s for s in stimuli
              if isinstance(s, dict) and s.get("stimulus_id")}
    valid = set()
    for index, question in enumerate(questions):
        content = question.get("content") or {}
        marking = content.get("marking") or {}
        if str(marking.get("key_type") or "").upper() != "RUBRIC_ONLY":
            continue
        try:
            projection = _projection(question, lookup)
            decision = _ph_validate_scored_or_guided_assessment(projection)
        except (question_contracts.QuestionContractError, KeyError,
                TypeError, ValueError):
            continue
        if (isinstance(decision, dict)
                and decision.get("delivery_mode") == "GUIDED_UNSCORED"
                and decision.get("scoring_authorised") is False):
            valid.add(index)
    return [err for err in errors if not (
        err.get("code") == "UNSUPPORTED_RUBRIC_ONLY_DELIVERY"
        and err.get("path") in {
            f"payload.questions[{index}].content.marking.key_type"
            for index in valid
        }
    )]

'''
    updated = ("".join(lines[:node.lineno - 1]) + helper + amended
               + "".join(lines[node.end_lineno:]))
    compile(updated, str(path), "exec")
    path.write_text(updated, encoding="utf-8")
    print("SM_PH_GUIDED_RELEASE_BOUNDARY_BUILD_PASS exact_guided_only=true "
          "native_scored_unchanged=true activation=false", flush=True)
