#!/usr/bin/env python3
from __future__ import annotations
import ast,json,sys
from pathlib import Path

POLICY="SCOREMAX-PH-ADMISSION-EXAM-SCOPE-QUAL-20261007-1"
ROOT=Path(sys.argv[1] if len(sys.argv)>1 else "scoremax_runtime_v669b")

def emit(event,**kw):
    print("SCOREMAX_PH_ADMISSION_SCOPE "+json.dumps({"event":event,"policy":POLICY,**kw},sort_keys=True),flush=True)

def extract(path,names):
    text=Path(path).read_text(encoding="utf-8");tree=ast.parse(text);lines=text.splitlines();out=[]
    found=set()
    for n in tree.body:
        if isinstance(n,ast.FunctionDef) and n.name in names:
            out.append("\n".join(lines[n.lineno-1:n.end_lineno]));found.add(n.name)
    if set(names)!=found:raise RuntimeError("MISSING_HELPERS")
    ns={};exec(compile("\n\n".join(out),str(path),"exec"),ns);return ns

def main():
    ns=extract(ROOT/"scoremax_integration_v1.py",["_ph_release_scope_compatible","_ph_release_scope_mismatch"])
    mismatch=ns["_ph_release_scope_mismatch"]
    fsc={"market_id":"PK","programme_id":"FSC_PART_I","subject_id":"CHEMISTRY","chapter_id":"CHAPTER::CHEMISTRY::11::05",
         "qualification_id":"FSC","display":{"programme":"FSc Part 1","subject":"Chemistry"}}
    mdcat={"market_id":"PK","programme_id":"MDCAT","subject_id":"CHEMISTRY","chapter_id":"MDCAT::CHEMISTRY::UNIT::03"}
    ecat={"market_id":"PK","programme_id":"ECAT","subject_id":"CHEMISTRY","chapter_id":"ECAT::CHEMISTRY::UNIT::03"}
    cross_subject=dict(mdcat,subject_id="PHYSICS")
    bad_market=dict(mdcat,market_id="IN")
    other={"market_id":"PK","programme_id":"GRADE_10","subject_id":"CHEMISTRY","chapter_id":"CH10"}
    normal_bad={"market_id":"PK","programme_id":"FSC_PART_I","subject_id":"CHEMISTRY","chapter_id":"OTHER_CHAPTER"}

    if mismatch(fsc,mdcat)!=[]:raise RuntimeError("FSC_MDCAT_NOT_ALLOWED")
    if mismatch(fsc,ecat)!=[]:raise RuntimeError("FSC_ECAT_NOT_ALLOWED")
    if mismatch(fsc,cross_subject)!=[]:raise RuntimeError("PH_CROSS_SUBJECT_ALLOCATION_NOT_ALLOWED")
    if "market_id" not in mismatch(fsc,bad_market):raise RuntimeError("CROSS_MARKET_NOT_BLOCKED")
    if "programme_id" not in mismatch(other,mdcat):raise RuntimeError("NON_FSC_TO_MDCAT_NOT_BLOCKED")
    if "chapter_id" not in mismatch(fsc,normal_bad):raise RuntimeError("ORDINARY_CHAPTER_MISMATCH_NOT_BLOCKED")

    emit("PASS",fsc_to_mdcat=True,fsc_to_ecat=True,ph_cross_subject_allocation=True,cross_market_blocked=True,
         non_fsc_source_blocked=True,ordinary_chapter_mismatch_blocked=True,production_mutation=False,learner_release=False)
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        emit("FAIL",error_type=type(exc).__name__,detail=str(exc)[:2000],production_mutation=False,learner_release=False)
        raise
