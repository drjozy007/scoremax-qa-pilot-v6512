"""Bounded unexpected-error rollback for the accepted student submission path.

This build-time delta changes only exception cleanup, never grading, frozen
evidence, mastery policy, or question authority. It is installed in disposable
CI after accepted source assembly, never at boot and never in live production.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

MARKER="SCOREMAX_SUBMIT_UNEXPECTED_ROLLBACK_20261115"
ANCHOR=("        abort(409,description='Assessment contract could not be verified. "
        "Your previous saved work has not been changed.')")
ADDITION="""        abort(409,description='Assessment contract could not be verified. Your previous saved work has not been changed.')
    # SCOREMAX_SUBMIT_UNEXPECTED_ROLLBACK_20261115: do not leave the SQLite
    # write lock or uncommitted attempt/mastery rows alive on unexpected errors.
    # Preserve the original exception and its monitoring; never convert it
    # into an academic pass or an idempotent duplicate receipt.
    except Exception:
        try:
            c.rollback()
        except Exception:
            pass
        try:
            c.close()
        except Exception:
            pass
        raise"""

def functions(src):
    return {node.name:ast.dump(node,include_attributes=False)
            for node in ast.parse(src).body if isinstance(node,ast.FunctionDef)}

def apply(runtime):
    p=Path(runtime)/"app.py"
    previous=p.read_text(encoding="utf8")
    matches=[node for node in ast.parse(previous).body
        if isinstance(node,ast.FunctionDef) and node.name=="submit_assessment_v4"]
    if len(matches)!=1:raise RuntimeError("SUBMIT_ROLLBACK_FUNCTION_DRIFT")
    src=ast.get_source_segment(previous,matches[0]) or ""
    if MARKER in src:
        if src.count(MARKER)!=1 or ADDITION not in src:
            raise RuntimeError("SUBMIT_ROLLBACK_PARTIAL_REPLAY")
        return {"status":"ALREADY_APPLIED","unexpected_exception_cleanup":True}
    required=("BEGIN IMMEDIATE","submitted_attempt_id","attempt_answers",
       "process_mastery_result(","c.commit()","QuestionContractError",
       "c.rollback()","save_assessment(")
    missing=[part for part in required if part not in src]
    if missing:raise RuntimeError("SUBMIT_OR_ACADEMIC_CONTRACT_DRIFT:"+repr(missing))
    if src.count(ANCHOR)!=1 or not src.rstrip().endswith(ANCHOR):
        raise RuntimeError("SUBMIT_NATIVE_ERROR_BOUNDARY_DRIFT")
    altered=src.replace(ANCHOR,ADDITION,1)
    updated=previous.replace(src,altered,1)
    compile(updated,str(p),"exec")
    before_map=functions(previous)
    after_map=functions(updated)
    if set(before_map)!=set(after_map) or any(
        before_map[k]!=after_map[k] for k in before_map
        if k!="submit_assessment_v4"):
        raise RuntimeError("SUBMIT_UNRELATED_FUNCTION_CHANGE")
    p.write_text(updated,encoding="utf8",newline="\n")
    return {"status":"APPLIED","function":"submit_assessment_v4",
        "source_locked":True,"no_schema_change":True,
        "marking_mastery_policy_change":False,
        "previous_sha256":hashlib.sha256(previous.encode()).hexdigest(),
        "new_sha256":hashlib.sha256(updated.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("runtime_root",type=Path)
    args=parser.parse_args()
    print("SCOREMAX_SUBMIT_UNEXPECTED_ROLLBACK="+json.dumps(
        apply(args.runtime_root),sort_keys=True),flush=True)
