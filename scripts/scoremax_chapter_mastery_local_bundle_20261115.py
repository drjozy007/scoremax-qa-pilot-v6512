"""Eliminate chapter-card policy/blueprint/access N+1 reads per subject GET.

This source-bound overlay extends the ACCEPTED chapter mastery routine by an
optional local read bundle, consumed only inside _chapter_snapshots. It reuses
the same native policies, active blueprint and student access for all cards
of one subject on the SAME connection during ONE GET request. Coverage,
chapter-scoped eligibility, PH approval, prior family evidence, mastery
selection, and exact learner output remain fully authoritative and unchanged.

No cross-request/shared cache, no schema, no academic or release policy edit.
Direct chapter_mastery_opportunity callers keep their original execution.
"""
from __future__ import annotations
import ast, hashlib, json, textwrap
from pathlib import Path

MARKER="SCOREMAX_CHAPTER_MASTERY_LOCAL_BUNDLE_20261115"
OLD_HEADER="def chapter_mastery_opportunity(c,student_id,subject,chapter,programme=''):"
NEW_HEADER="def chapter_mastery_opportunity(c,student_id,subject,chapter,programme='',_read_bundle=None):"
OLD_BLUEPRINT="governing_blueprint=active_assessment_blueprint(c,programme) if programme else None"
NEW_BLUEPRINT="""if _read_bundle is None or not programme:
    governing_blueprint=active_assessment_blueprint(c,programme) if programme else None
else:
    _b=_read_bundle.setdefault('blueprints',{})
    if programme not in _b:
        _b[programme]=active_assessment_blueprint(c,programme)
    governing_blueprint=_b[programme]"""
OLD_POLICY="policy=mastery_policy(c,level)"
NEW_POLICY="""if _read_bundle is None:
    policy=mastery_policy(c,level)
else:
    _p=_read_bundle.setdefault('policies',{})
    if level not in _p:
        _p[level]=mastery_policy(c,level)
    policy=_p[level]"""
OLD_ACCESS="access=get_access_profile(c,student_id)"
NEW_ACCESS="""if _read_bundle is None:
    access=get_access_profile(c,student_id)
else:
    _a=_read_bundle.setdefault('access',{})
    if student_id not in _a:
        _a[student_id]=get_access_profile(c,student_id)
    access=_a[student_id]"""
OLD_CHAPTER_LOC="    out=[]\n    for idx,item in enumerate(browse_items,1):"
NEW_CHAPTER_LOC="    _mastery_card_bundle={}  # "+MARKER+": one subject-page local read bundle\n    out=[]\n    for idx,item in enumerate(browse_items,1):"
OLD_CARD_CALL="""        mastery=runtime.chapter_mastery_opportunity(
            conn,student_id,subject,source_chapter,programme
        )"""
NEW_CARD_CALL="""        mastery=runtime.chapter_mastery_opportunity(
            conn,student_id,subject,source_chapter,programme,
            _read_bundle=_mastery_card_bundle
        )"""

def fn_dict(source):
    return {x.name:ast.dump(x,include_attributes=False)
            for x in ast.parse(source).body
            if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef))}

def replace_once(content,old,new,who):
    if content.count(old)!=1:
        raise RuntimeError("MASTERy_BUNDLE_SOURCE_DRIFT:"+who+":"+str(content.count(old)))
    return content.replace(old,new,1)

def replace_statement_block(source,statement,new_block,where):
    # Match a complete original Python line; derive indentation from THAT line
    # rather than embedding guessed four/eight-space indentation in a delta.
    # This supports both loop-body and function-body replacements reliably.
    lines=source.splitlines(keepends=True)
    found=[i for i,line in enumerate(lines) if line.strip()==statement.strip()]
    if len(found)!=1:
        raise RuntimeError("MASTERY_BUNDLE_STATEMENT_DRIFT:"+where+":"+str(len(found)))
    index=found[0]
    original=lines[index]
    indent=original[:len(original)-len(original.lstrip(' \\t'))]
    block=textwrap.dedent(new_block).strip('\\n').splitlines()
    if not block or any(not part.strip() for part in block):
        raise RuntimeError("MASTERY_BUNDLE_INVALID_BLOCK:"+where)
    lines[index]='\\n'.join(indent+part for part in block)
    if original.endswith('\\n'):lines[index]+='\\n'
    return ''.join(lines)

def extract(src,name):
    nodes=[n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name==name]
    if len(nodes)!=1:raise RuntimeError("MASTERY_BUNDLE_FUNCTION_CARDINALITY:"+name)
    return ast.get_source_segment(src,nodes[0]) or ""

