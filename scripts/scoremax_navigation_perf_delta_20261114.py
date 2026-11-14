"""Fail-closed optimization for ScoreMax's accepted student subject navigation.

This build-time read-only delta is applied only *after* all accepted ScoreMax
runtime hash checks. It changes grouping of previously loaded learner evidence
without altering publication, academic governance, grading, mastery or SQL.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

MARKER = "SCOREMAX_STUDENT_EVIDENCE_INDEX_20261114"
CACHE_MARKER = "SCOREMAX_REQUEST_SUBJECT_MAP_CACHE_20261114"
CACHE_ENTRY = """def _subject_map(c, student_id):
    # SCOREMAX_REQUEST_SUBJECT_MAP_CACHE_20261114: same-request reuse only.
    # Read-only GET requests; never retain results across users or HTTP requests.
    from flask import g, has_request_context, request
    _cache_on=has_request_context() and request.method=='GET'
    _cache_key=('_subject_map',student_id)
    if _cache_on:
        _cached=getattr(g,'_scoremax_subject_map_cache',{})
        if _cache_key in _cached:
            from copy import deepcopy
            return deepcopy(_cached[_cache_key])
"""
CACHE_EXIT = """    if _cache_on:
        from copy import deepcopy
        _cached=getattr(g,'_scoremax_subject_map_cache',{})
        _cached[_cache_key]=deepcopy(data)
        g._scoremax_subject_map_cache=_cached
    return data"""

ANCHOR = "    evidence=learner_answer_evidence(c,student_id)\n    data=[]\n"
REPLACEMENT = """    evidence=learner_answer_evidence(c,student_id)
    # SCOREMAX_STUDENT_EVIDENCE_INDEX_20261114: index the existing evidence
    # once, avoiding one full-array scan for every subject and chapter card.
    by_subject={}
    by_chapter={}
    for row in evidence:
        key=row['subject'].casefold()
        by_subject.setdefault(key,[]).append(row)
        by_chapter.setdefault((key,row['chapter']),[]).append(row)
    data=[]
"""
SUBJECT_OLD = "        stats=evidence_summary([r for r in evidence if r['subject'].casefold()==display.casefold()])"
SUBJECT_NEW = "        stats=evidence_summary(by_subject.get(display.casefold(),[]))"
CHAPTER_OLD = "            stats=evidence_summary([r for r in evidence if r['subject'].casefold()==display.casefold() and r['chapter']==ch['chapter']])"
CHAPTER_NEW = "            stats=evidence_summary(by_chapter.get((display.casefold(),ch['chapter']),[]))"


def _functions(source):
    return {n.name: ast.dump(n, include_attributes=False)
            for n in ast.parse(source).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}


def apply(root: Path):
    path=Path(root)/"app.py"
    before=path.read_text(encoding="utf8")
    if MARKER in before and CACHE_MARKER in before:
        if before.count(MARKER)!=1 or before.count(CACHE_MARKER)!=1 or CACHE_ENTRY not in before or CACHE_EXIT not in before:
            raise RuntimeError("PERF_PARTIAL_REPLAY")
        return {"status":"already_applied"}
    tree=ast.parse(before)
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_subject_map"]
    if len(functions)!=1:
        raise RuntimeError("PERF_SUBJECT_MAP_NOT_UNIQUE")
    source=ast.get_source_segment(before,functions[0]) or ""
    if MARKER not in before:
        for anchor in (ANCHOR,SUBJECT_OLD,CHAPTER_OLD):
            if source.count(anchor.strip("\n"))!=1 or before.count(anchor)!=1:
                raise RuntimeError("PERF_SOURCE_ANCHOR_MISMATCH:"+anchor[:80])
        after=before.replace(ANCHOR,REPLACEMENT,1).replace(SUBJECT_OLD,SUBJECT_NEW,1).replace(CHAPTER_OLD,CHAPTER_NEW,1)
    else:
        after=before
    if CACHE_MARKER not in after:
        tree2=ast.parse(after)
        node=next(n for n in tree2.body if isinstance(n,ast.FunctionDef) and n.name=="_subject_map")
        seg=ast.get_source_segment(after,node)
        if after.count("def _subject_map(c, student_id):")!=1 or seg.count("    return data")!=1:
            raise RuntimeError("PERF_CACHE_SOURCE_ANCHOR_DRIFT")
        after=after.replace("def _subject_map(c, student_id):", CACHE_ENTRY,1)
        # Insert only in the subject-map AST span, not into another function.
        boundary="\n"+ast.get_source_segment(after,next(n for n in ast.parse(after).body if isinstance(n,ast.FunctionDef) and n.name=="_subject_map"))
        revised=boundary.replace("    return data", CACHE_EXIT,1)
        if after.count(boundary)!=1:raise RuntimeError("PERF_CACHE_BOUNDARY_DRIFT")
        after=after.replace(boundary,revised,1)
    assert after.count(MARKER)==1 and after.count(CACHE_MARKER)==1
    compile(after,str(path),"exec")
    old=_functions(before);new=_functions(after)
    if old.keys()!=new.keys():
        raise RuntimeError("PERF_FUNCTION_SET_CHANGED")
    if any(old[k]!=new[k] for k in old if k!="_subject_map"):
        raise RuntimeError("PERF_UNRELATED_FUNCTION_CHANGED")
    path.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","functions_changed":["_subject_map"],"request_scoped_only":True,"production_data_mutations":0,
        "baseline_sha256":hashlib.sha256(before.encode()).hexdigest(),
        "candidate_sha256":hashlib.sha256(after.encode()).hexdigest()}


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("runtime_root",type=Path)
    args=parser.parse_args()
    print("SCOREMAX_NAV_PERF_DELTA="+json.dumps(apply(args.runtime_root),sort_keys=True))
