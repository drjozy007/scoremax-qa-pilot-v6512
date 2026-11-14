"""Bounded request-only reuse of ScoreMax's authoritative frozen student evidence.

Preserve the native evidence reader and its checks. For safe student GET navigation,
validate the student's programme evidence once, then apply the exact original
subject/chapter filters to copies of that validated result.

No global/shared cache, persistent state, schema, marking, or policy changes.
Refuse application if the accepted runtime reader has drifted.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path

MARKER = "SCOREMAX_REQUEST_FROZEN_EVIDENCE_REUSE_20261114"
HEAD = """    import hashlib
    programme=canonical_programme(student_programme(c,student_id) if programme is None else programme)
    aliases=_programme_aliases(programme)
    if not aliases:return []
"""
NEW_HEAD = """    import hashlib
    programme=canonical_programme(student_programme(c,student_id) if programme is None else programme)
    aliases=_programme_aliases(programme)
    if not aliases:return []
    # SCOREMAX_REQUEST_FROZEN_EVIDENCE_REUSE_20261114: no cross-request cache.
    # These learner navigation routes are read-only. Do not cache POST, writes,
    # attempt-specific reads, or non-navigation GETs.
    from flask import g, has_request_context, request
    from copy import deepcopy
    _reuse=(attempt_id is None and has_request_context()
            and request.method=='GET'
            and (request.path in ('/student/learn-vnext','/student/chapter')
                 or request.path.startswith('/student/subject/')
                 or request.path.startswith('/student/catalogue/')))
    _key=(student_id,programme)
    if _reuse:
        _entries=getattr(g,'_scoremax_frozen_evidence_20261114',None)
        if _entries is not None and _key in _entries:
            _rows=_entries[_key]
            return deepcopy([r for r in _rows
                if (not subject or str(r.get('subject') or '').casefold()==subject.strip().casefold())
                and (not chapter or str(r.get('chapter') or '').casefold()==chapter.strip().casefold())])
"""
FILTER_SUBJECT="    if subject and str(context.get('subject') or '').casefold()!=subject.strip().casefold():continue"
FILTER_CHAPTER="    if chapter and str(context.get('chapter') or '').casefold()!=chapter.strip().casefold():continue"
NEW_FILTER_SUBJECT="    if not _reuse and subject and str(context.get('subject') or '').casefold()!=subject.strip().casefold():continue"
NEW_FILTER_CHAPTER="    if not _reuse and chapter and str(context.get('chapter') or '').casefold()!=chapter.strip().casefold():continue"
TAIL="    return out"
NEW_TAIL="""    if _reuse:
        _entries=getattr(g,'_scoremax_frozen_evidence_20261114',None)
        if _entries is None:
            _entries={}
            g._scoremax_frozen_evidence_20261114=_entries
        # Frozen rows are validated by exactly the existing checksum and
        # contextual authority checks. Never return cache-owned dictionaries.
        _entries[_key]=deepcopy(out)
        return deepcopy([r for r in out
            if (not subject or str(r.get('subject') or '').casefold()==subject.strip().casefold())
            and (not chapter or str(r.get('chapter') or '').casefold()==chapter.strip().casefold())])
    return out"""

def apply(root:Path):
    path=Path(root)/"app.py"
    before=path.read_text(encoding="utf8")
    tree=ast.parse(before)
    matches=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="learner_answer_evidence"]
    if len(matches)!=1:
        raise RuntimeError("EVIDENCE_READER_NOT_UNIQUE")
    func=ast.get_source_segment(before,matches[0]) or ""
    if MARKER in func:
        if func.count(MARKER)!=1 or NEW_HEAD not in func or NEW_TAIL not in func:
            raise RuntimeError("EVIDENCE_REQUEST_CACHE_PARTIAL_REPLAY")
        return {"status":"already_applied","read_only":True}
    checks=((HEAD,1),(FILTER_SUBJECT,1),(FILTER_CHAPTER,1),(TAIL,1))
    for snippet,count in checks:
        if func.count(snippet)!=count:
            raise RuntimeError("EVIDENCE_REQUEST_CACHE_SOURCE_DRIFT:"+snippet[:72])
    if "ORDER BY a.created_at DESC,aa.id DESC" not in func or "checksum_sha256" not in func:
        raise RuntimeError("EVIDENCE_FROZEN_AUTHORITY_GUARDS_MISSING")
    revised=(func.replace(HEAD,NEW_HEAD,1)
                 .replace(FILTER_SUBJECT,NEW_FILTER_SUBJECT,1)
                 .replace(FILTER_CHAPTER,NEW_FILTER_CHAPTER,1)
                 .replace(TAIL,NEW_TAIL,1))
    after=before.replace(func,revised,1)
    compile(after,str(path),"exec")
    orig={n.name:ast.dump(n,include_attributes=False) for n in tree.body
          if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    now={n.name:ast.dump(n,include_attributes=False) for n in ast.parse(after).body
         if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    if orig.keys()!=now.keys() or any(orig[k]!=now[k] for k in orig if k!="learner_answer_evidence"):
        raise RuntimeError("EVIDENCE_REQUEST_CACHE_UNRELATED_CHANGE")
    path.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","function":"learner_answer_evidence","no_shared_cache":True,
            "no_schema_change":True,"no_academic_rule_change":True,
            "before_sha256":hashlib.sha256(before.encode()).hexdigest(),
            "after_sha256":hashlib.sha256(after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("runtime_root",type=Path)
    args=parser.parse_args()
    print("SCOREMAX_FROZEN_EVIDENCE_REQUEST_REUSE="+json.dumps(apply(args.runtime_root),sort_keys=True))
