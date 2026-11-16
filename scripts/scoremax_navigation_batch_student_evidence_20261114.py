"""Batch student chapter evidence once per subject, preserving frozen eligibility.

The existing learner_answer_evidence() is authoritative. It runs once for the
subject rather than again for every chapter card. Every row retains its
validated source/PH context, version, weight, marking and programme checks.
No schema, auth, release, mastery-rule or database mutation is introduced.
"""
from __future__ import annotations
import ast,hashlib,json
from pathlib import Path

MARKER="SCOREMAX_NAV_CHAPTER_EVIDENCE_ONCE_20261114"
OLD_ANCHOR="    out=[]\n    for idx,item in enumerate(browse_items,1):\n"
NEW_ANCHOR="""    # SCOREMAX_NAV_CHAPTER_EVIDENCE_ONCE_20261114: same authoritative
    # eligibility reader, once per page. The original reader applies its
    # chapter predicate case-insensitively after validating frozen context.
    validated_evidence=runtime.learner_answer_evidence(conn,student_id,programme,subject)
    evidence_by_chapter={}
    for row in validated_evidence:
        key=str(row['chapter'] or '').casefold()  # native stored context is NOT stripped
        evidence_by_chapter.setdefault(key,[]).append(row)
    out=[]
    for idx,item in enumerate(browse_items,1):
"""
OLD_STATS="        stats=runtime.evidence_summary(runtime.learner_answer_evidence(conn,student_id,programme,subject,source_chapter))"
NEW_STATS="        stats=runtime.evidence_summary((evidence_by_chapter.get(source_chapter.strip().casefold(),[]) if source_chapter else validated_evidence))"

def apply(root:Path):
    path=Path(root)/"ux_student_batch.py"
    before=path.read_text(encoding="utf8")
    if MARKER in before:
        if before.count(MARKER)!=1 or NEW_ANCHOR not in before or NEW_STATS not in before:
            raise RuntimeError("CHAPTER_EVIDENCE_PARTIAL_REPLAY")
        return {"status":"already_applied"}
    tree=ast.parse(before)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_chapter_snapshots"]
    if len(nodes)!=1:raise RuntimeError("CHAPTER_EVIDENCE_FUNCTION_MISMATCH")
    fragment=ast.get_source_segment(before,nodes[0]) or ""
    for anchor in (OLD_ANCHOR,OLD_STATS):
        if fragment.count(anchor.strip("\n"))!=1 or before.count(anchor)!=1:
            raise RuntimeError("CHAPTER_EVIDENCE_SOURCE_MISMATCH:"+anchor[:75])
    after=before.replace(OLD_ANCHOR,NEW_ANCHOR,1).replace(OLD_STATS,NEW_STATS,1)
    compile(after,str(path),"exec")
    def fn(src):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(src).body if isinstance(n,ast.FunctionDef)}
    old,new=fn(before),fn(after)
    if old.keys()!=new.keys() or any(old[k]!=new[k] for k in old if k!="_chapter_snapshots"):
        raise RuntimeError("CHAPTER_EVIDENCE_UNRELATED_FUNCTION_CHANGED")
    path.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","function":"_chapter_snapshots","schema_change":False,
            "release_or_mastery_policy_change":False,
            "before_sha256":hashlib.sha256(before.encode()).hexdigest(),
            "after_sha256":hashlib.sha256(after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("runtime_root",type=Path);a=p.parse_args()
    print("SCOREMAX_NAV_CHAPTER_EVIDENCE_BATCH="+json.dumps(apply(a.runtime_root),sort_keys=True))
