from __future__ import annotations

import base64
import json
import os
import re
import textwrap
import time
import urllib.request
from hashlib import sha256
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.run_semantic_qa_seeded_visual_diagnostic_v2_1 import (
    _original_reviewer,
    _original_student,
    _student_complete_evidence,
)

HARNESS_VERSION = "PH_SEMANTIC_QA_Q25_TWELVE_CASE_V2_9"
POPULATION_SALT = "PH-QA-EIGHT-Q25-V2.6|"
AGENT = os.environ["SEMANTIC_QA_AGENT_ID"].strip()
MODEL = os.environ.get("SEMANTIC_QA_MODEL", "qwen2.5vl:3b").strip()
OLLAMA = os.environ.get("SEMANTIC_QA_OLLAMA_BASE", "http://127.0.0.1:11434").rstrip("/")
PROMPTS = Path(os.environ.get("SEMANTIC_QA_PROMPT_FILE", "config/semantic_qa_agent_prompts_v2.json"))
OUT = Path(os.environ.get("SEMANTIC_QA_DIAGNOSTIC_DIR", "/tmp/semantic-qa-twelve-qwen25vl-v2-9"))
OUT.mkdir(parents=True, exist_ok=True)

STUDENT_IDS = (
    "S-C02", "S-C04", "S-C06", "S-C08", "S-C09", "S-C10",
    "S-D01", "S-D02", "S-D03", "S-D04", "S-D06", "S-D08",
)
REVIEWER_IDS = (
    "R-C02", "R-C04", "R-C05", "R-C06", "R-C08", "R-C10",
    "R-D01", "R-D02", "R-D03", "R-D04", "R-D06", "R-D07",
)


class PredictionFormatError(RuntimeError):
    pass


def opaque_id(original_id: str) -> str:
    return "QAX-" + sha256((POPULATION_SALT + original_id).encode()).hexdigest()[:12].upper()


def cases():
    rows = _student_complete_evidence(_original_student()) if AGENT.startswith("STUDENT_") else _original_reviewer()
    wanted = STUDENT_IDS if AGENT.startswith("STUDENT_") else REVIEWER_IDS
    by_id = {x.case_id: x for x in rows}
    selected = []
    for original in wanted:
        c = by_id[original]
        selected.append(type(c)(opaque_id(original), c.expected, c.severity, c.category, c.lines))
    selected = sorted(selected, key=lambda x: sha256((AGENT + "|" + x.case_id).encode()).hexdigest())
    assert len(selected) == 12
    assert sum(x.expected == "CLEAN" for x in selected) == 6
    assert sum(x.expected == "DEFECT" for x in selected) == 6
    return selected


def font(size=26, bold=False):
    path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def render(case):
    width, height = 1024, 800
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((18, 18, width - 18, height - 18), outline="black", width=2)
    draw.text((38, 38), f"Question QA ID: {case.case_id}", fill="black", font=font(29, True))
    y = 92
    for raw in case.lines:
        for line in textwrap.wrap(str(raw), width=61) or [""]:
            draw.text((45, y), line, fill="black", font=font())
            y += 37
            if y > 720:
                raise RuntimeError(f"case {case.case_id} overflow")
        y += 4
    draw.text((45, 758), "Inspect only what is visibly shown.", fill="black", font=font(18))
    path = OUT / f"{AGENT}_{case.case_id}.png"
    image.save(path, optimize=True)
    return path


