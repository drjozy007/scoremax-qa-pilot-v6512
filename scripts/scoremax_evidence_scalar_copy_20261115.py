"""Copy validated immutable student evidence without nested deepcopy overhead.

Pure scalar sqlite row values are immutable. A fresh shallow dict copy per row
prevents downstream mutations from touching request-cache-owned dictionaries.
Any unexpected nested fields fall back to standard deepcopy so behavior cannot
be weakened by future metadata additions. Cache remains student+programme
partitioned and only on read-only GET; no shared cache or DB mutation.
"""
from __future__ import annotations
import ast,hashlib,json
from pathlib import Path

MARKER="SCOREMAX_EVIDENCE_SCALAR_COPY_20261115"
OLD_KEY="    _key=(student_id,programme)\n"
NEW_KEY="""    _key=(student_id,programme)
    # SCOREMAX_EVIDENCE_SCALAR_COPY_20261115: native SQL scalar rows can be
    # copied one dictionary at a time; keep a recursive-copy fallback for
    # unknown future nested metadata. Never return cache-owned dictionaries.
    def _clone_frozen_rows(_items):
        _scalar=(str,int,float,bool,bytes,type(None))
        return [dict(_record) if type(_record) is dict and
                all(type(_value) in _scalar for _value in _record.values())
                else deepcopy(_record) for _record in _items]
"""
OLD_CACHE_RETURN="            return deepcopy([r for r in _rows"
NEW_CACHE_RETURN="            return _clone_frozen_rows([r for r in _rows"
OLD_ASSIGN="        _entries[_key]=deepcopy(out)"
NEW_ASSIGN="        _entries[_key]=_clone_frozen_rows(out)"
OLD_TAIL_RETURN="        return deepcopy([r for r in out"
NEW_TAIL_RETURN="        return _clone_frozen_rows([r for r in out"

def functions(src):
    return {node.name:ast.dump(node,include_attributes=False)
            for node in ast.parse(src).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}

def apply(root:Path):
    p=Path(root)/"app.py"
    before=p.read_text(encoding="utf8")
    funcs=[x for x in ast.parse(before).body
           if isinstance(x,ast.FunctionDef) and x.name=="learner_answer_evidence"]
    if len(funcs)!=1:raise RuntimeError("SCALAR_COPY_READER_DRIFT")
    old=ast.get_source_segment(before,funcs[0]) or ""
    if MARKER in old:
        if old.count(MARKER)!=1 or NEW_KEY not in old or NEW_ASSIGN not in old:
            raise RuntimeError("SCALAR_COPY_PARTIAL_REPLAY")
        return {"status":"already_applied","request_scoped":True}
    for snippet in [OLD_KEY,OLD_CACHE_RETURN,OLD_ASSIGN,OLD_TAIL_RETURN]:
        if old.count(snippet)!=1:raise RuntimeError("SCALAR_COPY_SOURCE_DRIFT:"+snippet[:48])
    if "SCOREMAX_REQUEST_FROZEN_EVIDENCE_REUSE_20261114" not in old:
        raise RuntimeError("SCALAR_COPY_EVIDENCE_AUTHORITY_MISSING")
    new=old.replace(OLD_KEY,NEW_KEY,1).replace(OLD_CACHE_RETURN,NEW_CACHE_RETURN,1)
    new=new.replace(OLD_ASSIGN,NEW_ASSIGN,1).replace(OLD_TAIL_RETURN,NEW_TAIL_RETURN,1)
    after=before.replace(old,new,1)
    compile(after,str(p),"exec")
    a,b=functions(before),functions(after)
    if a.keys()!=b.keys() or any(a[k]!=b[k] for k in a if k!="learner_answer_evidence"):
        raise RuntimeError("SCALAR_COPY_UNRELATED_FUNCTION_CHANGE")
    p.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","read_only":True,"schema_change":False,
            "academic_predicates_unchanged":True,"cache_scope_unchanged":True,
            "before_sha256":hashlib.sha256(before.encode()).hexdigest(),
            "after_sha256":hashlib.sha256(after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("runtime_root",type=Path)
    arg=p.parse_args()
    print("SCOREMAX_EVIDENCE_SCALAR_COPY="+json.dumps(apply(arg.runtime_root),sort_keys=True))