def apply(root):
    root=Path(root)
    app_path=root/"app.py"
    cards_path=root/"ux_student_batch.py"
    before=app_path.read_text(encoding="utf8")
    card_before=cards_path.read_text(encoding="utf8")
    mastery=extract(before,"chapter_mastery_opportunity")
    cards=extract(card_before,"_chapter_snapshots")
    if MARKER in cards:
        guards=("_b=_read_bundle.setdefault('blueprints',{})",
                "_p=_read_bundle.setdefault('policies',{})",
                "_a=_read_bundle.setdefault('access',{})",
                "_read_bundle=None")
        if (cards.count(MARKER)!=1 or NEW_CARD_CALL not in cards
            or NEW_CHAPTER_LOC not in cards or NEW_HEADER not in mastery
            or any(marker not in mastery for marker in guards)):
            raise RuntimeError("MASTERY_BUNDLE_PARTIAL_REPLAY")
        return {"status":"already_applied","request_local":True}
    if mastery.count(OLD_HEADER)!=1:
        raise RuntimeError("MASTERY_BUNDLE_HEADER_DRIFT")
    for old in (OLD_CHAPTER_LOC,OLD_CARD_CALL):
        if cards.count(old)!=1:raise RuntimeError("MASTERY_BUNDLE_CARD_FUNC_DRIFT:"+old[:65])
    for required in (
        "eligible_for_formal_mastery(r)",
        "select_mastery_coverage_questions(",
        "mastery_coverage_contract(",
        "get_access_profile(",
        "_mastery_previous_families(",
        "COALESCE(q.chapter,'')=?",
        "LIVE_MARKABLE_TYPES",
    ):
        if required not in mastery:raise RuntimeError("MASTERY_BUNDLE_GOVERNANCE_DRIFT:"+required)
    if "SCOREMAX_NAV_CHAPTER_EVIDENCE_ONCE_20261114" not in cards:
        raise RuntimeError("MASTERY_BUNDLE_ACCEPTED_EVIDENCE_BATCH_MISSING")
    changed=replace_once(mastery,OLD_HEADER,NEW_HEADER,"mastery_header")
    for old,new,where in ((OLD_BLUEPRINT,NEW_BLUEPRINT,"blueprint"),
                          (OLD_POLICY,NEW_POLICY,"policy"),
                          (OLD_ACCESS,NEW_ACCESS,"access")):
        changed=replace_statement_block(changed,old,new,where)
    card_changed=replace_once(cards,OLD_CHAPTER_LOC,NEW_CHAPTER_LOC,"local_cards")
    card_changed=replace_once(card_changed,OLD_CARD_CALL,NEW_CARD_CALL,"mastery_call")
    after=replace_once(before,mastery,changed,"mastery_ast")
    card_after=replace_once(card_before,cards,card_changed,"chapter_ast")
    compile(after,str(app_path),"exec")
    compile(card_after,str(cards_path),"exec")
    o,n=fn_dict(before),fn_dict(after)
    co,cn=fn_dict(card_before),fn_dict(card_after)
    if (o.keys()!=n.keys()
        or any(o[x]!=n[x] for x in o if x!="chapter_mastery_opportunity")
        or co.keys()!=cn.keys()
        or any(co[x]!=cn[x] for x in co if x!="_chapter_snapshots")):
        raise RuntimeError("MASTERY_BUNDLE_UNRELATED_FUNCTION_CHANGED")
    app_path.write_text(after,encoding="utf8",newline="\n")
    cards_path.write_text(card_after,encoding="utf8",newline="\n")
    return {
        "status":"applied","function_changes":["chapter_mastery_opportunity","_chapter_snapshots"],
        "scope":"per_subject_http_GET_only","original_direct_calls_unchanged":True,
        "source_guarded":True,"academic_policy_change":False,"db_migration":False,
        "app_before_sha256":hashlib.sha256(before.encode()).hexdigest(),
        "app_after_sha256":hashlib.sha256(after.encode()).hexdigest(),
        "cards_before_sha256":hashlib.sha256(card_before.encode()).hexdigest(),
        "cards_after_sha256":hashlib.sha256(card_after.encode()).hexdigest(),
    }
if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("runtime_root",type=Path)
    args=p.parse_args()
    print("SCOREMAX_CHAPTER_MASTERY_LOCAL_BUNDLE="+json.dumps(apply(args.runtime_root),sort_keys=True))
