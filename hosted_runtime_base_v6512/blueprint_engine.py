"""ScoreMax V5.5 Assessment Blueprint and calibration helpers.

Power House remains the authoritative source of approved blueprints.  This module
contains deterministic validation, checksum/signature verification, section
normalisation, rigor-policy interpretation and impact helpers that can be tested
without a Flask request context.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ELIGIBLE_SOURCE_STATUSES = {"APPROVED", "APPROVED_ACTIVE", "ACTIVE"}
LOCAL_BLUEPRINT_STATUSES = {"IMPORTED", "VALIDATED", "ACTIVE", "SUPERSEDED", "REJECTED", "SYNC_ERROR", "ARCHIVED"}
DIFFICULTY_ORDER = ("Easy", "Moderate", "Difficult")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_for_integrity(payload: Mapping[str, Any]) -> Dict[str, Any]:
    clean = dict(payload)
    clean.pop("checksum", None)
    clean.pop("payload_checksum", None)
    clean.pop("signature", None)
    clean.pop("signature_algorithm", None)
    return clean


def calculate_checksum(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload_for_integrity(payload)).encode("utf-8")).hexdigest()


def calculate_signature(payload: Mapping[str, Any], shared_secret: str) -> str:
    return hmac.new(shared_secret.encode("utf-8"), canonical_json(payload_for_integrity(payload)).encode("utf-8"), hashlib.sha256).hexdigest()


def _number(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: Optional[int] = None) -> Optional[int]:
    num = _number(value)
    if num is None or not float(num).is_integer():
        return default
    return int(num)


def normalize_sections(payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows = payload.get("sections") or payload.get("subjects") or []
    out: List[Dict[str, Any]] = []
    for index, raw in enumerate(rows, 1):
        raw = dict(raw or {})
        subject = str(raw.get("subject") or raw.get("name") or "").strip()
        out.append({
            "section_order": _integer(raw.get("section_order"), index) or index,
            "section_code": str(raw.get("section_code") or raw.get("subject_code") or "").strip(),
            "section_title": str(raw.get("section_title") or subject).strip(),
            "subject": subject,
            "question_count": _integer(raw.get("question_count")),
            "weight_percent": _number(raw.get("weight_percent")),
            "duration_minutes": _integer(raw.get("duration_minutes")),
            "difficulty_distribution": raw.get("difficulty_distribution") or {},
            "rules": raw.get("rules") or {},
        })
    return sorted(out, key=lambda x: (x["section_order"], x["subject"].lower()))


def normalize_blueprint_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    framework = dict(payload.get("framework") or {})
    framework_version = dict(payload.get("framework_version") or {})
    approval = dict(payload.get("approval") or {})
    source_status = str(payload.get("status") or "").strip().upper()
    version = payload.get("blueprint_version")
    if version is None:
        version = payload.get("version")
    return {
        "schema_version": str(payload.get("schema_version") or "1.0").strip(),
        "blueprint_id": str(payload.get("blueprint_id") or payload.get("id") or "").strip(),
        "framework_id": str(framework.get("id") or payload.get("framework_id") or "").strip(),
        "framework_name": str(framework.get("name") or payload.get("framework_name") or "").strip(),
        "framework_version_id": str(framework_version.get("id") or payload.get("framework_version_id") or "").strip(),
        "framework_version_name": str(framework_version.get("name") or payload.get("framework_version_name") or "").strip(),
        "blueprint_version": str(version if version is not None else "").strip(),
        "source_status": source_status,
        "authority": str(payload.get("authority") or payload.get("issuing_authority") or "").strip(),
        "source_reference": str(payload.get("source_reference") or payload.get("source") or "").strip(),
        "governance_note": str(payload.get("governance_note") or "").strip(),
        "total_questions": _integer(payload.get("total_questions")),
        "duration_minutes": _integer(payload.get("duration_minutes")),
        "activation_date": str(payload.get("activation_date") or payload.get("effective_from") or "").strip(),
        "superseded_date": str(payload.get("superseded_date") or payload.get("effective_to") or "").strip(),
        "source_created_at": str(payload.get("created_at") or "").strip(),
        "source_approved_at": str(approval.get("approved_at") or payload.get("approved_at") or "").strip(),
        "source_approved_by": str(approval.get("approved_by") or payload.get("approved_by") or "").strip(),
        "source_policy_version": str(approval.get("policy_version") or payload.get("policy_version") or "").strip(),
        "difficulty_distribution": payload.get("difficulty_distribution") or {},
        "required_subjects": payload.get("required_subjects") or [],
        "sections": normalize_sections(payload),
    }


def validate_blueprint_payload(payload: Mapping[str, Any], *, shared_secret: str = "", require_signature: bool = False,
                               percent_tolerance: float = 0.25) -> Dict[str, Any]:
    normalized = normalize_blueprint_payload(payload)
    errors: List[str] = []
    warnings: List[str] = []
    passed: List[str] = []

    required_text = [
        ("blueprint_id", "Blueprint ID"),
        ("framework_id", "Framework ID"),
        ("framework_name", "Framework name"),
        ("framework_version_id", "Framework-version ID"),
        ("framework_version_name", "Framework-version name"),
        ("blueprint_version", "Blueprint version"),
        ("authority", "Issuing authority"),
    ]
    for key, label in required_text:
        if not normalized.get(key):
            errors.append(f"{label} is required.")
    if not errors:
        passed.append("Core identity and authority fields are present.")

    if normalized["source_status"] not in ELIGIBLE_SOURCE_STATUSES:
        errors.append(f"Power House status {normalized['source_status'] or '(blank)'} is not eligible for production use.")
    else:
        passed.append("Power House status is approved/active.")

    total = normalized["total_questions"]
    if total is None or total <= 0:
        errors.append("Total questions must be a positive integer.")
    sections = normalized["sections"]
    if not sections:
        errors.append("At least one subject/section row is required.")
    seen = set()
    count_sum = 0
    weight_sum = 0.0
    for row in sections:
        subject = row["subject"]
        key = subject.casefold()
        if not subject:
            errors.append(f"Section {row['section_order']} has no subject name.")
        elif key in seen:
            errors.append(f"Duplicate subject row: {subject}.")
        seen.add(key)
        count = row["question_count"]
        weight = row["weight_percent"]
        if count is None or count <= 0:
            errors.append(f"{subject or 'A section'} must have a positive integer question count.")
        else:
            count_sum += count
        if weight is None or weight <= 0:
            errors.append(f"{subject or 'A section'} must have a positive weight percentage.")
        else:
            weight_sum += weight
    if total is not None and sections and count_sum != total:
        errors.append(f"Subject counts sum to {count_sum}, not total_questions={total}.")
    elif sections:
        passed.append("Subject counts sum exactly to total questions.")
    if sections and abs(weight_sum - 100.0) > percent_tolerance:
        errors.append(f"Subject percentages sum to {weight_sum:.4g}%, outside the {percent_tolerance}% rounding tolerance.")
    elif sections:
        passed.append("Subject percentages sum to 100% within tolerance.")

    required_subjects = [str(x).strip() for x in normalized.get("required_subjects") or [] if str(x).strip()]
    missing = [x for x in required_subjects if x.casefold() not in seen]
    if missing:
        errors.append("Required subjects missing: " + ", ".join(missing) + ".")
    elif required_subjects:
        passed.append("All blueprint-declared required subjects are present.")

    expected_checksum = str(payload.get("checksum") or payload.get("payload_checksum") or "").strip().lower()
    actual_checksum = calculate_checksum(payload)
    if not expected_checksum:
        errors.append("Payload checksum is required.")
    elif not hmac.compare_digest(expected_checksum, actual_checksum):
        errors.append("Payload checksum does not match the immutable blueprint content.")
    else:
        passed.append("Payload checksum matches.")

    signature = str(payload.get("signature") or "").strip().lower()
    if shared_secret:
        expected_signature = calculate_signature(payload, shared_secret)
        if not signature:
            errors.append("A Power House signature is required because a shared verification secret is configured.")
        elif not hmac.compare_digest(signature, expected_signature):
            errors.append("Power House signature verification failed.")
        else:
            passed.append("Power House HMAC signature verified.")
    elif require_signature:
        errors.append("Signature verification is required but no shared secret is configured.")
    else:
        warnings.append("No shared Power House signing secret is configured; checksum integrity is verified but source authenticity is not cryptographically proven.")

    if normalized["duration_minutes"] is None:
        warnings.append("Assessment duration is not supplied.")
    if not normalized["source_reference"]:
        warnings.append("No official source reference/governance reference is supplied.")
    if not normalized["source_approved_at"] or not normalized["source_approved_by"]:
        warnings.append("Power House approval metadata is incomplete.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "passed": passed,
        "normalized": normalized,
        "calculated_checksum": actual_checksum,
    }


def normalize_difficulty(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"easy", "accessible", "foundation", "low"}:
        return "Easy"
    if text in {"difficult", "hard", "challenging", "very difficult", "high"}:
        return "Difficult"
    return "Moderate"


def normalize_mix(raw: Mapping[str, Any]) -> Dict[str, float]:
    values = {
        "Easy": max(0.0, _number(raw.get("easy_percent") if raw else None, 0.0) or 0.0),
        "Moderate": max(0.0, _number(raw.get("moderate_percent") if raw else None, 0.0) or 0.0),
        "Difficult": max(0.0, _number(raw.get("difficult_percent") if raw else None, 0.0) or 0.0),
    }
    total = sum(values.values())
    if total <= 0:
        return {"Easy": 20.0, "Moderate": 60.0, "Difficult": 20.0}
    return {k: 100.0 * v / total for k, v in values.items()}


def rigor_mix(rigor_score: int, official_mix: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    """Return a transparent target mix for future assembly.

    Official blueprint composition wins when supplied.  Otherwise rigor 50 maps
    to 20/60/20; movement tightens or relaxes future selection, never question
    metadata or historical results.
    """
    if official_mix and any(_number(official_mix.get(k)) for k in ("easy_percent", "moderate_percent", "difficult_percent")):
        return normalize_mix(official_mix)
    score = max(0, min(100, int(rigor_score)))
    if score >= 50:
        t = (score - 50) / 50.0
        easy = 20 - 15 * t
        moderate = 60 - 15 * t
        difficult = 20 + 30 * t
    else:
        t = (50 - score) / 50.0
        easy = 20 + 25 * t
        moderate = 60 - 10 * t
        difficult = 20 - 15 * t
    return normalize_mix({"easy_percent": easy, "moderate_percent": moderate, "difficult_percent": difficult})


def allocate_counts(total: int, percentages: Mapping[str, float]) -> Dict[str, int]:
    total = max(0, int(total))
    raw = {k: total * float(percentages.get(k, 0.0)) / 100.0 for k in DIFFICULTY_ORDER}
    base = {k: int(math.floor(v)) for k, v in raw.items()}
    remaining = total - sum(base.values())
    for key in sorted(DIFFICULTY_ORDER, key=lambda k: (raw[k] - base[k]), reverse=True)[:remaining]:
        base[key] += 1
    return base


def compare_blueprints(old_payload: Optional[Mapping[str, Any]], new_payload: Mapping[str, Any]) -> Dict[str, Any]:
    old = normalize_blueprint_payload(old_payload or {}) if old_payload else None
    new = normalize_blueprint_payload(new_payload)
    changes: List[str] = []
    if not old:
        return {"changes": ["No currently active blueprint exists for this framework version."], "old": None, "new": new}
    if old["total_questions"] != new["total_questions"]:
        changes.append(f"Total questions: {old['total_questions']} → {new['total_questions']}.")
    if old["duration_minutes"] != new["duration_minutes"]:
        changes.append(f"Duration: {old['duration_minutes'] or 'unspecified'} → {new['duration_minutes'] or 'unspecified'} minutes.")
    old_rows = {x["subject"].casefold(): x for x in old["sections"]}
    new_rows = {x["subject"].casefold(): x for x in new["sections"]}
    for key in sorted(set(old_rows) | set(new_rows)):
        o, n = old_rows.get(key), new_rows.get(key)
        if o is None:
            changes.append(f"Subject added: {n['subject']} ({n['question_count']} questions, {n['weight_percent']}%).")
        elif n is None:
            changes.append(f"Subject removed: {o['subject']}.")
        else:
            if o["question_count"] != n["question_count"]:
                changes.append(f"{n['subject']} questions: {o['question_count']} → {n['question_count']}.")
            if abs(float(o["weight_percent"] or 0) - float(n["weight_percent"] or 0)) > 1e-9:
                changes.append(f"{n['subject']} weight: {o['weight_percent']}% → {n['weight_percent']}%.")
    if old.get("difficulty_distribution") != new.get("difficulty_distribution"):
        changes.append("Official difficulty composition changed.")
    if not changes:
        changes.append("No structural composition change detected; governance/version metadata differs only.")
    return {"changes": changes, "old": old, "new": new}


def confidence_label(answered: int, coverage_percent: float, calibrated_ratio: float = 0.0) -> Tuple[str, float]:
    answered = max(0, int(answered or 0))
    coverage_percent = max(0.0, min(100.0, float(coverage_percent or 0.0)))
    calibrated_ratio = max(0.0, min(1.0, float(calibrated_ratio or 0.0)))
    evidence = min(1.0, answered / 120.0)
    score = 0.55 * evidence + 0.30 * (coverage_percent / 100.0) + 0.15 * calibrated_ratio
    if score >= 0.72:
        return "High", score
    if score >= 0.42:
        return "Moderate", score
    return "Low", score
