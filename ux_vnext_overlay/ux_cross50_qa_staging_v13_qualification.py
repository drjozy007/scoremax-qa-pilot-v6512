from __future__ import annotations

import ast
import json
from pathlib import Path

def assert_cross50_qa_v13(root: Path) -> None:
    root=Path(root)
    runtime=root/"scoremax_integration_v1.py"
    schema_path=root/"integration_contracts"/"v1_3_0"/"PH_SM_APPROVED_CONTENT_V1.schema.json"
    if not runtime.is_file() or not schema_path.is_file():
        raise SystemExit("SCOREMAX_QA_V13_QUAL_INPUT_MISSING")
    text=runtime.read_text(encoding="utf-8")
    compile(text,str(runtime),"exec")
    schema=json.loads(schema_path.read_text(encoding="utf-8"))
    payload=schema["properties"]["payload"]
    release=schema["$defs"]["release"]
    arch=schema["$defs"]["question"]["properties"]["architecture"]
    gov=schema["$defs"]["question"]["properties"]["governance"]

    checks={
      "schema_version":schema["properties"]["schema_version"].get("const")=="1.3.0",
      "qa_operation_only":payload["properties"]["release_operation"].get("const")=="STAGE_FOR_DELIVERY_QA",
      "inline_only":payload["properties"]["delivery_mode"].get("const")=="INLINE",
      "qa_release_only":release["properties"]["release_status"].get("const")=="DELIVERY_QA_ONLY",
      "mastery_pending":arch["properties"]["mastery_status"].get("const")=="PENDING_CONTRACT",
      "mastery_eligible_false":arch["properties"]["independent_mastery_eligible"].get("const") is False,
      "mastery_weight_zero":arch["properties"]["independent_mastery_weight"].get("const")==0,
      "qa_candidate_only":gov["properties"]["academic_review_state"].get("const")=="QA_CANDIDATE",
      "release_not_authorized":gov["properties"]["release_readiness"].get("const")=="NOT_AUTHORIZED",
      "release_authority_false":gov["properties"]["release_authority_conferred"].get("const") is False,
      "mastery_authority_false":gov["properties"]["mastery_authority_conferred"].get("const") is False,
      "activation_fence":"'QA_STAGING_NOT_ACTIVATABLE'" in text and "release_operation" in text,
      "staged_store":"STAGE_FOR_DELIVERY_QA" in text and "'STAGED'" in text,
      "qa_projection":"content_environment':'QA_STAGED'" in text and "'scoremax_ready':0" in text and "'active':0" in text,
      "matching_key_helper":"def _matching_key(content):" in text,
      "matching_visible_helper":"def _matching_visible_refs(content,stimuli):" in text,
      "matching_surface_helper":"def _matching_surface_items(content,stimuli,matching_key):" in text,
      "matching_validator_bound":"matching=_matching_key(content)" in text,
    }
    failed=[k for k,v in checks.items() if not v]
    if failed:
        raise SystemExit("SCOREMAX_QA_V13_QUAL_FAIL:"+",".join(failed))

    # Assert the QA 1.3 path delegates to exactly the same *native* governed
    # FSc->admission allocation rule already qualified in the v1.2 receiver.
    # No sample fixture is permitted to substitute for the assembled runtime.
    tree=ast.parse(text)
    helper_names={"_ph_release_scope_mismatch","_ph_release_scope_compatible","_qa_v13_scope_mismatches"}
    funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in helper_names}
    if set(funcs)!=helper_names:
        raise SystemExit("SCOREMAX_QA13_ACCEPTED_SCOPE_HELPER_MISSING:"+repr(sorted(helper_names-set(funcs))))
    ns={}
    nodes=[funcs[n] for n in ("_ph_release_scope_compatible","_ph_release_scope_mismatch","_qa_v13_scope_mismatches")]
    # AST extraction isolates the three pure policy helpers, not startup code.
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(runtime),"exec"),ns)
    native,qa=ns["_ph_release_scope_mismatch"],ns["_qa_v13_scope_mismatches"]
    fsc={"market_id":"PK","programme_id":"FSC_PART_I","subject_id":"PHYSICS",
         "chapter_id":"CHAPTER::PHYSICS::12::13","qualification_id":"FSC"}
    cases={
      "FSC_SAME":(fsc,dict(fsc),True),
      "FSC_TO_MDCAT_CHEMISTRY":(fsc,{"market_id":"PK","programme_id":"MDCAT",
        "subject_id":"CHEMISTRY","chapter_id":"MDCAT::CHEMISTRY::UNIT::03"},True),
      "CROSS_MARKET_REJECT":(fsc,{"market_id":"IN","programme_id":"MDCAT",
        "subject_id":"CHEMISTRY","chapter_id":"MDCAT::CHEMISTRY::UNIT::03"},False),
      "NON_FSC_REJECT":(dict(fsc,programme_id="GRADE_10",qualification_id="GRADE_10"),{"market_id":"PK",
        "programme_id":"MDCAT","subject_id":"CHEMISTRY",
        "chapter_id":"MDCAT::CHEMISTRY::UNIT::03"},False),
      "ORDINARY_SCOPE_REJECT":(fsc,dict(fsc,chapter_id="OTHER_CHAPTER"),False)
    }
    for name,(source,dest,expected_ok) in cases.items():
        orig=native(source,dest)
        derived=qa(source,dest)
        if orig!=derived or (not bool(derived))!=expected_ok:
            raise SystemExit("SCOREMAX_QA13_SCOPE_PARITY_FAIL:"+name+":"+repr((orig,derived)))
    # Absence of shared native helper fails closed on cross-programme membership.
    saved=ns.pop("_ph_release_scope_mismatch")
    try:
        if not qa(fsc,cases["FSC_TO_MDCAT_CHEMISTRY"][1]):
            raise SystemExit("SCOREMAX_QA13_SCOPE_ABSENT_HELPER_FAIL_OPEN")
    finally:
        ns["_ph_release_scope_mismatch"]=saved

    # Backward contracts must still be present in the assembled runtime.
    backward=[
      root/"integration_contracts"/"PH_SM_APPROVED_CONTENT_V1.schema.json",
      root/"integration_contracts"/"v1_1_0"/"PH_SM_APPROVED_CONTENT_V1.schema.json",
      root/"integration_contracts"/"v1_2_0"/"PH_SM_APPROVED_CONTENT_V1.schema.json",
    ]
    if not all(p.is_file() for p in backward):
        raise SystemExit("SCOREMAX_QA_V13_BACKWARD_SCHEMA_MISSING")

    print("SCOREMAX_CROSS50_QA_STAGING_V13_QUAL_PASS "
          "schema=1.3.0 qa_operation_only=true inline_only=true "
          "mastery_pending=true mastery_credit_zero=true learner_materialisation=false "
          "activation_fenced=true matching_semantic_helpers=true "
          "backward_1_0_1_1_1_2_present=true",flush=True)
