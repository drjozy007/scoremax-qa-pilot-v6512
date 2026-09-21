from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

def assert_cross50_stimulus_single_select_alias(root: Path) -> None:
    root=Path(root)
    target=root/"question_contract_engine.py"
    if not target.is_file():
        raise SystemExit("SCOREMAX_QA_V13B_QUAL_INPUT_MISSING")
    text=target.read_text(encoding="utf-8")
    if "SCOREMAX_CROSS50_STIMULUS_SINGLE_SELECT_ALIAS_V13B_1" not in text:
        raise SystemExit("SCOREMAX_QA_V13B_ALIAS_MARKER_MISSING")
    spec=importlib.util.spec_from_file_location("scoremax_qce_v13b_qual",target)
    if spec is None or spec.loader is None:
        raise SystemExit("SCOREMAX_QA_V13B_IMPORT_FAILED")
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    resolved=mod.canonical_family("STIMULUS_SINGLE_SELECT_MCQ")
    if not resolved or str(resolved).strip().lower()=="stimulus_single_select_mcq":
        raise SystemExit("SCOREMAX_QA_V13B_NATIVE_ALIAS_UNRESOLVED:"+repr(resolved))
    # Existing numeric alias must remain intact.
    numeric=mod.canonical_family("NUMERIC_ENTRY")
    if str(numeric)!="numerical_interpretation":
        raise SystemExit("SCOREMAX_QA_V13B_NUMERIC_ALIAS_REGRESSION:"+repr(numeric))
    print("SCOREMAX_CROSS50_STIMULUS_SINGLE_SELECT_ALIAS_V13B_QUAL_PASS resolved="+str(resolved)+" numeric_alias_preserved=true native_only=true",flush=True)
