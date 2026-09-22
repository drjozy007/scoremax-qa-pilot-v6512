from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

EXPECTED={
 "NUMERIC_ENTRY":None,
 "STANDARD_MCQ":None,
 "SHORT_RESPONSE":None,
 "TWO_TIER_DIAGNOSTIC_SINGLE_BEST_PAIR":None,
 "ORDERING_SEQUENCE":None,
 "ORDERING_SEQUENCE_SINGLE_SELECT":None,
 "CLOZE_SINGLE_SELECT":None,
}

def assert_cross50_ph_family_registry(root: Path) -> None:
    root=Path(root)
    target=root/"question_contract_engine.py"
    text=target.read_text(encoding="utf-8")
    if "SCOREMAX_CROSS50_PH_FAMILY_REGISTRY_V13C_1" not in text:
        raise SystemExit("SCOREMAX_QA_V13C_REGISTRY_MARKER_MISSING")
    spec=importlib.util.spec_from_file_location("scoremax_qce_v13c_qual",target)
    if spec is None or spec.loader is None:
        raise SystemExit("SCOREMAX_QA_V13C_IMPORT_FAILED")
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    resolved={}
    for token in EXPECTED:
        try:
            value=mod.canonical_family(token)
        except Exception as exc:
            raise SystemExit("SCOREMAX_QA_V13C_CROSS50_FAMILY_UNRESOLVED:"+token+":"+repr(exc))
        if not str(value).strip():
            raise SystemExit("SCOREMAX_QA_V13C_EMPTY_RESOLUTION:"+token)
        resolved[token]=str(value)
    # Existing aliases must remain semantically intact.
    if resolved["NUMERIC_ENTRY"]!="numerical_interpretation":
        raise SystemExit("SCOREMAX_QA_V13C_NUMERIC_REGRESSION:"+repr(resolved["NUMERIC_ENTRY"]))
    if resolved["TWO_TIER_DIAGNOSTIC_SINGLE_BEST_PAIR"] not in {"standard_mcq","single_choice","single_select_mcq","single_option_mcq","mcq"}:
        raise SystemExit("SCOREMAX_QA_V13C_TWO_TIER_NOT_SINGLE_SELECT:"+repr(resolved["TWO_TIER_DIAGNOSTIC_SINGLE_BEST_PAIR"]))
    # Unknown family must still fail closed.
    try:
        mod.canonical_family("PH_UNKNOWN_FAMILY_MUST_FAIL")
    except mod.QuestionContractError:
        pass
    else:
        raise SystemExit("SCOREMAX_QA_V13C_UNKNOWN_DID_NOT_FAIL_CLOSED")
    print("SCOREMAX_CROSS50_PH_FAMILY_REGISTRY_V13C_QUAL_PASS resolved="+repr(resolved)+" unknown_fail_closed=true",flush=True)
