"""ScoreMax V6 written-response package validation and deterministic pilot marker.

Power House owns the immutable academic package. This module validates transport
and produces transparent pilot evidence. It is not a claim of validated high-stakes
AI marking; external grader/OCR adapters can replace the local heuristic through the
same versioned result contract.
"""
from __future__ import annotations
import hashlib, hmac, json, re
from copy import deepcopy

STOP={"the","a","an","and","or","of","to","in","on","is","are","was","were","be","been","with","for","that","this","it","as","by","from","at","into","than"}
CAUSAL={"because","therefore","thus","so","causes","causing","leads","result","results","due","consequently"}


def canonical_json(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)


def package_checksum(payload):
    clean=deepcopy(payload)
    clean.pop("export_checksum",None); clean.pop("signature",None)
    return hashlib.sha256(canonical_json(clean).encode("utf-8")).hexdigest()


def package_signature(payload, secret):
    clean=deepcopy(payload)
    clean.pop("signature",None)
    return hmac.new(str(secret).encode("utf-8"),canonical_json(clean).encode("utf-8"),hashlib.sha256).hexdigest()


def validate_assessment_package(payload, shared_secret='', require_signature=False):
    errors=[]; warnings=[]
    if not isinstance(payload,dict): return {"valid":False,"errors":["Payload must be a JSON object."],"warnings":[]}
    for key in ("assessment_package_id","assessment_package_version","framework_id","framework_version_id","subject_id","chapter_id","academic_approval_status"):
        if payload.get(key) in (None,""): errors.append(f"Missing {key}.")
    if str(payload.get("academic_approval_status","")).upper() not in {"APPROVED","APPROVED_EXPORTABLE","APPROVED_ACTIVE"}:
        errors.append("Only an approved Power House package can be imported.")
    questions=payload.get("questions") or []
    if not isinstance(questions,list) or not questions: errors.append("At least one approved written question is required.")
    ids=set()
    for i,q in enumerate(questions,1):
        if not isinstance(q,dict): errors.append(f"Question {i} is not an object."); continue
        for key in ("question_id","question_family_id","question_type","question_text","command_verb","maximum_marks","required_mark_points"):
            if q.get(key) in (None,"",[]): errors.append(f"Question {i}: missing {key}.")
        qid=str(q.get("question_id","")).strip()
        if qid in ids: errors.append(f"Duplicate question_id: {qid}.")
        ids.add(qid)
        try:
            if float(q.get("maximum_marks",0))<=0: errors.append(f"Question {qid}: maximum_marks must be positive.")
        except Exception: errors.append(f"Question {qid}: maximum_marks must be numeric.")
        points=q.get("required_mark_points") or []
        if isinstance(points,list):
            mark_total=0.0
            for n,pt in enumerate(points,1):
                if not isinstance(pt,dict): errors.append(f"Question {qid}: mark point {n} is invalid."); continue
                if not pt.get("id") or not pt.get("description"): errors.append(f"Question {qid}: mark point {n} needs id and description.")
                try: mark_total+=float(pt.get("marks",1))
                except Exception: errors.append(f"Question {qid}: mark point {n} marks invalid.")
            try:
                if mark_total>float(q.get("maximum_marks",0))+0.001: errors.append(f"Question {qid}: mark points exceed maximum marks.")
            except Exception: pass
        else: errors.append(f"Question {qid}: required_mark_points must be a list.")
    supplied=str(payload.get("export_checksum","")).strip()
    calculated=package_checksum(payload)
    if supplied and supplied!=calculated: errors.append("Package checksum mismatch.")
    if not supplied: warnings.append("No export checksum supplied; production import should require it.")
    signature=str(payload.get("signature","")).strip()
    signature_status="NOT_CONFIGURED"
    if shared_secret:
        signature_status="VERIFIED" if signature and hmac.compare_digest(signature,package_signature(payload,shared_secret)) else "FAILED"
        if signature_status=="FAILED": errors.append("Package signature verification failed.")
    elif require_signature:
        signature_status="REQUIRED_MISSING"; errors.append("A signed Power House package is required in this environment.")
    elif not signature:
        warnings.append("Package signature not configured; acceptable only for controlled local testing.")
    return {"valid":not errors,"errors":errors,"warnings":warnings,"checksum":calculated,"signature_status":signature_status,"question_count":len(questions)}


