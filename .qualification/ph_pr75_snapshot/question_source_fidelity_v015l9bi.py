from __future__ import annotations

"""Adaptive source-fidelity persistence for V015L9A first admission.

Reuse the existing question_source_fidelity_v015l1 table and lineage contract, but
consume the exact immutable raw rows already captured by the canonical adaptive
real-chapter admission. This avoids a second fixed-header workbook parser.

Explicit source-evidence text may be projected into the existing canonical source
locator field only when the source row itself supplies it. No source, curriculum,
ID hierarchy, marks, answers or academic truth is inferred.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import db

try:
    from powerhouse_operator import question_source_fidelity_v015l1 as _base
    from powerhouse_operator.question_import_fidelity_v1 import _index, _norm, _value
except ImportError:
    import question_source_fidelity_v015l1 as _base
    from question_import_fidelity_v1 import _index, _norm, _value

POLICY_VERSION = "PH-QUESTION-SOURCE-FIDELITY-015L9BI-ADAPTIVE-OPAQUE-ID-SCHEMA-TOLERANT"


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _first(row: list[Any], idx: dict[str, int], *names: str) -> str:
    return str(_value(row, idx, *names) or "").strip()


def persist_adaptive_source_fidelity(
    bank_path: str | Path,
    import_public_id: str,
    *,
    actor: str,
) -> dict[str, Any]:
    from real_chapter_gateway_v014r import real_chapter_import

    path = Path(bank_path)
    bundle = real_chapter_import(str(import_public_id))
    items = list(bundle.get("items") or [])
    imp = dict(bundle.get("import") or {})
    expected_sha = str(imp.get("file_sha256") or "").strip().lower()
    observed_sha = _sha_file(path).lower()
    if not expected_sha or observed_sha != expected_sha:
        raise ValueError("adaptive source fidelity is bound to different source workbook bytes")

    raw_rows: list[dict[str, Any]] = []
    headers: list[str] = []
    for item in items:
        decoded = json.loads(str(item.get("raw_record_json") or "{}"))
        raw = decoded.get("raw") if isinstance(decoded, dict) else None
        if not isinstance(raw, dict):
            raise ValueError("real-chapter item is missing immutable adaptive raw source row")
        row = {str(key): value for key, value in raw.items()}
        raw_rows.append(row)
        for key in row:
            if key not in headers:
                headers.append(key)

    idx = _index(headers)
    rows = [[row.get(header) for header in headers] for row in raw_rows]
    source_to_question = {
        str(item.get("source_question_id") or "").strip(): int(item["question_id"])
        for item in items
    }
    if len(source_to_question) != len(items) or any(not key for key in source_to_question):
        raise ValueError("adaptive source-fidelity import identity is incomplete or duplicated")

    by_source: dict[str, tuple[list[Any], dict[str, Any]]] = {}
    for row_values, row_dict in zip(rows, raw_rows):
        source_id = _first(row_values, idx, "Question_ID", "Question ID", "QuestionID", "Record ID", "Record_ID")
        if not source_id:
            continue
        if source_id in by_source:
            raise ValueError(f"duplicate opaque Question_ID in immutable source rows: {source_id}")
        by_source[source_id] = (row_values, row_dict)
    if set(by_source) != set(source_to_question):
        raise ValueError(
            "adaptive source-fidelity membership differs from governed import: "
            f"missing={len(set(source_to_question)-set(by_source))} "
            f"extra={len(set(by_source)-set(source_to_question))}"
        )

    _base.ensure_schema()
    header_sha = _stable_sha(headers)
    persisted: list[dict[str, Any]] = []
    explicit_source_alias_count = 0

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        for source_id, (row, row_dict) in by_source.items():
            question_id = source_to_question[source_id]
            qrow = conn.execute("SELECT public_id FROM questions WHERE id=?", (question_id,)).fetchone()
            if not qrow:
                raise ValueError(f"governed question missing for source ID {source_id}")
            public_id = str(qrow["public_id"] or "").strip()
            row_sha = _stable_sha({"headers": headers, "raw": row_dict})
            source_option_count = _base._source_option_count(row, idx)
            canonical_seed_id = _first(row, idx, "Canonical_Seed_ID", "Canonical Seed ID", "Seed_ID", "Seed ID")
            parent_question_id = _first(row, idx, "Parent_Question_ID", "Parent Question ID", "Parent_ID", "Parent ID")
            family_group_id = _first(row, idx, "Family_Group_ID", "Family Group ID", "Family_ID", "Family ID")
            dependency_group_id = _first(row, idx, "Dependency_Group_ID", "Dependency Group ID", "Dependency_ID", "Dependency ID")
            hierarchy_node_id = _first(row, idx, "Hierarchy_Node_ID", "Hierarchy Node ID", "Node_ID", "Node ID")
            explicit_source_locator = _first(
                row,
                idx,
                "Source_Locator",
                "Source Locator",
                "Source_Evidence",
                "Source Evidence",
                "Source_Reference",
                "Source Reference",
            )

            conn.execute(
                """INSERT INTO question_source_fidelity_v015l1(
                       question_id,question_public_id,source_question_id,canonical_seed_id,parent_question_id,
                       family_group_id,dependency_group_id,hierarchy_node_id,source_option_count,source_row_json,
                       source_row_checksum_sha256,source_workbook_sha256,source_header_checksum_sha256,
                       policy_version,created_by)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(question_id) DO UPDATE SET
                       question_public_id=excluded.question_public_id,
                       source_question_id=excluded.source_question_id,
                       canonical_seed_id=excluded.canonical_seed_id,
                       parent_question_id=excluded.parent_question_id,
                       family_group_id=excluded.family_group_id,
                       dependency_group_id=excluded.dependency_group_id,
                       hierarchy_node_id=excluded.hierarchy_node_id,
                       source_option_count=excluded.source_option_count,
                       source_row_json=excluded.source_row_json,
                       source_row_checksum_sha256=excluded.source_row_checksum_sha256,
                       source_workbook_sha256=excluded.source_workbook_sha256,
                       source_header_checksum_sha256=excluded.source_header_checksum_sha256,
                       policy_version=excluded.policy_version,
                       created_by=excluded.created_by,
                       updated_at=CURRENT_TIMESTAMP""",
                (
                    question_id,
                    public_id,
                    source_id,
                    canonical_seed_id,
                    parent_question_id,
                    family_group_id,
                    dependency_group_id,
                    hierarchy_node_id,
                    source_option_count,
                    json.dumps(row_dict, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str),
                    row_sha,
                    expected_sha,
                    header_sha,
                    POLICY_VERSION,
                    str(actor),
                ),
            )

            # Reuse the existing canonical binding surfaces. Only fill a missing locator
            # from explicit source text; never replace a governed non-empty locator.
            if explicit_source_locator:
                explicit_source_alias_count += 1
                _tables = {str(r[0]) for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "question_curriculum_bindings_v1" in _tables:
                    conn.execute(
                        """UPDATE question_curriculum_bindings_v1
                           SET source_locator=?
                           WHERE question_id=? AND COALESCE(TRIM(source_locator),'')=''""",
                        (explicit_source_locator, question_id),
                    )
                if "question_marking_contracts_v015d" in _tables:
                    conn.execute(
                        """UPDATE question_marking_contracts_v015d
                           SET source_locator=?
                           WHERE question_id=? AND COALESCE(TRIM(source_locator),'')=''""",
                        (explicit_source_locator, question_id),
                    )

            persisted.append({
                "question_id": question_id,
                "source_question_id": source_id,
                "canonical_seed_id": canonical_seed_id,
                "parent_question_id": parent_question_id,
                "family_group_id": family_group_id,
                "dependency_group_id": dependency_group_id,
                "hierarchy_node_id": hierarchy_node_id,
                "source_option_count": source_option_count,
                "source_row_checksum_sha256": row_sha,
                "explicit_source_locator_preserved": bool(explicit_source_locator),
            })
        conn.commit()

    receipt: dict[str, Any] = {
        "policy_version": POLICY_VERSION,
        "import_public_id": str(import_public_id),
        "source_workbook_sha256": expected_sha,
        "source_header_checksum_sha256": header_sha,
        "question_count": len(items),
        "source_fidelity_count": len(persisted),
        "explicit_source_locator_alias_count": explicit_source_alias_count,
        "opaque_identity_fields_inferred": False,
        "unknown_source_columns_preserved": True,
        "source_truth_inferred": False,
        "release_conferred": False,
        "opaque_source_id_aliases_supported": True,
        "optional_locator_targets_schema_tolerant": True,
        "population_sha256": _stable_sha(persisted),
    }
    receipt["receipt_sha256"] = _stable_sha(receipt)
    try:
        db.audit(
            str(actor),
            "QUESTION_SOURCE_FIDELITY_ADAPTIVE_PRESERVED_V015L9A",
            "REAL_CHAPTER_IMPORT",
            str(import_public_id),
            f"questions={len(items)}; source_aliases={explicit_source_alias_count}; receipt={receipt['receipt_sha256']}; release=false",
        )
    except Exception:
        pass
    return receipt


# PH-SOURCE-MARKING-EVIDENCE-1
# Preserve explicit SAQ source marking. This does not grade students or infer academic truth.
def source_marking_evidence(source_row: dict[str, Any], effective: dict[str, Any] | None = None) -> dict[str, Any]:
    import re
    from decimal import Decimal, InvalidOperation
    if not isinstance(source_row, dict) or (effective is not None and not isinstance(effective, dict)):
        raise ValueError("MARKING_SOURCE_OBJECT_REQUIRED")

    def norm(key):
        return re.sub(r"[^a-z0-9]", "", str(key).casefold())

    def number(raw):
        if isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
            raise ValueError("EXPLICIT_MARKS_INVALID")
        text = str(raw).strip()
        if not re.fullmatch(r"[0-9]{1,4}(?:\.[0-9]{1,3})?", text):
            raise ValueError("EXPLICIT_MARKS_INVALID")
        try:
            value = Decimal(text)
        except InvalidOperation as exc:
            raise ValueError("EXPLICIT_MARKS_INVALID") from exc
        if not value.is_finite() or not Decimal(0) < value <= Decimal(1000):
            raise ValueError("EXPLICIT_MARKS_INVALID")
        return value

    def allocated(text):
        if not isinstance(text, str):
            return []
        raw = text
        start = re.search(r"\bAward\s+", raw, re.I)
        pos = 0
        tail = raw
        matches = []
        mode = None
        if start:
            prefix = raw[:start.start()].rstrip()
            if re.search(r"(?:do\s+not|never|not|no)\s*$", prefix, re.I):
                return []
            pos = start.end()
            tail = raw[pos:]
            pattern = r"(?:^|[;,]\s*(?:and\s+)?|\s+and\s+)([0-9]{1,4}(?:\.[0-9]{1,3})?)\s*(?:marks?\s+)?for\s+"
            matches = list(re.finditer(pattern, tail, re.I))
            mode = "for"
        else:
            head = re.match(r"\s*[0-9]{1,4}(?:\.[0-9]{1,3})?\s+marks?\s*:\s*", raw, re.I)
            if head:
                candidate = raw[head.end():]
                pattern = r"(?:^|[;,]\s*(?:and\s+)?|\s+and\s+)([0-9]{1,4}(?:\.[0-9]{1,3})?)\s*(?:marks?\s+)?for\s+"
                cm = list(re.finditer(pattern, candidate, re.I))
                if cm and cm[0].start() == 0:
                    pos = head.end()
                    tail = candidate
                    matches = cm
                    mode = "for"
            if not matches:
                pattern = r"(?:^|(?<=[.;])\s+|(?<=;)\s*)([0-9]{1,4}(?:\.[0-9]{1,3})?)\s*marks?\s*(?::|=|[-–—])\s*"
                matches = list(re.finditer(pattern, raw, re.I))
                mode = "label"
        if not matches or matches[0].start() != 0:
            return []
        result = []
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(tail)
            desc = tail[match.end():end].strip().rstrip(".;").strip()
            if not desc or len(desc) > 5000:
                return []
            if re.search(r"\b[0-9]+(?:\.[0-9]+)?\s+marks?\s*(?::|=|[-–—]|\bfor\b)", desc, re.I):
                return []
            lo = pos + match.end()
            hi = pos + end
            result.append({
                "id": f"p{i+1}",
                "description": desc,
                "marks": float(number(match[1])),
                "source_start": lo,
                "source_end": hi,
                "source_quote": raw[lo:hi],
                "allocation_syntax": mode,
            })
        return result

    numeric = {"maximummarks", "maxmarks", "marks", "totalmarks", "maxscore"}
    rules = {"scoringrule", "scoringconstruct", "markscheme", "markingscheme", "scoringinstructions", "markinginstructions"}
    explanations = {"explanation", "explanationmarkingrubric", "markingrubric", "rubric"}
    literal = []
    totals = []
    allocations = []
    for origin, obj in (("source", source_row), ("effective", effective or {})):
        for field, raw in obj.items():
            key = norm(field)
            if key not in numeric | rules | explanations or raw in (None, ""):
                continue
            if key in numeric:
                value = number(raw)
                totals.append((origin, field, value))
                literal.append({"origin": origin, "field": field, "value": raw})
                continue
            if not isinstance(raw, str):
                continue
            if len(raw) > 30000:
                raise ValueError("MARKING_SOURCE_TEXT_LIMIT")
            literal.append({"origin": origin, "field": field, "value": raw})
            points = allocated(raw)
            if key in rules:
                head = re.match(r"\s*([0-9]{1,4}(?:\.[0-9]{1,3})?)\s+marks?\b", raw, re.I)
                repeated = bool(points and len(points) > 1 and points[0].get("allocation_syntax") == "label")
                if head and not repeated:
                    totals.append((origin, field, number(head[1])))
            if points:
                total = sum((number(point["marks"]) for point in points), Decimal(0))
                totals.append((origin, field, total))
                allocations.append((origin, field, points))
    unique = {value for _, _, value in totals}
    if len(unique) > 1:
        raise ValueError("SOURCE_MARK_TOTAL_CONFLICT")
    maximum = float(next(iter(unique))) if unique else None
    point_sets = {tuple((p["description"], p["marks"]) for p in a[2]) for a in allocations}
    if len(point_sets) > 1:
        raise ValueError("SOURCE_MARK_CRITERIA_CONFLICT")
    selected = allocations[0] if allocations else None
    points = [dict(point, source_origin=selected[0], source_field=selected[1]) for point in selected[2]] if selected else []
    body = {
        "version": "PH-SOURCE-MARKING-GUIDANCE-1",
        "maximum_marks": maximum,
        "required_mark_points": points,
        "literal_sources": literal,
        "status": "SOURCE_ALLOCATION_RESOLVED" if maximum is not None else "SOURCE_ALLOCATION_UNRESOLVED",
        "automatic_marking_qualified": False,
        "academic_approval_conferred": False,
    }
    body["evidence_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return body


def _explicit_saq_contract_from_source(source_row: dict[str, Any], effective: dict[str, Any] | None, evidence: dict[str, Any]) -> dict[str, Any]:
    import re
    from copy import deepcopy

    def norm(key):
        return re.sub(r"[^a-z0-9]", "", str(key).casefold())

    def lookup(obj, *names):
        if not isinstance(obj, dict):
            return None
        idx = {norm(k): v for k, v in obj.items()}
        for name in names:
            value = idx.get(norm(name))
            if value not in (None, ""):
                return value
        return None

    def stable(obj):
        return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    structured = None
    for obj in (effective or {}, source_row):
        raw = lookup(obj, "SAQ_Scoring_Contract_JSON", "SAQ Scoring Contract JSON",
                     "Marking_Contract_JSON", "Marking Contract JSON",
                     "Scoring_Contract_JSON", "Scoring Contract JSON", "SAQ_Scoring_Contract")
        if raw in (None, ""):
            continue
        if isinstance(raw, dict):
            candidate = deepcopy(raw)
        elif isinstance(raw, str):
            try:
                candidate = json.loads(raw)
            except Exception as exc:
                raise ValueError("SAQ_STRUCTURED_CONTRACT_JSON_INVALID") from exc
        else:
            raise ValueError("SAQ_STRUCTURED_CONTRACT_INVALID")
        if not isinstance(candidate, dict):
            raise ValueError("SAQ_STRUCTURED_CONTRACT_INVALID")
        structured = candidate
        break

    maximum = evidence.get("maximum_marks")
    points = evidence.get("required_mark_points") or []
    if maximum is None:
        raise ValueError("SOURCE_MARK_ALLOCATION_REQUIRED")

    if structured is not None:
        if structured.get("version") not in (None, "PH-SAQ-SCORING-CONTRACT-1"):
            raise ValueError("SAQ_STRUCTURED_CONTRACT_VERSION_UNSUPPORTED")
        structured["version"] = "PH-SAQ-SCORING-CONTRACT-1"
        try:
            if float(structured.get("maximum_marks")) != float(maximum):
                raise ValueError("SAQ_STRUCTURED_CONTRACT_TOTAL_CONFLICT")
        except (TypeError, ValueError, OverflowError):
            raise ValueError("SAQ_STRUCTURED_CONTRACT_TOTAL_CONFLICT")
        spts = structured.get("required_mark_points")
        if not isinstance(spts, list) or not spts:
            raise ValueError("SAQ_STRUCTURED_MARK_POINTS_REQUIRED")
        try:
            total = sum(float(point["marks"]) for point in spts if isinstance(point, dict))
        except Exception as exc:
            raise ValueError("SAQ_STRUCTURED_MARK_POINT_INVALID") from exc
        if len(spts) != sum(1 for point in spts if isinstance(point, dict)) or abs(total - float(maximum)) > 1e-9:
            raise ValueError("SAQ_STRUCTURED_CONTRACT_TOTAL_CONFLICT")
        structured.pop("contract_sha256", None)
        structured["contract_sha256"] = stable(structured)
        return structured

    canonical_points = []
    for i, point in enumerate(points, 1):
        if not isinstance(point, dict):
            raise ValueError("SOURCE_MARK_POINT_INVALID")
        canonical_points.append({
            "id": str(point.get("id") or f"MP{i}"),
            "description": str(point.get("description") or "").strip(),
            "marks": point.get("marks"),
            "accepted_expressions": [],
            "accepted_synonyms": [],
            "contradictions": [],
            "source_origin": point.get("source_origin"),
            "source_field": point.get("source_field"),
            "source_start": point.get("source_start"),
            "source_end": point.get("source_end"),
        })
    body = {
        "version": "PH-SAQ-SCORING-CONTRACT-1",
        "maximum_marks": maximum,
        "auto_marking_eligibility": "RUBRIC_SEMANTICALLY_SCORABLE",
        "scoring_type": "SEMANTIC_MARK_POINT",
        "required_mark_points": canonical_points,
        "source_marking_evidence_sha256": evidence.get("evidence_sha256"),
        "academic_approval_conferred": False,
    }
    body["contract_sha256"] = stable(body)
    return body


def canonicalize_source_marking(material: dict[str, Any], source_row: dict[str, Any], effective: dict[str, Any] | None = None) -> bool:
    from copy import deepcopy
    if not isinstance(material, dict) or not isinstance(material.get("content"), dict):
        raise ValueError("QUESTION_MATERIAL_REQUIRED")
    content = material["content"]
    forms = {"SHORT_RESPONSE", "SHORT_CONSTRUCTED_RESPONSE", "CONSTRUCTED_RESPONSE",
             "EXTENDED_RESPONSE", "SAQ", "SHORT_ANSWER", "LONG_ANSWER"}
    fmt = lambda value: str(value or "").strip().upper().replace(" ", "_").replace("-", "_")
    if fmt(content.get("question_family_type")) not in forms and fmt(content.get("exam_question_type")) not in forms:
        return False
    evidence = source_marking_evidence(source_row, effective)
    if evidence["maximum_marks"] is None:
        raise ValueError("SOURCE_MARK_ALLOCATION_REQUIRED")
    marking = deepcopy(content.get("marking"))
    if not isinstance(marking, dict):
        raise ValueError("CANONICAL_MARKING_OBJECT_REQUIRED")
    rubric = marking.get("rubric")
    if rubric is not None and (not isinstance(rubric, dict) or not rubric):
        raise ValueError("CANONICAL_RUBRIC_INVALID")
    if rubric:
        rmax = rubric.get("maximum_marks")
        weights = rubric.get("required_mark_points")
        if isinstance(weights, list) and weights:
            from decimal import Decimal, InvalidOperation
            try:
                if any(not isinstance(point, dict) or isinstance(point.get("marks"), bool) for point in weights):
                    raise ValueError()
                values = [Decimal(str(point["marks"])) for point in weights]
                if any(not value.is_finite() or value <= 0 for value in values):
                    raise ValueError()
                total = sum(values, Decimal(0))
            except (TypeError, KeyError, ValueError, InvalidOperation) as exc:
                raise ValueError("CANONICAL_RUBRIC_WEIGHT_INVALID") from exc
            if total != Decimal(str(evidence["maximum_marks"])):
                raise ValueError("CANONICAL_RUBRIC_TOTAL_CONFLICT")
        if rmax is not None and (isinstance(rmax, bool) or float(rmax) != evidence["maximum_marks"]):
            raise ValueError("CANONICAL_RUBRIC_TOTAL_CONFLICT")
    else:
        rubric = _explicit_saq_contract_from_source(source_row, effective, evidence)
    marking.update(marks=evidence["maximum_marks"], key_type="RUBRIC_ONLY", rubric=rubric)
    content["marking"] = marking
    return True


def prepare_source_local_rubric(guidance, stem, model_answer):
    return None
