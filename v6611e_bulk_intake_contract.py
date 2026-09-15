"""ScoreMax V6.6.11E candidate — governed bulk-intake response-contract adapter.

This extends the existing Emergency Direct Intake writer. It does not create a second
importer and it does not infer Power House academic identities. Raw imported rows stay
preserved by the existing content_import_batch_rows ledger.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping


CANDIDATE_RELEASE = "6.6.11E"
MARKER = "SM-BULK-INTAKE-CONTRACT-V6611E-1"
TWO_TIER_HOLD = "PRODUCT_CAPABILITY_HOLD_TWO_TIER_COMPOSITE"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_type(row: Mapping[str, Any], fallback: str = "") -> str:
    return _text(
        row.get("Source Question Type")
        or row.get("Question_Type")
        or row.get("Question Type")
        or row.get("Type")
        or fallback
    ).upper()


def _is_hold(row: Mapping[str, Any]) -> bool:
    status = " ".join(
        _text(row.get(k)).upper()
        for k in ("Destination Release Status", "Release Status", "Readiness", "Status")
    )
    ready = _text(row.get("ScoreMax Ready")).lower()
    return "PRODUCT_CAPABILITY_HOLD" in status or ready in {"no", "false", "0"}


def supports_source_type(value: Any) -> bool:
    return _source_type({"Type": value}) in {
        "STANDARD_MCQ", "FOUR_STATEMENT_SELECTION", "CLOZE_SINGLE_SELECT",
        "MULTIPLE_RESPONSE", "MATCHING_SET", "ORDERING_SEQUENCE",
        "SHORT_CONSTRUCTED_RESPONSE", "ADAPTIVE_RECOVERY_PATHWAY_ITEM",
    }


def _parse_key(raw: Any, source_type: str) -> tuple[Any, str]:
    value = _text(raw)
    if source_type == "SHORT_CONSTRUCTED_RESPONSE":
        return value, "RUBRIC_ONLY"
    if source_type == "MATCHING_SET":
        try:
            parsed = json.loads(value)
        except Exception as exc:
            raise ValueError("MATCHING_KEY_JSON_REQUIRED") from exc
        if not isinstance(parsed, dict) or not parsed:
            raise ValueError("MATCHING_KEY_MAPPING_REQUIRED")
        return parsed, "MAPPING"
    if source_type == "ORDERING_SEQUENCE":
        if not value:
            raise ValueError("ORDERING_KEY_REQUIRED")
        return value, "ORDER"
    if source_type == "MULTIPLE_RESPONSE":
        try:
            parsed = json.loads(value)
        except Exception:
            parsed = [x.strip() for x in re.split(r"[|,;]", value) if x.strip()]
        if not isinstance(parsed, list) or len(parsed) < 2:
            raise ValueError("MULTIPLE_RESPONSE_KEY_LIST_REQUIRED")
        return [str(x).strip() for x in parsed], "MULTIPLE_OPTIONS"
    if source_type == "ADAPTIVE_RECOVERY_PATHWAY_ITEM":
        if re.search(r"(?i)tier\s*1\s*:", value) and re.search(r"(?i)tier\s*2\s*:", value):
            raise RuntimeError(TWO_TIER_HOLD)
        if re.fullmatch(r"[A-E]", value, re.I):
            return value.upper(), "SINGLE_OPTION"
        if value.upper() in {"TRUE", "FALSE"}:
            return value.upper() == "TRUE", "BOOLEAN"
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
            return float(value), "NUMERIC"
        if value:
            return value, "TEXT"
        raise ValueError("ADAPTIVE_RESPONSE_CONTRACT_REQUIRED")
    if re.fullmatch(r"[A-E]", value, re.I):
        return value.upper(), "SINGLE_OPTION"
    if value:
        return value, "TEXT"
    raise ValueError("ANSWER_KEY_REQUIRED")


def _options(row: Mapping[str, Any]) -> list[dict[str, str]]:
    out = []
    for code in "ABCDE":
        value = _text(row.get(code) or row.get(f"Option {code}") or row.get(f"Option_{code}"))
        if value:
            out.append({"option_id": code, "text": value})
    return out


def _strip_structural_heading_aliases(value: Any) -> str:
    """Normalise parser-only headings without changing the stored learner/source text."""
    kept = []
    for line in _text(value).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip().lower().rstrip(":") in {"left", "right"}:
            continue
        kept.append(line)
    return "\n".join(kept)


def _family_for_source(source_type: str) -> str:
    if source_type == "SHORT_CONSTRUCTED_RESPONSE":
        return "constructed_response"
    return source_type


def build_configs(row: Mapping[str, Any], question_contracts, *, fallback_type: str = "MCQ") -> dict[str, Any]:
    """Return persisted qtype plus governed answer/marking configs for one intake row.

    Genuine two-tier recovery composites are admitted only when the destination row is
    explicitly held and non-ready; they remain inactive and unsupported rather than being
    silently coerced to another learner interaction.
    """
    source_type = _source_type(row, fallback_type)
    try:
        key, key_type = _parse_key(row.get("Answer") or row.get("Key Answer") or row.get("Correct_Answer"), source_type)
    except RuntimeError as exc:
        if str(exc) != TWO_TIER_HOLD:
            raise
        if not _is_hold(row):
            raise ValueError("TWO_TIER_COMPOSITE_REQUIRES_EXPLICIT_DESTINATION_HOLD") from exc
        return {
            "source_type": source_type,
            "persisted_qtype": source_type,
            "runtime_type": "unsupported",
            "answer_config": {},
            "marking_config": {
                "marks": float(row.get("Marks") or 1),
                "auto_markable": False,
                "destination_hold": TWO_TIER_HOLD,
            },
            "destination_hold": TWO_TIER_HOLD,
        }

    options = _options(row)
    statements = _text(row.get("Statements_Raw") or row.get("Statements / Options"))
    content_options: Any = options
    if source_type == "MATCHING_SET":
        statements = _strip_structural_heading_aliases(
            row.get("Statements_Raw") or row.get("Stimulus / Context")
        )
        content_options = _strip_structural_heading_aliases(row.get("Options_Raw") or "")

    rubric = _text(row.get("Explanation") or row.get("Explanation / Marking Rubric"))
    marking = {
        "key": key,
        "key_type": key_type,
        "marks": float(row.get("Marks") or 1),
    }
    if rubric:
        marking["rubric"] = rubric

    content: dict[str, Any] = {
        "question_family_type": _family_for_source(source_type),
        "exam_question_type": source_type,
        "statements": statements,
        "options": content_options,
        "marking": marking,
    }
    if source_type == "ADAPTIVE_RECOVERY_PATHWAY_ITEM":
        response = {
            "SINGLE_OPTION": "single_choice",
            "BOOLEAN": "true_false",
            "NUMERIC": "numerical",
            "TEXT": "constructed_response",
        }.get(key_type)
        if not response:
            raise ValueError("ADAPTIVE_RESPONSE_CONTRACT_REQUIRED")
        content["response_contract"] = response

    contract = question_contracts.resolve_content_contract(content)
    interaction = question_contracts.build_interaction_contract(content, contract)
    response = contract.response_contract

    answer_config: dict[str, Any] = {
        "options": [
            {"id": str(x.get("option_id") or ""), "text": str(x.get("text") or "")}
            for x in options
        ],
        "response_contract": response,
        "question_family": contract.family,
    }
    marking_config: dict[str, Any] = {
        "marks": float(row.get("Marks") or 1),
        "negative_marks": 0.0,
        "auto_markable": bool(contract.auto_markable),
        "key_type": key_type,
        "response_contract": response,
        "scoring_contract": contract.scoring_contract,
        "partial_credit": False,
    }

    if response == "matching":
        answer_config.update({
            "left_items": interaction["left_items"],
            "right_options": interaction["right_options"],
            "allow_duplicate_targets": interaction["allow_duplicate_targets"],
        })
        marking_config.update({
            "correct_mapping": interaction["correct_mapping"],
            "allow_duplicate_targets": interaction["allow_duplicate_targets"],
        })
    elif response == "ordering":
        answer_config["ordering_items"] = interaction["items"]
        marking_config["correct_order"] = interaction["correct_order"]
    elif response in {"single_choice", "true_false", "multiple_select"}:
        marking_config["correct_option_ids"] = key if isinstance(key, list) else [str(key)]
    elif response == "numerical":
        marking_config["correct_value"] = float(key)
        marking_config["tolerance"] = float(row.get("Numerical Tolerance") or 0)
    elif response == "fill_blank":
        answer_config.update({"accepted_answers": [str(key)], "case_sensitive": False, "trim_spaces": True})
    elif response == "constructed_response":
        # Rubric-only source questions route to the existing governed reviewer queue.
        marking_config["rubric"] = rubric
        marking_config["auto_markable"] = False
        marking_config["scoring_contract"] = "rubric_review"

    persisted_qtype = "Constructed Response" if source_type == "SHORT_CONSTRUCTED_RESPONSE" else source_type
    return {
        "source_type": source_type,
        "persisted_qtype": persisted_qtype,
        "runtime_type": response,
        "answer_config": answer_config,
        "marking_config": marking_config,
        "destination_hold": "",
    }


def validate_row_contract(row: Mapping[str, Any], question_contracts) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    qtype = _text(row.get("Type") or row.get("Question Type") or row.get("Question_Type"))
    if not qtype:
        return errors, warnings
    try:
        result = build_configs(row, question_contracts, fallback_type=qtype)
        if result.get("destination_hold"):
            warnings.append("Destination product capability hold: genuine two-tier composite interaction is not coerced")
    except Exception as exc:
        errors.append("Question response contract invalid: " + str(exc))
    return errors, warnings
