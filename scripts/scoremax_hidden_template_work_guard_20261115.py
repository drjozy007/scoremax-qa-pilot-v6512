"""Source-locked, read-only removal of hidden shared-template work.

The accepted injector computes subject_nav even when show_subject_nav is false,
and scoremax_coach even when show_coach is false. Do not change visibility rules,
template variables, student role/access, PH predicates or displayed components.
When the native visibility flag is false, the associated result is already
hidden, so skip expensive backend reads entirely.

Install after the existing PR #55 deltas, not in production; fail on source drift.
"""
from __future__ import annotations
import ast,hashlib,json
from pathlib import Path

MARKER="SCOREMAX_HIDDEN_TEMPLATE_WORK_GUARD_20261115"
OLD_NAV="subject_nav=_subject_map(c,session['user_id']) if '_subject_map' in globals() else []"
NEW_NAV="subject_nav=_subject_map(c,session['user_id']) if show_subject_nav and '_subject_map' in globals() else []"
OLD_COACH="coach_global=scoremax_coach(c,session['user_id']) if 'scoremax_coach' in globals() else None"
NEW_COACH="coach_global=scoremax_coach(c,session['user_id']) if show_coach and 'scoremax_coach' in globals() else None"

def functions(s):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(s).body
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def apply(root):
    path=Path(root)/"app.py"
    before=path.read_text(encoding="utf8")
    tree=ast.parse(before)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="inject_ui_preferences"]
    if len(nodes)!=1:raise RuntimeError("HIDDEN_TEMPLATE_INJECTOR_DRIFT")
    fn=ast.get_source_segment(before,nodes[0]) or ""
    if MARKER in fn:
        if (fn.count(MARKER)!=1 or fn.count(NEW_NAV)!=1 or fn.count(NEW_COACH)!=1
                or OLD_NAV in fn or OLD_COACH in fn):
            raise RuntimeError("HIDDEN_TEMPLATE_PARTIAL_REPLAY")
        return {"status":"already_applied","feature":"hide_when_existing_flags_false"}
    if fn.count(OLD_NAV)!=1 or fn.count(OLD_COACH)!=1:
        raise RuntimeError("HIDDEN_TEMPLATE_SOURCE_DRIFT")
    if "show_subject_nav=endpoint in set().union(" not in fn or        "show_coach=endpoint not in {" not in fn:
        raise RuntimeError("HIDDEN_TEMPLATE_VISIBILITY_POLICY_DRIFT")
    replaced=fn.replace(OLD_NAV,NEW_NAV,1).replace(OLD_COACH,NEW_COACH,1)
    replaced=replaced.replace(NEW_NAV, "    # "+MARKER+": preserve the accepted visibility flag.\n    "+NEW_NAV,1)
    after=before.replace(fn,replaced,1)
    compile(after,str(path),"exec")
    a,b=functions(before),functions(after)
    if a.keys()!=b.keys() or any(a[k]!=b[k] for k in a if k!="inject_ui_preferences"):
        raise RuntimeError("HIDDEN_TEMPLATE_UNRELATED_FUNCTION_CHANGE")
    path.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","read_only":True,"schema_change":False,
            "templates_changed":False,"student_access_changed":False,
            "publication_policy_changed":False,
            "before_sha256":hashlib.sha256(before.encode()).hexdigest(),
            "after_sha256":hashlib.sha256(after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("runtime_root",type=Path)
    x=p.parse_args()
    print("SCOREMAX_HIDDEN_TEMPLATE_WORK="+json.dumps(apply(x.runtime_root),sort_keys=True))