def _tokens(text):
    return [x for x in re.findall(r"[a-z0-9]+",str(text or "").lower()) if len(x)>2 and x not in STOP]


def _sentences(text):
    return [s.strip() for s in re.split(r"[.!?;\n]+",str(text or "")) if s.strip()]


def _norm_phrase(value):
    return re.sub(r"[^a-z0-9]+"," ",str(value or "").lower()).strip()

def _phrase_present(answer, phrases):
    low=" "+_norm_phrase(answer)+" "
    return any((" "+_norm_phrase(p)+" ") in low for p in phrases if _norm_phrase(p))


def _point_evidence(answer, point, strategy="A"):
    terms=point.get("required_terms") or []
    alternatives=point.get("acceptable_paraphrases") or []
    phrases=point.get("accepted_phrases") or []
    answer_tokens=set(_tokens(answer)); target=set(_tokens(" ".join([point.get("description","")]+terms+alternatives+phrases)))
    overlap=len(answer_tokens & target)/max(1,len(target))
    exact=_phrase_present(answer,phrases+alternatives)
    causal_required=bool(point.get("causal_link_required"))
    raw_low=" "+_norm_phrase(answer)+" "
    causal_ok=not causal_required or bool(answer_tokens & CAUSAL) or any((" "+x+" ") in raw_low for x in ("so","because","therefore","thus","causes","causing","leads to","results in","due to"))
    # Strategy B is deliberately more conservative and sentence-local.
    if strategy=="B":
        local=max((len(set(_tokens(s))&target)/max(1,len(target)) for s in _sentences(answer)),default=0)
        overlap=local
    if exact and causal_ok: return "awarded",1.0
    if overlap>=0.58 and causal_ok and len(answer_tokens & target)>=2: return "awarded",overlap
    if overlap>=0.30 and len(answer_tokens & target)>=1: return "partial",overlap
    return "absent",overlap