def norm(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def validate_prediction(raw, case):
    required = {"case_id", "decision", "confidence", "category", "visible_anchor"}
    if not isinstance(raw, dict):
        raise PredictionFormatError("prediction must be one JSON object")
    if set(raw) != required:
        raise PredictionFormatError(f"prediction keys must be exactly {sorted(required)}")
    if str(raw.get("case_id") or "") != case.case_id:
        raise PredictionFormatError("case identity mismatch")
    try:
        confidence = float(raw.get("confidence"))
    except Exception as exc:
        raise PredictionFormatError("confidence is not numeric") from exc
    decision = str(raw.get("decision") or "").upper()
    category = str(raw.get("category") or "").strip()
    anchor = str(raw.get("visible_anchor") or "").strip()
    if decision not in {"ACCEPT", "FLAG", "UNCERTAIN"}:
        raise PredictionFormatError(f"invalid decision {decision}")
    if not 0 <= confidence <= 1:
        raise PredictionFormatError("confidence outside 0..1")
    if not category or not anchor:
        raise PredictionFormatError("category and visible_anchor are required")
    if decision == "ACCEPT" and category.upper() != "CLEAN":
        raise RuntimeError("ACCEPT must use category CLEAN")
    if decision in {"FLAG", "UNCERTAIN"} and category.upper() == "CLEAN":
        raise RuntimeError(f"{decision} may not use category CLEAN")
    visible = norm(" ".join(map(str, case.lines)))
    if norm(anchor) not in visible:
        raise RuntimeError(f"anchor not visible: {anchor!r}")
    return {
        "decision": decision,
        "confidence": confidence,
        "category": category,
        "visible_anchor": anchor,
    }


def _ollama(payload):
    req = urllib.request.Request(
        OLLAMA + "/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        return json.loads(response.read())


def call(prompt, case, image_path):
    image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    user = (
        f"Evaluate this rendered QA page independently. The only valid case_id is {case.case_id}. "
        "Return exactly one JSON object with exactly these keys: case_id, decision, confidence, category, visible_anchor. "
        "decision must be ACCEPT, FLAG, or UNCERTAIN. Use category CLEAN if and only if decision is ACCEPT. "
        "For FLAG or UNCERTAIN, category must name the concrete defect or evidence insufficiency and must not be CLEAN. "
        "Before ACCEPT on a single-select question, test every visible answer option and confirm exactly one is materially defensible under ordinary accepted syllabus/textbook interpretation. "
        "Do not invent obscure edge cases merely to manufacture ambiguity. "
        "For reviewer pages, independently solve the learner task before comparing the displayed key and rubric. "
        "A correct key, rubric or explanation is never, by itself, evidence of a defect. "
        "visible_anchor must be copied verbatim from visible question/options/context/selected response/feedback/key/rubric; do not use the QA header/footer as evidence. "
        "Use only visible evidence. Do not explain outside JSON."
    )
    seed = int(sha256((AGENT + "|" + case.case_id).encode()).hexdigest()[:8], 16) % 2147483647
    payload = {
        "model": MODEL,
        "stream": False,
        "format": "json",
        "keep_alive": "30m",
        "options": {"temperature": 0, "seed": seed, "num_predict": 180, "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user, "images": [image_b64]},
        ],
    }
    started = time.time()
    data = _ollama(payload)
    elapsed = round(time.time() - started, 3)
    content = str((data.get("message") or {}).get("content") or "").strip()
    if not content:
        raise RuntimeError("EMPTY_FINAL_CONTENT")
    try:
        parsed = json.loads(content)
        return validate_prediction(parsed, case), elapsed, False
    except (json.JSONDecodeError, PredictionFormatError) as first_exc:
        repair_user = (
            f"FORMAT REPAIR ONLY for case {case.case_id}. Do not reconsider the semantic judgment. "
            "Rewrite your immediately previous answer as exactly one JSON object with exactly these keys: "
            "case_id, decision, confidence, category, visible_anchor. Preserve the same judgment and evidence. "
            f"Your previous output was: {content}"
        )
        repair_payload = {
            "model": MODEL,
            "stream": False,
            "format": "json",
            "keep_alive": "30m",
            "options": {"temperature": 0, "seed": seed, "num_predict": 120, "num_ctx": 4096},
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": repair_user},
            ],
        }
        repair_started = time.time()
        repaired_data = _ollama(repair_payload)
        elapsed += round(time.time() - repair_started, 3)
        repaired_content = str((repaired_data.get("message") or {}).get("content") or "").strip()
        if not repaired_content:
            raise RuntimeError(f"FORMAT_REPAIR_EMPTY after {type(first_exc).__name__}")
        repaired = json.loads(repaired_content)
        prediction = validate_prediction(repaired, case)
        try:
            initial_obj = json.loads(content)
        except Exception:
            initial_obj = {}
        initial_decision = str(initial_obj.get("decision") or "").upper()
        if initial_decision and initial_decision in {"ACCEPT", "FLAG", "UNCERTAIN"} and prediction["decision"] != initial_decision:
            raise RuntimeError("format repair changed semantic decision")
        return prediction, round(elapsed, 3), True


def main():
    prompt_doc = json.loads(PROMPTS.read_text(encoding="utf-8"))
    prompt_version = str(prompt_doc.get("version") or "")
    prompt = str(prompt_doc["agents"][AGENT]["prompt"])
    rows = cases()
    population_identity = sha256(
        json.dumps(
            [{"id": c.case_id, "expected": c.expected, "severity": c.severity, "category": c.category, "lines": c.lines} for c in rows],
            sort_keys=True,
            ensure_ascii=False,
            default=list,
        ).encode()
    ).hexdigest()
    predictions = {}
    timings = []
    repairs = []
    for position, case in enumerate(rows, 1):
        started = time.time()
        try:
            prediction, elapsed, repaired = call(prompt, case, render(case))
        except Exception as exc:
            elapsed = round(time.time() - started, 3)
            repaired = False
            prediction = {
                "decision": "SYSTEM_ERROR",
                "confidence": 0.0,
                "category": "SYSTEM_ERROR",
                "visible_anchor": "",
                "error": f"{type(exc).__name__}:{exc}",
            }
        predictions[case.case_id] = prediction
        timings.append(elapsed)
        if repaired:
            repairs.append(case.case_id)
        print(
            "SEMANTIC_QA_Q25_TWELVE_CASE "
            + json.dumps(
                {
                    "agent": AGENT,
                    "position": position,
                    "case_id": case.case_id,
                    "decision": prediction["decision"],
                    "format_repair_used": repaired,
                    "elapsed_seconds": elapsed,
                },
                sort_keys=True,
            ),
            flush=True,
        )

    clean = [c for c in rows if c.expected == "CLEAN"]
    defects = [c for c in rows if c.expected == "DEFECT"]
    critical = [c for c in defects if c.severity == "CRITICAL"]
    true_positive = [c for c in defects if predictions[c.case_id]["decision"] == "FLAG"]
    false_positive = [c for c in clean if predictions[c.case_id]["decision"] == "FLAG"]
    critical_miss = [c for c in critical if predictions[c.case_id]["decision"] != "FLAG"]
    high_confidence_fn = [
        c for c in defects
        if predictions[c.case_id]["decision"] == "ACCEPT" and predictions[c.case_id]["confidence"] >= 0.9
    ]
    system_error = [c for c in rows if predictions[c.case_id]["decision"] == "SYSTEM_ERROR"]
    uncertain = [c for c in rows if predictions[c.case_id]["decision"] == "UNCERTAIN"]

    semantic_pass = (
        not system_error
        and not uncertain
        and not critical_miss
        and len(true_positive) == 6
        and not false_positive
        and not high_confidence_fn
    )
    reliability_pass = not repairs and not system_error
    result = {
        "schema": HARNESS_VERSION,
        "harness_version": HARNESS_VERSION,
        "prompt_manifest_version": prompt_version,
        "agent": AGENT,
        "model": MODEL,
        "cases": 12,
        "clean_cases": 6,
        "defect_cases": 6,
        "population_identity_sha256": population_identity,
        "defect_recall": round(len(true_positive) / 6, 4),
        "clean_false_positive_rate": round(len(false_positive) / 6, 4),
        "critical_misses": len(critical_miss),
        "missed_defects": [c.case_id for c in defects if c not in true_positive],
        "false_positives": [c.case_id for c in false_positive],
        "uncertain_cases": [c.case_id for c in uncertain],
        "system_errors": len(system_error),
        "format_repair_count": len(repairs),
        "format_repair_cases": repairs,
        "high_confidence_false_negatives": len(high_confidence_fn),
        "total_inference_seconds": round(sum(timings), 3),
        "mean_inference_seconds": round(sum(timings) / len(timings), 3),
        "predictions": predictions,
        "semantic_diagnostic_pass": semantic_pass,
        "reliability_pass": reliability_pass,
        "diagnostic_pass": semantic_pass and reliability_pass,
        "qualification_conferred": False,
        "release_authority": False,
    }
    print("SEMANTIC_QA_Q25_TWELVE_FINAL " + json.dumps(result, sort_keys=True), flush=True)
    (OUT / f"{AGENT}_result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    if not result["diagnostic_pass"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
