"""Fail-closed reuse of ScoreMax's native text-entry family for PH constructed Cloze.

This is a common contract boundary: do not misclassify Cloze as MCQ merely to
stage a release. The ordinary native answer validator remains mandatory.
"""
from __future__ import annotations

import ast
from pathlib import Path

MARKER = "SM-SHARED-PH-CLOZE-TEXT-ENTRY-20261031-1"
CANDIDATES = ("fill_blank", "fill_in_blank", "cloze")
TEXT_FAMILIES = frozenset(CANDIDATES)


def apply(root: Path) -> None:
    path = Path(root) / "question_contract_engine.py"
    if not path.is_file():
        raise RuntimeError("ACCEPTED_SCOREMAX_CONTRACT_ENGINE_MISSING")
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        return
    tree = ast.parse(source)
    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if not {"canonical_family", "runtime_type_from_row"}.issubset(names):
        raise RuntimeError("SCOREMAX_NATIVE_FAMILY_BOUNDARY_DRIFT")
    patch = '''
# SM-SHARED-PH-CLOZE-TEXT-ENTRY-20261031-1
# Never coerce a constructed Cloze into MCQ or rubric-only response.
_prior_canonical_family_for_ph_cloze = canonical_family
def canonical_family(value):
    token = _text(value).strip().lower().replace("-", "_").replace(" ", "_")
    if token != "cloze_constructed_response":
        return _prior_canonical_family_for_ph_cloze(value)
    for candidate in ("fill_blank", "fill_in_blank", "cloze"):
        try:
            resolved = _prior_canonical_family_for_ph_cloze(candidate)
        except QuestionContractError:
            continue
        if resolved in ("fill_blank", "fill_in_blank", "cloze"):
            return resolved
    raise QuestionContractError("CLOZE_CONSTRUCTED_NATIVE_TEXT_ENTRY_FAMILY_REQUIRED")
'''
    updated = source + "\n" + patch
    compile(updated, str(path), "exec")
    path.write_text(updated, encoding="utf-8")
    print("SM_SHARED_PH_CLOZE_ADAPTER_APPLIED native_text_only=true mcq_coercion=false", flush=True)
