"""Minimise ScoreMax mastery-card question payload without changing eligibility.

The projection contains the union of fields referenced by the 2026-11-14
canonical runtime-type interpreter, independent mastery evidence predicate,
coverage selector, and chapter mastery level/family calculation. The full
question payload remains untouched for test generation and actual marking.
This is a post-sealed-runtime build delta; no production DDL or data edits.
"""
from __future__ import annotations
import ast,hashlib,json,re
from pathlib import Path
MARKER="SCOREMAX_MASTERY_NARROW_PROJECTION_20261114"
OLD = """    all_rows=c.execute(f"SELECT q.* FROM questions q WHERE {' AND '.join(clauses)}",params).fetchall()"""
FIELDS=("id","level","family_id","difficulty","ph_knowledge_node_ids_json",
        "ph_question_id","ph_question_version_id","ph_question_checksum_sha256",
        "ph_release_id","ph_evidence_role","ph_dependency_type","ph_projection_owner",
        "source_type","ph_independent_mastery_weight","ph_response_contract",
        "qtype","answer_config","marking_config")
NEW = """    # SCOREMAX_MASTERY_NARROW_PROJECTION_20261114: identical active
    # publication predicate, independent-evidence eligibility, node coverage
    # selection, and question type. Avoid large stems, choices, explanations
    # and snapshots when only a chapter-card opportunity is requested.
    all_rows=c.execute(f"SELECT """ + ",".join("q."+k for k in FIELDS) + """ FROM questions q WHERE {' AND '.join(clauses)}",params).fetchall()"""

def functions(source):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(source).body
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def require_fields(source, names):
    nodes=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in names]
    found={n.name for n in nodes}
    if found!=set(names):raise RuntimeError("MASTERY_PROJECTION_REQUIRED_FUNCTION_MISSING:"+repr(set(names)-found))
    usage={}
    for n in nodes:
        snippet=ast.get_source_segment(source,n) or ''
        usage[n.name]=set(re.findall(r"""\bq\[['"]([A-Za-z_0-9]+)['"]\]""",snippet))|set(
            re.findall(r"""\br\[['"]([A-Za-z_0-9]+)['"]\]""",snippet))
    return usage

def apply(root:Path):
    root=Path(root)
    path=root/"app.py"; before=path.read_text(encoding="utf8")
    if MARKER in before:
        if before.count(MARKER)!=1 or NEW not in before:
            raise RuntimeError("MASTERY_NARROW_PARTIAL_REPLAY")
        return {"status":"already_applied"}
    ast.parse(before)
    names=["chapter_mastery_opportunity","select_mastery_coverage_questions","question_coverage_nodes","canonical_question_type"]
    use=require_fields(before,names)
    permitted=set(FIELDS)
    # The chapter-card selector, coverage and form assembler must never
    # begin using a new field without failing this preflight.
    used=(use["chapter_mastery_opportunity"]|
          use["select_mastery_coverage_questions"]|
          use["question_coverage_nodes"])
    if used-permitted:raise RuntimeError("MASTERY_PROJECTION_FIELD_DRIFT:"+repr(sorted(used-permitted)))
    src=next(ast.get_source_segment(before,n) for n in ast.parse(before).body
             if isinstance(n,ast.FunctionDef) and n.name=="chapter_mastery_opportunity")
    if before.count(OLD)!=1 or src.count(OLD)!=1:
        raise RuntimeError("MASTERY_NARROW_SOURCE_DRIFT")
    # The dependency guards enforce that the existing model continues to
    # inspect PH independence and governed node coverage, not raw counts.
    required=("eligible_for_formal_mastery(r)","canonical_question_type(r)",
              "select_mastery_coverage_questions(","mastery_coverage_contract(")
    if any(token not in src for token in required):
        raise RuntimeError("MASTERY_NARROW_GOVERNANCE_GUARD_MISSING")
    helper=(root/"ph_mastery_evidence.py").read_text(encoding="utf8")
    if not all(t in helper for t in ("ph_question_id","ph_question_version_id",
             "ph_question_checksum_sha256","ph_release_id","ph_evidence_role",
             "ph_dependency_type","ph_projection_owner","source_type",
             "ph_independent_mastery_weight")):
        raise RuntimeError("MASTERY_NARROW_INDEPENDENCE_CONTRACT_DRIFT")
    before_functions=functions(before)
    after=before.replace(OLD,NEW,1)
    compile(after,str(path),"exec")
    after_functions=functions(after)
    if before_functions.keys()!=after_functions.keys() or any(before_functions[k]!=after_functions[k]
                 for k in before_functions if k!="chapter_mastery_opportunity"):
        raise RuntimeError("MASTERY_NARROW_UNRELATED_FUNCTION_CHANGED")
    path.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","fields":FIELDS,"read_only":True,
       "before_sha256":hashlib.sha256(before.encode()).hexdigest(),
       "after_sha256":hashlib.sha256(after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("runtime_root",type=Path);a=p.parse_args()
    print("SCOREMAX_MASTERY_NARROW_PROJECTION="+json.dumps(apply(a.runtime_root),sort_keys=True))