def mark_written_response(question, answer, policy=None):
    policy=policy or {}
    answer=str(answer or "").strip()
    max_marks=float(question.get("maximum_marks") or 0)
    if not answer:
        return {"proposed_mark":0.0,"maximum_mark":max_marks,"percentage":0.0,"confidence":1.0,
                "status":"RESPONSE_INCOMPLETE","mark_points":[],"feedback":["No response was submitted."],
                "grader_a":{},"grader_b":{},"reconciliation_policy_version":policy.get("reconciliation_policy_version","local-1")}
    contradictions=[]
    low=answer.lower()
    for item in question.get("contradictions") or []:
        phrase=item.get("phrase") if isinstance(item,dict) else str(item)
        if phrase and phrase.lower() in low: contradictions.append(item if isinstance(item,dict) else {"phrase":phrase,"message":"Contradictory statement detected."})
    misconceptions=[]
    for item in question.get("misconceptions") or []:
        phrase=item.get("trigger") if isinstance(item,dict) else str(item)
        if phrase and phrase.lower() in low: misconceptions.append(item if isinstance(item,dict) else {"trigger":phrase,"message":"Known misconception detected."})
    outputs=[]; scores_a=[]; scores_b=[]
    for point in question.get("required_mark_points") or []:
        sa,ca=_point_evidence(answer,point,"A"); sb,cb=_point_evidence(answer,point,"B")
        marks=float(point.get("marks",1)); mapv={"awarded":1.0,"partial":0.5,"absent":0.0}
        a=marks*mapv[sa]; b=marks*mapv[sb]
        # Conservative reconciliation: agreement receives full status; disagreement uses lower award.
        reconciled=min(a,b) if sa!=sb else a
        evidence=[]
        target=set(_tokens(" ".join([point.get("description","")]+(point.get("required_terms") or []))))
        for sent in _sentences(answer):
            if set(_tokens(sent)) & target: evidence.append(sent)
        final_status="awarded" if reconciled>=marks-.001 else ("partial" if reconciled>0 else "absent")
        outputs.append({"point_id":point.get("id"),"description":point.get("description"),"available_marks":marks,
                        "awarded_marks":round(reconciled,2),"status":final_status,"grader_a_status":sa,"grader_b_status":sb,
                        "grader_a_confidence":round(ca,3),"grader_b_confidence":round(cb,3),"evidence":evidence[:2],
                        "improvement_instruction":point.get("improvement_instruction") or ("Add this scientific point explicitly." if final_status!="awarded" else "Point demonstrated.")})
        scores_a.append(a); scores_b.append(b)
    raw=sum(x["awarded_marks"] for x in outputs)
    penalty=0.0
    for item in contradictions:
        try: penalty+=float(item.get("penalty",1))
        except Exception: penalty+=1
    mark=max(0.0,min(max_marks,raw-penalty))
    command=str(question.get("command_verb","")).lower()
    command_ok=True; command_feedback=""
    causal_language=bool(set(_tokens(answer)) & CAUSAL) or any((" "+x+" ") in (" "+_norm_phrase(answer)+" ") for x in ("so","because","therefore","thus","causes","causing","leads to","results in","due to"))
    if command in {"explain","analyse","justify","evaluate","predict"} and not causal_language:
        command_ok=False; command_feedback=f"The command verb '{command}' requires explicit reasoning or causal links."
        mark=min(mark,max_marks*0.75)
    if command=="compare" and not any(x in low for x in ("whereas","while","both","however","in contrast")):
        command_ok=False; command_feedback="A comparison needs linked similarities and/or differences."
        mark=min(mark,max_marks*0.75)
    disagreements=sum(1 for x in outputs if x["grader_a_status"]!=x["grader_b_status"])
    avg_overlap=sum((x["grader_a_confidence"]+x["grader_b_confidence"])/2 for x in outputs)/max(1,len(outputs))
    confidence=max(0.05,min(0.99,0.92-0.10*disagreements-0.12*len(contradictions)+0.12*avg_overlap))
    threshold=float(policy.get("confirmed_confidence",0.72))
    status="MARK_CONFIRMED" if confidence>=threshold else "MORE_EVIDENCE_REQUIRED"
    feedback=[]
    strengths=[x["description"] for x in outputs if x["status"]=="awarded"]
    missing=[x["description"] for x in outputs if x["status"]!="awarded"]
    if strengths: feedback.append("Strengths: "+"; ".join(strengths[:3]))
    if missing: feedback.append("Improve: "+"; ".join(missing[:3]))
    if command_feedback: feedback.append(command_feedback)
    for m in misconceptions[:2]: feedback.append(m.get("message") or "Known misconception detected.")
    return {"proposed_mark":round(mark,2),"maximum_mark":max_marks,"percentage":round(100*mark/max_marks,1) if max_marks else 0,
            "confidence":round(confidence,3),"status":status,"mark_points":outputs,"contradictions":contradictions,
            "misconceptions":misconceptions,"command_verb":question.get("command_verb"),"command_verb_met":command_ok,
            "feedback":feedback,"grader_a":{"score":round(sum(scores_a),2),"version":policy.get("grader_a_version","local-rubric-a-1")},
            "grader_b":{"score":round(sum(scores_b),2),"version":policy.get("grader_b_version","local-rubric-b-1")},
            "reconciliation_policy_version":policy.get("reconciliation_policy_version","local-conservative-1"),
            "validation_boundary":"Deterministic pilot marker; not validated for high-stakes certification."}
