from __future__ import annotations
from typing import Any

POLICY="PH-CROSS50-SHORT-RESPONSE-STRUCTURE-V015L9CM-1"
_SHORT={"SHORT_RESPONSE","SHORT_CONSTRUCTED_RESPONSE","CONSTRUCTED_RESPONSE","SAQ","SHORT_ANSWER"}

def normalize_token(v:Any)->str:
    return str(v or "").strip().upper().replace("-","_").replace(" ","_")

def _assert_short_response_marking(marking:dict[str,Any], *, subject:str="", source_question_id:str="")->None:
    key_type=normalize_token(marking.get("key_type"))
    rubric=marking.get("rubric")
    if key_type=="TEXT":
        if rubric is not None and (not isinstance(rubric,dict) or rubric):
            raise RuntimeError(f"{subject}:{source_question_id}: TEXT short response cannot carry a nonempty or malformed rubric")
        return
    if key_type=="RUBRIC_ONLY":
        if not isinstance(rubric,dict) or not rubric:
            raise RuntimeError(f"{subject}:{source_question_id}: RUBRIC_ONLY short response requires an existing nonempty rubric object")
        return
    raise RuntimeError(f"{subject}:{source_question_id}: unsupported short-response marking mode {key_type!r}")

def canonicalize_short_response_structure(material:dict[str,Any], *, subject:str="", source_question_id:str="",
                                          source_row:dict[str,Any]|None=None, effective:dict[str,Any]|None=None)->bool:
    if source_row is not None:
        from copy import deepcopy
        from powerhouse_operator.question_source_fidelity_v015l9bi import canonicalize_source_marking
        candidate=deepcopy(material)
        changed=canonicalize_source_marking(candidate,source_row,effective)
        structural=canonicalize_short_response_structure(candidate,subject=subject,source_question_id=source_question_id)
        if changed or structural:
            material.clear();material.update(candidate)
        return changed or structural
    if not isinstance(material,dict): return False
    content=material.get("content")
    if not isinstance(content,dict): return False
    family=normalize_token(content.get("question_family_type"))
    exam=normalize_token(content.get("exam_question_type"))
    marking=content.get("marking") if isinstance(content.get("marking"),dict) else {}
    if family not in _SHORT and exam not in _SHORT:
        return False
    _assert_short_response_marking(marking,subject=subject,source_question_id=source_question_id)
    options=content.get("options")
    if options in (None,[]):
        content["options"]=[]
        return False
    if not isinstance(options,list):
        raise RuntimeError(f"{subject}:{source_question_id}: short-response options are not a list")
    # Source option arrays are preserved upstream/in PH evidence. They must not survive
    # into a learner free-text delivery projection.
    content["options"]=[]
    return True

def assert_short_response_structure(material:dict[str,Any], *, subject:str="", source_question_id:str="")->None:
    if not isinstance(material,dict): return
    content=material.get("content")
    if not isinstance(content,dict): return
    family=normalize_token(content.get("question_family_type"))
    exam=normalize_token(content.get("exam_question_type"))
    if family not in _SHORT and exam not in _SHORT: return
    marking=content.get("marking") if isinstance(content.get("marking"),dict) else {}
    _assert_short_response_marking(marking,subject=subject,source_question_id=source_question_id)
    if list(content.get("options") or []):
        raise RuntimeError(f"{subject}:{source_question_id}: outbound short response leaked learner options")
