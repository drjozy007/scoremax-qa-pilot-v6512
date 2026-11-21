"""Request-local validated evidence grouping for the ScoreMax Learn overview.

The canonical learner_answer_evidence performs frozen checksum, programme and
source authority validation ONCE. This delta passes its already-validated
subject sublists to _subject_snapshot, rather than independently calling the
same reader and cloning the eligible answer rows for every subject.

Only _learn_context's own subject-card path uses the new optional argument.
All direct _subject_snapshot calls retain native behavior, academic marking,
mastery, programme/PH authorisation and release code are unchanged.
No shared cache, no persistent projection and no production deployment.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

MARKER="SCOREMAX_LEARN_SUBJECT_VALIDATED_GROUP_ONCE_20261116"
OLD_SIGNATURE="def _subject_snapshot(conn,student_id,subject):"
NEW_SIGNATURE="def _subject_snapshot(conn,student_id,subject,_validated_subject_rows=None):"
OLD_ROWS="    rows=runtime.learner_answer_evidence(conn,student_id,subject=subject)"
NEW_ROWS="""    # SCOREMAX_LEARN_SUBJECT_VALIDATED_GROUP_ONCE_20261116: only an already
    # validated same-request sublist is reused; no academic eligibility bypass.
    rows=(runtime.learner_answer_evidence(conn,student_id,subject=subject)
          if _validated_subject_rows is None else _validated_subject_rows)"""
OLD_LEARN="""    subjects=[]
    for name in _subjects_for_student(conn,student_id):
        snap=_subject_snapshot(conn,student_id,name)"""
NEW_LEARN="""    # Request-scoped only: validate every frozen context with the original
    # native reader exactly once. Do not trim or normalise stored subject keys
    # beyond native comparison's .casefold(); keep sorted subject order below.
    import app as runtime
    _subject_names=_subjects_for_student(conn,student_id)
    _validated=runtime.learner_answer_evidence(conn,student_id) if _subject_names else []
    _groups={}
    for _record in _validated:
        _groups.setdefault(str(_record.get('subject') or '').casefold(),[]).append(_record)
    subjects=[]
    for name in _subject_names:
        snap=_subject_snapshot(conn,student_id,name,
            _validated_subject_rows=_groups.get(name.strip().casefold(),[]))"""

def fn(src,name):
    functions=[n for n in ast.parse(src).body
        if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(functions)!=1:raise RuntimeError("LEARN_GROUP_FUNCTION_NOT_UNIQUE:"+name)
    return ast.get_source_segment(src,functions[0]) or ""

def apply(root):
    p=Path(root)/"ux_student_batch.py"
    before=p.read_text(encoding="utf8")
    old_subject=fn(before,"_subject_snapshot")
    old_learn=fn(before,"_learn_context")
    if MARKER in old_subject:
        if (old_subject.count(MARKER)!=1 or NEW_SIGNATURE not in old_subject
             or NEW_ROWS not in old_subject or NEW_LEARN not in old_learn):
            raise RuntimeError("LEARN_EVIDENCE_GROUP_PARTIAL_REPLAY")
        return {"status":"ALREADY_APPLIED","request_only":True}
    for text,src,name in ((OLD_SIGNATURE,old_subject,"subject_sig"),
                          (OLD_ROWS,old_subject,"subject_reader"),
                          (OLD_LEARN,old_learn,"learn_loop")):
        if src.count(text)!=1:
            raise RuntimeError("LEARN_EVIDENCE_GROUP_SOURCE_DRIFT:"+name)
    new_subject=old_subject.replace(OLD_SIGNATURE,NEW_SIGNATURE,1).replace(
       OLD_ROWS,NEW_ROWS,1)
    new_learn=old_learn.replace(OLD_LEARN,NEW_LEARN,1)
    modified=before.replace(old_subject,new_subject,1).replace(old_learn,new_learn,1)
    compile(modified,str(p),"exec")
    bef={n.name:ast.dump(n,include_attributes=False)
         for n in ast.parse(before).body if isinstance(n,ast.FunctionDef)}
    aft={n.name:ast.dump(n,include_attributes=False)
         for n in ast.parse(modified).body if isinstance(n,ast.FunctionDef)}
    if bef.keys()!=aft.keys() or any(bef[k]!=aft[k] for k in bef
                                     if k not in ("_subject_snapshot","_learn_context")):
        raise RuntimeError("LEARN_EVIDENCE_GROUP_UNRELATED_CHANGE")
    p.write_text(modified,encoding="utf8",newline="\n")
    return {"status":"APPLIED","source_guarded":True,
            "changes":["_subject_snapshot","_learn_context"],
            "request_only":True,"formal_mastery_unchanged":True,
            "source_admission_unchanged":True,
            "before_sha256":hashlib.sha256(before.encode()).hexdigest(),
            "after_sha256":hashlib.sha256(modified.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("generated_runtime",type=Path)
    args=parser.parse_args()
    print("SCOREMAX_LEARN_EVIDENCE_GROUPING="+json.dumps(
         apply(args.generated_runtime),sort_keys=True),flush=True)
