"""Opt-in epoch-checked mastery inventory reader; native fallback remains authority.

Install after the existing chapter read bundle and shadow helper have been
qualified. A fresh shadow projection is used only as a programme-membership
prefilter; mastery-specific live, demo, calibration, subject and chapter
predicates and all downstream academic calculations remain byte-identical.
If a shadow is absent, stale, empty or the helper errors, execute original
native governance SQL. Feature OFF by default, no database/schema writes.
"""
from __future__ import annotations
import ast,hashlib,json
from pathlib import Path
from scoremax_mastery_card_projection_20261114 import FIELDS

MARKER="SCOREMAX_MASTERY_EPOCH_PREFILTER_20261115"
SELECT="SELECT "+",".join("q."+k for k in FIELDS)+" FROM questions q WHERE {' AND '.join(clauses)}"
OLD="    all_rows=c.execute(f\""+SELECT+"\",params).fetchall()"
NEW = """    # SCOREMAX_MASTERY_EPOCH_PREFILTER_20261115: optional native-governed prefilter
    from scoremax_shadow_navigation_v1 import try_shadow_mastery_rows
    _shadow_mastery_rows=(
        try_shadow_mastery_rows(c,programme,clauses[:-1],params[:2],["id","level","family_id","difficulty","ph_knowledge_node_ids_json","ph_question_id","ph_question_version_id","ph_question_checksum_sha256","ph_release_id","ph_evidence_role","ph_dependency_type","ph_projection_owner","source_type","ph_independent_mastery_weight","ph_response_contract","qtype","answer_config","marking_config"])
        if programme and len(clauses)==6 else None
    )
    if _shadow_mastery_rows is None:
        all_rows=c.execute(f"SELECT q.id,q.level,q.family_id,q.difficulty,q.ph_knowledge_node_ids_json,q.ph_question_id,q.ph_question_version_id,q.ph_question_checksum_sha256,q.ph_release_id,q.ph_evidence_role,q.ph_dependency_type,q.ph_projection_owner,q.source_type,q.ph_independent_mastery_weight,q.ph_response_contract,q.qtype,q.answer_config,q.marking_config FROM questions q WHERE {' AND '.join(clauses)}",params).fetchall()
    else:
        all_rows=_shadow_mastery_rows"""

def fn_dict(source):
    return {n.name:ast.dump(n,include_attributes=False)
            for n in ast.parse(source).body
            if isinstance(n,ast.FunctionDef)}

def apply(root:Path):
    p=Path(root)/"app.py"
    before=p.read_text(encoding="utf8")
    tree=ast.parse(before)
    matches=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="chapter_mastery_opportunity"]
    if len(matches)!=1:raise RuntimeError("EPOCH_MASTERY_FUNCTION_DRIFT")
    fn=ast.get_source_segment(before,matches[0]) or ""
    helper=Path(root)/"scoremax_shadow_navigation_v1.py"
    if (not helper.is_file() or
       "def try_shadow_mastery_rows(" not in helper.read_text(encoding="utf8")):
        raise RuntimeError("EPOCH_MASTERY_HELPER_MISSING")
    if MARKER in fn:
        if fn.count(MARKER)!=1 or NEW not in fn:
            raise RuntimeError("EPOCH_MASTERY_PARTIAL_REPLAY")
        return {"status":"already_applied","feature_default_off":True}
    if fn.count(OLD)!=1:
        raise RuntimeError("EPOCH_MASTERY_NATIVE_SELECT_DRIFT")
    if not all(x in fn for x in ("mastery_coverage_contract(","_mastery_previous_families(",
        "eligible_for_formal_mastery(r)","select_mastery_coverage_questions(",
        "SCOREMAX_MASTERY_NARROW_PROJECTION_20261114")):
        raise RuntimeError("EPOCH_MASTERY_ACADEMIC_CONTRACT_DRIFT")
    changed=fn.replace(OLD,NEW,1)
    after=before.replace(fn,changed,1)
    compile(after,str(p),"exec")
    orig=fn_dict(before);current=fn_dict(after)
    if orig.keys()!=current.keys() or any(orig[k]!=current[k] for k in orig if k!="chapter_mastery_opportunity"):
        raise RuntimeError("EPOCH_MASTERY_UNRELATED_CHANGE")
    p.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","feature_default_off":True,"no_schema_change":True,
        "no_mastery_policy_change":True,"source_anchored":True,
        "previous_hash":hashlib.sha256(before.encode()).hexdigest(),
        "result_hash":hashlib.sha256(after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("runtime_root",type=Path)
    args=parser.parse_args()
    print("SCOREMAX_MASTERY_EPOCH_PREFILTER="+json.dumps(apply(args.runtime_root),sort_keys=True))
