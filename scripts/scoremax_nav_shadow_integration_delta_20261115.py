"""Install opt-in shadow inventory reader into generated ScoreMax runtime only.

Source-bound delta follows accepted ScoreMax runtime reconstruction and the
existing PR #55 fused-subject inventory installer. Keeps the original query
exactly as a fallback, and does not change app boot, any mutation, question
content, release scope, marking, learner UI or the production deployment.
"""
import ast
import hashlib
import json
from pathlib import Path
from scoremax_fused_subject_inventory_20261114 import NEW_LIVE

MARKER="SCOREMAX_NAV_SHADOW_OPTIN_20261115"
START="    inventory=c.execute(f"
END="    live_rows=[]"
a=NEW_LIVE.find(START)
b=NEW_LIVE.find(END,a)
if a<0 or b<=a:raise RuntimeError("SHADOW_INSTALLER_FUSED_ANCHOR_DRIFT")
ORIGINAL=NEW_LIVE[a:b]
REPLACEMENT="""    # SCOREMAX_NAV_SHADOW_OPTIN_20261115: unchanged native fallback on OFF,
    # stale, absent, unqualified or otherwise invalid shadow projection.
    from scoremax_shadow_navigation_v1 import try_shadow_inventory
    inventory=try_shadow_inventory(c,programme)
    if inventory is None:
"""+ "".join("    "+line if line.strip() else line for line in ORIGINAL.splitlines(keepends=True))

def _fn_map(text):
    return {node.name:ast.dump(node,include_attributes=False)
            for node in ast.parse(text).body
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}

def apply(root):
    root=Path(root)
    app=root/"app.py"
    helper_src=Path(__file__).with_name("scoremax_shadow_navigation_v1.py")
    helper=root/"scoremax_shadow_navigation_v1.py"
    source=app.read_text(encoding="utf8")
    funcs=[x for x in ast.parse(source).body
           if isinstance(x,ast.FunctionDef) and x.name=="_subject_map"]
    if len(funcs)!=1:raise RuntimeError("SHADOW_INSTALLER_SUBJECT_MAP_DRIFT")
    original_fn=ast.get_source_segment(source,funcs[0]) or ""
    if MARKER in original_fn:
        if original_fn.count(MARKER)!=1 or REPLACEMENT not in original_fn:
            raise RuntimeError("SHADOW_INSTALLER_PARTIAL_REPLAY")
        if not helper.is_file() or helper.read_bytes()!=helper_src.read_bytes():
            raise RuntimeError("SHADOW_HELPER_CONTENT_DRIFT")
        return {"status":"already_applied","enabled_by_default":False}
    if ORIGINAL not in original_fn or original_fn.count(ORIGINAL)!=1:
        raise RuntimeError("SHADOW_INSTALLER_NATIVE_FALLBACK_MISSING")
    helper_bytes=helper_src.read_bytes()
    if helper.exists() and helper.read_bytes()!=helper_bytes:
        raise RuntimeError("SHADOW_HELPER_EXISTING_BYTES_CONFLICT")
    altered=source.replace(original_fn,original_fn.replace(ORIGINAL,REPLACEMENT,1),1)
    compile(altered,str(app),"exec")
    orig=_fn_map(source);new=_fn_map(altered)
    if orig.keys()!=new.keys() or any(orig[k]!=new[k] for k in orig if k!="_subject_map"):
        raise RuntimeError("SHADOW_INSTALLER_UNRELATED_RUNTIME_CHANGE")
    if not helper.exists():helper.write_bytes(helper_bytes)
    app.write_text(altered,encoding="utf8",newline="\n")
    return {"status":"applied","function":"_subject_map","enabled_by_default":False,
      "native_fallback_unchanged":True,"read_only":True,"new_file":"scoremax_shadow_navigation_v1.py",
      "original_runtime_hash":hashlib.sha256(source.encode()).hexdigest(),
      "candidate_runtime_hash":hashlib.sha256(altered.encode()).hexdigest(),
      "helper_sha256":hashlib.sha256(helper_bytes).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("runtime_root",type=Path);a=p.parse_args()
    print("SCOREMAX_NAV_SHADOW_INSTALLER="+json.dumps(apply(a.runtime_root),sort_keys=True))
