"""ScoreMax V6.2 pilot-readiness and Power House transport helpers.

This module deliberately contains no Flask dependencies.  It can be tested in
isolation and keeps Power House authority separate from ScoreMax delivery.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

PROMPT_ELIGIBLE_STATUSES = {
    "APPROVED_FOR_MANUAL_GENERATION",
    "APPROVED_EXPORTABLE",
    "APPROVED_ACTIVE",
}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_checksum(value: Any, checksum_field: str = "checksum") -> str:
    payload = json.loads(json.dumps(value))
    if isinstance(payload, dict):
        payload.pop(checksum_field, None)
        payload.pop("signature", None)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def safe_filename(value: str, fallback: str = "scoremax") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip("-.")
    return cleaned[:120] or fallback


def prompt_pack_signature(payload: Any, shared_secret: str) -> str:
    body=json.loads(json.dumps(payload))
    if isinstance(body,dict):
        body.pop("signature",None)
    return hmac.new(str(shared_secret).encode("utf-8"),canonical_json(body).encode("utf-8"),hashlib.sha256).hexdigest()


def validate_prompt_pack(payload: Any, shared_secret: str = "", require_signature: bool = False) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(payload, dict):
        return {"valid": False, "errors": ["Prompt pack must be a JSON object."], "warnings": [], "checksum": ""}

    def text(key: str) -> str:
        return str(payload.get(key, "") or "").strip()

    required = ["prompt_pack_id", "prompt_pack_version", "framework", "subject", "chapter", "prompt_text"]
    for key in required:
        if not text(key):
            errors.append(f"Missing {key}.")
    status = text("status").upper()
    if status not in PROMPT_ELIGIBLE_STATUSES:
        errors.append("Power House prompt pack is not approved for manual generation.")
    if len(text("prompt_text")) < 200:
        warnings.append("Prompt text is unusually short; verify that the full provider-neutral pack was exported.")
    evidence = payload.get("source_evidence_ids", [])
    if not isinstance(evidence, list) or not evidence:
        errors.append("At least one Power House source evidence ID is required.")
    learning_outcomes = payload.get("learning_outcome_ids", [])
    if not isinstance(learning_outcomes, list) or not learning_outcomes:
        errors.append("At least one learning-outcome ID is required.")
    expected = payload.get("expected_output_schema", {})
    if not isinstance(expected, dict) or not expected:
        errors.append("A non-empty expected_output_schema object is required.")
    calculated = payload_checksum(payload)
    supplied = text("checksum").lower()
    checksum_status = "NOT_SUPPLIED"
    if not supplied:
        errors.append("Prompt pack checksum is required.")
    else:
        checksum_status = "VERIFIED" if supplied == calculated else "MISMATCH"
        if checksum_status == "MISMATCH":
            errors.append("Prompt pack checksum does not match its immutable payload.")
    signature_status="NOT_SUPPLIED"
    signature=text("signature").lower()
    if signature:
        if not shared_secret:
            signature_status="UNVERIFIED_NO_SECRET"
            if require_signature: errors.append("Prompt pack signature cannot be verified because no shared secret is configured.")
        else:
            expected_signature=prompt_pack_signature(payload,shared_secret)
            signature_status="VERIFIED" if hmac.compare_digest(signature,expected_signature) else "MISMATCH"
            if signature_status=="MISMATCH": errors.append("Prompt pack signature is invalid.")
    elif require_signature:
        errors.append("A signed Power House prompt pack is required in this environment.")
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "checksum": calculated,
        "checksum_status": checksum_status,
        "signature_status": signature_status,
        "prompt_pack_id": text("prompt_pack_id"),
        "prompt_pack_version": text("prompt_pack_version"),
    }


def parse_generation_output(raw: str, prompt_pack: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        return {"valid": False, "errors": [f"Output is not valid JSON: {exc}"], "warnings": [], "parsed": None, "item_count": 0}
    items = parsed.get("questions") if isinstance(parsed, dict) else parsed
    if not isinstance(items, list):
        errors.append("Generated output must be a JSON list or contain a questions list.")
        items = []
    if not items:
        errors.append("Generated output contains no questions.")
    seen = set()
    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            errors.append(f"Item {idx} is not an object.")
            continue
        qid = str(item.get("question_id") or item.get("Question ID") or "").strip()
        if not qid:
            warnings.append(f"Item {idx} has no question ID; Power House must assign or validate one.")
        elif qid in seen:
            errors.append(f"Duplicate question ID in output: {qid}.")
        seen.add(qid)
        if not str(item.get("question") or item.get("Question") or "").strip():
            errors.append(f"Item {idx} has no question text.")
    if isinstance(parsed, dict):
        source_id = str(parsed.get("prompt_pack_id", "") or "").strip()
        source_version = str(parsed.get("prompt_pack_version", "") or "").strip()
        if source_id and source_id != str(prompt_pack.get("prompt_pack_id", "")):
            errors.append("Generated output references a different prompt pack ID.")
        if source_version and source_version != str(prompt_pack.get("prompt_pack_version", "")):
            errors.append("Generated output references a different prompt pack version.")
        if not source_id:
            warnings.append("Generated output does not repeat the prompt pack ID; ScoreMax will preserve the linkage in its transport wrapper.")
    return {"valid": not errors, "errors": errors, "warnings": warnings, "parsed": parsed, "item_count": len(items)}


def generation_transport(prompt_pack: Dict[str, Any], batch: Dict[str, Any], parsed_output: Any) -> Dict[str, Any]:
    payload = {
        "schema_version": "1.0",
        "transport_type": "MANUAL_AI_GENERATION_RETURN",
        "source_system": "ScoreMax",
        "destination_system": "Power House",
        "prompt_pack_id": prompt_pack.get("prompt_pack_id", ""),
        "prompt_pack_version": prompt_pack.get("prompt_pack_version", ""),
        "provider": batch.get("provider", ""),
        "model": batch.get("model", ""),
        "provider_run_id": batch.get("provider_run_id", ""),
        "generated_at": batch.get("created_at", ""),
        "submitted_by_scoremax_user_id": batch.get("submitted_by"),
        "output": parsed_output,
        "governance_note": "Candidate output only. Power House validation, independent review and academic approval are required before ScoreMax delivery.",
    }
    payload["checksum"] = payload_checksum(payload)
    return payload


def sqlite_backup(source_db: Path, destination: Path) -> Tuple[bool, str]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        src = sqlite3.connect(str(source_db), timeout=10)
        dst = sqlite3.connect(str(destination), timeout=10)
        with dst:
            src.backup(dst)
        integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        dst.close(); src.close()
        if integrity != "ok":
            return False, f"Backup integrity check returned {integrity}."
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def feedback_route(category: str) -> str:
    value = str(category or "").strip().lower()
    if value in {"incorrect question", "wrong answer", "unclear wording", "explanation problem", "difficulty mismatch", "curriculum mapping"}:
        return "POWER_HOUSE"
    if value in {"technical failure", "display problem", "login/account", "upload failure", "messaging/safety"}:
        return "SCOREMAX"
    return "JOINT_REVIEW"


def readiness_status(required: int, usable: int, family_count: int, target_forms: int = 3) -> str:
    required = max(0, int(required or 0)); usable = max(0, int(usable or 0)); family_count = max(0, int(family_count or 0))
    if required <= 0:
        return "NOT_APPLICABLE"
    if usable < required:
        return "BLOCKED"
    safe_forms = min(usable // required, family_count // max(1, required // 2)) if family_count else 0
    return "READY" if safe_forms >= int(target_forms or 3) else "THIN"


def utc_stamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
