from __future__ import annotations
from pathlib import Path
import sys

MARKER="# PH-CROSS50-NUMERIC-MARKING-OVERLAY-V015L9CG-1"

def main()->int:
    if len(sys.argv)!=2:
        raise SystemExit("usage: apply_overlay.py <app_root>")
    app=Path(sys.argv[1]).resolve()
    target=app/"powerhouse_operator"/"cross50_qa_staging_contract_v015l9bt.py"
    if not target.is_file():
        raise SystemExit("V015L9CG target contract missing")
    text=target.read_text(encoding="utf-8")
    if MARKER in text:
        return 0

    import_anchor='from typing import Any\n'
    if import_anchor not in text:
        raise SystemExit("V015L9CG import anchor missing")
    text=text.replace(
        import_anchor,
        import_anchor+'from powerhouse_operator.cross50_numeric_marking_v015l9cg import canonicalize_numeric_marking, assert_numeric_marking_contract\n'+MARKER+'\n',
        1
    )

    build_anchor='''            material=integration._build_question_material(
                projected,opts,mp,ep,[],context,state or None,stimulus,review_item_id
            )
            a=material["architecture"]
'''
    build_repl='''            material=integration._build_question_material(
                projected,opts,mp,ep,[],context,state or None,stimulus,review_item_id
            )
            canonicalize_numeric_marking(
                material,subject=subject,source_question_id=source_question_id
            )
            assert_numeric_marking_contract(
                material,subject=subject,source_question_id=source_question_id
            )
            a=material["architecture"]
'''
    if text.count(build_anchor)!=1:
        raise SystemExit(f"V015L9CG build anchor count={text.count(build_anchor)}")
    text=text.replace(build_anchor,build_repl,1)

    validate_anchor='''    for q in payload["questions"]:
        a=q["architecture"];g=q["governance"]
'''
    validate_repl='''    for q in payload["questions"]:
        assert_numeric_marking_contract(
            q,subject=str(((q.get("curriculum") or {}).get("subject_id") or "")),
            source_question_id=str(q.get("question_id") or "")
        )
        a=q["architecture"];g=q["governance"]
'''
    if text.count(validate_anchor)!=1:
        raise SystemExit(f"V015L9CG validate anchor count={text.count(validate_anchor)}")
    text=text.replace(validate_anchor,validate_repl,1)

    compile(text,str(target),"exec")
    target.write_text(text,encoding="utf-8")
    print("PH_V015L9CG_OVERLAY_APPLIED numeric_machine_key=true display_answer_preserved=true ambiguous_fail_closed=true source_immutable=true",flush=True)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
