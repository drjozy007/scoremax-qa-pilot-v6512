from __future__ import annotations
from pathlib import Path
import sys

MARKER="# PH-CROSS50-SHORT-RESPONSE-PROJECTION-V015L9CM-1"

def main()->int:
    if len(sys.argv)!=2: raise SystemExit("usage: apply_overlay.py <app_root>")
    app=Path(sys.argv[1]).resolve()
    target=app/"powerhouse_operator"/"cross50_qa_staging_contract_v015l9bt.py"
    if not target.is_file(): raise SystemExit("V015L9CM target contract missing")
    text=target.read_text(encoding="utf-8")
    if MARKER in text: return 0
    imp="from typing import Any\n"
    if imp not in text: raise SystemExit("V015L9CM import anchor missing")
    text=text.replace(imp,imp+"from powerhouse_operator.cross50_short_response_structure_v015l9cm import canonicalize_short_response_structure, assert_short_response_structure\n"+MARKER+"\n",1)
    anchor='''            material=integration._build_question_material(
                projected,opts,mp,ep,[],context,state or None,stimulus,review_item_id
            )
            canonicalize_numeric_marking(
'''
    repl='''            material=integration._build_question_material(
                projected,opts,mp,ep,[],context,state or None,stimulus,review_item_id
            )
            canonicalize_short_response_structure(
                material,subject=subject,source_question_id=source_question_id,
                source_row=source_row,effective=eff
            )
            assert_short_response_structure(
                material,subject=subject,source_question_id=source_question_id
            )
            canonicalize_numeric_marking(
'''
    if text.count(anchor)!=1: raise SystemExit(f"V015L9CM build anchor count={text.count(anchor)}")
    text=text.replace(anchor,repl,1)
    val='''    for q in payload["questions"]:
        assert_numeric_marking_contract(
'''
    vrepl='''    for q in payload["questions"]:
        assert_short_response_structure(
            q,subject=str(((q.get("curriculum") or {}).get("subject_id") or "")),
            source_question_id=str(q.get("question_id") or "")
        )
        assert_numeric_marking_contract(
'''
    if text.count(val)!=1: raise SystemExit(f"V015L9CM validation anchor count={text.count(val)}")
    text=text.replace(val,vrepl,1)
    compile(text,str(target),"exec")
    target.write_text(text,encoding="utf-8")
    print("PH_V015L9CM_OVERLAY_APPLIED short_response_options_cleared=true source_immutable=true keys_unchanged=true",flush=True)
    return 0

if __name__=="__main__": raise SystemExit(main())
