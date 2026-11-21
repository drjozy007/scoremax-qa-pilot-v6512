"""Push the catalogue's requested subject into existing governed placement SQL.

The old catalogue code materializes every subject in each programme, evaluates
a canonical question-type callback for those rows, and discards unrelated
subjects afterwards. This source-bound delta narrows ONLY the catalogue read:
existing PH membership, activation, withdrawal and programme predicates remain.

Other callers retain the exact legacy unfiltered behavior. The original Python
filter in the catalogue stays as a defensive equality check.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

MARKER="SCOREMAX_CATALOGUE_SUBJECT_PUSHDOWN_20261114"
OLD_DEF="def practice_scope_placements(c, programme, guided=False):"
NEW_DEF="def practice_scope_placements(c, programme, guided=False, subject_filter=''):"
OLD_SQL='ORDER BY subject,q.id,chapter""",aliases+aliases+aliases).fetchall()'
NEW_SQL='''{subject_filter_sql}
ORDER BY subject,q.id,chapter""",aliases+aliases+aliases+subject_filter_params).fetchall()'''
OLD_SETUP="    live=practice_pool_clause(guided)\n"
NEW_SETUP="""    live=practice_pool_clause(guided)
    # SCOREMAX_CATALOGUE_SUBJECT_PUSHDOWN_20261114: ASCII-only SQL pushdown
    # because SQLite lower() and Python Unicode casefold have different rules.
    # Retain existing Python filtering on all routes as a safety fence.
    scope=str(subject_filter or '').strip()
    _pushdown=bool(scope and scope.isascii())
    subject_filter_sql=(
        " AND lower(CASE WHEN q.ph_projection_owner='POWER_HOUSE' "
        "THEN replace(r.subject_id,'_',' ') ELSE q.subject END)=lower(?)"
        if _pushdown else "")
    subject_filter_params=[scope] if _pushdown else []
    # The catalogue counts placements; it never consumes question_type.
    # Keep the canonical interpreter in the unchanged, unfiltered caller path.
    type_projection=("NULL" if subject_filter else
        "scoremax_question_type(q.ph_response_contract,q.qtype,q.answer_config,q.marking_config)")
"""
OLD_TYPE="scoremax_question_type(q.ph_response_contract,q.qtype,q.answer_config,q.marking_config) question_type,"
NEW_TYPE="{type_projection} question_type,"
CAT_OLD="for row in practice_scope_placements(conn,programme,guided):"
CAT_NEW="for row in practice_scope_placements(conn,programme,guided,subject):"

def function_map(text):
    return {node.name:ast.dump(node,include_attributes=False)
            for node in ast.parse(text).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}

def one(src, old, new, where):
    if src.count(old)!=1:raise RuntimeError("CATALOGUE_SUBJECT_ANCHOR_DRIFT:"+where+":"+old[:55])
    return src.replace(old,new,1)

def apply(root:Path):
    root=Path(root)
    app_path=root/"app.py"
    cat_path=root/"ux_catalogue_browser.py"
    app_before=app_path.read_text(encoding="utf8")
    cat_before=cat_path.read_text(encoding="utf8")
    if MARKER in app_before:
        if (app_before.count(MARKER)!=1 or
            NEW_DEF not in app_before or NEW_SQL not in app_before or
            NEW_TYPE not in app_before or
            CAT_NEW not in cat_before):
            raise RuntimeError("CATALOGUE_SUBJECT_PARTIAL_REPLAY")
        return {"status":"already_applied","read_only":True}
    app_tree=ast.parse(app_before)
    cat_tree=ast.parse(cat_before)
    app_matches=[x for x in app_tree.body if isinstance(x,ast.FunctionDef)
                 and x.name=="practice_scope_placements"]
    cat_matches=[x for x in cat_tree.body if isinstance(x,ast.FunctionDef)
                 and x.name=="_release_scope_counts"]
    if len(app_matches)!=1 or len(cat_matches)!=1:
        raise RuntimeError("CATALOGUE_SUBJECT_FUNCTION_DRIFT")
    app_func=ast.get_source_segment(app_before,app_matches[0]) or ""
    cat_func=ast.get_source_segment(cat_before,cat_matches[0]) or ""
    if not all(x in app_func for x in ("ph_bridge_staged_withdrawal_exclusions",
          "integration_ph_product_activation_authorizations","scoremax_release_programme",
          "practice_pool_clause","ORDER BY subject,q.id,chapter")):
        raise RuntimeError("CATALOGUE_GOVERNANCE_PREDICATES_MISSING")
    new_app=one(app_func,OLD_DEF,NEW_DEF,"app:def")
    new_app=one(new_app,OLD_SETUP,NEW_SETUP,"app:setup")
    new_app=one(new_app,OLD_SQL,NEW_SQL,"app:sql")
    new_app=one(new_app,OLD_TYPE,NEW_TYPE,"app:type_projection")
    new_cat=one(cat_func,CAT_OLD,CAT_NEW,"catalogue:call")
    app_after=one(app_before,app_func,new_app,"app:func")
    cat_after=one(cat_before,cat_func,new_cat,"catalogue:func")
    compile(app_after,str(app_path),"exec")
    compile(cat_after,str(cat_path),"exec")
    old_app,new_app_maps=function_map(app_before),function_map(app_after)
    old_cat,new_cat_maps=function_map(cat_before),function_map(cat_after)
    if (old_app.keys()!=new_app_maps.keys() or
        any(old_app[k]!=new_app_maps[k] for k in old_app if k!="practice_scope_placements") or
        old_cat.keys()!=new_cat_maps.keys() or
        any(old_cat[k]!=new_cat_maps[k] for k in old_cat if k!="_release_scope_counts")):
        raise RuntimeError("CATALOGUE_SUBJECT_UNRELATED_CHANGE")
    app_path.write_text(app_after,encoding="utf8",newline="\n")
    cat_path.write_text(cat_after,encoding="utf8",newline="\n")
    return {"status":"applied","changed":["practice_scope_placements","_release_scope_counts"],
            "read_only":True,"schema_change":False,"release_policy_change":False,
            "app_before_sha256":hashlib.sha256(app_before.encode()).hexdigest(),
            "app_after_sha256":hashlib.sha256(app_after.encode()).hexdigest(),
            "catalogue_before_sha256":hashlib.sha256(cat_before.encode()).hexdigest(),
            "catalogue_after_sha256":hashlib.sha256(cat_after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("runtime_root",type=Path)
    args=p.parse_args()
    print("SCOREMAX_CATALOGUE_SUBJECT_PUSHDOWN="+json.dumps(apply(args.runtime_root),sort_keys=True))
