from __future__ import annotations
from pathlib import Path

MARKER="SCOREMAX_CROSS50_PH_FAMILY_REGISTRY_V13C_1"

# Explicit governed aliases only. Each alias resolves through the pre-existing
# ScoreMax canonical_family implementation; no new native family is invented.
ALIASES={
    "two_tier_diagnostic_single_best_pair": (
        "standard_mcq","single_choice","single_select_mcq","single_option_mcq","mcq"
    ),
    "ordering_sequence": (
        "ordering","ordering_sequence","sequence_ordering"
    ),
    "cloze_single_select": (
        "cloze_single_select","cloze","standard_mcq","single_choice","mcq"
    ),
}

def apply_cross50_ph_family_registry(root: Path) -> None:
    root=Path(root)
    target=root/"question_contract_engine.py"
    if not target.is_file():
        raise SystemExit("SCOREMAX_QA_V13C_CONTRACT_ENGINE_MISSING")
    text=target.read_text(encoding="utf-8")
    if MARKER in text:
        return
    patch=f'''\n\n# {MARKER}\n_original_canonical_family_cross50_registry = canonical_family\n_CROSS50_PH_FAMILY_ALIASES = {ALIASES!r}\ndef canonical_family(value):\n    token=_text(value).strip().lower().replace("-", "_").replace(" ", "_")\n    candidates=_CROSS50_PH_FAMILY_ALIASES.get(token)\n    if candidates:\n        for candidate in candidates:\n            try:\n                return _original_canonical_family_cross50_registry(candidate)\n            except QuestionContractError:\n                continue\n        raise QuestionContractError("PH_FAMILY_ALIAS_UNRESOLVED::"+token)\n    return _original_canonical_family_cross50_registry(value)\n'''
    text += patch
    compile(text,str(target),"exec")
    target.write_text(text,encoding="utf-8")
    print("SCOREMAX_CROSS50_PH_FAMILY_REGISTRY_V13C_BUILD_PASS explicit_aliases=3 invented_family=false unknown_fail_closed=true",flush=True)
