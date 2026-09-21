from __future__ import annotations
from pathlib import Path

MARKER="SCOREMAX_CROSS50_STIMULUS_SINGLE_SELECT_ALIAS_V13B_1"

def apply_cross50_stimulus_single_select_alias(root: Path) -> None:
    root=Path(root)
    target=root/"question_contract_engine.py"
    if not target.is_file():
        raise SystemExit("SCOREMAX_QA_V13B_CONTRACT_ENGINE_MISSING")
    text=target.read_text(encoding="utf-8")
    if MARKER in text:
        return
    patch=f'''\n\n# {MARKER}\n_original_canonical_family_cross50_stimulus_single = canonical_family\ndef canonical_family(value):\n    token=_text(value).strip().lower().replace("-", "_").replace(" ", "_")\n    if token=="stimulus_single_select_mcq":\n        for candidate in ("single_select_mcq","single_option_mcq","single_select","single_option","mcq","single_choice"):\n            try:\n                return _original_canonical_family_cross50_stimulus_single(candidate)\n            except QuestionContractError:\n                continue\n        return _original_canonical_family_cross50_stimulus_single(value)\n    return _original_canonical_family_cross50_stimulus_single(value)\n'''
    text += patch
    compile(text,str(target),"exec")
    target.write_text(text,encoding="utf-8")
    print("SCOREMAX_CROSS50_STIMULUS_SINGLE_SELECT_ALIAS_V13B_BUILD_PASS source_token=STIMULUS_SINGLE_SELECT_MCQ native_only=true invented_family=false fail_closed=true",flush=True)
