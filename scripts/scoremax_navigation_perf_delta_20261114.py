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
    if MARKER in before:
        if before.count(MARKER)!=1 or REPLACEMENT not in before or SUBJECT_NEW not in before or CHAPTER_NEW not in before:
            raise RuntimeError("PERF_PARTIAL_REPLAY")
        return {"status":"already_applied"}
    tree=ast.parse(before)
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_subject_map"]
    if len(functions)!=1:
        raise RuntimeError("PERF_SUBJECT_MAP_NOT_UNIQUE")
    source=ast.get_source_segment(before,functions[0]) or ""
    for anchor in (ANCHOR,SUBJECT_OLD,CHAPTER_OLD):
        if source.count(anchor.strip("\n"))!=1:
            raise RuntimeError("PERF_SOURCE_ANCHOR_MISMATCH:"+anchor[:80])
        if before.count(anchor)!=1:
            raise RuntimeError("PERF_DOCUMENT_ANCHOR_MISMATCH")
    after=before.replace(ANCHOR,REPLACEMENT,1).replace(SUBJECT_OLD,SUBJECT_NEW,1).replace(CHAPTER_OLD,CHAPTER_NEW,1)
    assert after.count(MARKER)==1
    compile(after,str(path),"exec")
    old=_functions(before);new=_functions(after)
    if old.keys()!=new.keys():
        raise RuntimeError("PERF_FUNCTION_SET_CHANGED")
    if any(old[k]!=new[k] for k in old if k!="_subject_map"):
        raise RuntimeError("PERF_UNRELATED_FUNCTION_CHANGED")
    path.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","functions_changed":["_subject_map"],"production_data_mutations":0,
        "baseline_sha256":hashlib.sha256(before.encode()).hexdigest(),
        "candidate_sha256":hashlib.sha256(after.encode()).hexdigest()}


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("runtime_root",type=Path)
    args=parser.parse_args()
    print("SCOREMAX_NAV_PERF_DELTA="+json.dumps(apply(args.runtime_root),sort_keys=True))
